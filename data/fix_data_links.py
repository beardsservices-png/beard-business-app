"""
Fix data links: match services_performed records to service_categories,
and link time_entries to jobs where customer matches.

Run after build_database.py to clean up unlinked data.

Usage:
  python fix_data_links.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fix_service_categories(conn):
    """Match services_performed.category text to service_categories table."""
    cursor = conn.cursor()

    cursor.execute('SELECT id, name FROM service_categories')
    categories = {row['name'].lower(): row['id'] for row in cursor.fetchall()}

    cursor.execute('SELECT id, category FROM services_performed WHERE category IS NOT NULL')
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        cat_name = (row['category'] or '').strip().lower()
        if cat_name in categories:
            # Already a valid name, no action needed
            pass
        else:
            # Try fuzzy match
            for cat_key in categories:
                if cat_key in cat_name or cat_name in cat_key:
                    cursor.execute(
                        'UPDATE services_performed SET category = ? WHERE id = ?',
                        (cat_key.title(), row['id'])
                    )
                    updated += 1
                    break

    conn.commit()
    print(f"[OK] Service category links fixed: {updated} updated")


def link_time_to_jobs(conn):
    """Link time_entries to jobs based on customer_id and date proximity."""
    cursor = conn.cursor()

    # Get all time entries without a job_id
    cursor.execute('''
        SELECT te.id, te.customer_id, te.entry_date
        FROM time_entries te
        WHERE te.job_id IS NULL AND te.customer_id IS NOT NULL
    ''')
    entries = cursor.fetchall()

    linked = 0
    for entry in entries:
        # Find jobs for this customer, ordered by date proximity
        cursor.execute('''
            SELECT j.id
            FROM jobs j
            WHERE j.customer_id = ?
              AND j.start_date IS NOT NULL
            ORDER BY ABS(julianday(j.start_date) - julianday(?))
            LIMIT 1
        ''', (entry['customer_id'], entry['entry_date'] or '2025-01-01'))
        job = cursor.fetchone()
        if job:
            cursor.execute(
                'UPDATE time_entries SET job_id = ? WHERE id = ?',
                (job['id'], entry['id'])
            )
            linked += 1

    conn.commit()
    print(f"[OK] Time entries linked to jobs: {linked} of {len(entries)}")


def report_orphans(conn):
    """Report records that couldn't be linked."""
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM time_entries WHERE job_id IS NULL')
    unlinked_te = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM services_performed WHERE category IS NULL')
    uncat_svc = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customers WHERE name = '_UNASSIGNED'")
    # Actually check invoices with unassigned customer
    cursor.execute('''
        SELECT COUNT(*) FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE c.name = '_UNASSIGNED'
    ''')
    unassigned_inv = cursor.fetchone()[0]

    print(f"\n  Unlinked time entries:     {unlinked_te}")
    print(f"  Uncategorized services:    {uncat_svc}")
    print(f"  Unassigned invoices:       {unassigned_inv}")


if __name__ == '__main__':
    print("Fixing data links in database...")
    print(f"Database: {DB_PATH}")
    print("=" * 50)

    if not os.path.exists(DB_PATH):
        print("[ERROR] Database not found. Run build_database.py first.")
        exit(1)

    conn = get_db()
    try:
        fix_service_categories(conn)
        link_time_to_jobs(conn)
        report_orphans(conn)
        print("\n[OK] Done!")
    finally:
        conn.close()
