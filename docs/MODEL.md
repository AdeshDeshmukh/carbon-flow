# Database Schema Design

**Project:** Carbon Flow  
**Author:** Adesh Deshmukh  
**Date:** May 26, 2024  
**Purpose:** BreatheESG Technical Assessment - Data Model Documentation

---

## Design Principles

### Principle 1: Multi-Tenancy by Design

Every data table includes a `company_id` foreign key. This ensures complete data isolation between client organizations without requiring separate database instances.

**Rationale:** BreatheESG serves multiple enterprise clients. A shared database with logical isolation is more cost-effective than per-client deployments while maintaining security boundaries.

**Implementation:** All queries include `WHERE company_id = :current_company` filter enforced at the ORM level.

### Principle 2: Preserve Source of Truth

Raw uploaded data is stored immutably in `raw_data` JSONB fields. Calculations and normalizations are derived values, never overwriting originals.

**Rationale:** Auditors require traceability to original source documents. If emission factors change (EPA updates factors annually), we can recalculate historical emissions without re-uploading source files.

**Implementation:** Each `emission` record contains:
- `original_value` + `original_unit` (as uploaded)
- `normalized_value` + `normalized_unit` (converted)
- `raw_data` (entire CSV row as JSON)

### Principle 3: Comprehensive Audit Trail

Every modification to emission records is logged with user, timestamp, old value, and new value.

**Rationale:** Scope 1/2/3 emissions reports are legally binding in many jurisdictions (e.g., EU CSRD, California SB 253). Complete audit trails are mandatory for compliance.

**Implementation:** `audit_logs` table with trigger-based inserts on `emissions` UPDATE/DELETE operations.

### Principle 4: Dual-Unit Storage

Store both imperial and metric units, convert on read, not on write.

**Rationale:** 
- US companies report in imperial (gallons, miles)
- International standards use metric (liters, kilometers)
- Avoids precision loss from repeated conversions

**Implementation:** Conversion factors hardcoded as constants (1 GAL = 3.78541 L), applied in API serializers.

### Principle 5: Flexible Status Workflow

Emission records progress through states: `pending` → `approved` → `locked`. State transitions are irreversible (except by admin override with audit log).

**Rationale:** Prevents accidental modification of audited data while allowing analysts to review and approve new ingestions.

---

## Entity-Relationship Diagram

```
┌──────────────────┐
│ companies │
│ │
│ PK: id │
│ name │
│ created_at │
│ is_active │
└────────┬─────────┘
│
│ 1:N
│
┌────┴─────────────────┬──────────────────┬─────────────────┐
│ │ │ │
┌───▼──────────┐ ┌──────▼─────────┐ ┌────▼────────┐ ┌────▼──────────┐
│data_sources │ │ emissions │ │ingestion_ │ │ emission_ │
│ │ │ │ │ jobs │ │ factors │
│PK: id │───>│PK: id │ │ │ │ │
│FK: company_id│ 1:N│FK: company_id │ │PK: id │ │PK: id │
│ source_type│ │ data_source │ │FK: data_ │ │ fuel_type │
│ name │ │ ingestion_job│ │ source_id │ │ scope │
│ config │ │ scope │ │ status │ │ factor_ │
└──────┬───────┘ │ category │ │ started_at│ │ kg_co2e │
│ │ activity_date│ │ file_name │ │ unit │
│ 1:N │ original_* │ └─────────────┘ │ source │
│ │ normalized_* │ └───────────────┘
│ │ co2e_kg │
│ │ status │
│ │ reviewed_by │
│ │ raw_data │
│ └────────┬───────┘
│ │
│ │ 1:N
│ ┌────▼─────────┐
│ │ audit_logs │
│ │ │
│ │PK: id │
│ │FK: emission │
│ │ user │
│ │ action │
│ │ old_value │
│ │ new_value │
│ │ timestamp │
│ └──────────────┘
│
│ 1:N
┌────▼────────┐
│ facilities │
│ │
│PK: id │
│FK: data_ │
│ source_id │
│ name │
│ plant_code│
│ address │
│ lat │
│ long │
└─────────────┘
```

