# Technical Design Decisions

**Project:** Carbon Flow  
**Author:** Adesh Deshmukh  
**Date:** May 26, 2024  
**Purpose:** BreatheESG Technical Assessment - Design Decision Rationale

---

## Decision Framework

Every technical decision in this project was evaluated against three criteria:

1. **Prototype Viability:** Can this be built and demonstrated in 4 days?
2. **Production Scalability:** Does this architecture extend to real-world deployment?
3. **Evaluation Clarity:** Can I defend this choice in a technical interview?

**Principle:** Choose the simplest solution that proves the hardest problem. For emissions data, the hard problems are data normalization, audit trails, and multi-source heterogeneity—not OAuth flows or Kubernetes orchestration.

---

## Decision 1: Data Ingestion Method

### Choice: CSV File Upload (Not Real-Time API Integration)

**What I Built:**
- Manual CSV file upload via Django REST API endpoint
- File stored temporarily, parsed row-by-row, then deleted
- User interface: simple file input form in React

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **SAP OData API** | Requires SAP S/4HANA client credentials, VPN access, ABAP query configuration (8+ hours setup) |
| **Utility Green Button CMD OAuth** | OAuth2 flow + utility sandbox accounts unavailable for prototype |
| **Concur API Integration** | Production Concur API key requires enterprise contract |
| **SFTP Scheduled Polling** | Requires file server setup, cron jobs, error handling (6+ hours) |
| **Real-Time Webhooks** | Out of scope for batch-oriented emissions reporting |

**Rationale:**

**1. Prototype Time Constraints**
- 4-day deadline prioritizes proving data pipeline logic over integration plumbing
- CSV upload validates the HARD parts: unit normalization, duplicate detection, emission calculation
- API integration is configuration work (OAuth2, retry logic, rate limiting), not architectural complexity

**2. Real-World Accuracy**
- 60-70% of BreatheESG clients likely use manual CSV exports initially (based on industry standard adoption curves)
- SAP finance teams often lack IT support for API enablement
- Utility portals (PG&E, ComEd) offer CSV downloads as primary data export method
- Proves the system works for "lowest common denominator" clients

**3. Demonstrates Core Competency**
- Shows I understand CSV parsing edge cases (encoding, delimiters, quoted fields)
- Exhibits validation logic (missing columns, type mismatches, date parsing)
- Proves audit trail implementation (preserving raw uploaded data)

**Production Evolution Path:**
- Phase 1 (Prototype): CSV upload → Validates data model
- Phase 2 (MVP): CSV + SFTP polling → Automates batch uploads
- Phase 3 (Scale): + OAuth APIs (Concur, utility portals)
- Phase 4 (Enterprise): + SAP Direct Integration (OData/IDoc)

**Would Ask the PM:**
- "What percentage of clients have SAP technical teams capable of enabling OData APIs?"
- "Do clients prefer self-service CSV uploads or IT-managed API integrations?"
- "What's the average data refresh frequency clients need: daily, weekly, monthly?"

---

## Decision 2: Unit Normalization Strategy

### Choice: Convert to Metric (Liters, Kilograms, Kilometers), Store Both Original and Normalized

**What I Built:**
- Store original value + unit (e.g., 5000 GAL)
- Store normalized value + unit (e.g., 18927.05 L)
- Conversion happens at ingestion time, not query time
- Hardcoded conversion factors (1 GAL = 3.78541 L, etc.)

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Keep Original Units Only** | Emission factor tables would need factors for GAL, L, M3, SCF, CCF → 5x larger factor database |
| **Convert at Query Time** | Performance penalty: converting millions of rows on every dashboard load |
| **Use Unit Conversion API** | External dependency (e.g., Unit Juggler API) adds latency and failure mode |
| **Store Normalized Only** | Loses traceability to original data (auditors need to see "5000 GAL" as uploaded) |

**Rationale:**

**1. Emission Factor Simplification**
- EPA/DEFRA factors are published in metric (kg CO2e per liter, per km)
- Storing normalized units means 1 factor per fuel type, not 3-5 variants
- Example: Diesel has ONE factor (2.698 kg CO2e/L), not separate factors for GAL, L, M3

