"""
Import BusyBusy time tracking CSV exports into the database.

Usage:
  python import_busybusy.py <csv_file>
  python import_busybusy.py time_tracking/busybusy_export_2025.csv

Handles both the standard BusyBusy export format and the alternate
column naming used in different export versions.
"""

import sqlite3
import csv
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def import_csv(csv_path):
    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        return 0

    conn = get_db()
    cursor = conn.cursor()

    # Build customer name → id lookup
    cursor.execute('SELECT id, name FROM customers')
    customer_ids = {}
    for row in cursor.fetchall():
        customer_ids[row['name'].lower()] = row['id']

    total = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        print(f"[INFO] CSV columns: {', '.join(headers)}")

        for row in reader:
            customer_name = (
                row.get('Customer') or
                row.get('Project') or
                row.get('customer') or ''
            ).strip()

            if not customer_name or customer_name.lower() in ('claude anthropic', 'test', ''):
                skipped += 1
                continue

            # Resolve or create customer
            cid = customer_ids.get(customer_name.lower())
            if cid is None:
                cursor.execute('INSERT OR IGNORE INTO customers (name) VALUES (?)', (customer_name,))
                cursor.execute('SELECT id FROM customers WHERE name = ?', (customer_name,))
                r = cursor.fetchone()
                if r:
                    cid = r[0]
                    customer_ids[customer_name.lower()] = cid

            # Parse hours from HH:MM or decimal
            total_str = (
                row.get('Total') or
                row.get('Total Time') or
                row.get('Duration') or
                row.get('Hours') or '0'
            ).strip()

            try:
                if ':' in total_str:
                    parts = total_str.split(':')
                    hours = int(parts[0]) + int(parts[1]) / 60
                else:
                    hours = float(total_str)
            except (ValueError, IndexError):
                hours = 0

            if hours <= 0:
                skipped += 1
                continue

            # Parse start date
            start_str = (
                row.get('Start') or
                row.get('Start Time') or
                row.get('Date') or ''
            ).strip()
            entry_date = start_str[:10] if start_str else None

            end_str = (
                row.get('End') or
                row.get('End Time') or ''
            ).strip() or None

            description = (row.get('Description') or row.get('Notes') or '').strip()
            cost_code = (row.get('Cost Code') or row.get('CostCode') or '').strip()
            busybusy_project = (row.get('Project #') or row.get('Project#') or '').strip() or None
            busybusy_subproject = (row.get('Subproject 1  #') or row.get('Subproject 1 #') or '').strip() or None

            # Skip if already imported (deduplicate by customer + start_time)
            if start_str:
                cursor.execute(
                    'SELECT id FROM time_entries WHERE customer_id = ? AND start_time = ?',
                    (cid, start_str)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

            cursor.execute('''
                INSERT INTO time_entries
                (customer_id, entry_date, start_time, end_time, hours,
                 description, cost_code, source, busybusy_project, busybusy_subproject)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'busybusy', ?, ?)
            ''', (cid, entry_date, start_str or None, end_str, hours, description, cost_code,
                  busybusy_project, busybusy_subproject))
            total += 1

    conn.commit()
    conn.close()
    print(f"[OK] Imported {total} time entries, skipped {skipped}")
    return total


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_busybusy.py <csv_file>")
        print("\nExpected column names (either format works):")
        print("  Customer, Start, End, Total, Description, Cost Code")
        print("  OR: Project, Date, Duration, Notes, CostCode")
        sys.exit(1)

    csv_file = sys.argv[1]
    print(f"Importing: {csv_file}")
    print(f"Database:  {DB_PATH}")
    count = import_csv(csv_file)
    if count > 0:
        print(f"\n[OK] Done! {count} entries added.")
