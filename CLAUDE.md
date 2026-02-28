# Beard's Home Services - Business App

Owner: Brian (non-technical). Mountain Home, AR handyman business.

## Project Structure
```
beard-business-app/
├── api/
│   └── app.py              # Flask API, port 5000
├── data/
│   ├── beard_business.db   # SQLite database
│   ├── build_database.py   # Rebuild DB from source files
│   ├── import_busybusy.py  # Import BusyBusy CSV exports
│   ├── fix_data_links.py   # Fix category/job links
│   ├── match_invoices_to_time.py
│   ├── customer_profitability.py
│   ├── time_tracking/      # BusyBusy CSV exports
│   └── invoice_workflow/   # JSON files from invoice extraction
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── pages/
│           ├── Dashboard.jsx
│           ├── FilingCabinet.jsx
│           ├── Jobs.jsx
│           ├── Customers.jsx
│           ├── TimeEntry.jsx
│           ├── Estimate.jsx
│           └── PrintView.jsx
├── invoice_workflow/       # Claude invoice extraction artifacts
│   ├── customer_invoice_mapping.json
│   ├── extracted_services.json
│   └── matched_services.json
├── .claude/
│   └── agents/             # Sub-agents for invoice workflow
├── start_app.bat           # Start Flask + Vite
└── requirements.txt
```

## Tech Stack
- **Backend**: Flask (Python), SQLite (raw sqlite3, NO SQLAlchemy)
- **Frontend**: React 18 + Vite + TailwindCSS v4 + react-router-dom + recharts
- **DB path**: `data/beard_business.db`
- **API port**: 5000
- **Frontend port**: 5173

## Database Schema
8 tables: `customers`, `jobs`, `invoices`, `services_performed`,
`time_entries`, `materials_expenses`, `service_categories`, `timeline_visits`

## Phases
- **Phase 0**: ✅ Invoice extraction (5-agent workflow)
- **Phase 1**: ✅ Database build + import (52+ invoices, 34 customers)
- **Phase 2**: ✅ Flask API + React frontend connected
- **Phase 3**: ✅ Estimates, Filing Cabinet, PrintView
- **Phase 4**: Google Maps Timeline import
- **Phase 5**: Receipt scanning + P&L reports
- **Phase 6**: Local deployment polish

## Critical Rules
- NEVER use SQLAlchemy — always raw `sqlite3`
- NEVER Unicode in Python print() on Windows — use ASCII only
- ALWAYS use subagents for long tasks to conserve context
- DB queries use `conn.row_factory = sqlite3.Row` + `dict(row)` pattern

## Invoice Source Files
- InvoiceBee format: ZIP files containing `1.txt`, `1.jpeg`, `manifest.json`
- Use `zipfile` module to read, NOT `pdfplumber`
- Source path: check PROGRESS.md for current location

## Key API Endpoints
```
GET  /api/dashboard
GET  /api/customers
POST /api/customers
GET  /api/customers/<id>
GET  /api/jobs
POST /api/jobs/full
GET  /api/filing-cabinet
GET  /api/filing-cabinet/<job_id>
POST /api/filing-cabinet/new
PUT  /api/filing-cabinet/<job_id>
POST /api/jobs/<job_id>/convert
GET  /api/time-entries
POST /api/time-entries
GET  /api/invoices
GET  /api/service-categories
GET  /api/pricing/suggest
GET  /api/pricing/suggest-all
GET  /api/health
```

## Brian's Preferences
- Explain in plain business terms, not tech terms
- FreshBooks-style clean UI
- Free tools only (has Claude subscription)
- End-of-day time entry (quick, 2 min per job)
