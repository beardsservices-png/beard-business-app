"""
import_timeline.py
Parses Unprocessed_Timeline.txt (Google Maps Timeline export) and imports
visits into the timeline_visits table.

Run from the data/ directory:
    python import_timeline.py [--dry-run]
"""

import sqlite3
import re
import os
import sys
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'beard_business.db')
TIMELINE_PATH = os.path.join(SCRIPT_DIR, '..', 'Unprocessed_Timeline.txt')

DRY_RUN = '--dry-run' in sys.argv

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

JUNK_PATTERNS = re.compile(
    r'^[:\s]+$'            # colon-only or whitespace-only
    r'|^\d{1,3}$'          # standalone numbers (10, 101, 530 etc.)
    r'|^[\u0041-\u0041]$'  # single ASCII letter junk (unlikely, but safe)
    r'|^\([\u3131-\u314e\uAC00-\uD7A3]+\)$'  # Korean in parens like (ㅁ)
    r'|^[\u0B80-\u0BFF]+$'  # Tamil chars like ப
    r'|^[\u3131-\u314e]+$'  # Korean jamo standalone
)

DATE_RE = re.compile(
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
    r'\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    r'\s+(\d{1,2}),\s+(\d{4})',
    re.IGNORECASE
)

# Time regex: matches HH:MM AM/PM (with optional space before AM/PM)
TIME_RE = re.compile(r'\d{1,2}:\d{2}\s*(?:AM|PM)', re.IGNORECASE)