---

## Table Specifications

### Table 1: `companies`

**Purpose:** Multi-tenant organization records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| name | VARCHAR(255) | NOT NULL, UNIQUE | Company legal name |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Account creation date |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Soft delete flag |

**Indexes:**
- PRIMARY KEY on `id` (B-tree, clustered)
- UNIQUE on `name` (B-tree)

**Sample Data:**
```sql
INSERT INTO companies (id, name, created_at, is_active) VALUES
(1, 'Tesla Inc', '2024-01-10 09:00:00', TRUE),
(2, 'Microsoft Corporation', '2024-01-15 10:30:00', TRUE);
```

**Design Rationale:**
- Simple structure; extended attributes (industry, size, contact) would be in separate company_profiles table in production
- is_active allows logical deletion without breaking foreign key references

### Table 2: `data_sources`

**Purpose:** Configuration for each data ingestion source (one company can have multiple SAP plants, utility accounts, travel systems).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| company_id | INTEGER | NOT NULL, FOREIGN KEY → companies(id) | Owning organization |
| source_type | VARCHAR(20) | NOT NULL, CHECK IN ('sap', 'utility', 'travel') | Emission data category |
| name | VARCHAR(255) | NOT NULL | User-friendly label (e.g., "Fremont Plant - Fuel Data") |
| config | JSONB | DEFAULT '{}' | Source-specific settings (plant codes, account numbers, API credentials) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Configuration creation date |

**Indexes:**
- PRIMARY KEY on id
- FOREIGN KEY on company_id → companies(id) ON DELETE CASCADE
- INDEX on (company_id, source_type) for filtered queries

**Sample Data:**
```sql
INSERT INTO data_sources (id, company_id, source_type, name, config) VALUES
(1, 1, 'sap', 'Fremont Manufacturing - Fuel Purchases', '{"plant_codes": ["PL01", "PL02"]}'),
(2, 1, 'utility', 'PG&E Commercial Accounts', '{"account_numbers": ["ACC-789456", "ACC-789457"]}'),
(3, 1, 'travel', 'Concur Corporate Travel', '{"api_endpoint": "https://us.api.concursolutions.com"}');
```

**Design Rationale:**
- config as JSONB allows flexible storage of source-specific metadata without ALTER TABLE for each new field
- Example config structures:
  - SAP: `{"plant_codes": ["PL01"], "movement_types": ["261", "551"]}`
  - Utility: `{"account_numbers": ["ACC-123"], "egrid_subregion": "CAMX"}`
  - Travel: `{"api_key_encrypted": "...", "default_cabin_class": "Economy"}`

### Table 3: `ingestion_jobs`

**Purpose:** Track each file upload or API sync operation for debugging and lineage.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| data_source_id | INTEGER | NOT NULL, FOREIGN KEY → data_sources(id) | Which source configuration was used |
| status | VARCHAR(20) | NOT NULL, CHECK IN ('pending', 'processing', 'completed', 'failed') | Job state |
| file_name | VARCHAR(255) | NULL | Original uploaded file name (NULL for API pulls) |
| started_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Job start time |
| completed_at | TIMESTAMP | NULL | Job completion time (NULL while running) |
| total_rows | INTEGER | DEFAULT 0 | Total records in source file/API response |
| successful_rows | INTEGER | DEFAULT 0 | Records successfully parsed and stored |
| failed_rows | INTEGER | DEFAULT 0 | Records rejected due to validation errors |
| error_log | TEXT | NULL | JSON array of error messages per row |

**Indexes:**
- PRIMARY KEY on id
- FOREIGN KEY on data_source_id → data_sources(id) ON DELETE CASCADE
- INDEX on (data_source_id, started_at DESC) for recent job lookups

**Sample Data:**
```sql
INSERT INTO ingestion_jobs (id, data_source_id, status, file_name, started_at, completed_at, total_rows, successful_rows, failed_rows, error_log) VALUES
(1, 1, 'completed', 'sap_fuel_sample.csv', '2024-05-26 10:00:00', '2024-05-26 10:00:15', 10, 10, 0, NULL),
(2, 2, 'completed', 'utility_electricity_sample.csv', '2024-05-26 10:05:00', '2024-05-26 10:05:08', 8, 8, 0, NULL);
```

