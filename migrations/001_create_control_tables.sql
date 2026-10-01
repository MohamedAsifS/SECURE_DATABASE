CREATE TABLE IF NOT EXISTS database_connections (
  id TEXT PRIMARY KEY,
  user_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  database_type TEXT NOT NULL,
  host TEXT NOT NULL,
  port INTEGER NOT NULL,
  database_name TEXT NOT NULL,
  username TEXT NOT NULL,
  credential_reference TEXT UNIQUE NOT NULL,
  ssl_required BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS database_credentials (
  credential_reference TEXT PRIMARY KEY,
  encrypted_password TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
