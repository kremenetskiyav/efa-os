ALTER TABLE promotion_snapshots
  ADD COLUMN current_boost numeric CHECK (current_boost IS NULL OR current_boost >= 0),
  ADD COLUMN min_boost numeric CHECK (min_boost IS NULL OR min_boost >= 0),
  ADD COLUMN max_boost numeric CHECK (max_boost IS NULL OR max_boost >= 0);