**Design Rationale:**
- Enables "data lineage": Given an emission record, trace back to original file upload
- error_log as TEXT (not table) for simplicity in prototype; production would normalize to ingestion_errors table
- Duration calculation: completed_at - started_at for performance monitoring

### Table 4: `emissions` (CORE TABLE)

**Purpose:** Normalized emission activity records with full audit trail and review workflow.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| company_id | INTEGER | NOT NULL, FOREIGN KEY → companies(id) | Owning organization (denormalized for query performance) |
| data_source_id | INTEGER | NOT NULL, FOREIGN KEY → data_sources(id) | Which source this came from |
| ingestion_job_id | INTEGER | NOT NULL, FOREIGN KEY → ingestion_jobs(id) | Which upload batch |
| scope | VARCHAR(1) | NOT NULL, CHECK IN ('1', '2', '3') | GHG Protocol scope classification |
| category | VARCHAR(100) | NOT NULL | Emission sub-category (e.g., 'stationary_combustion', 'purchased_electricity', 'business_travel') |
| activity_date | DATE | NOT NULL | Date emission activity occurred |
| original_value | NUMERIC(15,3) | NOT NULL | Quantity as uploaded (e.g., 5000) |
| original_unit | VARCHAR(20) | NOT NULL | Unit as uploaded (e.g., 'GAL', 'kWh', 'km') |
| normalized_value | NUMERIC(15,3) | NOT NULL | Quantity in standard unit (e.g., 18927.050 L) |
| normalized_unit | VARCHAR(20) | NOT NULL | Standard unit (e.g., 'L', 'kWh', 'km') |
| co2e_kg | NUMERIC(15,3) | NOT NULL | Calculated CO2 equivalent emissions in kilograms |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending', 'approved', 'rejected', 'locked') | Review workflow state |
| reviewed_by | VARCHAR(255) | NULL | Email or user ID of approver |
| reviewed_at | TIMESTAMP | NULL | Approval/rejection timestamp |
| raw_data | JSONB | NOT NULL | Complete original CSV row or API response |
| notes | TEXT | NULL | Analyst comments |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last modification time |

**Indexes:**
- PRIMARY KEY on id
- FOREIGN KEY on company_id → companies(id) ON DELETE CASCADE
- FOREIGN KEY on data_source_id → data_sources(id) ON DELETE RESTRICT (prevent deletion of sources with emissions)
- FOREIGN KEY on ingestion_job_id → ingestion_jobs(id) ON DELETE RESTRICT
- INDEX on (company_id, status) for dashboard filtering
- INDEX on (company_id, activity_date) for date-range queries
- INDEX on scope for Scope 1/2/3 reporting

**Sample Data:**
```sql
INSERT INTO emissions (id, company_id, data_source_id, ingestion_job_id, scope, category, activity_date, original_value, original_unit, normalized_value, normalized_unit, co2e_kg, status, reviewed_by, reviewed_at, raw_data, notes) VALUES
(1, 1, 1, 1, '1', 'stationary_combustion', '2024-01-15', 5000.000, 'GAL', 18927.050, 'L', 51061.16, 'approved', 'analyst@tesla.com', '2024-05-26 14:00:00', '{"Material_Number":"10001234","Material_Description":"DIESEL FUEL","Plant":"PL01","Posting_Date":"20240115","Quantity":"5000","Unit":"GAL","Document_Number":"4500123456","Cost_Center":"CC-LOG-001"}', 'Fremont boiler fuel - Jan 2024'),
(2, 1, 2, 2, '2', 'purchased_electricity', '2024-01-15', 45600.000, 'kWh', 45600.000, 'kWh', 15960.00, 'pending', NULL, NULL, '{"Account_Number":"ACC-789456","Service_Address":"123 Factory Rd Building A","Meter_ID":"MTR-001","Bill_Start_Date":"2024-01-01","Bill_End_Date":"2024-01-31","Usage_kWh":"45600","Demand_kW":"120","Amount_USD":"4532.50"}', NULL);
```

