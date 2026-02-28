"""
Extract customer phone numbers and addresses from invoiceBHS*.pdf ZIP files
and update the customers table.

Run from the data/ directory:
  python extract_contacts.py          (preview)
  python extract_contacts.py --apply  (write to DB)
"""

import sqlite3
import zipfile
import glob
import os
import re
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')
INVOICE_DIR = os.path.join(os.path.dirname(__file__), '..', 'Invoices')


def parse_contact(text):
    """
    Parse customer name, phone, and address from invoice 1.txt.
    Returns dict with keys: customer_name, phone, address
    """
    lines = [l.strip() for l in text.strip().splitlines()]

    customer_name = None
    phone = None
    address_lines = []

    for i, line in enumerate(lines):
        if line == 'To:' and i + 1 < len(lines):
            customer_name = lines[i + 1].strip()
            # Look at lines after customer name until 'Customer' keyword
            j = i + 2
            while j < len(lines) and lines[j] != 'Customer':
                candidate = lines[j]
                if not candidate:
                    j += 1
                    continue
                # Phone: starts with +1, (, or is digits/dashes
                if re.match(r'^(\+1[\s\-]?)?(\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})', candidate):
                    phone = candidate
                elif candidate == 'USA':
                    pass  # skip country label
                else:
                    address_lines.append(candidate)
                j += 1
            break

    address = ', '.join(address_lines) if address_lines else None
    return {
        'customer_name': customer_name,
        'phone': phone,
        'address': address,
    }


def run(apply=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build name -> id lookup (case-insensitive)
    cursor.execute('SELECT id, name FROM customers')
    customer_lookup = {}
    for row in cursor.fetchall():
        customer_lookup[row['name'].lower()] = {'id': row['id'], 'name': row['name']}

    invoice_files = sorted(glob.glob(os.path.join(INVOICE_DIR, 'invoiceBHS*.pdf')))
    print(f'Processing {len(invoice_files)} invoice files...\n')

    updates = {}  # customer_id -> {phone, address, name}
    skipped = 0

    for fpath in invoice_files:
        fname = os.path.basename(fpath)
        try:
            with zipfile.ZipFile(fpath, 'r') as z:
                if '1.txt' not in z.namelist():
                    continue
                text = z.read('1.txt').decode('utf-8')
        except zipfile.BadZipFile:
            print(f'  [SKIP] {fname}: not a valid ZIP')
            continue

        contact = parse_contact(text)
        name = contact['customer_name']
        if not name:
            continue

        match = customer_lookup.get(name.lower())
        if not match:
            print(f'  [?] {fname}: customer "{name}" not in DB')
            skipped += 1
            continue

        cid = match['id']
        if cid not in updates:
            updates[cid] = {
                'name': match['name'],
                'phone': contact['phone'],
                'address': contact['address'],
            }
        else:
            # If we already have data for this customer, fill in any blanks
            if not updates[cid]['phone'] and contact['phone']:
                updates[cid]['phone'] = contact['phone']
            if not updates[cid]['address'] and contact['address']:
                updates[cid]['address'] = contact['address']

    print(f'Found contact info for {len(updates)} customers:\n')
    has_phone = sum(1 for v in updates.values() if v['phone'])
    has_address = sum(1 for v in updates.values() if v['address'])

    for cid, info in sorted(updates.items(), key=lambda x: x[1]['name']):
        phone_str = info['phone'] or '(no phone)'
        addr_str = info['address'] or '(no address)'
        print(f'  {info["name"]:<35} {phone_str:<22} {addr_str}')

    print()
    print(f'  Customers with phone:   {has_phone}')
    print(f'  Customers with address: {has_address}')
    print(f'  Not matched to DB:      {skipped}')

    if apply:
        updated = 0
        for cid, info in updates.items():
            cursor.execute('''
                UPDATE customers
                SET phone = COALESCE(NULLIF(phone, ''), ?),
                    address = COALESCE(NULLIF(address, ''), ?)
                WHERE id = ?
            ''', (info['phone'], info['address'], cid))
            if cursor.rowcount:
                updated += 1
        conn.commit()
        print(f'\n[OK] Updated {updated} customer records.')
    else:
        print('\nRun with --apply to write to database.')

    conn.close()


if __name__ == '__main__':
    apply = '--apply' in sys.argv
    run(apply=apply)
