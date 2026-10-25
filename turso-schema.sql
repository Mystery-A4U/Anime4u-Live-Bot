-- This SQL is for TURSO, not MongoDB.
CREATE TABLE IF NOT EXISTS anime (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  synopsis TEXT,
  poster_url TEXT,
  type TEXT NOT NULL,
  release_year INTEGER,
  language TEXT,
  published INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seasons (
  id TEXT PRIMARY KEY,
  anime_id TEXT NOT NULL,
  season_number INTEGER NOT NULL,
  title TEXT,
  UNIQUE(anime_id, season_number)
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  anime_id TEXT NOT NULL,
  season_id TEXT NOT NULL,
  episode_number INTEGER NOT NULL,
  title TEXT,
  synopsis TEXT,
  published INTEGER NOT NULL DEFAULT 0,
  UNIQUE(season_id, episode_number)
);