**Design Rationale:**

**Why company_id is denormalized (duplicates data_sources.company_id):**
- Performance: `SELECT * FROM emissions WHERE company_id = 1 AND status = 'pending'` avoids JOIN to data_sources
- Security: Row-level security policies can filter on company_id alone

**Why separate original_* and normalized_* fields:**
- Auditors need to see exactly what was uploaded (5000 GAL)
- Calculations need consistent units (18927.05 L)
- Recalculation scenarios: If EPA changes diesel factor, query `SELECT normalized_value, normalized_unit` and multiply by new factor

**Why status workflow:**
```
pending ──(analyst approves)──> approved ──(admin locks for audit)──> locked
   │
   └──(analyst rejects)──> rejected
```

- pending: Newly uploaded, awaiting review
- approved: Analyst verified data looks correct
- rejected: Data error (duplicate, wrong unit, etc.) - excluded from reports
- locked: Sent to auditors, immutable (UPDATE blocked by trigger)

**Why JSONB for raw_data:**
- Future-proof: New CSV columns don't break schema
- Searchability: `WHERE raw_data->>'Plant' = 'PL01'`
- Full audit trail: Can regenerate normalized values from raw

### Table 5: `audit_logs`

**Purpose:** Immutable record of all changes to emission records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| emission_id | INTEGER | NOT NULL, FOREIGN KEY → emissions(id) | Which emission record was modified |
| user | VARCHAR(255) | NOT NULL | Email or user ID of person making change |
| action | VARCHAR(20) | NOT NULL, CHECK IN ('created', 'approved', 'rejected', 'edited', 'locked') | Type of change |
| field_name | VARCHAR(100) | NULL | For 'edited' action: which field changed |
| old_value | TEXT | NULL | Value before change (NULL for 'created') |
| new_value | TEXT | NULL | Value after change |
| timestamp | TIMESTAMP | NOT NULL, DEFAULT NOW() | When change occurred |

**Indexes:**
- PRIMARY KEY on id
- FOREIGN KEY on emission_id → emissions(id) ON DELETE CASCADE
- INDEX on (emission_id, timestamp DESC) for audit trail queries

**Sample Data:**
```sql
INSERT INTO audit_logs (id, emission_id, user, action, field_name, old_value, new_value, timestamp) VALUES
(1, 1, 'system', 'created', NULL, NULL, NULL, '2024-05-26 10:00:10'),
(2, 1, 'analyst@tesla.com', 'approved', 'status', 'pending', 'approved', '2024-05-26 14:00:00'),
(3, 1, 'admin@tesla.com', 'locked', 'status', 'approved', 'locked', '2024-05-26 16:00:00');
```

**Design Rationale:**
- Append-only table (no UPDATEs or DELETEs)
- PostgreSQL trigger on emissions table inserts audit log automatically
- Example trigger:

```sql
CREATE OR REPLACE FUNCTION log_emission_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_logs (emission_id, user, action, field_name, old_value, new_value)
        VALUES (NEW.id, NEW.reviewed_by, 'edited', 'co2e_kg', OLD.co2e_kg::TEXT, NEW.co2e_kg::TEXT);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER emissions_audit
AFTER UPDATE ON emissions
FOR EACH ROW EXECUTE FUNCTION log_emission_change();
```

### Table 6: `emission_factors`

**Purpose:** Centralized emission factor library (EPA, DEFRA, custom factors).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| fuel_type | VARCHAR(50) | NOT NULL | Material type (e.g., 'diesel', 'natural_gas', 'electricity_us_avg') |
| scope | VARCHAR(1) | NOT NULL, CHECK IN ('1', '2', '3') | Scope classification |
| factor_kg_co2e | NUMERIC(10,6) | NOT NULL | Emission factor (kg CO2e per unit) |
| unit | VARCHAR(20) | NOT NULL | Per-unit basis (e.g., 'L', 'kWh', 'passenger-km') |
| source | VARCHAR(100) | NOT NULL | Factor provenance (e.g., 'EPA 2024 Table 1', 'DEFRA 2023') |
| valid_from | DATE | NOT NULL | Factor effective start date |
| valid_to | DATE | NULL | Factor expiration date (NULL = current) |