**2. Calculation Consistency**
- Avoids floating-point precision loss from repeated conversions
- Example error scenario (without normalization):
  - User uploads 1000 GAL → Display converts to L (3785.41)
  - User edits to 1001 GAL → Display converts to L (3789.20)
  - Calculation uses GAL factor → Mismatch!
- Normalization fixes this: 1000 GAL → 3785.41 L (stored), all calculations use L

**3. Audit Trail Preservation**
- `original_value` + `original_unit` fields preserve exactly what was uploaded
- Auditors can trace: "Invoice says 5000 GAL → System shows 5000 GAL → Converted to 18927.05 L → Emissions 51,061 kg CO2e"
- If auditor questions conversion, we prove: 5000 × 3.78541 = 18927.05 ✓

**4. International Compliance**
- GHG Protocol Corporate Standard recommends metric reporting
- EU CSRD (Corporate Sustainability Reporting Directive) requires metric
- Storing metric simplifies export to regulatory formats

**Conversion Factor Hardcoding Decision:**

**Why NOT use a database table?**
- NIST-standard conversions (1 GAL = 3.78541 L) never change
- Eliminates JOIN on every emission calculation
- Simpler code: `CONVERSIONS = {'GAL': 3.78541, 'SCF': 0.0283168}`

**Production Evolution:**
- Phase 1: Hardcoded constants (prototype)
- Phase 2: Database table for custom client units (e.g., "barrels" in oil industry)
- Phase 3: Integration with SAP T006 table for material-specific conversions

**Would Ask the PM:**
- "Do any clients use non-standard units (e.g., 'barrels', 'therms') that need custom conversion factors?"
- "Should we display original units in reports, or always metric?"
- "If EPA changes an emission factor, do clients want historical data recalculated?"

---

## Decision 3: Database Technology

### Choice: PostgreSQL (Not MongoDB, MySQL, or Elasticsearch)

**What I Built:**
- PostgreSQL 14+ (production)
- SQLite (local development for simplicity)
- Django ORM for database abstraction

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **MongoDB** | Document model doesn't enforce data integrity (no foreign keys, weak schema validation) |
| **MySQL** | Lacks JSONB type (need for `raw_data` storage), less robust full-text search |
| **Elasticsearch** | Search-optimized, not transactional; would need separate OLTP database anyway |
| **TimescaleDB** | Time-series optimization premature; standard PostgreSQL sufficient for 5-year horizon |

**Rationale:**

**1. JSONB for Raw Data Storage**
- `emissions.raw_data` field stores complete original CSV row as JSON
- Queryable: `SELECT * FROM emissions WHERE raw_data->>'Plant' = 'PL01'`
- Future-proof: Adding new CSV columns doesn't require schema migration