# Duration regexes
DUR_HR_MIN = re.compile(r'(\d+)\s*hr[s.]?\s*(\d+)\s*min', re.IGNORECASE)
DUR_HR_ONLY = re.compile(r'(\d+)\s*hr[s.]?(?!\s*\d)', re.IGNORECASE)
DUR_MIN_ONLY = re.compile(r'(\d+)\s*min', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Normalize dash-as-colon time notation (defined early, used by is_short_address)
# ---------------------------------------------------------------------------
def normalize_dashes_in_time(text):
    """
    Convert dash-as-colon time format: 8-31 AM -> 8:31 AM
    Pattern: digit(s)-digit(2) followed by space/AM/PM
    """
    def replacer(m):
        return m.group(1) + ':' + m.group(2) + m.group(3)
    # e.g. "8-31 AM" or "10-43 AM"
    text = re.sub(r'(\d{1,2})-(\d{2})(\s*(?:AM|PM))', replacer, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------------------
# Helper: is a line a "short address" (block header)?
# Short address: no comma, starts with a digit or letters, reasonable length.
# Full addresses contain commas (city, state).
# ---------------------------------------------------------------------------
def is_short_address(line):
    stripped = line.strip()
    if not stripped:
        return False
    # Must NOT contain a comma (full addresses do)
    if ',' in stripped:
        return False
    # Must look like an address: starts with digit or common street word
    # At least 4 chars, not a date, not junk
    if JUNK_PATTERNS.match(stripped):
        return False
    if DATE_RE.match(stripped):
        return False
    # Should start with a digit or a place name like "VFW Post 3246"
    if re.match(r'^\d', stripped) or re.match(r'^[A-Za-z]', stripped):
        # Exclude lines that are obviously time-related (check with dash normalization too)
        normalized = normalize_dashes_in_time(stripped)
        if TIME_RE.search(stripped) or TIME_RE.search(normalized):
            return False
        # Exclude lines that are partial times: e.g. "8:45" or "8:45 AM" fragments
        # A partial time: just digits:digits possibly with AM/PM
        if re.match(r'^\d{1,2}:\d{2}\s*(?:AM|PM)?$', stripped, re.IGNORECASE):
            return False
        # Exclude "AM 10:13 AM 1 hr 28 min" style (starts with AM/PM)
        if re.match(r'^(?:AM|PM)\b', stripped, re.IGNORECASE):
            return False
        # Exclude duration-only lines
        if DUR_HR_MIN.match(stripped) or DUR_HR_ONLY.match(stripped) or DUR_MIN_ONLY.match(stripped):
            return False
        # Must have a space (so it looks like "410 Grassy Dr" not a single token)
        # Allow "VFW Post 3246" which has spaces, but reject bare junk words
        if ' ' not in stripped:
            return False
        return True
    return False


def extract_times(text):
    """Return list of time strings found in text (after normalization)."""
    text = normalize_dashes_in_time(text)
    # Also handle "4:55PM" -> "4:55 PM" spacing normalization for finding
    matches = TIME_RE.findall(text)
    return matches


def parse_time_to_24h(time_str, visit_date):
    """
    Convert '9:50 AM' or '1:18PM' to a datetime object using visit_date (a date object).
    Returns datetime or None.
    """
    time_str = time_str.strip().upper()
    # Ensure space before AM/PM
    time_str = re.sub(r'(\d)(AM|PM)', r'\1 \2', time_str)
    try:
        t = datetime.strptime(time_str, '%I:%M %p')
        return datetime(visit_date.year, visit_date.month, visit_date.day,
                        t.hour, t.minute, 0)
    except ValueError:
        return None


def extract_duration_hours(text):
    """
    Extract duration in decimal hours from text.
    Returns float or None.
    """
    # Remove trailing periods
    text = text.rstrip('.')
    # "6.hr 20 min" -> "6 hr 20 min"
    text = re.sub(r'(\d+)\.hr', r'\1 hr', text, flags=re.IGNORECASE)

    m = DUR_HR_MIN.search(text)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60.0

    m = DUR_HR_ONLY.search(text)
    if m:
        return float(m.group(1))

    m = DUR_MIN_ONLY.search(text)
    if m:
        return int(m.group(1)) / 60.0

    return None


def parse_date(line):
    """Parse a date line like 'Wednesday Dec 24, 2025'. Returns date or None."""
    m = DATE_RE.search(line)
    if m:
        month_abbr = m.group(1).lower()[:3]
        day = int(m.group(2))
        year = int(m.group(3))
        month = MONTH_MAP.get(month_abbr)
        if month:
            return date(year, month, day)
    return None


def is_junk(line):
    """Return True if line should be completely ignored."""
    stripped = line.strip()
    if not stripped:
        return False  # blank lines are handled separately
    if JUNK_PATTERNS.match(stripped):
        return True
    # Single non-ASCII chars
    if len(stripped) == 1 and ord(stripped[0]) > 127:
        return True
    # Korean / Tamil multi-char
    if all(ord(c) > 127 for c in stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Block splitting and parsing
# ---------------------------------------------------------------------------

def split_into_blocks(lines):
    """
    Split lines into address blocks.
    Returns list of (short_address, full_address, block_lines) tuples.
    block_lines are all lines after the header (full address line).
    """
    blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].rstrip('\n').rstrip()

        # Check if this is a short address (block start)
        if is_short_address(line):
            short_addr = line.strip()
            full_addr = short_addr  # default

            # Look ahead for full address (line with comma, within ~3 lines)
            j = i + 1
            while j < n and j <= i + 4:
                peek = lines[j].rstrip('\n').rstrip()
                if peek.strip() == '':
                    j += 1
                    continue
                if ',' in peek and not DATE_RE.match(peek):
                    full_addr = peek.strip()
                    j += 1
                    break
                # If next non-blank line is a date or time, stop
                break

            # Collect all block lines up to (but not including) next short address
            block_lines = []
            while j < n:
                peek = lines[j].rstrip('\n').rstrip()
                if is_short_address(peek):
                    break
                block_lines.append(peek)
                j += 1

            blocks.append((short_addr, full_addr, block_lines))
            i = j
        else:
            i += 1

    return blocks


def parse_block(short_addr, full_addr, block_lines):
    """
    Parse a single address block into a list of visit dicts.
    Each visit: {address, visit_date, arrival_time, departure_time, duration_hours}
    """
    visits = []

    # We'll process lines in sequence, accumulating "pending" lines per date
    current_date = None
    pending_lines = []  # non-blank, non-junk lines since last date

    def flush_pending():
        """Try to extract a visit from pending_lines under current_date."""
        if not current_date or not pending_lines:
            return None
        combined = ' '.join(pending_lines)
        # Normalize dashes-as-colons before any extraction
        combined_norm = normalize_dashes_in_time(combined)

        # Extract all time occurrences
        times = extract_times(combined_norm)

        if len(times) < 2:
            # Only one time found: try to compute departure from duration
            if len(times) == 1:
                dur = extract_duration_hours(combined_norm)
                if dur is not None:
                    from datetime import timedelta
                    arr_dt = parse_time_to_24h(times[0], current_date)
                    if arr_dt:
                        dep_dt = arr_dt + timedelta(hours=dur)
                        return {
                            'address': full_addr,
                            'visit_date': current_date.strftime('%Y-%m-%d'),
                            'arrival_time': arr_dt.strftime('%Y-%m-%d %H:%M:%S'),
                            'departure_time': dep_dt.strftime('%Y-%m-%d %H:%M:%S'),
                            'duration_hours': round(dur, 4),
                        }
            return None  # no usable time data

        start_str = times[0]
        end_str = times[1]
        arr_dt = parse_time_to_24h(start_str, current_date)
        dep_dt = parse_time_to_24h(end_str, current_date)

        if arr_dt is None or dep_dt is None:
            return None

        # Extract duration
        dur = extract_duration_hours(combined_norm)
        if dur is None:
            # Compute from times
            diff = (dep_dt - arr_dt).total_seconds()
            if diff < 0:
                diff += 86400  # crosses midnight
            dur = diff / 3600.0

        return {
            'address': full_addr,
            'visit_date': current_date.strftime('%Y-%m-%d'),
            'arrival_time': arr_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'departure_time': dep_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_hours': round(dur, 4),
        }

    for raw_line in block_lines:
        line = raw_line.strip()

        # Blank line: try to flush pending, but only clear pending if a visit was produced
        # (so fragments like '8:45' carry over to the next line)
        if line == '':
            if pending_lines:
                visit = flush_pending()
                if visit:
                    visits.append(visit)
                    pending_lines = []
                # If no visit produced, keep pending_lines so the fragment carries forward
            continue

        # Junk line: skip it but leave pending_lines intact
        if is_junk(line):
            continue

        # Date line
        d = parse_date(line)
        if d is not None:
            # Flush any pending lines first (discard any fragment that yielded nothing)
            if pending_lines:
                visit = flush_pending()
                if visit:
                    visits.append(visit)
                pending_lines = []
            current_date = d
            continue

        # Otherwise it's a data line (time/duration)
        pending_lines.append(line)

    # Flush remaining
    if pending_lines and current_date:
        visit = flush_pending()
        if visit:
            visits.append(visit)

    return visits


# ---------------------------------------------------------------------------
# Customer matching
# ---------------------------------------------------------------------------

def load_customers(conn):
    """Returns list of dicts with id, name, address."""
    cur = conn.cursor()
    cur.execute('SELECT id, name, address FROM customers')
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def extract_street_number(addr):
    """Extract leading street number from address string."""
    if not addr:
        return None
    m = re.match(r'^(\d+)', addr.strip())
    return m.group(1) if m else None


def find_or_create_customer(conn, short_addr, full_addr, customers, dry_run=False):
    """
    Match timeline address to existing customer by street number.
    If no match, create a new customer (unless dry_run).
    Returns customer_id or None.
    """
    num = extract_street_number(short_addr)
    if num:
        for cust in customers:
            cust_num = extract_street_number(cust.get('address') or '')
            if cust_num and cust_num == num:
                return cust['id']

    # No match: create new customer
    name = short_addr  # Use short address as customer name
    if dry_run:
        print('  [DRY-RUN] Would create customer: ' + name)
        return None

    cur = conn.cursor()
    cur.execute('SELECT id FROM customers WHERE name = ?', (name,))
    row = cur.fetchone()
    if row:
        return row['id']

    cur.execute(
        'INSERT INTO customers (name, address, notes) VALUES (?, ?, ?)',
        (name, full_addr, 'Created by import_timeline.py')
    )
    conn.commit()
    new_id = cur.lastrowid
    # Refresh customers list
    customers.append({'id': new_id, 'name': name, 'address': full_addr})
    print('  [NEW] Created customer: ' + name + ' (id=' + str(new_id) + ')')
    return new_id


def visit_exists(conn, address, visit_date, arrival_time):
    """Check if a visit already exists in the DB."""
    cur = conn.cursor()
    cur.execute(
        'SELECT id FROM timeline_visits WHERE address = ? AND visit_date = ? AND arrival_time = ?',
        (address, visit_date, arrival_time)
    )
    return cur.fetchone() is not None


def insert_visit(conn, customer_id, visit):
    """Insert a visit into timeline_visits."""
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO timeline_visits
            (customer_id, job_id, visit_date, arrival_time, departure_time,
             duration_hours, address, source, matched)
        VALUES (?, NULL, ?, ?, ?, ?, ?, 'google_timeline', 0)
    ''', (
        customer_id,
        visit['visit_date'],
        visit['arrival_time'],
        visit['departure_time'],
        visit['duration_hours'],
        visit['address'],
    ))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(TIMELINE_PATH):
        print('ERROR: Timeline file not found: ' + TIMELINE_PATH)
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print('ERROR: Database not found: ' + DB_PATH)
        sys.exit(1)

    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    customers = load_customers(conn)

    blocks = split_into_blocks(lines)

    print('import_timeline.py' + (' [DRY-RUN]' if DRY_RUN else ''))
    print('=' * 60)
    print('Found ' + str(len(blocks)) + ' address blocks')
    print()

    imported = 0
    skipped = 0
    errors = 0
    no_time = 0

    for short_addr, full_addr, block_lines in blocks:
        visits = parse_block(short_addr, full_addr, block_lines)

        # Count date entries with no parseable time
        # We do a rough count: number of DATE_RE matches in block_lines minus parsed visits
        date_count = sum(1 for l in block_lines if parse_date(l.strip()) is not None)
        block_no_time = max(0, date_count - len(visits))
        no_time += block_no_time

        customer_id = find_or_create_customer(conn, short_addr, full_addr, customers, DRY_RUN)

        for visit in visits:
            try:
                # Format display times
                arr_dt = datetime.strptime(visit['arrival_time'], '%Y-%m-%d %H:%M:%S')
                dep_dt = datetime.strptime(visit['departure_time'], '%Y-%m-%d %H:%M:%S')
                arr_disp = arr_dt.strftime('%I:%M %p').lstrip('0')
                dep_disp = dep_dt.strftime('%I:%M %p').lstrip('0')

                if visit_exists(conn, visit['address'], visit['visit_date'], visit['arrival_time']):
                    skipped += 1
                    continue

                if DRY_RUN:
                    print('  [+] ' + visit['visit_date'] + ' | ' + short_addr +
                          ' | ' + arr_disp + ' - ' + dep_disp +
                          ' | ' + str(round(visit['duration_hours'], 2)) + ' hrs')
                    imported += 1
                else:
                    insert_visit(conn, customer_id, visit)
                    print('  [+] ' + visit['visit_date'] + ' | ' + short_addr +
                          ' | ' + arr_disp + ' - ' + dep_disp +
                          ' | ' + str(round(visit['duration_hours'], 2)) + ' hrs')
                    imported += 1

            except Exception as e:
                errors += 1
                print('  [ERR] ' + visit.get('visit_date', '?') + ' | ' +
                      short_addr + ' | ' + str(e))

    print()
    print('=' * 60)
    print('  Imported:  ' + str(imported))
    print('  Skipped:   ' + str(skipped) + ' (already in DB)')
    print('  Errors:    ' + str(errors))
    print('  No time:   ' + str(no_time) + ' (date entries with no parseable time)')

    conn.close()


if __name__ == '__main__':
    main()