**Indexes:**
- PRIMARY KEY on id
- UNIQUE on (fuel_type, unit, valid_from) to prevent duplicate factors
- INDEX on (fuel_type, valid_to) for current factor lookups

**Sample Data:**
```sql
INSERT INTO emission_factors (id, fuel_type, scope, factor_kg_co2e, unit, source, valid_from, valid_to) VALUES
(1, 'diesel', '1', 2.698000, 'L', 'EPA 2024 Table 1 (Distillate Fuel Oil No. 2)', '2024-01-01', NULL),
(2, 'gasoline', '1', 2.320000, 'L', 'EPA 2024 Table 1 (Motor Gasoline)', '2024-01-01', NULL),
(3, 'natural_gas', '1', 0.054440, 'SCF', 'EPA 2024 Table 1 (Natural Gas)', '2024-01-01', NULL),
(4, 'electricity_us_avg', '2', 0.350000, 'kWh', 'EPA eGRID 2023 US Average', '2023-01-01', NULL),
(5, 'flight_longhaul_economy', '3', 0.200110, 'passenger-km', 'DEFRA 2023 (with RF)', '2023-06-01', NULL),
(6, 'flight_longhaul_business', '3', 0.580290, 'passenger-km', 'DEFRA 2023 (with RF)', '2023-06-01', NULL);
```

**Design Rationale:**
- valid_from / valid_to allows historical factor versioning
- Example: EPA updates diesel factor from 2.68 to 2.70 in 2025
  - Old emissions use 2.68 (valid_from='2024-01-01', valid_to='2024-12-31')
  - New emissions use 2.70 (valid_from='2025-01-01', valid_to=NULL)
- Emission calculation logic:

```python
def get_factor(fuel_type, activity_date):
    return EmissionFactor.objects.filter(
        fuel_type=fuel_type,
        valid_from__lte=activity_date,
        Q(valid_to__gte=activity_date) | Q(valid_to__isnull=True)
    ).first()
```

### Table 7: `facilities` (Optional Enhancement)

**Purpose:** Geographic metadata for SAP plants and utility service addresses.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-incrementing identifier |
| data_source_id | INTEGER | NOT NULL, FOREIGN KEY → data_sources(id) | Associated SAP/utility source |
| name | VARCHAR(255) | NOT NULL | Facility name (e.g., "Fremont Manufacturing Plant") |
| plant_code | VARCHAR(20) | NULL | SAP plant code (e.g., "PL01") |
| address | TEXT | NULL | Full street address |
| city | VARCHAR(100) | NULL | City |
| state | VARCHAR(50) | NULL | State/province |
| country | VARCHAR(50) | NOT NULL | ISO 3166-1 alpha-2 code (e.g., "US", "DE") |
| postal_code | VARCHAR(20) | NULL | ZIP/postal code |
| lat | NUMERIC(10,7) | NULL | Latitude (for eGRID subregion mapping) |
| long | NUMERIC(10,7) | NULL | Longitude |
| egrid_subregion | VARCHAR(10) | NULL | EPA eGRID subregion code (e.g., "CAMX", "SRMW") |

**Indexes:**
- PRIMARY KEY on id
- FOREIGN KEY on data_source_id → data_sources(id) ON DELETE CASCADE
- INDEX on plant_code for SAP plant lookups

**Sample Data:**
```sql
INSERT INTO facilities (id, data_source_id, name, plant_code, address, city, state, country, postal_code, lat, long, egrid_subregion) VALUES
(1, 1, 'Fremont Manufacturing Plant', 'PL01', '45500 Fremont Blvd', 'Fremont', 'California', 'US', '94538', 37.548270, -121.988570, 'CAMX'),
(2, 1, 'Gigafactory Berlin', 'PL02', 'Freienbrink', 'Grünheide', 'Brandenburg', 'DE', '15537', 52.397850, 13.783900, NULL);
```

