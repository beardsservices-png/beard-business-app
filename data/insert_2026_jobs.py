"""
Insert 7 new 2026 jobs from CLAUDE_CODE_INTEGRATION_2026.md into beard_business.db
Maps to actual schema (invoice_id, invoices table, etc.) rather than the brief's assumed schema.
"""
import sqlite3

DB = 'data/beard_business.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── STEP 1: Insert George (only missing customer) ──────────────────────────────
print("STEP 1: Customers...")
george = c.execute("SELECT id FROM customers WHERE name='George' AND phone LIKE '%530%'").fetchone()
if not george:
    c.execute("""
        INSERT INTO customers (name, phone, address, notes)
        VALUES ('George', '+1 530-218-4563', '117 Reid Ln, Henderson, AR 72544',
                'Shingle roof repair. Last name unknown.')
    """)
    george_id = c.lastrowid
    print(f"  Inserted George -> id {george_id}")
else:
    george_id = george['id']
    print(f"  George already exists -> id {george_id}")

# Customer ID lookups (others already exist)
def cust(name):
    r = c.execute("SELECT id FROM customers WHERE name=?", (name,)).fetchone()
    if not r:
        raise ValueError(f"Customer not found: {name}")
    return r['id']

brasher_id   = cust('MJ and Tommy Brasher')
delao_id     = cust('Maleca Delao')
clark_id     = cust('Cassandra Clark')
sammy_id     = cust('Sammy Jones')

print(f"  Brasher={brasher_id}, Delao={delao_id}, Clark={clark_id}, Sammy={sammy_id}, George={george_id}")

# ── STEP 2: Insert Jobs + Invoices ─────────────────────────────────────────────
# Each "job" in the brief = 1 row in `jobs` + 1 row in `invoices`
print("\nSTEP 2: Jobs + Invoices...")

jobs_data = [
    # (invoice_num, project_num, customer_id, start_date, end_date, notes,
    #  total_labor, total_materials, total_amount, invoice_date)
    ('BHS20251216', '20251216', brasher_id, '2026-01-05', '2026-01-07',
     '7 pipe boots on 2-story metal roof. Materials: Masterflash boots, storm collars, flash mate, strip mastic.',
     490.00, 200.00, 690.00, '2026-01-05'),

    ('BHS20260121', '20260121', delao_id, '2026-01-21', '2026-01-21',
     'Reinstalled fallen batt insulation in crawlspace. Installed hand towel holder and TP holder.',
     100.00, 0.00, 100.00, '2026-01-21'),

    ('BHS20260127', '20260127', delao_id, '2026-01-27', '2026-01-27',
     'Drywall repair and paint. Door handle tightening.',
     110.00, 0.00, 110.00, '2026-01-27'),

    ('BHS20260206', '20260206', clark_id, '2026-02-06', '2026-02-07',
     'Repaired multiple leaks at coupling joints. Replaced pipe sections. Connected water heater. 2-day job. Max 45 lbs pressure until 4pm Feb 7.',
     290.00, 50.00, 340.00, '2026-02-06'),

    ('BHS20260309', '20260309', sammy_id, '2026-03-02', '2026-03-27',
     'House exterior painting. 1350 sq ft @ $1.50/sqft. Power wash, prep, 2 coats on siding and trim. Multi-week job Mar 2-27. $100 cash given by customer for 6th gallon + clear coat for shutters (not on invoice).',
     2025.00, 0.00, 2025.00, '2026-03-25'),

    ('BHS20260317', '20260317', george_id, '2026-03-17', '2026-03-17',
     'Install ridgecap and antennae. Properly seal and fasten per industry standards.',
     160.00, 0.00, 160.00, '2026-03-17'),

    ('BHS20260330', '20260330', brasher_id, '2026-03-30', '2026-03-30',
     'Inspect and seal protrusions: pipe boots, double-walled vents, antenna anchor bolts. Trip charge includes specialized high-access equipment for 2-story metal roof.',
     350.00, 0.00, 350.00, '2026-03-30'),
]

job_ids = {}     # invoice_num -> jobs.id
inv_ids = {}     # invoice_num -> invoices.id

