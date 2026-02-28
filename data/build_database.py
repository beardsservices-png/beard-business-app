"""
Build the Beard's Home Services SQLite database.
Imports all existing data: invoices, services, time tracking, customers.

Run from the data/ directory:
  python build_database.py
"""

import sqlite3
import json
import csv
import os
from datetime import datetime

DB_PATH = 'beard_business.db'
INVOICE_WORKFLOW = '../invoice_workflow'


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            invoice_id TEXT,
            project_number TEXT,
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'completed',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            job_id INTEGER,
            total_labor REAL DEFAULT 0,
            total_materials REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            invoice_date DATE,
            status TEXT DEFAULT 'paid',
            pdf_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services_performed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            job_id INTEGER,
            original_description TEXT,
            standardized_description TEXT,
            category TEXT,
            amount REAL DEFAULT 0,
            service_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            job_id INTEGER,
            entry_date DATE,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            hours REAL DEFAULT 0,
            description TEXT,
            cost_code TEXT,
            source TEXT DEFAULT 'busybusy',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            customer_id INTEGER,
            description TEXT,
            cost REAL DEFAULT 0,
            vendor TEXT,
            receipt_path TEXT,
            expense_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_labor INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timeline_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            job_id INTEGER,
            visit_date DATE,
            arrival_time TIMESTAMP,
            departure_time TIMESTAMP,
            duration_hours REAL,
            address TEXT,
            source TEXT DEFAULT 'google_timeline',
            matched INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    conn.commit()
    print("[OK] Tables created")


def import_service_categories(conn):
    cursor = conn.cursor()
    categories = [
        ('General Handyman Labor', 'General repairs and maintenance', 1),
        ('Deck Construction Labor', 'New deck builds', 1),
        ('Deck Repair & Restoration Labor', 'Deck repairs, refinishing, staining', 1),
        ('Fence Construction Labor', 'New fence installation', 1),
        ('Flooring Installation Labor', 'All flooring types', 1),
        ('Concrete Pad Installation Labor', 'Concrete work', 1),
        ('Painting/Staining Labor', 'Interior and exterior painting', 1),
        ('Bathroom Remodel Labor', 'Bathroom renovations', 1),
        ('Door/Window Installation Labor', 'Door and window work', 1),
        ('Tile Installation Labor', 'Tile work', 1),
        ('Materials', 'Materials and supplies - not labor income', 0),
        ('Plumbing Labor', 'Plumbing repairs and installation', 1),
        ('Gutter & Roofing Labor', 'Gutters and roofing', 1),
        ('Landscaping Labor', 'Yard and landscape work', 1),
        ('Kitchen Remodel Labor', 'Kitchen renovations', 1),
        ('Appliance Installation Labor', 'Appliance installs', 1),
        ('Outdoor Structure Labor', 'Pergolas, gazebos, etc.', 1),
        ('Demolition & Hauling Labor', 'Demo and removal', 1),
        ('Asphalt & Paving Labor', 'Asphalt and paving work', 1),
        ('Screen & Enclosure Labor', 'Screen porches and enclosures', 1),
    ]
    for name, desc, is_labor in categories:
        cursor.execute(
            'INSERT OR IGNORE INTO service_categories (name, description, is_labor) VALUES (?, ?, ?)',
            (name, desc, is_labor)
        )
    conn.commit()
    print("[OK] Service categories imported")


def parse_invoice_date(invoice_id):
    numeric = invoice_id[3:] if invoice_id.startswith('BHS') else invoice_id
    if len(numeric) == 8:
        return f"{numeric[:4]}-{numeric[4:6]}-{numeric[6:8]}"
    elif len(numeric) == 6:
        return f"20{numeric[:2]}-{numeric[2:4]}-{numeric[4:6]}"
    return None


