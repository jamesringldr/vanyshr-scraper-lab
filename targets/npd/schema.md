# NPD Database Schema

## Tables

### scrape_results_npd
Stores all scrape runs for this target.

```sql
CREATE TABLE scrape_results_npd (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    search_params JSONB NOT NULL,
    summary_results JSONB NOT NULL,
    profile_data JSONB NOT NULL,
    raw_html TEXT,
    status ENUM('success', 'partial', 'failed'),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_npd_user ON scrape_results_npd(user_id, created_at);
CREATE INDEX idx_npd_search ON scrape_results_npd USING GIN(search_params);
```

### people_profiles_npd
Normalized person data from NPD (deduplicated).

```sql
CREATE TABLE people_profiles_npd (
    id UUID PRIMARY KEY,
    source_id TEXT UNIQUE NOT NULL,  -- NPD profile ID
    full_name TEXT NOT NULL,
    date_of_birth DATE,
    age INTEGER,
    current_address_id UUID REFERENCES addresses(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_npd_profiles_name ON people_profiles_npd(full_name);
```

### addresses_npd
Address history linked to profiles.

```sql
CREATE TABLE addresses_npd (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_npd(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    address_type ENUM('current', 'previous'),
    years_active DATERANGE,
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_addresses_profile ON addresses_npd(profile_id);
```

### contacts_npd
Phone and email contacts.

```sql
CREATE TABLE contacts_npd (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_npd(id) ON DELETE CASCADE,
    contact_type ENUM('phone', 'email') NOT NULL,
    contact_value TEXT NOT NULL,
    phone_type ENUM('mobile', 'landline', 'voip'),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_contacts_profile ON contacts_npd(profile_id);
CREATE UNIQUE INDEX idx_contacts_unique ON contacts_npd(profile_id, contact_type, contact_value);
```

### relatives_npd
Family relationships.

```sql
CREATE TABLE relatives_npd (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_npd(id) ON DELETE CASCADE,
    relative_name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    address_id UUID REFERENCES addresses_npd(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_relatives_profile ON relatives_npd(profile_id);
```

### properties_npd
Real estate holdings.

```sql
CREATE TABLE properties_npd (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_npd(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    property_type TEXT,
    year_built INTEGER,
    estimated_value INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_properties_profile ON properties_npd(profile_id);
```

## Data Flow

```
scraper.run(params) 
  → scrape_results_npd (raw output stored)
  → people_profiles_npd (normalized, deduplicated)
  → addresses_npd, contacts_npd, relatives_npd, properties_npd (linked tables)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_npd (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_npd

people_profiles_npd
  ├── addresses_npd (one-to-many)
  ├── contacts_npd (one-to-many)
  ├── relatives_npd (one-to-many)
  └── properties_npd (one-to-many)
```

