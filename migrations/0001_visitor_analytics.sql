CREATE TABLE IF NOT EXISTS page_views (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visitor_id TEXT NOT NULL,
  visited_at TEXT NOT NULL DEFAULT (datetime('now')),
  country TEXT NOT NULL DEFAULT 'Unknown',
  region TEXT NOT NULL DEFAULT 'Unknown',
  city TEXT NOT NULL DEFAULT 'Unknown',
  latitude REAL,
  longitude REAL,
  path TEXT NOT NULL DEFAULT '/',
  is_bot INTEGER NOT NULL DEFAULT 0 CHECK (is_bot IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_page_views_visited_at
  ON page_views(visited_at);

CREATE INDEX IF NOT EXISTS idx_page_views_visitor_id
  ON page_views(visitor_id);

CREATE INDEX IF NOT EXISTS idx_page_views_location
  ON page_views(country, region, city);