def import_from_invoice_workflow(conn):
    """Import invoice + customer data from invoice_workflow JSON files."""
    cursor = conn.cursor()

    mapping_path = os.path.join(INVOICE_WORKFLOW, 'customer_invoice_mapping.json')
    extracted_path = os.path.join(INVOICE_WORKFLOW, 'extracted_services.json')
    matched_path = os.path.join(INVOICE_WORKFLOW, 'matched_services.json')

    if not os.path.exists(mapping_path):
        print("[SKIP] customer_invoice_mapping.json not found")
        return
    if not os.path.exists(extracted_path):
        print("[SKIP] extracted_services.json not found")
        return

    with open(mapping_path, 'r') as f:
        customer_mapping = json.load(f)
    with open(extracted_path, 'r') as f:
        invoice_data = json.load(f)

    matched_lookup = {}
    if os.path.exists(matched_path):
        with open(matched_path, 'r') as f:
            matched = json.load(f)
        for m in matched.get('matches', []):
            matched_lookup[m['original_description']] = m

    invoice_lookup = {inv['invoice_id']: inv for inv in invoice_data['invoices']}
    customer_ids = {}

    # Import customers + their invoices
    for customer_name, data in customer_mapping.items():
        if customer_name.startswith('_'):
            continue

        cursor.execute('INSERT OR IGNORE INTO customers (name, notes) VALUES (?, ?)',
                       (customer_name, data.get('notes', '')))
        cursor.execute('SELECT id FROM customers WHERE name = ?', (customer_name,))
        customer_id = cursor.fetchone()[0]
        customer_ids[customer_name] = customer_id

        for invoice_num in data.get('invoices', []):
            if invoice_num not in invoice_lookup:
                continue
            inv = invoice_lookup[invoice_num]
            invoice_date = parse_invoice_date(invoice_num)
            total_labor = sum(s['amount'] for s in inv['services'] if s.get('type') == 'labor')
            total_materials = sum(s['amount'] for s in inv['services'] if s.get('type') == 'materials')

            cursor.execute('''
                INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, status)
                VALUES (?, ?, ?, ?, 'completed')
            ''', (customer_id, invoice_num,
                  invoice_num[3:] if invoice_num.startswith('BHS') else invoice_num,
                  invoice_date))
            job_id = cursor.lastrowid

            cursor.execute('''
                INSERT OR IGNORE INTO invoices
                (invoice_number, customer_id, job_id, total_labor, total_materials,
                 total_amount, invoice_date, pdf_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_num, customer_id, job_id, total_labor, total_materials,
                  total_labor + total_materials, invoice_date, inv.get('filename')))
            invoice_id = cursor.lastrowid

            for svc in inv['services']:
                orig = svc['original_description']
                matched = matched_lookup.get(orig, {})
                cursor.execute('''
                    INSERT INTO services_performed
                    (invoice_id, job_id, original_description, standardized_description,
                     category, amount, service_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, job_id, orig,
                      matched.get('standardized_description', orig),
                      matched.get('matched_category'),
                      svc['amount'], svc.get('type')))

    # Unassigned invoices
    cursor.execute('INSERT OR IGNORE INTO customers (name, notes) VALUES (?, ?)',
                   ('_UNASSIGNED', 'Invoices not yet matched to a customer'))
    cursor.execute('SELECT id FROM customers WHERE name = ?', ('_UNASSIGNED',))
    unassigned_id = cursor.fetchone()[0]

    for invoice_num in customer_mapping.get('_unassigned_invoices', []):
        if invoice_num not in invoice_lookup:
            continue
        inv = invoice_lookup[invoice_num]
        invoice_date = parse_invoice_date(invoice_num)
        total_labor = sum(s['amount'] for s in inv['services'] if s.get('type') == 'labor')
        total_materials = sum(s['amount'] for s in inv['services'] if s.get('type') == 'materials')

        cursor.execute('''
            INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, status, notes)
            VALUES (?, ?, ?, ?, 'completed', 'Needs customer assignment')
        ''', (unassigned_id, invoice_num,
              invoice_num[3:] if invoice_num.startswith('BHS') else invoice_num, invoice_date))
        job_id = cursor.lastrowid

        cursor.execute('''
            INSERT OR IGNORE INTO invoices
            (invoice_number, customer_id, job_id, total_labor, total_materials,
             total_amount, invoice_date, pdf_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (invoice_num, unassigned_id, job_id, total_labor, total_materials,
              total_labor + total_materials, invoice_date, inv.get('filename')))
        invoice_id = cursor.lastrowid

        for svc in inv['services']:
            cursor.execute('''
                INSERT INTO services_performed
                (invoice_id, job_id, original_description, standardized_description,
                 category, amount, service_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, job_id, svc['original_description'],
                  svc['original_description'], None,
                  svc['amount'], svc.get('type')))

    conn.commit()
    print(f"[OK] Invoice data imported ({len(customer_mapping)} customers)")


