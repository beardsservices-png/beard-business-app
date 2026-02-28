"""
Match time entries to invoice jobs.

Matching priority (best to worst):
  1. Subproject # -> invoice number (exact)
  2. Project #    -> invoice number (exact or YYMMDD -> 20YYMMDD expansion)
  3. Fuzzy customer name + date within 90 days

Usage:
  python match_invoices_to_time.py             (preview only)
  python match_invoices_to_time.py --apply     (write to DB)
  python match_invoices_to_time.py --reset     (un-link all, then re-match)
"""

import sqlite3
import os
import sys
from datetime import datetime
from difflib import SequenceMatcher

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')


# ---------------------------------------------------------------------------
# Project-number -> invoice-number normalization
# ---------------------------------------------------------------------------

def candidate_invoice_numbers(proj):
    """
    Convert a BusyBusy project/subproject number to possible invoice_number values.

    Examples:
      20240321  -> ['BHS20240321']
      240321    -> ['BHS240321', 'BHS20240321']   (6-digit YYMMDD)
      250212    -> ['BHS250212', 'BHS20250212']
      241209    -> ['BHS241209', 'BHS20241209']
      070724    -> ['BHS070724']  (MMDDYY - leave as-is, unusual format)
      270       -> []  (internal ID, too short to be a date)
    """
    if not proj:
        return []
    p = proj.strip()
    if not p or not p.isdigit():
        return []

    candidates = [f'BHS{p}']

    # 6-digit: likely YYMMDD -> try prepending '20'
    if len(p) == 6:
        candidates.append(f'BHS20{p}')

    return candidates


# ---------------------------------------------------------------------------
# Fuzzy name matching
# ---------------------------------------------------------------------------

def name_similarity(a, b):
    """
    Return 0-1 similarity between two customer name strings.
    Tries multiple strategies to handle common real-world issues:
      - Straight string similarity
      - Word-sorted comparison (catches "Kemp Kristen" vs "Kristen Kemp")
      - Word-subset match (catches "Kemp" vs "Kemp Kristen", "Lisa" vs "Lisa Smith")
    """
    a, b = a.lower().strip(), b.lower().strip()
    straight = SequenceMatcher(None, a, b).ratio()

    # Compare sorted words (handles reversed names)
    a_words = ' '.join(sorted(a.split()))
    b_words = ' '.join(sorted(b.split()))
    sorted_sim = SequenceMatcher(None, a_words, b_words).ratio()

    a_set = set(a.split())
    b_set = set(b.split())
    if a_set and b_set:
        overlap = len(a_set & b_set) / max(len(a_set), len(b_set))
    else:
        overlap = 0

    # Subset match: if all words of the shorter name appear in the longer
    # e.g. "Kemp" in "Kemp Kristen", "Lisa" in "Lisa Smith"
    subset_sim = 0.0
    if a_set and b_set and (a_set.issubset(b_set) or b_set.issubset(a_set)):
        subset_sim = 0.75

    return max(straight, sorted_sim, overlap, subset_sim)


# ---------------------------------------------------------------------------
# Main matching logic
# ---------------------------------------------------------------------------