for (inv_num, proj_num, cust_id, start, end, notes,
     labor, materials, total, inv_date) in jobs_data:

    # Check not already inserted
    existing = c.execute("SELECT id FROM jobs WHERE invoice_id=?", (inv_num,)).fetchone()
    if existing:
        print(f"  {inv_num}: already exists (job id {existing['id']})")
        job_ids[inv_num] = existing['id']
        inv = c.execute("SELECT id FROM invoices WHERE invoice_number=?", (inv_num,)).fetchone()
        inv_ids[inv_num] = inv['id'] if inv else None
        continue

    # Insert job
    c.execute("""
        INSERT INTO jobs (customer_id, invoice_id, project_number, start_date, end_date, status, notes)
        VALUES (?, ?, ?, ?, ?, 'completed', ?)
    """, (cust_id, inv_num, proj_num, start, end, notes))
    job_id = c.lastrowid
    job_ids[inv_num] = job_id

    # Insert invoice
    c.execute("""
        INSERT INTO invoices (invoice_number, customer_id, job_id, total_labor, total_materials,
                              total_amount, invoice_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'paid')
    """, (inv_num, cust_id, job_id, labor, materials, total, inv_date))
    inv_id = c.lastrowid
    inv_ids[inv_num] = inv_id

    print(f"  {inv_num}: job_id={job_id}, invoice_id={inv_id}  (${total:.2f})")

# ── STEP 3: Services Performed ─────────────────────────────────────────────────
print("\nSTEP 3: Services...")

def add_service(inv_num, svc_name, category, svc_type, qty, uom, amount, description):
    # Skip if already there
    existing = c.execute("""
        SELECT id FROM services_performed
        WHERE job_id=? AND original_description=?
    """, (job_ids[inv_num], description[:80])).fetchone()
    if existing:
        return
    c.execute("""
        INSERT INTO services_performed
            (invoice_id, job_id, original_description, standardized_description,
             category, amount, service_type, quantity, unit_of_measure)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (inv_ids[inv_num], job_ids[inv_num],
          description, svc_name, category, amount, svc_type, qty, uom))

# BHS20251216 - Brasher Pipe Boots
add_service('BHS20251216', 'Pipe Boot Installation Labor', 'Roofing - Metal Roof', 'labor',
            7, 'boot', 490.00,
            'Install 7 pipe boots on 2-story metal roof. Secure ladder with toe board. Remove existing worn boots. Install properly sized/sealed metal pipe boots with rubber gasket fasteners. Apply roofing sealant around all penetrations.')
add_service('BHS20251216', 'Roofing Materials', 'Materials', 'materials',
            1, 'lot', 200.00,
            'Masterflash adj pipe flash (4x$34.48), storm collar 4in, Flash Mate 10oz, ductboard starting collar 6in, storm collar 6in, metal roof strip mastic 45ft. Total w/tax ~$200.')

# BHS20260121 - Delao Crawlspace + Bathroom
add_service('BHS20260121', 'Crawlspace Insulation Reinstall', 'Insulation - Crawlspace', 'labor',
            1, 'job', 50.00,
            'Reinstall fallen batt insulation in crawlspace.')
add_service('BHS20260121', 'Bathroom Hardware Installation', 'Carpentry - Hardware Install', 'labor',
            2, 'piece', 50.00,
            'Install and securely fasten 1 hand towel holder and 1 TP holder in 2nd office bathroom.')

# BHS20260127 - Delao Drywall + Door
add_service('BHS20260127', 'Drywall Repair and Paint', 'Drywall - Repair & Paint', 'labor',
            1, 'job', 100.00,
            'Drywall repair and paint.')
add_service('BHS20260127', 'Door Handle Tightening', 'Carpentry - Hardware Install', 'labor',
            1, 'each', 10.00,
            'Tighten and secure door handle.')

# BHS20260206 - Clark Plumbing
add_service('BHS20260206', 'Plumbing Repair Labor', 'Plumbing - Pipe Repair', 'labor',
            1, 'job', 290.00,
            'Day 1: Repair multiple leaks at coupling joints. Replace pipe sections with new fittings. Connect water heater properly. Day 2: Fix hot/cold leaks. Repair water heater outlet leak. 24hr wait before pressurizing.')
add_service('BHS20260206', 'Plumbing Materials', 'Materials', 'materials',
            1, 'lot', 50.00,
            'Pipe fittings, couplings, and repair materials for plumbing job.')

# BHS20260309 - Sammy Jones Painting
add_service('BHS20260309', 'House Exterior Paint Labor', 'Painting - Exterior', 'labor',
            1350, 'sq ft', 2025.00,
            '1350 sq ft exterior painting @ $1.50/sqft. Prep: remove loose paint, spot prime, caulk edges/gaps. Roll/brush 2 coats on siding and trim. Includes equipment, supplies (except paint), setup and cleanup.')
add_service('BHS20260309', 'Power Wash and Surface Prep', 'Painting - Surface Prep', 'labor',
            1, 'job', 0.00,
            'Included: Power wash surface (clear debris, apply cleaner, scrub, rinse). Masking tape/paper, surface repair, solvents, cleanup supplies.')

# BHS20260317 - George Shingle Roof
add_service('BHS20260317', 'Shingle Roof Repair Labor', 'Roofing - Shingle', 'labor',
            1, 'job', 160.00,
            'Install ridgecap and antennae. Properly seal and fasten per industry standards.')

# BHS20260330 - Brasher Inspection/Sealing
add_service('BHS20260330', 'Pipe Boot Inspection and Sealing', 'Roofing - Metal Roof', 'labor',
            1, 'job', 210.00,
            'Inspect and seal protrusions including pipe boots, double-walled vents, antenna anchor bolts, and other penetrations.')
add_service('BHS20260330', 'Trip Charge - High Access Safety Equipment', 'Roofing - Access & Safety', 'labor',
            1, 'job', 140.00,
            'Safety & access charge: provision of specialized high-access equipment including extension ladders and anchors for 2-story metal roof navigation.')

print("  Services inserted.")

# ── STEP 4: Payments ───────────────────────────────────────────────────────────
print("\nSTEP 4: Payments...")

payments_data = [
    ('BHS20251216', brasher_id,  690.00, '2026-01-05', 'Unknown', None),
    ('BHS20260121', delao_id,    100.00, '2026-01-22', 'Unknown', None),
    ('BHS20260127', delao_id,    110.00, '2026-01-27', 'Unknown', None),
    ('BHS20260206', clark_id,    200.00, '2026-02-06', 'Unknown', None),
    ('BHS20260206', clark_id,    140.00, '2026-02-07', 'Unknown', None),
    ('BHS20260309', sammy_id,    200.00, '2026-03-09', 'Unknown', 'Deposit'),
    ('BHS20260309', sammy_id,    300.00, '2026-03-20', 'Unknown', None),
    ('BHS20260309', sammy_id,    725.00, '2026-03-25', 'Unknown', None),
    ('BHS20260309', sammy_id,    800.00, '2026-03-28', 'Unknown', None),
    ('BHS20260317', george_id,   160.00, '2026-03-17', 'Unknown', None),
    ('BHS20260330', brasher_id,  350.00, '2026-03-31', 'Unknown', None),
]

for (inv_num, cust_id, amount, pdate, method, memo) in payments_data:
    # Check for duplicate (same job, amount, date)
    existing = c.execute("""
        SELECT id FROM payments WHERE job_id=? AND amount=? AND payment_date=?
    """, (job_ids[inv_num], amount, pdate)).fetchone()
    if existing:
        print(f"  {inv_num} {pdate} ${amount}: already exists")
        continue
    c.execute("""
        INSERT INTO payments (job_id, customer_id, amount, payment_date, payment_method, memo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_ids[inv_num], cust_id, amount, pdate, method, memo))
    print(f"  {inv_num} {pdate} ${amount:.2f}")