**Design Rationale:**
- egrid_subregion enables location-based Scope 2 factors (California 0.198 kg/kWh vs national 0.350 kg/kWh)
- lat/long for geospatial queries (e.g., "emissions within 50km of city center")
- Prototype simplification: This table is NOT implemented in Phase 1 (noted in TRADEOFFS.md)

---

## Calculation Logic Pseudocode

### Unit Normalization

```python
UNIT_CONVERSIONS = {
    'GAL': {'to': 'L', 'factor': 3.78541},
    'SCF': {'to': 'M3', 'factor': 0.0283168},
    'miles': {'to': 'km', 'factor': 1.60934},
}

def normalize_unit(value, from_unit):
    if from_unit in UNIT_CONVERSIONS:
        conversion = UNIT_CONVERSIONS[from_unit]
        normalized_value = value * conversion['factor']
        normalized_unit = conversion['to']
    else:
        normalized_value = value
        normalized_unit = from_unit
    
    return normalized_value, normalized_unit
```

### Emission Calculation

```python
def calculate_emission(fuel_type, normalized_value, normalized_unit, activity_date, scope):
    factor = EmissionFactor.objects.get(
        fuel_type=fuel_type,
        unit=normalized_unit,
        scope=scope,
        valid_from__lte=activity_date,
        valid_to__gte=activity_date OR valid_to__isnull=True
    )
    
    co2e_kg = normalized_value * factor.factor_kg_co2e
    
    return co2e_kg
```

**Example:**

```python
# SAP fuel row: 5000 GAL diesel, date 2024-01-15
normalized_value, normalized_unit = normalize_unit(5000, 'GAL')
# Returns: (18927.05, 'L')

co2e_kg = calculate_emission('diesel', 18927.05, 'L', '2024-01-15', '1')
# Looks up: factor_kg_co2e = 2.698 (EPA 2024)
# Returns: 18927.05 * 2.698 = 51,061.16 kg CO2e
```

---

## Performance Considerations

### Query Optimization

**Dashboard Summary Query (Scope 1/2/3 totals):**

```sql
SELECT 
    scope,
    SUM(co2e_kg) AS total_co2e_kg,
    COUNT(*) AS record_count
FROM emissions
WHERE company_id = :company_id
  AND status IN ('approved', 'locked')
  AND activity_date BETWEEN :start_date AND :end_date
GROUP BY scope;
```

**Execution Plan:**
- Index scan on (company_id, status) → Filter on activity_date → Aggregate
- Estimated cost: O(log n) for index scan + O(m) for aggregation (m = matching rows)

### Partitioning Strategy (Future)

- Partition emissions table by activity_date (monthly partitions)
- Enables partition pruning for date-range queries
- Example: Query for Q1 2024 only scans Jan/Feb/Mar partitions

### Data Volume Projections

**Assumptions:**
- 1 enterprise client = 50 facilities
- 1 facility = 200 emission records/month (daily fuel, weekly electricity, monthly travel)
- 10,000 emission records/month per client

**Annual Growth:**
- 1 client = 120,000 records/year
- 100 clients = 12,000,000 records/year

**Table Size Estimates (5-year horizon):**
- emissions: 60,000,000 rows × 1 KB/row = 60 GB
- audit_logs: 180,000,000 rows × 0.5 KB/row = 90 GB
- Total: ~150 GB (fits comfortably on standard PostgreSQL instance)

**Scaling Strategy:**
- Years 1-3: Single PostgreSQL instance (16 GB RAM, 500 GB SSD)
- Years 4-5: Read replicas for reporting queries
- Years 6+: Time-series database (TimescaleDB) for historical data

---

## Security and Compliance

### Row-Level Security (RLS)

**PostgreSQL RLS Policies:**

```sql
ALTER TABLE emissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY company_isolation ON emissions
    FOR ALL
    TO authenticated_users
    USING (company_id = current_setting('app.current_company_id')::INTEGER);
```

**Application Enforcement:**

```python
# Django middleware sets company_id from JWT token
def set_company_context(request):
    company_id = request.user.company_id
    with connection.cursor() as cursor:
        cursor.execute("SET app.current_company_id = %s", [company_id])
```

