-- Extensions required by the platform.
--   postgis   -> lease boundary polygons, site centroids, spatial queries
--   vector    -> pgvector, semantic search over regulations and documents
--   pg_trgm   -> fuzzy search on lease numbers, holder names
--   btree_gist-> exclusion constraints for non-overlapping validity windows
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