def run(apply=False, reset=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if reset:
        cursor.execute('UPDATE time_entries SET job_id = NULL')
        conn.commit()
        print('[RESET] All time entry job links cleared.\n')

    # Build invoice lookup: normalized_number -> invoice row
    cursor.execute('''
        SELECT i.id, i.invoice_number, i.invoice_date, i.customer_id, i.job_id,
               c.name as customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        ORDER BY i.invoice_date
    ''')
    invoices = cursor.fetchall()

    inv_by_number = {}   # 'BHS20240321' -> invoice row
    for inv in invoices:
        inv_by_number[inv['invoice_number']] = inv

    # Build customer lookup for fuzzy matching
    cursor.execute('SELECT id, name FROM customers')
    all_customers = cursor.fetchall()

    # Get unlinked time entries with their project numbers
    cursor.execute('''
        SELECT te.id, te.customer_id, te.entry_date, te.hours,
               te.busybusy_project, te.busybusy_subproject, te.description,
               c.name as customer_name
        FROM time_entries te
        LEFT JOIN customers c ON te.customer_id = c.id
        WHERE te.job_id IS NULL
        ORDER BY te.entry_date
    ''')
    unlinked = cursor.fetchall()

    print(f'Invoices in DB:          {len(invoices)}')
    print(f'Unlinked time entries:   {len(unlinked)}')
    print('=' * 70)

    matched = 0
    no_match = 0
    results = {}  # te_id -> (job_id, method, detail)

    for te in unlinked:
        te_id = te['id']
        proj = te['busybusy_project']
        sub = te['busybusy_subproject']
        cust_name = te['customer_name'] or ''
        entry_date = te['entry_date']

        # --- 1. Subproject # match ---
        for cand in candidate_invoice_numbers(sub):
            if cand in inv_by_number:
                inv = inv_by_number[cand]
                results[te_id] = (inv['job_id'], 'subproject#', cand)
                break

        if te_id in results:
            matched += 1
            continue

        # --- 2. Project # match ---
        for cand in candidate_invoice_numbers(proj):
            if cand in inv_by_number:
                inv = inv_by_number[cand]
                results[te_id] = (inv['job_id'], 'project#', cand)
                break

        if te_id in results:
            matched += 1
            continue

        # --- 3. Fuzzy name + date proximity ---
        if not entry_date:
            no_match += 1
            continue

        try:
            te_date = datetime.strptime(entry_date, '%Y-%m-%d')
        except ValueError:
            no_match += 1
            continue

        best_inv = None
        best_score = 0

        for inv in invoices:
            if not inv['invoice_date']:
                continue
            try:
                inv_date = datetime.strptime(inv['invoice_date'], '%Y-%m-%d')
            except ValueError:
                continue

            days_diff = abs((te_date - inv_date).days)
            if days_diff > 90:
                continue

            sim = name_similarity(cust_name, inv['customer_name'])
            if sim < 0.65:
                continue

            # Score: heavily weight name similarity, lightly penalize date distance
            score = sim * 100 - days_diff * 0.1

            if score > best_score:
                best_score = score
                best_inv = inv

        if best_inv and best_score >= 65:
            results[te_id] = (
                best_inv['job_id'],
                'fuzzy-name',
                f"{best_inv['invoice_number']} | {best_inv['customer_name']} | sim={best_score:.0f}"
            )
            matched += 1
        else:
            no_match += 1

    # --- Print and optionally apply results ---
    method_counts = {}
    for te in unlinked:
        te_id = te['id']
        if te_id in results:
            job_id, method, detail = results[te_id]
            method_counts[method] = method_counts.get(method, 0) + 1
            label = f'[{method.upper():<12}]'
            print(f'  MATCH {label} {te["customer_name"]:<30} {te["entry_date"]}  -> {detail}')
        else:
            print(f'  NO MATCH              {te["customer_name"]:<30} {te["entry_date"]}  proj={te["busybusy_project"]} sub={te["busybusy_subproject"]}')

    print()
    print('=' * 70)
    print(f'  Matched:   {matched}')
    for method, count in sorted(method_counts.items()):
        print(f'    via {method}: {count}')
    print(f'  No match:  {no_match}')
    print('=' * 70)

    if apply:
        for te_id, (job_id, method, detail) in results.items():
            cursor.execute('UPDATE time_entries SET job_id = ? WHERE id = ?', (job_id, te_id))
        conn.commit()
        print(f'\n[OK] Applied {matched} matches to database.')
    else:
        print('\nRun with --apply to write these to the database.')

    conn.close()


if __name__ == '__main__':
    apply = '--apply' in sys.argv
    reset = '--reset' in sys.argv
    run(apply=apply, reset=reset)