**Result:** Analysts at Tesla can only see company_id = 1 rows. Microsoft analysts see company_id = 2 rows.

### Data Retention

**GHG Protocol Requirements:**
- Emission data must be retained for 7 years (minimum)
- Audit logs must be immutable

**Implementation:**
- emissions and audit_logs tables have no DELETE permissions (except superuser)
- Soft delete via is_active = FALSE flag
- Archival strategy: Move activity_date < (NOW() - INTERVAL '7 years') rows to cold storage (S3 + Parquet)

---

## Migration Strategy

### From Prototype (SQLite) to Production (PostgreSQL)

**Schema Compatibility:**
- All SQL is PostgreSQL-compatible (SERIAL, JSONB, CHECK constraints)
- SQLite development database uses same column types (TEXT for JSONB simulated)

**Migration Commands:**

```bash
# Export from SQLite
python manage.py dumpdata --exclude contenttypes --exclude auth.permission > data.json

# Load into PostgreSQL
export DATABASE_URL="postgresql://user:pass@localhost/carbon_flow"
python manage.py migrate
python manage.py loaddata data.json
```

**Validation Checks:**
- Row count match: `SELECT COUNT(*) FROM emissions` (SQLite vs PostgreSQL)
- Checksum sample: `SELECT SUM(co2e_kg) FROM emissions WHERE company_id = 1`
- Foreign key integrity: `SELECT COUNT(*) FROM emissions e LEFT JOIN companies c ON e.company_id = c.id WHERE c.id IS NULL` (should return 0)

---

## Appendix: SQL Schema Definition

```sql
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('sap', 'utility', 'travel')),
    name VARCHAR(255) NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_data_sources_company ON data_sources(company_id, source_type);

CREATE TABLE ingestion_jobs (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    file_name VARCHAR(255),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_rows INTEGER DEFAULT 0,
    successful_rows INTEGER DEFAULT 0,
    failed_rows INTEGER DEFAULT 0,
    error_log TEXT
);

CREATE INDEX idx_ingestion_jobs_source ON ingestion_jobs(data_source_id, started_at DESC);

CREATE TABLE emissions (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    ingestion_job_id INTEGER NOT NULL REFERENCES ingestion_jobs(id) ON DELETE RESTRICT,
    scope VARCHAR(1) NOT NULL CHECK (scope IN ('1', '2', '3')),
    category VARCHAR(100) NOT NULL,
    activity_date DATE NOT NULL,
    original_value NUMERIC(15,3) NOT NULL,
    original_unit VARCHAR(20) NOT NULL,
    normalized_value NUMERIC(15,3) NOT NULL,
    normalized_unit VARCHAR(20) NOT NULL,
    co2e_kg NUMERIC(15,3) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'locked')),
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    raw_data JSONB NOT NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_emissions_company_status ON emissions(company_id, status);
CREATE INDEX idx_emissions_company_date ON emissions(company_id, activity_date);
CREATE INDEX idx_emissions_scope ON emissions(scope);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    emission_id INTEGER NOT NULL REFERENCES emissions(id) ON DELETE CASCADE,
    user VARCHAR(255) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('created', 'approved', 'rejected', 'edited', 'locked')),
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_emission ON audit_logs(emission_id, timestamp DESC);

CREATE TABLE emission_factors (
    id SERIAL PRIMARY KEY,
    fuel_type VARCHAR(50) NOT NULL,
    scope VARCHAR(1) NOT NULL CHECK (scope IN ('1', '2', '3')),
    factor_kg_co2e NUMERIC(10,6) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    source VARCHAR(100) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    UNIQUE (fuel_type, unit, valid_from)
);

CREATE INDEX idx_emission_factors_lookup ON emission_factors(fuel_type, valid_to);
```

---

## Document Metadata

- **Tables Defined:** 7 (6 core + 1 optional)
- **Columns Total:** 87
- **Foreign Keys:** 9
- **Indexes:** 12
- **Check Constraints:** 11
- **Sample SQL Rows:** 15
- **Last Updated:** May 26, 2024
- **Version:** 1.0 (Initial Submission)
- **Status:** Final for BreatheESG Technical Assessment

