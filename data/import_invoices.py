"""
Import all invoiceBHS*.pdf (InvoiceBee ZIP format) into the database.

Idempotent - safe to run multiple times. Skips invoices already in DB.
Reads ZIPs from the project root (one folder up from data/).

Usage:
  cd data
  python import_invoices.py
  python import_invoices.py --dry-run    (preview without writing)
  python import_invoices.py --reset      (clear invoices/jobs first, then re-import)
"""

import sqlite3
import zipfile
import os
import re
import glob
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')
INVOICE_DIR = os.path.join(os.path.dirname(__file__), '..', 'Invoices')


# ---------------------------------------------------------------------------
# Category mapping: keywords -> service_categories.name
# Materials = passthrough (not income). Labor = billable income.
# ---------------------------------------------------------------------------

CATEGORY_RULES = [
    # --- Materials (check first so labor keywords don't override) ---
    (['material', 'sealer', 'reimbursement', 'lowes purchase', 'hd ', 'redimix',
      'allsteel', 'column materials', 'deck materials', 'deck replacement materials',
      'gutter install materials', 'flower beds materials', 'lawn edging materials',
      'tile installation materials', 'bathtoom subfoor repair materials',
      'pergola materials', 'new border materials', 'trailer tires',
      'materials ereceipt', 'materials: concrete',
      ], 'Materials'),

    # --- Specific labor categories ---
    (['deck construction', 'deck installation labor', 'wood decking installation',
      'new deck', 'covered pergola installation', 'pergola installation'],
     'Deck Construction Labor'),

    (['deck repair', 'deck and building repairs', 'refnish deck', 'refinish deck',
      'existing deck disassembly', 'deck removal', 'lattice staining',
      'deck stain', 'deck repair and stain'],
     'Deck Repair & Restoration Labor'),

    (['asphalt', 'driveway repair'],
     'Asphalt & Paving Labor'),

    (['painting', 'staining', 'interior paint', 'exterior paint', 'siding repair',
      'paint prep', 'organizing, cleaning, floor, paint prep'],
     'Painting/Staining Labor'),

    (['flooring installation', 'flooring, vinyl', 'laminate flooring',
      'vinyl bathroom flooring', 'kitchen flooring', 'replace subfoor',
      'bathtoom subfoor repair labor', 'subfoor repair labor',
      'flooring install'],
     'Flooring Installation Labor'),

    (['tile installation labor', 'tile install', 'grout repair', 'mortar repair',
      'tub and tile', 'caulk replacement'],
     'Tile Installation Labor'),

    (['bathroom', 'bath - shower', 'bath glass', 'bathtoom', 'shower conversion',
      'shower leak', 'tub and tile', 'toilet', 'bathroom sink'],
     'Bathroom Remodel Labor'),

    (['plumbing', 'faucet', 'water heater', 'dishwasher', 'water shutof',
      'water shutoff', 'garbage disposal', 'drain water', 'sink plumb',
      'leak repair labor', 'plumbing / leak'],
     'Plumbing Labor'),

    (['gutter', 'downspout', 'roofing'],
     'Gutter & Roofing Labor'),

    (['privacy fence', 'fence labor', 'fence construction'],
     'Fence Construction Labor'),

    (['screen replacement', 'patio screen', 'rescreening'],
     'Screen & Enclosure Labor'),

    (['lawn', 'flower bed', 'limb removal', 'rock bed', 'lawn edging',
      'lawn reclaim', 'landscaping'],
     'Landscaping Labor'),

    (['covered pergola', 'pergola'],
     'Outdoor Structure Labor'),

    (['concrete finishing', 'concrete steps', 'concrete pad',
      'additional labor (concrete)'],
     'Concrete Pad Installation Labor'),

    (['kitchen remodel', 'countertop', 'cabinet sink', 'cabinet spacer',
      'kitchen sink refnish', 'kitchen sink replacement'],
     'Kitchen Remodel Labor'),

    (['door', 'window', 'trim install', 'baseboard', 'casing',
      'crawlspace door', 'door seal', 'exterior door', 'hang door'],
     'Door/Window Installation Labor'),

    (['haul away', 'demolition', 'debris', 'deck removal / haul',
      'antenna removal'],
     'Demolition & Hauling Labor'),

    (['microwave', 'range hood', 'appliance', 'electric fireplace',
      'floating mantle', 'tv wall mount', 'dishwasher install'],
     'Appliance Installation Labor'),

    (['ac return', 'insulation'],
     'General Handyman Labor'),
]


def categorize_service(description):
    """Map a service description to a service_categories.name value."""
    desc = description.lower()
    for keywords, category in CATEGORY_RULES:
        for kw in keywords:
            if kw in desc:
                return category
    return 'General Handyman Labor'