# ── STEP 5: Time Entries ───────────────────────────────────────────────────────
print("\nSTEP 5: Time entries...")

def add_time(inv_num, cust_id, visit_date, start_t, end_t, hours, notes=None):
    existing = c.execute("""
        SELECT id FROM time_entries WHERE job_id=? AND entry_date=? AND start_time=?
    """, (job_ids[inv_num], visit_date, start_t)).fetchone()
    if existing:
        return
    desc = notes or f"On-site work at {visit_date}"
    c.execute("""
        INSERT INTO time_entries
            (customer_id, job_id, entry_date, start_time, end_time, hours, description, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Google Maps')
    """, (cust_id, job_ids[inv_num], visit_date, start_t, end_t, hours, desc))

# BHS20251216
add_time('BHS20251216', brasher_id, '2026-01-05', '8:36 AM',  '3:17 PM', 6.68)
add_time('BHS20251216', brasher_id, '2026-01-07', '11:28 AM', '12:00 PM', 0.53, 'Follow-up/check visit')

# BHS20260121
add_time('BHS20260121', delao_id,   '2026-01-21', '9:12 AM',  '11:44 AM', 2.53)

# BHS20260127
add_time('BHS20260127', delao_id,   '2026-01-27', '11:35 AM', '12:03 PM', 0.47)

# BHS20260206
add_time('BHS20260206', clark_id,   '2026-02-06', '12:48 PM', '1:45 PM',  0.95)
add_time('BHS20260206', clark_id,   '2026-02-06', '2:08 PM',  '4:24 PM',  2.27)
add_time('BHS20260206', clark_id,   '2026-02-07', '10:54 AM', '12:26 PM', 1.53)

