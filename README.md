# Carbon Flow

Enterprise-grade greenhouse gas emissions data ingestion and audit platform.

## Overview

Carbon Flow is a Django REST + React application that ingests emissions data from SAP enterprise systems, utility providers, and corporate travel platforms. It normalizes heterogeneous data formats, calculates CO2e emissions using EPA and DEFRA factors, and provides an analyst review dashboard for audit-ready reporting.

## Project Structure

```
carbon-flow/
├── backend/                    # Django REST API
│   ├── carbon_backend/        # Django project settings
│   ├── emissions/             # Core emissions app
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/                   # React dashboard
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
│
├── sample_data/               # Realistic test datasets
│   ├── sap_fuel_sample.csv
│   ├── utility_electricity_sample.csv
│   └── travel_sample.csv
│
└── docs/                      # Technical documentation
    ├── MODEL.md              # Database schema design
    ├── DECISIONS.md          # Technical decision rationale
    ├── TRADEOFFS.md          # What was not built and why
    └── SOURCES.md            # Data source research findings
```

## Key Features

**Data Ingestion**
- Multi-source CSV upload (SAP fuel, utility electricity, corporate travel)
- Automatic unit normalization (GAL→L, SCF→M3, miles→km)
- Intelligent validation (overlapping dates, missing values, suspicious outliers)

**Emissions Calculation**
- EPA 2024 emission factors for Scope 1 (stationary/mobile combustion)
- EPA eGRID 2023 factors for Scope 2 (purchased electricity)
- DEFRA 2023 factors for Scope 3 Category 6 (business travel, including radiative forcing)

**Audit Trail**
- Immutable ingestion logs preserving raw uploaded data
- Complete change history tracking (who, what, when)
- Multi-state review workflow (pending → approved → locked)

**Analyst Dashboard**
- Real-time Scope 1/2/3 emissions summary
- Interactive data table with inline editing
- Status-based filtering and bulk actions
- Audit history timeline per emission record

## Documentation

- **[MODEL.md](docs/MODEL.md)** - Database schema with multi-tenancy, audit trails, and normalization patterns
- **[DECISIONS.md](docs/DECISIONS.md)** - Why CSV over API, metric normalization, PostgreSQL choices
- **[TRADEOFFS.md](docs/TRADEOFFS.md)** - Scope management: real-time syncing, complex factor libraries, SSO auth
- **[SOURCES.md](docs/SOURCES.md)** - Research on SAP MM formats, Green Button standard, Concur API structure

## Technology Stack

**Backend**
- Django 4.2 + Django REST Framework 3.14
- PostgreSQL 14 (production) / SQLite (development)
- Pandas for CSV parsing and unit conversion

**Frontend**
- React 18 with functional components and hooks
- Axios for API communication
- CSS3 for responsive styling

**Deployment**
- Railway (single-container deployment)
- Gunicorn + Whitenoise for static file serving
- GitHub Actions for CI/CD (future enhancement)

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (for production)

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API will be available at `http://localhost:8000/api/`

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

Dashboard will be available at `http://localhost:3000`

## Sample Data

Three realistic datasets are provided in `sample_data/`:

**SAP Fuel Data** (`sap_fuel_sample.csv`)
- 10 fuel purchase records
- Mixed units (GAL, SCF, L) demonstrating normalization
- Multiple plants (PL01, PL02, PL03)
- Scope 1 stationary/mobile combustion

**Utility Electricity** (`utility_electricity_sample.csv`)
- 8 billing periods across 4 meters
- Non-calendar-aligned billing cycles
- Commercial demand charges (kW)
- Scope 2 purchased electricity

**Corporate Travel** (`travel_sample.csv`)
- 11 travel segments across 6 trips
- Flights (Economy/Business class), hotels, car rentals
- Real airport distances (Haversine-calculated)
- Scope 3 Category 6 business travel

## Deployment

### Railway Deployment (Recommended)

```bash
railway login
railway init
railway up
```

Deployed app URL: `https://carbon-flow-production.up.railway.app`

## Testing

### Sample Data Ingestion Test

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "source_type=sap" \
  -F "file=@sample_data/sap_fuel_sample.csv"
```

### API Health Check

```bash
curl http://localhost:8000/api/health/
```

## License

Proprietary - BreatheESG Technical Assessment

## Author

Adesh Kishor Deshmukh  
Email: adesh@example.com  
GitHub: @adeshdeshmukh

## Acknowledgments

- EPA Greenhouse Gas Emission Factors (2024 update)
- DEFRA UK GHG Reporting Conversion Factors (2023)
- GHG Protocol Corporate Accounting and Reporting Standard
- Green Button Alliance (NAESB REQ.21 standard)
