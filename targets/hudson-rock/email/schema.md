# Hudson Rock Email Search Database Schema

## Tables

### scrape_results_hudson_rock_email
Stores all email search runs.

```sql
CREATE TABLE scrape_results_hudson_rock_email (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    email TEXT NOT NULL,
    stealers JSONB NOT NULL,  -- Array of stealer records
    total_stealers INTEGER DEFAULT 0,
    total_credentials INTEGER DEFAULT 0,
    status ENUM('success', 'not_found', 'rate_limited', 'error'),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_hudson_rock_email_user ON scrape_results_hudson_rock_email(user_id, created_at);
CREATE INDEX idx_hudson_rock_email_email ON scrape_results_hudson_rock_email(email);
CREATE UNIQUE INDEX idx_hudson_rock_email_unique ON scrape_results_hudson_rock_email(user_id, email, created_at);
```

### hudson_rock_stealers
Infostealer events.

```sql
CREATE TABLE hudson_rock_stealers (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_hudson_rock_email(id) ON DELETE CASCADE,
    stealer_id TEXT NOT NULL,
    malware_name TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    credential_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stealers_scrape ON hudson_rock_stealers(scrape_result_id);
CREATE INDEX idx_stealers_malware ON hudson_rock_stealers(malware_name);
```

### hudson_rock_credentials
Compromised credentials.

```sql
CREATE TABLE hudson_rock_credentials (
    id UUID PRIMARY KEY,
    stealer_id UUID REFERENCES hudson_rock_stealers(id) ON DELETE CASCADE,
    url TEXT,
    login TEXT NOT NULL,
    password TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_credentials_stealer ON hudson_rock_credentials(stealer_id);
CREATE INDEX idx_credentials_login ON hudson_rock_credentials(login);
```

### hudson_rock_email_profiles
Aggregated email compromise data.

```sql
CREATE TABLE hudson_rock_email_profiles (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    total_stealers INTEGER DEFAULT 0,
    total_credentials INTEGER DEFAULT 0,
    malware_types TEXT[],
    last_checked TIMESTAMP DEFAULT NOW(),
    is_monitored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_email_profiles_email ON hudson_rock_email_profiles(email);
CREATE INDEX idx_email_profiles_monitored ON hudson_rock_email_profiles(is_monitored);
```

