# Anywho Database Schema

## Tables

### scrape_results_anywho
Stores all scrape runs for this target.

```sql
CREATE TABLE scrape_results_anywho (
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

CREATE INDEX idx_anywho_user ON scrape_results_anywho(user_id, created_at);
CREATE INDEX idx_anywho_search ON scrape_results_anywho USING GIN(search_params);
```

### people_profiles_anywho
Normalized person data from Anywho (deduplicated).

```sql
CREATE TABLE people_profiles_anywho (
    id UUID PRIMARY KEY,
    source_id TEXT UNIQUE NOT NULL,  -- Anywho profile ID
    full_name TEXT NOT NULL,
    age INTEGER,
    current_address_id UUID REFERENCES addresses(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anywho_profiles_name ON people_profiles_anywho(full_name);
```

### addresses_anywho
Address records linked to profiles.

```sql
CREATE TABLE addresses_anywho (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_anywho(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    address_type ENUM('current', 'previous'),
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anywho_addresses_profile ON addresses_anywho(profile_id);
```

### contacts_anywho
Phone and email contacts.

```sql
CREATE TABLE contacts_anywho (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_anywho(id) ON DELETE CASCADE,
    contact_type ENUM('phone', 'email') NOT NULL,
    contact_value TEXT NOT NULL,
    phone_type ENUM('mobile', 'landline'),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anywho_contacts_profile ON contacts_anywho(profile_id);
CREATE UNIQUE INDEX idx_anywho_contacts_unique ON contacts_anywho(profile_id, contact_type, contact_value);
```

### family_members_anywho
Family relationships.

```sql
CREATE TABLE family_members_anywho (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_anywho(id) ON DELETE CASCADE,
    member_name TEXT NOT NULL,
    relationship TEXT,
    age INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anywho_family_profile ON family_members_anywho(profile_id);
```

### properties_anywho
Real estate holdings.

```sql
CREATE TABLE properties_anywho (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_anywho(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    property_type TEXT,
    estimated_value INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_anywho_properties_profile ON properties_anywho(profile_id);
```

## Data Flow

```
scraper.run(params)
  → scrape_results_anywho (raw output stored)
  → people_profiles_anywho (normalized, deduplicated)
  → addresses_anywho, contacts_anywho, family_members_anywho, properties_anywho (linked tables)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_anywho (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_anywho

people_profiles_anywho
  ├── addresses_anywho (one-to-many)
  ├── contacts_anywho (one-to-many)
  ├── family_members_anywho (one-to-many)
  └── properties_anywho (one-to-many)
```