def classify_type(description):
    """Return 'labor' or 'materials' based on description."""
    desc = description.lower()
    material_kw = [
        'material', 'sealer', 'reimbursement', 'lowes', ' hd ', 'redimix',
        'allsteel', 'trailer tires', 'concrete:', 'lumber', 'supplies',
        'hardware', 'ereceipt',
    ]
    for kw in material_kw:
        if kw in desc:
            return 'materials'
    # Also catch descriptions where the category is Materials
    if categorize_service(description) == 'Materials':
        return 'materials'
    return 'labor'


# Description standardization: fix common typos and inconsistencies
STANDARDIZE = {
    'bathtoom': 'Bathroom',
    'subfoor': 'Subfloor',
    'refnish': 'Refinish',
    'troubleshoor': 'Troubleshoot',
    'shutof': 'Shutoff',
    'fow': 'Flow',
    'preperation': 'Preparation',
    'fnish': 'Finish',
    'oerings': 'Orings',
}


def standardize_description(description):
    """Fix common typos in service descriptions."""
    result = description
    for typo, fix in STANDARDIZE.items():
        result = re.sub(typo, fix, result, flags=re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# Invoice text parser
# ---------------------------------------------------------------------------

# Matches full service line: Description  Qty  $Price  [$Discount]  *?$Amount|null
SERVICE_RE = re.compile(
    r'^(.+?)\s+(\d+(?:\.\d+)?)\s+\$[\d,]+\.\d{2}(?:\s+\$[\d,]+\.\d{2})?\s+\*?\$?([\d,]+\.\d{2}|null)\s*$'
)

# Matches prices-only line (description was on preceding lines):
# Qty  $Price  [$Discount]  *?$Amount|null
PRICES_ONLY_RE = re.compile(
    r'^(\d+(?:\.\d+)?)\s+\$[\d,]+\.\d{2}(?:\s+\$[\d,]+\.\d{2})?\s+\*?\$?([\d,]+\.\d{2}|null)\s*$'
)

TOTAL_RE = re.compile(r'^Total\s+\$([\d,]+\.\d{2})\s*$')


def parse_invoice_text(text):
    """Parse 1.txt from an InvoiceBee ZIP and return structured invoice data."""
    lines = [l.strip() for l in text.strip().splitlines()]

    result = {
        'customer_name': None,
        'invoice_number': None,
        'invoice_date': None,
        'services': [],
        'total': 0.0,
    }

    # --- Customer name (line after "To:") ---
    for i, line in enumerate(lines):
        if line == 'To:' and i + 1 < len(lines):
            result['customer_name'] = lines[i + 1].strip()
            break

    # --- Invoice number (BHSxxxxxxxx near "Agreement #") ---
    for i, line in enumerate(lines):
        if 'Agreement #' in line:
            match = re.search(r'BHS\d+', line)
            if not match and i + 1 < len(lines):
                match = re.search(r'BHS\d+', lines[i + 1])
            if match:
                result['invoice_number'] = match.group()
            break

    # --- Invoice date ---
    for line in lines:
        match = re.search(r'Date\s+(\d{4}/\d{2}/\d{2})', line)
        if match:
            result['invoice_date'] = match.group(1).replace('/', '-')
            break

    # --- Services section ---
    # Collect all non-empty lines between the header and "Subtotal"/"*Indicates"
    service_section = []
    in_services = False
    for line in lines:
        if 'Service Type' in line and 'Quantity' in line and 'Price' in line:
            in_services = True
            continue
        if in_services:
            if line.startswith('*Indicates') or line.startswith('Subtotal') or TOTAL_RE.match(line):
                break
            if line:
                service_section.append(line)

    # Parse services
    # For wrapped descriptions, the true description is the last 1-2 pending lines
    # before the prices-only line. Earlier lines are continuation notes from the
    # previous service and should be ignored.
    pending_parts = []
    for line in service_section:
        full_match = SERVICE_RE.match(line)
        prices_match = PRICES_ONLY_RE.match(line)

        if full_match:
            desc = full_match.group(1).strip()
            raw_amount = full_match.group(3)
            amount = 0.0 if raw_amount == 'null' else float(raw_amount.replace(',', ''))
            _add_service(result['services'], desc, amount)
            pending_parts = []

        elif prices_match:
            raw_amount = prices_match.group(2)
            amount = 0.0 if raw_amount == 'null' else float(raw_amount.replace(',', ''))
            # Use at most last 2 pending lines as description
            # (earlier lines are continuation text from the previous service)
            desc_parts = pending_parts[-2:] if len(pending_parts) > 2 else pending_parts
            desc = ' '.join(desc_parts).strip() or 'Service'
            _add_service(result['services'], desc, amount)
            pending_parts = []

        else:
            pending_parts.append(line)

    # --- Total ---
    for line in lines:
        match = TOTAL_RE.match(line)
        if match:
            result['total'] = float(match.group(1).replace(',', ''))
            break

    return result


def _add_service(services_list, description, amount):
    std_desc = standardize_description(description)
    services_list.append({
        'description': description,
        'standardized_description': std_desc,
        'amount': amount,
        'type': classify_type(description),
        'category': categorize_service(description),
    })


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_or_create_customer(cursor, name):
    cursor.execute('SELECT id FROM customers WHERE name = ?', (name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    cursor.execute('INSERT INTO customers (name) VALUES (?)', (name,))
    return cursor.lastrowid


def import_invoice(cursor, parsed, pdf_filename, dry_run=False):
    """Insert one invoice (job + invoice record + services) into the database."""
    inv_num = parsed['invoice_number']
    if not inv_num:
        return False, 'no invoice number'

    cursor.execute('SELECT id FROM invoices WHERE invoice_number = ?', (inv_num,))
    if cursor.fetchone():
        return False, 'already in DB'

    customer_name = parsed['customer_name'] or 'Unknown'
    invoice_date = parsed['invoice_date']
    services = parsed['services']

    total_labor = sum(s['amount'] for s in services if s['type'] == 'labor')
    total_materials = sum(s['amount'] for s in services if s['type'] == 'materials')
    total_amount = parsed['total'] or (total_labor + total_materials)

    summary = f"{customer_name} | {invoice_date} | ${total_amount:.2f} | {len(services)} services"

    if dry_run:
        return True, summary

    customer_id = get_or_create_customer(cursor, customer_name)

    cursor.execute('''
        INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, status)
        VALUES (?, ?, ?, ?, 'completed')
    ''', (customer_id, inv_num,
          inv_num[3:] if inv_num.startswith('BHS') else inv_num,
          invoice_date))
    job_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO invoices
        (invoice_number, customer_id, job_id, total_labor, total_materials,
         total_amount, invoice_date, status, pdf_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', ?)
    ''', (inv_num, customer_id, job_id, total_labor, total_materials,
          total_amount, invoice_date, pdf_filename))
    invoice_id = cursor.lastrowid

    for svc in services:
        cursor.execute('''
            INSERT INTO services_performed
            (invoice_id, job_id, original_description, standardized_description,
             category, amount, service_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (invoice_id, job_id,
              svc['description'],
              svc['standardized_description'],
              svc['category'],
              svc['amount'],
              svc['type']))

    return True, summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run=False, reset=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if reset and not dry_run:
        print("[RESET] Clearing invoices, jobs, services_performed...")
        cursor.execute('DELETE FROM services_performed')
        cursor.execute('DELETE FROM invoices')
        cursor.execute('DELETE FROM jobs')
        conn.commit()

    invoice_files = sorted(glob.glob(os.path.join(INVOICE_DIR, 'invoiceBHS*.pdf')))
    print(f"Found {len(invoice_files)} invoice file(s) in {os.path.abspath(INVOICE_DIR)}")
    if dry_run:
        print("[DRY RUN] No changes will be written.\n")

    imported = 0
    skipped = 0
    errors = []

    for fpath in invoice_files:
        fname = os.path.basename(fpath)
        try:
            with zipfile.ZipFile(fpath, 'r') as z:
                if '1.txt' not in z.namelist():
                    errors.append(f"{fname}: no 1.txt in ZIP")
                    continue
                text = z.read('1.txt').decode('utf-8')

            parsed = parse_invoice_text(text)

            if not parsed['invoice_number']:
                errors.append(f"{fname}: could not parse invoice number")
                continue

            ok, detail = import_invoice(cursor, parsed, fname, dry_run=dry_run)

            if ok:
                print(f"  [+] {fname}: {detail}")
                imported += 1
            else:
                print(f"  [=] {fname}: {detail}")
                skipped += 1

        except zipfile.BadZipFile:
            errors.append(f"{fname}: not a valid ZIP file")
        except Exception as e:
            errors.append(f"{fname}: {e}")

    if not dry_run:
        conn.commit()

    conn.close()

    print()
    print("=" * 60)
    if dry_run:
        print(f"  Would import: {imported}")
        print(f"  Would skip:   {skipped}")
    else:
        print(f"  Imported:  {imported}")
        print(f"  Skipped:   {skipped} (already in DB)")
    if errors:
        print(f"  Errors:    {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    print("=" * 60)

    return imported


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    reset = '--reset' in sys.argv
    run(dry_run=dry_run, reset=reset)
