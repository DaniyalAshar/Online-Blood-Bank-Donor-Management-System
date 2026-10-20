# LifeFlow Analytics — Blood Bank Management + Data Analytics

A multi-page learning project using Python Flask, SQLite, HTML, Tailwind CSS, vanilla JavaScript, Chart.js, and Pandas. No Node.js/npm required.

## Pages
- `/` — Home
- `/search` — Search blood stock by blood group and city
- `/donor/register` — Register donor profile
- `/request/new` — Submit a request for staff review
- `/dashboard` — Operations overview with KPI cards and charts
- `/analytics` — Data analytics studio: trends, group distribution, facility stock, urgency mix, and CSV export
- `/about` — Project information and FAQs

## Run on Windows
1. Extract ZIP and open the folder in VS Code.
2. `python -m venv venv`
3. `venv\\Scripts\\activate` (PowerShell may require `venv\\Scripts\\Activate.ps1`)
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and set a strong `SECRET_KEY`.
6. `python app.py`
7. Open `http://127.0.0.1:5000`

## Demo data
With `FLASK_DEBUG=1` in `.env`, visit `http://127.0.0.1:5000/api/demo/seed` once to add synthetic facilities, inventory, donors, requests, and dated history records. This route returns 404 when debug is off. Demo data is synthetic and must not be used for medical decisions.

## Analytics features
- KPI cards: donors, verified facilities, requests, available stock, and fill-rate proxy
- Chart.js charts: stock by blood group, requests by month, urgency mix, facility comparison
- Pandas-powered summary statistics and CSV export at `/api/analytics/export.csv`
- Filter by city and blood group on the analytics page
- API endpoints return aggregate analytics, not personal donor details

## Important
This is a student/demo project, not a production clinical system. Authentication and role-based authorization, audit logs, inventory expiry/batch accounting, facility verification workflows, consent management, backups, privacy review, and real messaging integrations must be implemented before deployment. The fill-rate shown is a demo proxy and is not a clinical supply adequacy metric. Charts use illustrative seeded records.
