# Hudson Rock Username Search Database Schema

## Tables

### scrape_results_hudson_rock_username
Stores all username search runs.

```sql
CREATE TABLE scrape_results_hudson_rock_username (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    username TEXT NOT NULL,
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

CREATE INDEX idx_hudson_rock_username_user ON scrape_results_hudson_rock_username(user_id, created_at);
CREATE INDEX idx_hudson_rock_username_username ON scrape_results_hudson_rock_username(username);
CREATE UNIQUE INDEX idx_hudson_rock_username_unique ON scrape_results_hudson_rock_username(user_id, username, created_at);
```

### hudson_rock_username_stealers
Infostealer events for usernames.

```sql
CREATE TABLE hudson_rock_username_stealers (
    id UUID PRIMARY KEY,
    scrape_result_id UUID REFERENCES scrape_results_hudson_rock_username(id) ON DELETE CASCADE,
    stealer_id TEXT NOT NULL,
    malware_name TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    credential_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_username_stealers_scrape ON hudson_rock_username_stealers(scrape_result_id);
CREATE INDEX idx_username_stealers_malware ON hudson_rock_username_stealers(malware_name);
```

### hudson_rock_username_credentials
Compromised credentials for usernames.

```sql
CREATE TABLE hudson_rock_username_credentials (
    id UUID PRIMARY KEY,
    stealer_id UUID REFERENCES hudson_rock_username_stealers(id) ON DELETE CASCADE,
    url TEXT,
    login TEXT NOT NULL,
    password TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_username_credentials_stealer ON hudson_rock_username_credentials(stealer_id);
CREATE INDEX idx_username_credentials_login ON hudson_rock_username_credentials(login);
```

### hudson_rock_username_profiles
Aggregated username compromise data.

```sql
CREATE TABLE hudson_rock_username_profiles (
    id UUID PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    total_stealers INTEGER DEFAULT 0,
    total_credentials INTEGER DEFAULT 0,
    malware_types TEXT[],
    last_checked TIMESTAMP DEFAULT NOW(),
    is_monitored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_username_profiles_username ON hudson_rock_username_profiles(username);
CREATE INDEX idx_username_profiles_monitored ON hudson_rock_username_profiles(is_monitored);
```

