# HIBP Database Schema

## Tables

### scrape_results_hibp
Stores all email breach lookups for this target.

```sql
CREATE TABLE scrape_results_hibp (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    email TEXT NOT NULL,
    breaches JSONB NOT NULL,  -- Array of breaches found
    pastes JSONB,             -- Array of pastes (if found)
    total_breaches INTEGER DEFAULT 0,
    total_pastes INTEGER DEFAULT 0,
    is_compromised BOOLEAN DEFAULT FALSE,
    status ENUM('success', 'not_found', 'rate_limited', 'error'),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_hibp_user ON scrape_results_hibp(user_id, created_at);
CREATE INDEX idx_hibp_email ON scrape_results_hibp(email);
CREATE INDEX idx_hibp_compromised ON scrape_results_hibp(is_compromised);
CREATE UNIQUE INDEX idx_hibp_unique ON scrape_results_hibp(user_id, email, created_at);
```

### email_breaches
Individual breach records for compromised emails.

```sql
CREATE TABLE email_breaches (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_hibp(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    email TEXT NOT NULL,
    breach_name TEXT NOT NULL,
    breach_date DATE,
    pwn_count INTEGER,
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT FALSE,
    data_classes TEXT[],  -- Array of exposed data types
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_breaches_user ON email_breaches(user_id);
CREATE INDEX idx_breaches_email ON email_breaches(email);
CREATE INDEX idx_breaches_breach ON email_breaches(breach_name);
CREATE UNIQUE INDEX idx_breaches_unique ON email_breaches(email, breach_name);
```

### email_breach_pastes
Paste bin records for compromised emails.

```sql
CREATE TABLE email_breach_pastes (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_hibp(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    email TEXT NOT NULL,
    source TEXT,  -- Pastebin, etc.
    paste_id TEXT,
    title TEXT,
    paste_date TIMESTAMP,
    email_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pastes_user ON email_breach_pastes(user_id);
CREATE INDEX idx_pastes_email ON email_breach_pastes(email);
```

### email_compromise_profiles
Aggregated compromise data for emails (for monitoring).

```sql
CREATE TABLE email_compromise_profiles (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    first_checked TIMESTAMP DEFAULT NOW(),
    last_checked TIMESTAMP DEFAULT NOW(),
    total_breaches INTEGER DEFAULT 0,
    total_pastes INTEGER DEFAULT 0,
    is_compromised BOOLEAN DEFAULT FALSE,
    latest_breach_date DATE,
    data_classes_exposed TEXT[],  -- Aggregate of all exposed types
    is_monitored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profiles_email ON email_compromise_profiles(email);
CREATE INDEX idx_profiles_compromised ON email_compromise_profiles(is_compromised);
CREATE INDEX idx_profiles_monitored ON email_compromise_profiles(is_monitored);
```

## Data Flow

```
scraper.run(email)
  → scrape_results_hibp (raw API response stored)
  → email_breaches (individual breach records)
  → email_breach_pastes (paste records)
  → email_compromise_profiles (aggregate for monitoring)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_hibp (one-to-many)
  ├── email_breaches (one-to-many)
  ├── email_breach_pastes (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_hibp

email_compromise_profiles
  └── email_breaches (one-to-many via email)
  └── email_breach_pastes (one-to-many via email)
```

