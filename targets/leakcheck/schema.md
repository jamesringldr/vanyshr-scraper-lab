# LeakCheck Database Schema

## Tables

### scrape_results_leakcheck
Stores all email breach lookups for this target.

```sql
CREATE TABLE scrape_results_leakcheck (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    email TEXT NOT NULL,
    breaches JSONB NOT NULL,  -- Array of breaches found
    total_breaches INTEGER DEFAULT 0,
    is_compromised BOOLEAN DEFAULT FALSE,
    status ENUM('success', 'not_found', 'rate_limited', 'error'),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_leakcheck_user ON scrape_results_leakcheck(user_id, created_at);
CREATE INDEX idx_leakcheck_email ON scrape_results_leakcheck(email);
CREATE INDEX idx_leakcheck_compromised ON scrape_results_leakcheck(is_compromised);
CREATE UNIQUE INDEX idx_leakcheck_unique ON scrape_results_leakcheck(user_id, email, created_at);
```

### email_leakcheck_breaches
Individual breach records for compromised emails.

```sql
CREATE TABLE email_leakcheck_breaches (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_leakcheck(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    email TEXT NOT NULL,
    breach_name TEXT NOT NULL,
    breach_date DATE,
    source TEXT,
    compromised_count INTEGER,
    confidence INTEGER,  -- 0-100
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_breaches_user ON email_leakcheck_breaches(user_id);
CREATE INDEX idx_breaches_email ON email_leakcheck_breaches(email);
CREATE INDEX idx_breaches_breach ON email_leakcheck_breaches(breach_name);
CREATE UNIQUE INDEX idx_breaches_unique ON email_leakcheck_breaches(email, breach_name);
```

### email_leakcheck_profiles
Aggregated breach data for emails (for monitoring).

```sql
CREATE TABLE email_leakcheck_profiles (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    first_checked TIMESTAMP DEFAULT NOW(),
    last_checked TIMESTAMP DEFAULT NOW(),
    total_breaches INTEGER DEFAULT 0,
    is_compromised BOOLEAN DEFAULT FALSE,
    compromised_records INTEGER DEFAULT 0,
    is_monitored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profiles_email ON email_leakcheck_profiles(email);
CREATE INDEX idx_profiles_compromised ON email_leakcheck_profiles(is_compromised);
CREATE INDEX idx_profiles_monitored ON email_leakcheck_profiles(is_monitored);
```

## Data Flow

```
scraper.run(email)
  → scrape_results_leakcheck (raw API response stored)
  → email_leakcheck_breaches (individual breach records)
  → email_leakcheck_profiles (aggregate for monitoring)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_leakcheck (one-to-many)
  ├── email_leakcheck_breaches (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_leakcheck

email_leakcheck_profiles
  └── email_leakcheck_breaches (one-to-many via email)
```