# BHS20260309 - Sammy Jones (29 sessions)
sammy_times = [
    ('2026-03-02','1:44 PM','3:55 PM',2.18), ('2026-03-06','12:51 PM','1:47 PM',0.93),
    ('2026-03-06','3:05 PM','4:02 PM',0.93), ('2026-03-09','1:02 PM','1:42 PM',0.65),
    ('2026-03-10','9:54 AM','10:28 AM',0.57), ('2026-03-11','11:55 AM','12:42 PM',0.78),
    ('2026-03-11','3:17 PM','4:20 PM',1.05), ('2026-03-12','12:11 PM','1:43 PM',1.53),
    ('2026-03-12','2:46 PM','4:19 PM',1.55), ('2026-03-13','9:05 AM','10:58 AM',1.88),
    ('2026-03-13','12:19 PM','2:20 PM',2.02), ('2026-03-16','3:33 PM','3:36 PM',0.05),
    ('2026-03-18','11:06 AM','1:08 PM',2.03), ('2026-03-18','4:49 PM','5:20 PM',0.52),
    ('2026-03-19','9:12 AM','9:29 AM',0.28), ('2026-03-19','11:11 AM','12:10 PM',0.98),
    ('2026-03-20','10:28 AM','11:44 AM',1.27), ('2026-03-20','1:17 PM','1:55 PM',0.65),
    ('2026-03-20','2:51 PM','4:16 PM',1.40), ('2026-03-21','12:03 PM','12:44 PM',0.68),
    ('2026-03-22','11:05 AM','12:26 PM',1.35), ('2026-03-24','6:50 AM','8:45 AM',1.92),
    ('2026-03-24','1:16 PM','4:35 PM',3.32), ('2026-03-25','10:13 AM','11:45 AM',1.53),
    ('2026-03-25','3:11 PM','4:50 PM',1.65), ('2026-03-26','9:33 AM','12:40 PM',3.12),
    ('2026-03-26','2:11 PM','4:49 PM',2.63), ('2026-03-26','6:23 PM','8:07 PM',1.73),
    ('2026-03-27','11:36 AM','1:52 PM',2.27),
]
for (d, s, e, h) in sammy_times:
    add_time('BHS20260309', sammy_id, d, s, e, h)

# BHS20260317
add_time('BHS20260317', george_id,  '2026-03-17', '1:08 PM',  '2:35 PM',  1.45)

# BHS20260330
add_time('BHS20260330', brasher_id, '2026-03-30', '12:33 PM', '12:59 PM', 0.43)

# Count time entries for Sammy Jones
sammy_hrs = c.execute(
    "SELECT ROUND(SUM(hours),2), COUNT(*) FROM time_entries WHERE job_id=?",
    (job_ids['BHS20260309'],)
).fetchone()
print(f"  Sammy Jones: {sammy_hrs[1]} sessions, {sammy_hrs[0]} total hours")
print("  All time entries inserted.")

# ── STEP 6: Verify ─────────────────────────────────────────────────────────────
conn.commit()
print("\n=== VERIFICATION ===")
rows = c.execute("""
    SELECT i.invoice_number, c.name, i.invoice_date, i.total_amount,
           i.total_labor, i.total_materials, i.status
    FROM invoices i
    JOIN customers c ON c.id = i.customer_id
    WHERE i.invoice_date >= '2026-01-01'
    ORDER BY i.invoice_date
""").fetchall()
print(f"{'Invoice':<16} {'Customer':<24} {'Date':<12} {'Total':>8} {'Labor':>8} {'Matl':>7} {'Status'}")
print("-"*85)
for r in rows:
    print(f"{r[0]:<16} {r[1]:<24} {r[2]:<12} ${r[3]:>7.2f} ${r[4]:>7.2f} ${r[5]:>6.2f}  {r[6]}")

total_2026 = sum(r[3] for r in rows if not r[0].startswith('EST'))
print(f"\n2026 revenue (paid invoices): ${total_2026:.2f}")

pmt_total = c.execute("""
    SELECT SUM(p.amount) FROM payments p
    JOIN jobs j ON j.id = p.job_id
    JOIN invoices i ON i.job_id = j.id
    WHERE i.invoice_date >= '2026-01-01'
""").fetchone()[0] or 0
print(f"2026 payments recorded:        ${pmt_total:.2f}")

time_total = c.execute("""
    SELECT ROUND(SUM(te.hours),2), COUNT(*) FROM time_entries te
    JOIN jobs j ON j.id = te.job_id
    JOIN invoices i ON i.job_id = j.id
    WHERE i.invoice_date >= '2026-01-01'
""").fetchone()
print(f"2026 time entries:             {time_total[1]} sessions, {time_total[0]} hours")

conn.close()
print("\nDone.")
