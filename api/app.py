"""
Beard's Home Services API
Flask backend serving data from SQLite database.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
import re
import urllib.request
import urllib.parse
import json
from datetime import datetime

BRIAN_HOME_LAT = 36.3345   # Mountain Home, AR
BRIAN_HOME_LON = -92.3857

app = Flask(__name__)
CORS(app)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'beard_business.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(row) for row in rows]


# ============================================================
# DASHBOARD
# ============================================================

@app.route('/api/dashboard')
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT SUM(total_labor) as labor, SUM(total_materials) as materials FROM invoices')
    revenue = cursor.fetchone()

    cursor.execute('SELECT SUM(hours) as total FROM time_entries')
    hours = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as count FROM customers WHERE name != '_UNASSIGNED'")
    customers = cursor.fetchone()

    cursor.execute('SELECT COUNT(*) as count FROM jobs')
    jobs_count = cursor.fetchone()

    cursor.execute('SELECT COUNT(*) as count FROM invoices')
    invoice_count = cursor.fetchone()

    # Average days on site per job (distinct calendar days with time entries)
    cursor.execute('''
        SELECT AVG(day_count) as avg_days
        FROM (
            SELECT job_id, COUNT(DISTINCT entry_date) as day_count
            FROM time_entries
            WHERE job_id IS NOT NULL
            GROUP BY job_id
            HAVING day_count > 0
        )
    ''')
    avg_days_row = cursor.fetchone()

    # Revenue by year
    cursor.execute('''
        SELECT SUBSTR(invoice_date, 1, 4) as year,
               SUM(total_labor) as total_labor,
               SUM(total_materials) as total_materials,
               SUM(total_amount) as total_revenue
        FROM invoices
        WHERE invoice_date IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    revenue_by_year = rows_to_list(cursor.fetchall())

    # Recent jobs - fixed field names to match frontend
    cursor.execute('''
        SELECT j.id, j.invoice_id, c.name as customer_name, j.start_date, j.status,
               COALESCE(i.total_labor, 0) as total_labor,
               COALESCE(i.total_materials, 0) as total_materials,
               COALESCE(i.total_amount, 0) as total_amount,
               (SELECT COUNT(DISTINCT entry_date) FROM time_entries WHERE job_id = j.id) as actual_days
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        LEFT JOIN invoices i ON j.id = i.job_id
        ORDER BY j.start_date DESC
        LIMIT 10
    ''')
    recent_jobs = rows_to_list(cursor.fetchall())

    # Top customers by labor revenue
    cursor.execute('''
        SELECT c.id, c.name,
               COUNT(DISTINCT j.id) as job_count,
               COALESCE(SUM(i.total_labor), 0) as total_revenue,
               COALESCE(SUM(te.hours), 0) as total_hours
        FROM customers c
        LEFT JOIN jobs j ON c.id = j.customer_id
        LEFT JOIN invoices i ON j.id = i.job_id
        LEFT JOIN (
            SELECT customer_id, SUM(hours) as hours FROM time_entries GROUP BY customer_id
        ) te ON c.id = te.customer_id
        WHERE c.name != '_UNASSIGNED'
        GROUP BY c.id
        HAVING total_revenue > 0
        ORDER BY total_revenue DESC
        LIMIT 8
    ''')
    top_customers = rows_to_list(cursor.fetchall())

    # Revenue by service category with avg days
    cursor.execute('''
        SELECT sp.category,
               COUNT(DISTINCT sp.job_id) as job_count,
               SUM(sp.amount) as total_revenue,
               ROUND(AVG(sp.amount), 2) as avg_revenue
        FROM services_performed sp
        WHERE sp.service_type = 'labor' AND sp.category IS NOT NULL
        GROUP BY sp.category
        ORDER BY total_revenue DESC
        LIMIT 12
    ''')
    by_category = rows_to_list(cursor.fetchall())

    # Estimation accuracy (jobs where estimated_days is set and have actual time entries)
    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN actual_days <= estimated_days THEN 1 ELSE 0 END) as on_time,
               ROUND(AVG(estimated_days), 1) as avg_estimated,
               ROUND(AVG(actual_days), 1) as avg_actual
        FROM (
            SELECT j.estimated_days,
                   COUNT(DISTINCT te.entry_date) as actual_days
            FROM jobs j
            JOIN time_entries te ON te.job_id = j.id
            WHERE j.estimated_days IS NOT NULL AND j.estimated_days > 0
            GROUP BY j.id
        )
    ''')
    est_row = cursor.fetchone()

    conn.close()

    total_hours = hours['total'] or 0
    total_labor = revenue['labor'] or 0

    return jsonify({
        'total_labor': total_labor,
        'total_materials': revenue['materials'] or 0,
        'total_revenue': total_labor + (revenue['materials'] or 0),
        'total_hours': total_hours,
        'avg_hourly_rate': round(total_labor / total_hours, 2) if total_hours > 0 else 0,
        'avg_days_per_job': round(avg_days_row['avg_days'], 1) if avg_days_row and avg_days_row['avg_days'] else 0,
        'customer_count': customers['count'],
        'job_count': jobs_count['count'],
        'invoice_count': invoice_count['count'],
        'revenue_by_year': revenue_by_year,
        'recent_jobs': recent_jobs,
        'top_customers': top_customers,
        'revenue_by_category': by_category,
        'estimation_accuracy': {
            'jobs_with_estimates': est_row['total'] if est_row else 0,
            'on_time': est_row['on_time'] if est_row else 0,
            'avg_estimated_days': est_row['avg_estimated'] if est_row else None,
            'avg_actual_days': est_row['avg_actual'] if est_row else None,
        }
    })


# ============================================================
# CUSTOMERS
# ============================================================

@app.route('/api/customers')
def list_customers():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.id, c.name, c.phone, c.email, c.address, c.notes, c.mileage_from_home,
               COALESCE(j_count.cnt, 0) as job_count,
               COALESCE(inv.labor, 0) as total_labor,
               COALESCE(te.hours, 0) as total_hours
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, COUNT(*) as cnt FROM jobs GROUP BY customer_id
        ) j_count ON c.id = j_count.customer_id
        LEFT JOIN (
            SELECT customer_id, SUM(total_labor) as labor FROM invoices GROUP BY customer_id
        ) inv ON c.id = inv.customer_id
        LEFT JOIN (
            SELECT customer_id, SUM(hours) as hours FROM time_entries GROUP BY customer_id
        ) te ON c.id = te.customer_id
        WHERE c.name != '_UNASSIGNED'
        ORDER BY c.name
    ''')
    customers = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(customers)


@app.route('/api/customers', methods=['POST'])
def create_customer():
    data = request.json
    if not data or not data.get('name'):
        return jsonify({'error': 'Customer name is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO customers (name, address, phone, email, notes) VALUES (?, ?, ?, ?, ?)',
            (data['name'], data.get('address'), data.get('phone'),
             data.get('email'), data.get('notes'))
        )
        customer_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Customer already exists'}), 409

    conn.close()
    return jsonify({'id': customer_id, 'name': data['name']}), 201


@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE customers SET name = ?, phone = ?, email = ?, address = ?, notes = ?
        WHERE id = ?
    ''', (data.get('name'), data.get('phone'), data.get('email'),
          data.get('address'), data.get('notes'), customer_id))
    conn.commit()
    conn.close()
    return jsonify({'id': customer_id, 'message': 'Customer updated'})


@app.route('/api/customers/<int:customer_id>/calculate-mileage', methods=['POST'])
def calculate_customer_mileage(customer_id):
    """Geocode the customer address and calculate driving distance from Brian's home."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT address FROM customers WHERE id = ?', (customer_id,))
    row = cursor.fetchone()
    if not row or not row['address']:
        conn.close()
        return jsonify({'error': 'No address on file'}), 400

    address = row['address']
    try:
        # Geocode with Nominatim (OpenStreetMap)
        encoded = urllib.parse.quote(address + ', USA')
        url = f'https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1'
        req = urllib.request.Request(url, headers={'User-Agent': 'BeardHomeServices/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            geo = json.loads(resp.read())
        if not geo:
            conn.close()
            return jsonify({'error': 'Could not geocode address'}), 422
        dest_lat = float(geo[0]['lat'])
        dest_lon = float(geo[0]['lon'])

        # Route with OSRM public API
        osrm_url = (
            f'https://router.project-osrm.org/route/v1/driving/'
            f'{BRIAN_HOME_LON},{BRIAN_HOME_LAT};{dest_lon},{dest_lat}'
            f'?overview=false'
        )
        req2 = urllib.request.Request(osrm_url, headers={'User-Agent': 'BeardHomeServices/1.0'})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            route = json.loads(resp2.read())

        if route.get('code') != 'Ok' or not route.get('routes'):
            conn.close()
            return jsonify({'error': 'Could not calculate route'}), 422

        meters = route['routes'][0]['distance']
        miles = round(meters / 1609.344, 1)

        cursor.execute('UPDATE customers SET mileage_from_home = ? WHERE id = ?', (miles, customer_id))
        conn.commit()
        conn.close()
        return jsonify({'customer_id': customer_id, 'mileage_from_home': miles})

    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/customers/<int:customer_id>')
def get_customer(customer_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
    customer = row_to_dict(cursor.fetchone())

    if not customer:
        conn.close()
        return jsonify({'error': 'Customer not found'}), 404

    cursor.execute('''
        SELECT j.*, i.total_labor, i.total_materials
        FROM jobs j
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE j.customer_id = ?
        ORDER BY j.start_date DESC
    ''', (customer_id,))
    customer['jobs'] = rows_to_list(cursor.fetchall())

    cursor.execute('''
        SELECT entry_date, hours, description
        FROM time_entries
        WHERE customer_id = ?
        ORDER BY entry_date DESC
    ''', (customer_id,))
    customer['time_entries'] = rows_to_list(cursor.fetchall())

    conn.close()
    return jsonify(customer)


# ============================================================
# JOBS
# ============================================================

@app.route('/api/jobs')
def list_jobs():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT j.id, j.invoice_id, j.start_date, j.status,
               c.name as customer,
               i.total_labor, i.total_materials,
               (SELECT SUM(hours) FROM time_entries WHERE job_id = j.id) as hours
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        LEFT JOIN invoices i ON j.id = i.job_id
        ORDER BY j.start_date DESC
    ''')
    jobs = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(jobs)


@app.route('/api/jobs/<int:job_id>')
def get_job(job_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT j.*, c.name as customer,
               i.total_labor, i.total_materials, i.invoice_number
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE j.id = ?
    ''', (job_id,))
    job = row_to_dict(cursor.fetchone())

    if not job:
        conn.close()
        return jsonify({'error': 'Job not found'}), 404

    cursor.execute('''
        SELECT original_description, standardized_description, category, amount, service_type
        FROM services_performed WHERE job_id = ?
    ''', (job_id,))
    job['services'] = rows_to_list(cursor.fetchall())

    cursor.execute('''
        SELECT entry_date, hours, description FROM time_entries
        WHERE job_id = ? ORDER BY entry_date
    ''', (job_id,))
    job['time_entries'] = rows_to_list(cursor.fetchall())

    conn.close()
    return jsonify(job)


@app.route('/api/jobs/full', methods=['POST'])
def create_full_job():
    data = request.json
    if not data.get('customer_id') or not data.get('invoice_number'):
        return jsonify({'error': 'customer_id and invoice_number are required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        invoice_num = data['invoice_number']
        if not invoice_num.startswith('BHS'):
            invoice_num = 'BHS' + invoice_num
        numeric = invoice_num[3:]
        if len(numeric) == 8:
            start_date = f"{numeric[:4]}-{numeric[4:6]}-{numeric[6:8]}"
        else:
            start_date = data.get('start_date')

        cursor.execute('''
            INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['customer_id'], invoice_num, numeric, start_date,
              data.get('status', 'completed'), data.get('notes', '')))
        job_id = cursor.lastrowid

        services = data.get('services', [])
        total_labor = sum(s['amount'] for s in services if s.get('service_type') == 'labor')
        total_materials = sum(s['amount'] for s in services if s.get('service_type') == 'materials')

        cursor.execute('''
            INSERT INTO invoices
            (invoice_number, customer_id, job_id, total_labor, total_materials,
             total_amount, invoice_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid')
        ''', (invoice_num, data['customer_id'], job_id, total_labor, total_materials,
              total_labor + total_materials, start_date))
        invoice_id = cursor.lastrowid

        for svc in services:
            cursor.execute('''
                INSERT INTO services_performed
                (invoice_id, job_id, original_description, standardized_description,
                 category, amount, service_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, job_id, svc.get('description', ''),
                  svc.get('description', ''), svc.get('category'),
                  svc.get('amount', 0), svc.get('service_type', 'labor')))

        for te in data.get('time_entries', []):
            cursor.execute('''
                INSERT INTO time_entries
                (customer_id, job_id, entry_date, hours, description, source)
                VALUES (?, ?, ?, ?, ?, 'app')
            ''', (data['customer_id'], job_id, te.get('date'),
                  te.get('hours', 0), te.get('description', '')))

        conn.commit()
        conn.close()

        return jsonify({
            'job_id': job_id,
            'invoice_id': invoice_id,
            'invoice_number': invoice_num,
            'total_labor': total_labor,
            'total_materials': total_materials,
            'services_count': len(services),
            'time_entries_count': len(data.get('time_entries', [])),
            'message': 'Job created successfully'
        }), 201

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': f'Invoice {data["invoice_number"]} already exists'}), 409
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs/<int:job_id>/convert', methods=['POST'])
def convert_to_invoice(job_id):
    """Convert an estimate to an invoice."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = 'completed' WHERE id = ?", (job_id,))
    cursor.execute("UPDATE invoices SET status = 'paid' WHERE job_id = ?", (job_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Converted to invoice', 'job_id': job_id})


# ============================================================
# FILING CABINET (main UI - browse/edit all invoices)
# ============================================================

@app.route('/api/filing-cabinet')
def filing_cabinet_list():
    """List all jobs for the sidebar."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT j.id as job_id,
               COALESCE(i.invoice_number, j.invoice_id) as invoice_number,
               c.name as customer,
               CASE WHEN c.name != '_UNASSIGNED' THEN 1 ELSE 0 END as has_customer,
               j.status,
               j.start_date,
               j.estimated_days,
               COALESCE(i.total_labor, 0) as total_labor,
               COALESCE(i.total_materials, 0) as total_materials,
               COALESCE(i.total_amount, i.total_labor + i.total_materials, 0) as total_amount,
               COALESCE((SELECT SUM(hours) FROM time_entries WHERE job_id = j.id), 0) as total_hours,
               COALESCE((SELECT COUNT(DISTINCT entry_date) FROM time_entries WHERE job_id = j.id), 0) as actual_days,
               (SELECT COUNT(*) FROM time_entries WHERE job_id = j.id) as time_entry_count,
               COALESCE((SELECT SUM(amount) FROM payments WHERE job_id = j.id), 0) as total_paid
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        LEFT JOIN invoices i ON j.id = i.job_id
        ORDER BY j.start_date DESC, j.id DESC
    ''')
    jobs = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify({'jobs': jobs})


@app.route('/api/filing-cabinet/<int:job_id>')
def filing_cabinet_get(job_id):
    """Get full job details for editing."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT j.id as job_id, j.customer_id, j.notes, j.status, j.start_date,
               j.estimated_days,
               c.name as customer_name, c.phone as customer_phone,
               c.email as customer_email, c.address as customer_address,
               COALESCE(i.invoice_number, j.invoice_id) as invoice_number,
               i.invoice_date, i.pdf_filename,
               COALESCE(i.total_labor, 0) as total_labor,
               COALESCE(i.total_materials, 0) as total_materials,
               COALESCE(i.total_amount, i.total_labor + i.total_materials, 0) as total_amount,
               i.id as invoice_db_id
        FROM jobs j
        JOIN customers c ON j.customer_id = c.id
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE j.id = ?
    ''', (job_id,))
    job = row_to_dict(cursor.fetchone())

    if not job:
        conn.close()
        return jsonify({'error': 'Job not found'}), 404

    cursor.execute('''
        SELECT id, original_description, standardized_description, category, amount, service_type,
               COALESCE(quantity, 1) as quantity, COALESCE(unit_of_measure, 'each') as unit_of_measure
        FROM services_performed WHERE job_id = ?
        ORDER BY id
    ''', (job_id,))
    job['services'] = rows_to_list(cursor.fetchall())

    cursor.execute('''
        SELECT id, entry_date, start_time, end_time, hours, description,
               cost_code, source, busybusy_project, busybusy_subproject
        FROM time_entries WHERE job_id = ?
        ORDER BY entry_date, id
    ''', (job_id,))
    job['time_entries'] = rows_to_list(cursor.fetchall())

    # Hours and days summary
    job['total_hours'] = sum(te['hours'] or 0 for te in job['time_entries'])
    job['actual_days'] = len({te['entry_date'] for te in job['time_entries'] if te['entry_date']})

    # Day-by-day breakdown: [{date, hours, entries}]
    days_map = {}
    for te in job['time_entries']:
        d = te['entry_date']
        if not d:
            continue
        if d not in days_map:
            days_map[d] = {'date': d, 'hours': 0, 'entries': 0}
        days_map[d]['hours'] += te['hours'] or 0
        days_map[d]['entries'] += 1
    job['days_on_site'] = sorted(days_map.values(), key=lambda x: x['date'])

    # Unlinked time entries for this customer (not yet linked to any job)
    cursor.execute('''
        SELECT id, entry_date, start_time, end_time, hours, description,
               cost_code, source, busybusy_project, busybusy_subproject
        FROM time_entries
        WHERE customer_id = ? AND job_id IS NULL
        ORDER BY entry_date
    ''', (job['customer_id'],))
    job['unlinked_time_entries'] = rows_to_list(cursor.fetchall())

    # All jobs for this customer — used to populate the reassignment dropdown
    cursor.execute('''
        SELECT j.id as job_id,
               COALESCE(i.invoice_number, j.invoice_id) as invoice_number,
               j.start_date, j.status
        FROM jobs j
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE j.customer_id = ?
        ORDER BY j.start_date DESC
    ''', (job['customer_id'],))
    job['customer_jobs'] = rows_to_list(cursor.fetchall())

    # Payments
    cursor.execute('''
        SELECT id, amount, payment_date, payment_method, memo, created_at
        FROM payments WHERE job_id = ?
        ORDER BY payment_date, id
    ''', (job_id,))
    job['payments'] = rows_to_list(cursor.fetchall())
    job['total_paid'] = sum(p['amount'] for p in job['payments'])
    job['balance_due'] = round(job['total_amount'] - job['total_paid'], 2)

    conn.close()
    return jsonify(job)


@app.route('/api/filing-cabinet/new', methods=['POST'])
def filing_cabinet_new():
    """Create a new job/invoice."""
    data = request.json
    if not data.get('customer_id'):
        return jsonify({'error': 'customer_id is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        start_date = data.get('start_date') or datetime.today().strftime('%Y-%m-%d')

        # Auto-generate number from date if not provided
        # Estimates use EST prefix; invoices use BHS prefix
        status = data.get('status', 'completed')
        raw_num = data.get('invoice_number') or ''
        if raw_num:
            if raw_num.startswith('BHS') or raw_num.startswith('EST'):
                invoice_num = raw_num
            elif status == 'estimate':
                invoice_num = 'EST' + raw_num
            else:
                invoice_num = 'BHS' + raw_num
        else:
            date_compact = start_date.replace('-', '')
            prefix = 'EST' if status == 'estimate' else 'BHS'
            invoice_num = f"{prefix}{date_compact}"

        numeric = invoice_num.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
        if len(numeric) == 8:
            start_date = f"{numeric[:4]}-{numeric[4:6]}-{numeric[6:8]}"

        cursor.execute('''
            INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, status, notes, estimated_days)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['customer_id'], invoice_num, numeric, start_date, status,
              data.get('notes', ''), data.get('estimated_days')))
        job_id = cursor.lastrowid

        services = data.get('services', [])
        total_labor = sum(s['amount'] for s in services if s.get('service_type') == 'labor')
        total_materials = sum(s['amount'] for s in services if s.get('service_type') == 'materials')

        invoice_status = 'paid' if status == 'completed' else status
        cursor.execute('''
            INSERT INTO invoices
            (invoice_number, customer_id, job_id, total_labor, total_materials,
             total_amount, invoice_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (invoice_num, data['customer_id'], job_id, total_labor, total_materials,
              total_labor + total_materials, start_date, invoice_status))
        invoice_id = cursor.lastrowid

        for svc in services:
            desc = svc.get('original_description') or svc.get('description', '')
            cursor.execute('''
                INSERT INTO services_performed
                (invoice_id, job_id, original_description, standardized_description,
                 category, amount, service_type, quantity, unit_of_measure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, job_id, desc, desc, svc.get('category'),
                  svc.get('amount', 0), svc.get('service_type', 'labor'),
                  svc.get('quantity', 1), svc.get('unit_of_measure', 'each')))

        for te in data.get('time_entries', []):
            if te.get('hours'):
                cursor.execute('''
                    INSERT INTO time_entries
                    (customer_id, job_id, entry_date, hours, description, source)
                    VALUES (?, ?, ?, ?, ?, 'app')
                ''', (data['customer_id'], job_id, te.get('date'),
                      te.get('hours', 0), te.get('description', '')))

        # Claim any unlinked time entries
        for te_id in data.get('claim_time_entry_ids', []):
            cursor.execute(
                'UPDATE time_entries SET job_id = ? WHERE id = ? AND customer_id = ?',
                (job_id, te_id, data['customer_id'])
            )

        conn.commit()
        conn.close()

        return jsonify({
            'job_id': job_id,
            'invoice_id': invoice_id,
            'invoice_number': invoice_num,
            'total_labor': total_labor,
            'total_materials': total_materials,
        }), 201

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': f'Invoice number already exists'}), 409
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/filing-cabinet/<int:job_id>', methods=['PUT'])
def filing_cabinet_update(job_id):
    """Update an existing job."""
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Update job notes/status/estimated_days
        cursor.execute('''
            UPDATE jobs SET customer_id = ?, notes = ?, estimated_days = ? WHERE id = ?
        ''', (data.get('customer_id'), data.get('notes', ''),
              data.get('estimated_days'), job_id))

        # Update customer contact info if provided
        customer = data.get('customer', {})
        if customer and data.get('customer_id'):
            cursor.execute('''
                UPDATE customers SET name = ?, phone = ?, email = ?, address = ?
                WHERE id = ?
            ''', (customer.get('name'), customer.get('phone'),
                  customer.get('email'), customer.get('address'),
                  data['customer_id']))

        # Get invoice id
        cursor.execute('SELECT id FROM invoices WHERE job_id = ?', (job_id,))
        inv_row = cursor.fetchone()
        invoice_id = inv_row['id'] if inv_row else None

        services = data.get('services', [])
        total_labor = sum(s.get('amount', 0) for s in services if s.get('service_type') == 'labor')
        total_materials = sum(s.get('amount', 0) for s in services if s.get('service_type') == 'materials')

        if invoice_id:
            # Update invoice totals and customer
            cursor.execute('''
                UPDATE invoices SET customer_id = ?, total_labor = ?, total_materials = ?,
                total_amount = ? WHERE id = ?
            ''', (data.get('customer_id'), total_labor, total_materials,
                  total_labor + total_materials, invoice_id))

            # Replace services — use standardized_description when provided
            cursor.execute('DELETE FROM services_performed WHERE job_id = ?', (job_id,))
            for svc in services:
                std_desc = svc.get('standardized_description') or svc.get('description', '')
                orig_desc = svc.get('original_description') or svc.get('description', '')
                cursor.execute('''
                    INSERT INTO services_performed
                    (invoice_id, job_id, original_description, standardized_description,
                     category, amount, service_type, quantity, unit_of_measure)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, job_id, orig_desc, std_desc,
                      svc.get('category'), svc.get('amount', 0), svc.get('service_type', 'labor'),
                      svc.get('quantity', 1), svc.get('unit_of_measure', 'each')))

        # Handle time entries - update existing, add new
        cursor.execute('SELECT id FROM time_entries WHERE job_id = ?', (job_id,))
        existing_te_ids = {row['id'] for row in cursor.fetchall()}
        submitted_te_ids = {t['id'] for t in data.get('time_entries', []) if t.get('id')}

        # Delete removed entries
        for te_id in existing_te_ids - submitted_te_ids:
            cursor.execute('DELETE FROM time_entries WHERE id = ?', (te_id,))

        for te in data.get('time_entries', []):
            if not te.get('hours'):
                continue
            if te.get('id') and te['id'] in existing_te_ids:
                cursor.execute('''
                    UPDATE time_entries SET entry_date = ?, hours = ?, description = ?
                    WHERE id = ?
                ''', (te.get('entry_date') or te.get('date'),
                      te.get('hours', 0), te.get('description', ''), te['id']))
            else:
                cursor.execute('''
                    INSERT INTO time_entries
                    (customer_id, job_id, entry_date, hours, description, source)
                    VALUES (?, ?, ?, ?, ?, 'app')
                ''', (data.get('customer_id'), job_id,
                      te.get('entry_date') or te.get('date'),
                      te.get('hours', 0), te.get('description', '')))

        # Claim unlinked time entries
        for te_id in data.get('claim_time_entry_ids', []):
            cursor.execute(
                'UPDATE time_entries SET job_id = ? WHERE id = ? AND customer_id = ?',
                (job_id, te_id, data.get('customer_id'))
            )

        conn.commit()

        cursor.execute('SELECT invoice_number FROM invoices WHERE job_id = ?', (job_id,))
        inv = cursor.fetchone()
        conn.close()

        return jsonify({
            'job_id': job_id,
            'invoice_number': inv['invoice_number'] if inv else '',
            'total_labor': total_labor,
            'total_materials': total_materials,
        })

    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


# ============================================================
# PAYMENTS
# ============================================================

@app.route('/api/jobs/<int:job_id>/payments', methods=['POST'])
def add_payment(job_id):
    """Record a payment against a job."""
    data = request.json
    if not data or not data.get('amount'):
        return jsonify({'error': 'amount is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Verify job exists and get customer_id + total
    cursor.execute('''
        SELECT j.customer_id,
               COALESCE(i.total_amount, i.total_labor + i.total_materials, 0) as total_amount
        FROM jobs j
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE j.id = ?
    ''', (job_id,))
    job_row = cursor.fetchone()
    if not job_row:
        conn.close()
        return jsonify({'error': 'Job not found'}), 404

    payment_date = data.get('payment_date') or datetime.today().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO payments (job_id, customer_id, amount, payment_date, payment_method, memo)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (job_id, job_row['customer_id'], float(data['amount']),
          payment_date, data.get('payment_method', 'cash'), data.get('memo', '')))
    payment_id = cursor.lastrowid

    # Check if fully paid and auto-update status
    cursor.execute('SELECT COALESCE(SUM(amount), 0) as total_paid FROM payments WHERE job_id = ?', (job_id,))
    total_paid = cursor.fetchone()['total_paid']
    total_amount = job_row['total_amount']
    if total_amount > 0 and total_paid >= total_amount:
        cursor.execute("UPDATE jobs SET status = 'paid' WHERE id = ?", (job_id,))
        cursor.execute("UPDATE invoices SET status = 'paid' WHERE job_id = ?", (job_id,))
        new_status = 'paid'
    else:
        cursor.execute("UPDATE jobs SET status = 'pending' WHERE id = ? AND status = 'estimate'", (job_id,))
        cursor.execute('SELECT status FROM jobs WHERE id = ?', (job_id,))
        new_status = cursor.fetchone()['status']

    conn.commit()
    conn.close()
    return jsonify({
        'id': payment_id,
        'total_paid': round(total_paid, 2),
        'balance_due': round(max(total_amount - total_paid, 0), 2),
        'status': new_status,
    }), 201


@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    """Remove a payment and re-evaluate job status."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT job_id FROM payments WHERE id = ?', (payment_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Payment not found'}), 404
    job_id = row['job_id']

    cursor.execute('DELETE FROM payments WHERE id = ?', (payment_id,))

    # Re-check balance
    cursor.execute('SELECT COALESCE(SUM(amount), 0) as total_paid FROM payments WHERE job_id = ?', (job_id,))
    total_paid = cursor.fetchone()['total_paid']
    cursor.execute('''
        SELECT COALESCE(i.total_amount, i.total_labor + i.total_materials, 0) as total_amount
        FROM jobs j LEFT JOIN invoices i ON j.id = i.job_id WHERE j.id = ?
    ''', (job_id,))
    total_amount = cursor.fetchone()['total_amount']

    if total_amount > 0 and total_paid >= total_amount:
        new_status = 'paid'
    elif total_paid > 0:
        new_status = 'pending'
    else:
        new_status = 'pending'

    cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    cursor.execute("UPDATE invoices SET status = ? WHERE job_id = ?", (new_status, job_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted', 'balance_due': round(max(total_amount - total_paid, 0), 2)})


# ============================================================
# TIME ENTRIES
# ============================================================

@app.route('/api/time-entries')
def list_time_entries():
    conn = get_db()
    cursor = conn.cursor()

    customer_id = request.args.get('customer_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = '''
        SELECT t.id, t.entry_date, t.hours, t.description, t.cost_code,
               c.name as customer, j.invoice_id
        FROM time_entries t
        LEFT JOIN customers c ON t.customer_id = c.id
        LEFT JOIN jobs j ON t.job_id = j.id
        WHERE 1=1
    '''
    params = []

    if customer_id:
        query += ' AND t.customer_id = ?'
        params.append(customer_id)
    if start_date:
        query += ' AND t.entry_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND t.entry_date <= ?'
        params.append(end_date)

    query += ' ORDER BY t.entry_date DESC LIMIT 100'

    cursor.execute(query, params)
    entries = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(entries)


@app.route('/api/time-entries', methods=['POST'])
def add_time_entry():
    data = request.json
    required = ['customer_id', 'entry_date', 'hours']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO time_entries (customer_id, job_id, entry_date, hours, description, source)
        VALUES (?, ?, ?, ?, ?, 'app')
    ''', (data['customer_id'], data.get('job_id'), data['entry_date'],
          data['hours'], data.get('description', '')))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': entry_id, 'message': 'Time entry added'}), 201


@app.route('/api/time-entries/<int:te_id>', methods=['PUT'])
def reassign_time_entry(te_id):
    """Move a time entry to a different job (or unassign it)."""
    data = request.json
    if not data or 'job_id' not in data:
        return jsonify({'error': 'job_id is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    te = cursor.execute('SELECT id, customer_id FROM time_entries WHERE id = ?', (te_id,)).fetchone()
    if not te:
        conn.close()
        return jsonify({'error': 'Time entry not found'}), 404

    new_job_id = data['job_id']
    if new_job_id:
        job = cursor.execute('SELECT id, customer_id FROM jobs WHERE id = ?', (new_job_id,)).fetchone()
        if not job:
            conn.close()
            return jsonify({'error': 'Target job not found'}), 404
        cursor.execute(
            'UPDATE time_entries SET job_id = ?, customer_id = ? WHERE id = ?',
            (new_job_id, job['customer_id'], te_id)
        )
    else:
        cursor.execute('UPDATE time_entries SET job_id = NULL WHERE id = ?', (te_id,))

    conn.commit()
    conn.close()
    return jsonify({'id': te_id, 'job_id': new_job_id, 'message': 'Reassigned'})


# ============================================================
# EXPENSES
# ============================================================

EXPENSE_CATEGORIES = [
    'Materials & Supplies',
    'Fuel & Transportation',
    'Tools & Equipment',
    'Equipment Repair & Maintenance',
    'Subcontractors',
    'Insurance',
    'Licensing & Permits',
    'Marketing & Advertising',
    'Office & Administrative',
    'Phone & Communications',
    'Clothing & Safety Gear',
    'Professional Development',
    'Disposal & Dump Fees',
    'Other',
]


@app.route('/api/expenses')
def list_expenses():
    conn = get_db()
    cursor = conn.cursor()

    job_id     = request.args.get('job_id')
    overhead   = request.args.get('overhead')  # '1' or '0'
    category   = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')

    query = '''
        SELECT e.id, e.description, e.cost, e.vendor, e.expense_date,
               e.expense_category, e.is_overhead, e.payment_method, e.notes,
               e.job_id, e.customer_id, e.receipt_path,
               c.name as customer_name,
               COALESCE(i.invoice_number, j.invoice_id) as invoice_number
        FROM materials_expenses e
        LEFT JOIN customers c ON e.customer_id = c.id
        LEFT JOIN jobs j ON e.job_id = j.id
        LEFT JOIN invoices i ON j.id = i.job_id
        WHERE 1=1
    '''
    params = []

    if job_id:
        query += ' AND e.job_id = ?'
        params.append(job_id)
    if overhead is not None:
        query += ' AND e.is_overhead = ?'
        params.append(int(overhead))
    if category:
        query += ' AND e.expense_category = ?'
        params.append(category)
    if start_date:
        query += ' AND e.expense_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND e.expense_date <= ?'
        params.append(end_date)

    query += ' ORDER BY e.expense_date DESC, e.id DESC LIMIT 500'
    cursor.execute(query, params)
    expenses = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(expenses)


@app.route('/api/expenses', methods=['POST'])
def create_expense():
    data = request.json
    if not data or not data.get('cost') or not data.get('description'):
        return jsonify({'error': 'description and cost are required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    expense_date = data.get('expense_date') or datetime.today().strftime('%Y-%m-%d')
    is_overhead  = 1 if (data.get('is_overhead') or not data.get('job_id')) else 0
    customer_id  = data.get('customer_id')

    # If job_id given and no customer_id, derive it
    if data.get('job_id') and not customer_id:
        row = cursor.execute('SELECT customer_id FROM jobs WHERE id = ?', (data['job_id'],)).fetchone()
        if row:
            customer_id = row['customer_id']

    cursor.execute('''
        INSERT INTO materials_expenses
        (job_id, customer_id, description, cost, vendor, expense_date,
         expense_category, is_overhead, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data.get('job_id'), customer_id, data['description'],
          float(data['cost']), data.get('vendor', ''), expense_date,
          data.get('expense_category', 'Materials & Supplies'),
          is_overhead, data.get('payment_method', ''), data.get('notes', '')))
    exp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': exp_id, 'message': 'Expense recorded'}), 201


@app.route('/api/expenses/<int:exp_id>', methods=['PUT'])
def update_expense(exp_id):
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE materials_expenses SET
            description = ?, cost = ?, vendor = ?, expense_date = ?,
            expense_category = ?, is_overhead = ?, payment_method = ?,
            notes = ?, job_id = ?
        WHERE id = ?
    ''', (data.get('description'), float(data.get('cost', 0)), data.get('vendor', ''),
          data.get('expense_date'), data.get('expense_category'),
          1 if data.get('is_overhead') else 0, data.get('payment_method', ''),
          data.get('notes', ''), data.get('job_id'), exp_id))
    conn.commit()
    conn.close()
    return jsonify({'id': exp_id, 'message': 'Updated'})


@app.route('/api/expenses/<int:exp_id>', methods=['DELETE'])
def delete_expense(exp_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM materials_expenses WHERE id = ?', (exp_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'})


@app.route('/api/expenses/categories')
def expense_categories():
    return jsonify(EXPENSE_CATEGORIES)


@app.route('/api/expenses/summary')
def expense_summary():
    """Totals by category and overhead vs job-specific for a date range."""
    conn = get_db()
    cursor = conn.cursor()
    start_date = request.args.get('start_date', '2000-01-01')
    end_date   = request.args.get('end_date', '2099-12-31')

    cursor.execute('''
        SELECT expense_category,
               SUM(CASE WHEN is_overhead = 1 THEN cost ELSE 0 END) as overhead_total,
               SUM(CASE WHEN is_overhead = 0 THEN cost ELSE 0 END) as job_total,
               SUM(cost) as grand_total,
               COUNT(*) as count
        FROM materials_expenses
        WHERE expense_date BETWEEN ? AND ?
        GROUP BY expense_category
        ORDER BY grand_total DESC
    ''', (start_date, end_date))
    by_category = rows_to_list(cursor.fetchall())

    cursor.execute('''
        SELECT
            SUM(CASE WHEN is_overhead = 1 THEN cost ELSE 0 END) as total_overhead,
            SUM(CASE WHEN is_overhead = 0 THEN cost ELSE 0 END) as total_job_costs,
            SUM(cost) as total_expenses
        FROM materials_expenses
        WHERE expense_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    totals = row_to_dict(cursor.fetchone())
    conn.close()
    return jsonify({'by_category': by_category, 'totals': totals})


# ============================================================
# INVOICES
# ============================================================

@app.route('/api/invoices')
def list_invoices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.id, i.invoice_number, i.invoice_date, i.total_labor,
               i.total_materials, i.total_amount, i.status,
               c.name as customer
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        ORDER BY i.invoice_date DESC
    ''')
    invoices = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(invoices)


# ============================================================
# SERVICE CATEGORIES
# ============================================================

@app.route('/api/categories')
@app.route('/api/service-categories')
def list_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sc.id, sc.name, sc.description, sc.is_labor,
               sc.parent_id,
               COUNT(sp.id) as usage_count,
               COALESCE(SUM(sp.amount), 0) as total_revenue
        FROM service_categories sc
        LEFT JOIN services_performed sp ON sc.name = sp.category
        GROUP BY sc.id
        ORDER BY sc.parent_id NULLS FIRST, sc.name
    ''')
    categories = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(categories)


@app.route('/api/categories', methods=['POST'])
def create_category():
    data = request.json
    if not data or not data.get('name'):
        return jsonify({'error': 'Category name is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO service_categories (name, description, is_labor, parent_id) VALUES (?, ?, ?, ?)',
            (data['name'].strip(), data.get('description', ''),
             1 if data.get('is_labor', True) else 0,
             data.get('parent_id'))
        )
        cat_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Category already exists'}), 409
    conn.close()
    return jsonify({'id': cat_id, 'name': data['name']}), 201


@app.route('/api/categories/<int:cat_id>', methods=['PUT'])
def update_category(cat_id):
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE service_categories SET name=?, description=?, is_labor=?, parent_id=? WHERE id=?',
        (data.get('name'), data.get('description'), 1 if data.get('is_labor', True) else 0,
         data.get('parent_id'), cat_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': cat_id, 'message': 'Updated'})


@app.route('/api/categories/<int:cat_id>', methods=['DELETE'])
def delete_category(cat_id):
    conn = get_db()
    cursor = conn.cursor()
    # Prevent deleting categories that have children or are in use
    cursor.execute('SELECT COUNT(*) as cnt FROM service_categories WHERE parent_id = ?', (cat_id,))
    if cursor.fetchone()['cnt'] > 0:
        conn.close()
        return jsonify({'error': 'Category has subcategories — delete those first'}), 409
    cursor.execute('DELETE FROM service_categories WHERE id = ?', (cat_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'})


# ============================================================
# PRICING SUGGESTIONS (for Estimate form)
# ============================================================

@app.route('/api/pricing/claude-suggest', methods=['POST'])
def pricing_claude_suggest():
    """Use Claude API to suggest pricing for a service description."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set', 'available': False}), 200

    data = request.json or {}
    description = data.get('description', '')
    category = data.get('category', '')
    historical = data.get('historical', {})

    prompt = f"""You are a pricing advisor for a one-person handyman business in Mountain Home, AR (rural Ozarks).

Service to price: {description}
Category: {category}
My historical data for this category: {json.dumps(historical) if historical else 'No history yet'}

Provide a concise JSON response with these fields:
- suggested_low: lower end of a fair price range (integer dollars)
- suggested_high: upper end of a fair price range (integer dollars)
- suggested_price: your single best recommendation (integer dollars)
- rationale: 1-2 sentence plain-English explanation of the pricing
- factors: array of 2-4 short strings noting key factors (difficulty, materials, time, etc.)

Base pricing on: rural Arkansas labor rates (~$45-85/hr skilled trades), realistic job complexity, material costs typical for Mountain Home area, and the goal of staying competitive while being profitable. Respond with ONLY valid JSON, no other text."""

    try:
        req_data = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 400,
            'messages': [{'role': 'user', 'content': prompt}]
        }).encode()
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=req_data,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        text = result['content'][0]['text'].strip()
        suggestion = json.loads(text)
        suggestion['available'] = True
        return jsonify(suggestion)
    except Exception as e:
        return jsonify({'error': str(e), 'available': False}), 200


@app.route('/api/pricing/suggest')
def pricing_suggest():
    category = request.args.get('category')
    if not category:
        return jsonify({'error': 'category is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG(amount) as avg_price, MIN(amount) as min_price,
               MAX(amount) as max_price, COUNT(*) as job_count
        FROM services_performed
        WHERE category = ? AND service_type = 'labor' AND amount > 0
    ''', (category,))
    row = cursor.fetchone()

    cursor.execute('''
        SELECT amount FROM services_performed
        WHERE category = ? AND service_type = 'labor' AND amount > 0
        ORDER BY rowid DESC LIMIT 3
    ''', (category,))
    recent = [r['amount'] for r in cursor.fetchall()]
    conn.close()

    if not row or not row['job_count']:
        return jsonify({'category': category, 'avg_price': None, 'job_count': 0})

    return jsonify({
        'category': category,
        'avg_price': round(row['avg_price'], 2),
        'min_price': round(row['min_price'], 2),
        'max_price': round(row['max_price'], 2),
        'job_count': row['job_count'],
        'recent_prices': recent
    })


@app.route('/api/pricing/suggest-all')
def pricing_suggest_all():
    """Return pricing hints for all categories at once (loaded on page open)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category,
               ROUND(AVG(amount), 2) as avg_price,
               ROUND(MIN(amount), 2) as min_price,
               ROUND(MAX(amount), 2) as max_price,
               COUNT(*) as job_count
        FROM services_performed
        WHERE service_type = 'labor' AND amount > 0 AND category IS NOT NULL
        GROUP BY category
    ''')
    rows = cursor.fetchall()

    # Avg days on site per category (from jobs that have that service category + time entries)
    cursor.execute('''
        SELECT sp.category,
               ROUND(AVG(day_count), 1) as avg_days
        FROM (
            SELECT sp2.job_id, sp2.category,
                   COUNT(DISTINCT te.entry_date) as day_count
            FROM services_performed sp2
            JOIN time_entries te ON te.job_id = sp2.job_id
            WHERE sp2.service_type = 'labor' AND sp2.category IS NOT NULL
            GROUP BY sp2.job_id, sp2.category
            HAVING day_count > 0
        ) sp
        GROUP BY sp.category
    ''')
    days_by_cat = {r['category']: r['avg_days'] for r in cursor.fetchall()}

    result = {}
    for row in rows:
        cat = row['category']
        cursor.execute('''
            SELECT amount FROM services_performed
            WHERE category = ? AND service_type = 'labor' AND amount > 0
            ORDER BY rowid DESC LIMIT 3
        ''', (cat,))
        recent = [r['amount'] for r in cursor.fetchall()]
        result[cat] = {
            'avg_price': row['avg_price'],
            'min_price': row['min_price'],
            'max_price': row['max_price'],
            'job_count': row['job_count'],
            'recent_prices': recent,
            'avg_days': days_by_cat.get(cat),
        }

    conn.close()
    return jsonify(result)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/api/health')
def health():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM customers')
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected', 'customers': count})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    print("Starting Beard's Home Services API...")
    print(f"Database: {DB_PATH}")
    app.run(debug=True, host='0.0.0.0', port=5000)
