# Holehe Database Schema

## Tables

### scrape_results_holehe
Stores all email scrape runs for this target.

```sql
CREATE TABLE scrape_results_holehe (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    email TEXT NOT NULL,
    results JSONB NOT NULL,  -- Array of service results
    total_checked INTEGER,
    services_found INTEGER,
    services_not_found INTEGER,
    rate_limited_count INTEGER,
    error_count INTEGER,
    status ENUM('success', 'partial', 'failed'),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_holehe_user ON scrape_results_holehe(user_id, created_at);
CREATE INDEX idx_holehe_email ON scrape_results_holehe(email);
CREATE UNIQUE INDEX idx_holehe_unique ON scrape_results_holehe(user_id, email, created_at);
```

### email_exposure_records
Denormalized records for each service result.

```sql
CREATE TABLE email_exposure_records (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_holehe(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    email TEXT NOT NULL,
    service TEXT NOT NULL,
    status ENUM('found', 'not_found', 'rate_limit', 'error') NOT NULL,
    metadata JSONB,  -- Service-specific metadata (name, URL, etc.)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_exposure_user ON email_exposure_records(user_id);
CREATE INDEX idx_exposure_email ON email_exposure_records(email);
CREATE INDEX idx_exposure_service ON email_exposure_records(service);
CREATE INDEX idx_exposure_status ON email_exposure_records(status);
CREATE UNIQUE INDEX idx_exposure_unique ON email_exposure_records(email, service);
```

### email_profiles
Aggregated profiles discovered via email exposure checks.

```sql
CREATE TABLE email_profiles (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    first_checked TIMESTAMP DEFAULT NOW(),
    last_checked TIMESTAMP DEFAULT NOW(),
    total_exposures INTEGER DEFAULT 0,
    metadata JSONB,  -- Aggregated metadata from all services
    is_monitored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profiles_email ON email_profiles(email);
CREATE INDEX idx_profiles_monitored ON email_profiles(is_monitored);
```

## Data Flow

```
scraper.run(email)
  → scrape_results_holehe (raw scan results stored)
  → email_exposure_records (individual service results)
  → email_profiles (aggregate profile for monitoring)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_holehe (one-to-many)
  ├── email_exposure_records (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_holehe

email_exposure_records
  └── scrape_results_holehe (many-to-one)

email_profiles
  └── email_exposure_records (one-to-many via email)
```