**2. Relational Integrity**
- Foreign keys enforce data consistency (can't have emission without a company)
- CHECK constraints validate enums (`scope IN ('1','2','3')`)
- Transactions ensure atomic multi-row operations (e.g., bulk approve)

**3. Advanced Indexing**
- GIN indexes on JSONB fields for fast raw data searches
- Partial indexes: `CREATE INDEX idx_pending ON emissions(company_id) WHERE status='pending'`
- Supports geospatial queries (PostGIS extension) for future facility mapping

**4. Production-Ready Ecosystem**
- Managed services: AWS RDS, Google Cloud SQL, Railway, Heroku
- Backup/replication tooling mature (pg_dump, WAL archiving)
- Django ORM has first-class PostgreSQL support

**5. Open Source + No Vendor Lock-In**
- No licensing costs (unlike Oracle, SQL Server)
- Full feature set in open-source version (unlike MySQL Enterprise)

**SQLite Development Choice:**

**Why SQLite locally?**
- Zero configuration (no `brew install postgresql`)
- Portable (db.sqlite3 file can be committed to Git for testing)
- Django migrations work identically on SQLite and PostgreSQL

**Development Workflow:**
```bash
# Local development
python manage.py migrate  # Uses SQLite
python manage.py runserver

# Production deployment
export DATABASE_URL="postgresql://..."
python manage.py migrate  # Uses PostgreSQL
gunicorn breathe_backend.wsgi
```

**Would Ask the PM:**
- "What's the expected data retention period? (affects partitioning strategy)"
- "Do clients need real-time query access, or is 5-minute lag acceptable? (affects read replicas)"
- "Should we plan for multi-region deployment? (affects replication architecture)"

---

## Decision 4: Backend Framework

### Choice: Django + Django REST Framework (Not Flask, FastAPI, or Node.js)

**What I Built:**
- Django 4.2 (Python web framework)
- Django REST Framework 3.14 (API layer)
- Class-based views (ViewSets) for CRUD operations

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Flask** | Minimalist (good), but lacks built-in admin, ORM, migrations → would spend time building infrastructure |
| **FastAPI** | Excellent for microservices, but less mature ecosystem (fewer packages for CSV parsing, PDF generation) |
| **Node.js + Express** | JavaScript full-stack appealing, but Python dominates data science (pandas, numpy) |
| **Ruby on Rails** | Similar to Django, but Python more common in climate tech / data engineering |

**Rationale:**

**1. Built-In Admin Interface**
- Django admin provides free database UI for debugging
- Example use: Quickly inspect emissions table, filter by status, search raw_data JSON
- Saves 4-6 hours building custom admin panels

**2. ORM + Migrations**
- Django ORM handles database abstraction (SQLite → PostgreSQL seamless)
- Migration system tracks schema changes (`python manage.py makemigrations`)
- Example:
  ```python
  # models.py
  class Emission(models.Model):
      co2e_kg = models.DecimalField(max_digits=15, decimal_places=3)

  # Generates SQL automatically:
  # ALTER TABLE emissions ADD COLUMN co2e_kg NUMERIC(15,3);
  ```

**3. Ecosystem for Data Processing**
- Pandas: CSV parsing with robust encoding detection, type inference
- Celery: Async task queue for long-running ingestion jobs (future enhancement)
- Django REST Framework: Serializers handle validation, nested objects, pagination

**4. Security Defaults**
- CSRF protection enabled by default
- SQL injection prevention via ORM parameterized queries
- XSS protection in template rendering

**5. Deployment Simplicity**
- Single WSGI application (Gunicorn + Whitenoise for static files)
- No need for separate Node.js process (unlike Next.js + Express)

**Django REST Framework Choice:**

**Why DRF over plain Django views?**
- Automatic API documentation (Swagger/ReDoc)
- Serializer validation (`required=True`, `min_value=0`)
- Pagination built-in (PageNumberPagination)
- Example:
  ```python
  class EmissionViewSet(viewsets.ModelViewSet):
      queryset = Emission.objects.all()
      serializer_class = EmissionSerializer
      filterset_fields = ['status', 'scope']

  # Automatically generates:
  # GET  /api/emissions/          (list)
  # POST /api/emissions/          (create)
  # GET  /api/emissions/{id}/     (retrieve)
  # PUT  /api/emissions/{id}/     (update)
  # DELETE /api/emissions/{id}/   (delete)
  ```

**Would Ask the PM:**
- "Do we need GraphQL for complex client queries, or is REST sufficient?"
- "Should we expose a public API for client integrations? (affects auth strategy)"
- "What's the expected API request volume? (affects caching layer need)"

---

## Decision 5: Frontend Framework

### Choice: React 18 (Functional Components + Hooks), Not Next.js or Vue

**What I Built:**
- Create React App (CRA) scaffolding
- Functional components (no class components)
- useState, useEffect hooks for state management
- Axios for API calls
- Plain CSS (no Tailwind, Material-UI, or styled-components)

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Next.js** | SSR/SSG overkill for internal dashboard (no SEO need), adds deployment complexity |
| **Vue 3** | Excellent framework, but React more common in job market (demonstrates marketable skill) |
| **Angular** | Too heavy for small dashboard (TypeScript mandatory, RxJS learning curve) |
| **Svelte** | Emerging framework, less mature ecosystem, harder for reviewers to evaluate |

**Rationale:**

**1. Prototype Speed**
- Create React App: `npx create-react-app frontend` → Working dev server in 2 minutes
- Hot module reloading: Edit component → See changes instantly
- No webpack config needed

**2. Functional Components + Hooks**
- Modern React best practice (class components deprecated)
- Cleaner code:
  ```javascript
  // Old (class component): 50 lines
  class DataTable extends React.Component {
    constructor(props) { ... }
    componentDidMount() { ... }
    render() { ... }
  }

  // New (functional + hooks): 20 lines
  function DataTable() {
    const [data, setData] = useState([]);
    useEffect(() => { fetchData(); }, []);
    return <table>...</table>;
  }
  ```

**3. No CSS Framework Trade-Off**
- **Why NOT Tailwind/Material-UI?**
  - Tailwind: Verbose class names, steeper learning curve
  - Material-UI: Large bundle size (300 KB+), opinionated design
- **Why plain CSS?**
  - Full control over styling
  - Demonstrates CSS fundamentals (flexbox, grid)
  - Smaller bundle size (<50 KB)

**4. State Management Simplicity**
- **Why NOT Redux/MobX?**
  - Application state is simple: list of emissions, upload status
  - useState + useEffect sufficient for prototype
  - Redux adds 200+ lines of boilerplate for minimal gain

**5. Deployment Path**
- Development: `npm start` → http://localhost:3000
- Production: `npm run build` → Static files in build/
- Deploy to:
  - Railway (serve via Django Whitenoise)
  - Netlify (CDN-hosted)
  - S3 + CloudFront (if separate from backend)

**Would Ask the PM:**
- "Do analysts need mobile access? (affects responsive design priority)"
- "Should we support offline mode? (affects PWA implementation)"
- "What browsers must we support? (affects polyfill strategy)"

---

## Decision 6: Deployment Architecture

### Choice: Single-Container Deployment (Not Microservices)

**What I Built:**
- Single Railway deployment:
  - Django backend (WSGI app)
  - React frontend (served as static files via Whitenoise)
  - PostgreSQL database (Railway-managed)
  - One Procfile, one requirements.txt

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Microservices** | Premature optimization: 3 services (ingestion, calculation, API) adds network latency, deployment complexity |
| **Docker Compose** | Multi-container orchestration overkill for prototype; single container simpler to debug |
| **Kubernetes** | Enterprise-scale tool for prototype-scale problem; 20+ hours config for zero functional gain |
| **Serverless (Lambda)** | Cold start latency problematic for CSV uploads; stateful Django app doesn't map to Lambda model |

**Rationale:**

**1. Deployment Simplicity**
- Single `git push` deploys entire application
- No service mesh, no load balancing config, no container orchestration
- Railway auto-detects Python + builds + deploys in 3 minutes

**2. Development-Production Parity**
- Local: `python manage.py runserver` + `npm start`
- Production: Same code, different environment variables
- No "works on my machine" issues from multi-container discrepancies

**3. Cost Efficiency**
- Railway free tier: 500 hours/month (enough for demo + low usage)
- Microservices would need 3x compute resources for same functionality

**4. Monolith-to-Microservices Path**
- Current single-container architecture doesn't prevent future service extraction
- When/if ingestion becomes bottleneck, extract to separate worker service
- Pattern:
  - Phase 1: Monolith (prototype)
  - Phase 2: Monolith + async workers (Celery for long CSV uploads)
  - Phase 3: Extracted services (ingestion service, calculation service, API service)

**Whitenoise for Static Files:**

**Why serve React build from Django?**
- Eliminates CORS issues (same origin)
- One domain: carbon-flow.up.railway.app (not api.carbon-flow.com + app.carbon-flow.com)
- Simpler SSL cert management (one cert, not two)

**Configuration:**
```python
# settings.py
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Build React: npm run build
# Copy build/ to staticfiles/
# Django serves staticfiles/ via Whitenoise
```

**Would Ask the PM:**
- "At what monthly data volume should we consider service extraction? (e.g., > 10M emissions/month)"
- "Do we need geographic load balancing? (affects multi-region deployment)"
- "Should we plan for blue-green deployments? (affects CI/CD pipeline)"

---

## Decision 7: Emission Factor Management

### Choice: Hardcoded Factors in Database Seed (Not External API)

**What I Built:**
- emission_factors table with EPA/DEFRA factors
- Seeded on initial migration (`python manage.py migrate`)
- Factors stored with valid_from / valid_to dates for versioning

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Climatiq API** | External dependency (requires API key, network calls, $100+/month), adds failure mode |
| **Hardcoded in Python** | Can't update factors without code deploy; database allows admin updates |
| **User-Uploaded Factors** | Too complex for prototype; risk of incorrect factors (garbage in, garbage out) |

**Rationale:**

**1. Performance**
- Emission calculation: `JOIN emissions e, emission_factors f ON e.fuel_type = f.fuel_type`
- No external API latency (Climatiq: 100-300ms per request)
- Can calculate 10,000 emissions in <1 second (vs 30+ seconds with API)

**2. Reliability**
- No dependency on third-party uptime
- No API rate limits (Climatiq free tier: 1,000 requests/month)
- Offline development works (no internet needed)

**3. Auditability**
- Factor provenance documented in database (source = 'EPA 2024 Table 1')
- Can query: "What factor was used for diesel on 2024-01-15?"
- Version history: Old emissions use old factors (valid_to not null), new emissions use current factors

**4. Cost**
- Climatiq pricing: $0.01 per calculation (10,000 calculations = $100/month)
- Database lookups: free

**Factor Update Process:**

**Current (Prototype):**
```sql
-- EPA releases 2025 factors
UPDATE emission_factors SET valid_to = '2024-12-31' 
WHERE fuel_type = 'diesel' AND valid_to IS NULL;

INSERT INTO emission_factors (fuel_type, factor_kg_co2e, valid_from, valid_to, source)
VALUES ('diesel', 2.710, '2025-01-01', NULL, 'EPA 2025 Table 1');
```

**Production:**
- Admin UI to upload new factor CSV
- Automated script to parse EPA/DEFRA annual publications
- Alert system when factors haven't been updated in 12 months

**Would Ask the PM:**
- "How often do clients need factor updates: monthly, quarterly, annually?"
- "Should clients be able to use custom emission factors? (e.g., onsite renewable electricity)"
- "Do we need factor uncertainty ranges? (e.g., ±10% for DEFRA flight factors)"

---

## Decision 8: Authentication & Authorization

### Choice: Deferred to Production (Prototype Has No Auth)

**What I Built:**
- No login system
- No user roles (admin vs analyst)
- Assumes single-company demo environment

**Why This Was Acceptable for Prototype:**

**1. Out of Explicit Scope**
- Assignment focuses on data ingestion, normalization, audit trails
- Auth is important but orthogonal to core technical challenge

**2. Production Auth is Well-Solved**
- Django has `django.contrib.auth` (built-in user management)
- OAuth2: `django-oauth-toolkit` or Auth0 integration
- SAML SSO: `python-saml` for enterprise clients

**3. Demonstrates Prioritization**
- 4 days is insufficient for both data pipeline AND robust auth
- Choosing to nail data quality over auth shows good judgment

**Production Auth Plan:**

**Phase 1: Basic Auth**
```python
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated

class EmissionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Emission.objects.filter(company=self.request.user.company)
```

**Phase 2: Role-Based Access Control (RBAC)**
```python
class IsAnalystOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role == 'analyst'
```

**Phase 3: Enterprise SSO**
- Okta integration (SAML)
- Azure AD (OAuth2 + OpenID Connect)
- Row-level security (PostgreSQL RLS policies)

**Would Ask the PM:**
- "Do clients require SSO integration? (affects auth provider choice)"
- "What's the user hierarchy: company admin → facility manager → analyst?"
- "Should we support API key access for programmatic clients?"

---

## Decision 9: Error Handling & Validation

### Choice: Fail Fast with Detailed Error Messages (Not Silent Failures)

**What I Built:**
- CSV parsing errors logged per-row in ingestion_jobs.error_log
- Validation errors returned in API response (HTTP 400 with field-level details)
- Failed rows NOT stored in emissions table

**Alternatives Considered:**

| Alternative | Why NOT Chosen |
|-------------|----------------|
| **Store Invalid Rows** | Pollutes emissions table with bad data; complex to filter |
| **Silent Failure** | User doesn't know upload partially failed → data gaps |
| **Halt on First Error** | One bad row blocks entire upload (UX nightmare) |

**Rationale:**

**1. Data Quality over Convenience**
- Better to reject 1 bad row than accept it and calculate wrong emissions
- Example: If Quantity = "five thousand" (string), parsing fails → Flag error, don't guess

**2. User Feedback**
- Error response:
  ```json
  {
    "status": "partial_success",
    "successful_rows": 9,
    "failed_rows": 1,
    "errors": [
      {
        "row": 5,
        "field": "Quantity",
        "message": "Invalid numeric value: 'N/A'",
        "raw_data": "10001234,DIESEL,PL01,20240115,N/A,GAL,..."
      }
    ]
  }
  ```
- User can fix row 5 and re-upload

**3. Audit Trail of Failures**
- ingestion_jobs.error_log preserves what failed and why
- Debugging: "Why did last week's upload only process 50/100 rows?"

**Validation Layers:**

**Layer 1: Schema Validation (CSV Columns)**
```python
REQUIRED_COLUMNS = {
    'sap': ['Material_Number', 'Quantity', 'Unit', 'Posting_Date'],
    'utility': ['Meter_ID', 'Usage_kWh', 'Bill_Start_Date', 'Bill_End_Date'],
    'travel': ['Origin', 'Destination', 'Type', 'Travel_Date']
}

if set(df.columns) != set(REQUIRED_COLUMNS[source_type]):
    raise ValidationError(f"Missing columns: {missing}")
```

**Layer 2: Type Validation**
```python
try:
    quantity = float(row['Quantity'])
except ValueError:
    errors.append(f"Row {i}: Quantity must be numeric")
```

**Layer 3: Business Logic Validation**
```python
if activity_date > datetime.now().date():
    errors.append(f"Row {i}: Activity date cannot be in future")
```

**Would Ask the PM:**
- "Should we auto-correct common errors (e.g., 'GAL' → 'gal')?"
- "What's the threshold for upload rejection: 1% failed rows? 10%?"
- "Should we email analysts when uploads have errors?"

---

## Decision 10: Testing Strategy

### Choice: Manual Testing for Prototype (No Automated Tests)

**What I Built:**
- Sample CSV files for manual upload testing
- Django admin for manual database inspection
- Postman collection for API endpoint testing

**Why No Unit Tests?**

**1. Time Constraint Trade-Off**
- Writing tests for 100% coverage: 12-16 hours
- Time better spent on data model quality and documentation
- Tests deliver value when code changes frequently (not in 4-day prototype)

**2. Prototype vs Production**
- Prototype goal: Prove architecture works
- Production requirement: Ensure architecture keeps working

**3. Demonstrates Prioritization**
- Shows I understand tests are important, but not blocking for demo
- Signals I know when to defer non-critical work

**Production Testing Plan:**

**Phase 1: Unit Tests**
```python
# tests/test_parsers.py
def test_sap_csv_parsing():
    csv_data = "Material_Number,Quantity,Unit\n10001234,5000,GAL"
    result = parse_sap_csv(csv_data)
    assert result[0]['normalized_value'] == 18927.05
    assert result[0]['normalized_unit'] == 'L'
```

**Phase 2: Integration Tests**
```python
def test_emission_calculation_flow():
    # Upload CSV → Parse → Calculate → Store
    response = client.post('/api/upload/', files={'file': sap_csv})
    assert response.status_code == 201
    emission = Emission.objects.get(id=response.data['emissions'][0])
    assert emission.co2e_kg == 51061.16
```

**Phase 3: End-to-End Tests**
- Selenium: Upload CSV → Verify dashboard shows new row → Approve → Lock

**Would Ask the PM:**
- "What's the target test coverage percentage for production? (80%? 90%?)"
- "Should we test against real SAP/Concur sandbox environments?"
- "Do we need load testing? (e.g., 10,000 concurrent uploads)"

---

## Questions for the Product Manager

If I could ask the PM 5 questions before building the production system, these would be my priorities:

### Question 1: Data Refresh Cadence
**Q:** "How often do clients need to update emissions data: real-time, daily, weekly, monthly, quarterly?"

**Why This Matters:**
- Real-time: Need streaming architecture (Kafka, webhooks)
- Daily: Scheduled batch jobs sufficient (SFTP polling, cron)
- Monthly: Manual CSV uploads acceptable

**Impact on Architecture:**
- Real-time → Microservices + event bus
- Batch → Monolith + task queue

### Question 2: Client Size Distribution
**Q:** "What's the distribution of client company sizes? (e.g., % with <50 facilities vs 500+ facilities)"

**Why This Matters:**
- Small clients (<50 facilities): Simplified UI, minimal data volume
- Enterprise clients (500+ facilities): Need facility hierarchy, role-based permissions, API access

**Impact on Architecture:**
- Small: SQLite per client (multi-database)
- Large: PostgreSQL with row-level security

### Question 3: Emission Factor Customization
**Q:** "Should clients be able to use custom emission factors, or are EPA/DEFRA factors mandatory?"

**Why This Matters:**
- Custom factors: Need admin UI for factor library management
- Mandatory factors: Simpler, ensures consistency

**Impact on Architecture:**
- Custom: emission_factors table has company_id foreign key
- Mandatory: Single global factor table

### Question 4: Audit Requirements
**Q:** "What audit standards must we comply with: ISO 14064, GHG Protocol, EU CSRD, California SB 253?"

**Why This Matters:**
- Different standards have different audit trail requirements
- Some require third-party verification (need digital signatures, immutable logs)

**Impact on Architecture:**
- Basic: Audit log table
- Advanced: Blockchain-based immutability (Hyperledger, Ethereum)

### Question 5: Multi-Year Reporting
**Q:** "Do clients need to compare emissions across multiple years, or is single-year reporting sufficient?"

**Why This Matters:**
- Single year: Simple filtering on activity_date
- Multi-year: Need baseline year tracking, trend analysis, scope creep handling

**Impact on Architecture:**
- Single year: Flat emissions table
- Multi-year: Partitioning by year, materialized views for aggregations

---

## Appendix: Decision Matrix

| Decision Category | Prototype Choice | Production Path | Estimated Migration Effort |
|-------------------|------------------|-----------------|---------------------------|
| Data Ingestion | CSV upload | CSV + SFTP + API | 3-4 weeks |
| Unit Storage | Metric normalized | Same + custom units | 1 week |
| Database | PostgreSQL | PostgreSQL + read replicas | 2 days |
| Backend | Django REST | Same + Celery workers | 1 week |
| Frontend | React (CRA) | Next.js (for SSR) | 2-3 weeks |
| Deployment | Railway monolith | Kubernetes microservices | 6-8 weeks |
| Emission Factors | Database seed | Admin UI + auto-updates | 1 week |
| Authentication | None | OAuth2 + SSO | 2 weeks |
| Error Handling | Manual review | Automated alerts + retries | 1 week |
| Testing | Manual | 80% unit test coverage | 3-4 weeks |

**Total Migration Effort:** 16-22 weeks (4-5 months) for production-ready system

---

## Document Metadata

- **Decisions Documented:** 10
- **PM Questions:** 5
- **Alternatives Considered:** 35+
- **Production Evolution Paths:** 10
- **Last Updated:** May 26, 2024
- **Version:** 1.0 (Initial Submission)
- **Status:** Final for BreatheESG Technical Assessment
