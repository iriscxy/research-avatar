CREATE TABLE IF NOT EXISTS page_views (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip_address TEXT NOT NULL,
  visited_at TEXT NOT NULL DEFAULT (datetime('now')),
  path TEXT NOT NULL DEFAULT '/'
);

CREATE INDEX IF NOT EXISTS idx_page_views_visited_at
  ON page_views(visited_at);

CREATE INDEX IF NOT EXISTS idx_page_views_ip_address
  ON page_views(ip_address);
