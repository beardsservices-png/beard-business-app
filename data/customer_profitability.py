"""
Customer profitability report.
Shows revenue, hours, and effective $/hour for each customer.

Usage:
  python customer_profitability.py
  python customer_profitability.py --min-revenue 500
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def run_report(min_revenue=0):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            c.id,
            c.name,
            COUNT(DISTINCT j.id) as job_count,
            SUM(i.total_labor) as total_labor,
            SUM(i.total_materials) as total_materials,
            SUM(i.total_amount) as total_revenue,
            COALESCE((
                SELECT SUM(te.hours)
                FROM time_entries te
                WHERE te.customer_id = c.id
            ), 0) as total_hours
        FROM customers c
        LEFT JOIN jobs j ON j.customer_id = c.id
        LEFT JOIN invoices i ON i.customer_id = c.id
        WHERE c.name != '_UNASSIGNED'
        GROUP BY c.id, c.name
        HAVING SUM(i.total_amount) >= ?
        ORDER BY total_revenue DESC
    ''', (min_revenue,))

    rows = cursor.fetchall()
    conn.close()

    print("=" * 75)
    print("CUSTOMER PROFITABILITY REPORT - Beard's Home Services")
    print("=" * 75)
    print(f"{'Customer':<28} {'Jobs':>4} {'Revenue':>10} {'Labor':>10} {'Hours':>7} {'$/hr':>8}")
    print("-" * 75)

    total_rev = 0
    total_hrs = 0

    for row in rows:
        rev = row['total_revenue'] or 0
        labor = row['total_labor'] or 0
        hrs = row['total_hours'] or 0
        rate = labor / hrs if hrs > 0 else 0
        total_rev += rev
        total_hrs += hrs

        print(f"{row['name'][:27]:<28} {row['job_count']:>4} ${rev:>9,.2f} ${labor:>9,.2f} {hrs:>6.1f}h {('$'+f'{rate:.2f}') if rate > 0 else '—':>8}")

    print("=" * 75)
    overall_rate = total_rev / total_hrs if total_hrs > 0 else 0
    print(f"{'TOTAL':<28} {'':>4} ${total_rev:>9,.2f} {'':>10} {total_hrs:>6.1f}h {('$'+f'{overall_rate:.2f}') if overall_rate > 0 else '—':>8}")


if __name__ == '__main__':
    min_rev = 0
    for arg in sys.argv[1:]:
        if arg.startswith('--min-revenue='):
            min_rev = float(arg.split('=')[1])
        elif arg == '--min-revenue' and len(sys.argv) > sys.argv.index(arg) + 1:
            min_rev = float(sys.argv[sys.argv.index(arg) + 1])

    run_report(min_revenue=min_rev)
