"""
Beard's Home Services API
Flask backend serving data from SQLite database.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

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
        SELECT c.id, c.name, c.phone, c.email, c.address, c.notes,
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
               (SELECT COUNT(*) FROM time_entries WHERE job_id = j.id) as time_entry_count
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
        SELECT id, original_description, standardized_description, category, amount, service_type
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

        # Auto-generate invoice number from date if not provided
        raw_num = data.get('invoice_number') or ''
        if raw_num:
            invoice_num = raw_num if (raw_num.startswith('BHS') or raw_num.startswith('EST')) else 'BHS' + raw_num
        else:
            date_compact = start_date.replace('-', '')
            invoice_num = f"BHS{date_compact}"

        numeric = invoice_num.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
        if len(numeric) == 8:
            start_date = f"{numeric[:4]}-{numeric[4:6]}-{numeric[6:8]}"

        status = data.get('status', 'completed')

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
            cursor.execute('''
                INSERT INTO services_performed
                (invoice_id, job_id, original_description, standardized_description,
                 category, amount, service_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, job_id, svc.get('description', ''),
                  svc.get('description', ''), svc.get('category'),
                  svc.get('amount', 0), svc.get('service_type', 'labor')))

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
                     category, amount, service_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, job_id, orig_desc, std_desc,
                      svc.get('category'), svc.get('amount', 0), svc.get('service_type', 'labor')))

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
               COUNT(sp.id) as usage_count,
               SUM(sp.amount) as total_revenue
        FROM service_categories sc
        LEFT JOIN services_performed sp ON sc.name = sp.category
        GROUP BY sc.id
        ORDER BY total_revenue DESC
    ''')
    categories = rows_to_list(cursor.fetchall())
    conn.close()
    return jsonify(categories)


# ============================================================
# PRICING SUGGESTIONS (for Estimate form)
# ============================================================

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
