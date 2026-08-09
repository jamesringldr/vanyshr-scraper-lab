# Zaba Database Schema

## Tables

### scrape_results_zaba
Stores all scrape runs for this target.

```sql
CREATE TABLE scrape_results_zaba (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    search_params JSONB NOT NULL,
    results JSONB NOT NULL,  -- Array of profiles (no summary/profile split)
    raw_html TEXT,
    status ENUM('success', 'partial', 'failed'),
    error_message TEXT,
    result_count INTEGER,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_zaba_user ON scrape_results_zaba(user_id, created_at);
CREATE INDEX idx_zaba_search ON scrape_results_zaba USING GIN(search_params);
```

### people_profiles_zaba
Normalized person data from Zaba (deduplicated).

```sql
CREATE TABLE people_profiles_zaba (
    id UUID PRIMARY KEY,
    source_id TEXT UNIQUE NOT NULL,  -- Zaba profile ID
    full_name TEXT NOT NULL,
    age INTEGER,
    current_address_id UUID REFERENCES addresses(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_profiles_name ON people_profiles_zaba(full_name);
```

### addresses_zaba
Address records linked to profiles.

```sql
CREATE TABLE addresses_zaba (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_zaba(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_addresses_profile ON addresses_zaba(profile_id);
```

### contacts_zaba
Phone and email contacts.

```sql
CREATE TABLE contacts_zaba (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_zaba(id) ON DELETE CASCADE,
    contact_type ENUM('phone', 'email') NOT NULL,
    contact_value TEXT NOT NULL,
    phone_type ENUM('mobile', 'landline'),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_contacts_profile ON contacts_zaba(profile_id);
CREATE UNIQUE INDEX idx_zaba_contacts_unique ON contacts_zaba(profile_id, contact_type, contact_value);
```

### relatives_zaba
Family relationships.

```sql
CREATE TABLE relatives_zaba (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_zaba(id) ON DELETE CASCADE,
    relative_name TEXT NOT NULL,
    relationship TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_relatives_profile ON relatives_zaba(profile_id);
```

### associates_zaba
Known associates.

```sql
CREATE TABLE associates_zaba (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_zaba(id) ON DELETE CASCADE,
    associate_name TEXT NOT NULL,
    relationship TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_associates_profile ON associates_zaba(profile_id);
```

### properties_zaba
Real estate holdings.

```sql
CREATE TABLE properties_zaba (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_zaba(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    property_type TEXT,
    year_built INTEGER,
    estimated_value INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zaba_properties_profile ON properties_zaba(profile_id);
```

## Data Flow

```
scraper.run(params)
  → scrape_results_zaba (raw output stored with multiple profiles)
  → people_profiles_zaba (normalized, deduplicated for each profile)
  → addresses_zaba, contacts_zaba, relatives_zaba, associates_zaba, properties_zaba (linked tables)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_zaba (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_zaba

people_profiles_zaba
  ├── addresses_zaba (one-to-many)
  ├── contacts_zaba (one-to-many)
  ├── relatives_zaba (one-to-many)
  ├── associates_zaba (one-to-many)
  └── properties_zaba (one-to-many)
```

