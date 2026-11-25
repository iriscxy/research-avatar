CREATE TABLE IF NOT EXISTS account_usage (
  account_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK (amount >= 0),
  PRIMARY KEY (account_id, project_id)
);
