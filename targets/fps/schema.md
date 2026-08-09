# FPS Database Schema

## Tables

### scrape_results_fps
Stores all scrape runs for this target.

```sql
CREATE TABLE scrape_results_fps (
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

CREATE INDEX idx_fps_user ON scrape_results_fps(user_id, created_at);
CREATE INDEX idx_fps_search ON scrape_results_fps USING GIN(search_params);
```

### people_profiles_fps
Normalized person data from FPS (deduplicated).

```sql
CREATE TABLE people_profiles_fps (
    id UUID PRIMARY KEY,
    source_id TEXT UNIQUE NOT NULL,  -- FPS profile ID
    full_name TEXT NOT NULL,
    age INTEGER,
    current_address_id UUID REFERENCES addresses(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_profiles_name ON people_profiles_fps(full_name);
```

### addresses_fps
Address records linked to profiles.

```sql
CREATE TABLE addresses_fps (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_fps(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    address_type ENUM('current', 'previous'),
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_addresses_profile ON addresses_fps(profile_id);
```

### contacts_fps
Phone and email contacts.

```sql
CREATE TABLE contacts_fps (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_fps(id) ON DELETE CASCADE,
    contact_type ENUM('phone', 'email') NOT NULL,
    contact_value TEXT NOT NULL,
    phone_type ENUM('mobile', 'landline'),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_contacts_profile ON contacts_fps(profile_id);
CREATE UNIQUE INDEX idx_fps_contacts_unique ON contacts_fps(profile_id, contact_type, contact_value);
```

### relatives_fps
Family relationships.

```sql
CREATE TABLE relatives_fps (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_fps(id) ON DELETE CASCADE,
    relative_name TEXT NOT NULL,
    relationship TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_relatives_profile ON relatives_fps(profile_id);
```

### associates_fps
Known associates and neighbors.

```sql
CREATE TABLE associates_fps (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_fps(id) ON DELETE CASCADE,
    associate_name TEXT NOT NULL,
    relationship TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_associates_profile ON associates_fps(profile_id);
```

### properties_fps
Real estate holdings.

```sql
CREATE TABLE properties_fps (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES people_profiles_fps(id) ON DELETE CASCADE,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL,
    zip CHAR(5),
    property_type TEXT,
    year_built INTEGER,
    estimated_value INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fps_properties_profile ON properties_fps(profile_id);
```

## Data Flow

```
scraper.run(params)
  → scrape_results_fps (raw output stored)
  → people_profiles_fps (normalized, deduplicated)
  → addresses_fps, contacts_fps, relatives_fps, associates_fps, properties_fps (linked tables)
```

## Foreign Key Relationships

```
users
  ├── scrape_results_fps (one-to-many)
  └── subscription_monitoring (one-to-many) → scrape_results_fps

people_profiles_fps
  ├── addresses_fps (one-to-many)
  ├── contacts_fps (one-to-many)
  ├── relatives_fps (one-to-many)
  ├── associates_fps (one-to-many)
  └── properties_fps (one-to-many)
```