def import_time_entries(conn):
    """Import BusyBusy time tracking CSV files."""
    cursor = conn.cursor()

    # Build customer name lookup
    cursor.execute('SELECT id, name FROM customers')
    customer_ids = {}
    for row in cursor.fetchall():
        customer_ids[row[0]] = row[1]
        customer_ids[row[1].lower()] = row[0]

    csv_files = [
        'time_entries.csv',
        'time_tracking/busybusy_official_export.csv',
        'time_tracking/busybusy_export_2024.csv',
        'time_tracking/busybusy_export_2025.csv',
    ]

    total = 0
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            continue

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                customer_name = (row.get('Customer') or '').strip()
                if not customer_name:
                    continue

                # Skip test entries
                if customer_name.lower() == 'claude anthropic':
                    continue

                # Match customer
                cid = customer_ids.get(customer_name.lower())
                if cid is None:
                    # Create new customer
                    cursor.execute('INSERT OR IGNORE INTO customers (name) VALUES (?)',
                                   (customer_name,))
                    cursor.execute('SELECT id FROM customers WHERE name = ?', (customer_name,))
                    row_r = cursor.fetchone()
                    if row_r:
                        cid = row_r[0]
                        customer_ids[customer_name.lower()] = cid

                # Parse hours
                total_str = row.get('Total', '00:00') or row.get('Total Time', '00:00')
                try:
                    parts = total_str.strip().split(':')
                    hours = int(parts[0]) + int(parts[1]) / 60 if len(parts) >= 2 else 0
                except (ValueError, IndexError):
                    hours = 0

                # Parse date
                start_str = row.get('Start', '') or row.get('Start Time', '')
                entry_date = start_str[:10] if start_str else None

                description = row.get('Description', '') or ''
                cost_code = row.get('Cost Code', '') or ''

                cursor.execute('''
                    INSERT INTO time_entries
                    (customer_id, entry_date, start_time, end_time, hours,
                     description, cost_code, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'busybusy')
                ''', (cid, entry_date, row.get('Start'), row.get('End'),
                      hours, description, cost_code))
                total += 1

    conn.commit()
    print(f"[OK] Time entries imported: {total}")


def print_summary(conn):
    cursor = conn.cursor()
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    for table, label in [
        ('customers', 'Customers'),
        ('jobs', 'Jobs'),
        ('invoices', 'Invoices'),
        ('services_performed', 'Service Line Items'),
        ('time_entries', 'Time Entries'),
        ('service_categories', 'Service Categories'),
    ]:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f"  {label:<25} {count:>6}")

    cursor.execute('SELECT SUM(total_labor), SUM(total_materials) FROM invoices')
    labor, materials = cursor.fetchone()
    print(f"\n  Total Labor Revenue:     ${labor or 0:>10,.2f}")
    print(f"  Total Materials:         ${materials or 0:>10,.2f}")

    cursor.execute('SELECT SUM(hours) FROM time_entries')
    hours = cursor.fetchone()[0]
    print(f"  Total Hours Tracked:     {hours or 0:>10,.1f}h")

    if hours and labor:
        print(f"  Overall $/Hour:          ${labor/hours:>10,.2f}")


if __name__ == '__main__':
    print("Building Beard's Home Services Database...")
    print("=" * 60)
    print(f"Run from: {os.getcwd()}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        create_tables(conn)
        import_service_categories(conn)
        import_from_invoice_workflow(conn)
        import_time_entries(conn)
        print_summary(conn)
        print(f"\n[OK] Database saved to: {DB_PATH}")
    finally:
        conn.close()
