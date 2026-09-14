# PostGIS and pgvector are not bundled in a single upstream image, so we layer
# pgvector on top of the official PostGIS image. The postgis image is already
# wired to the PGDG apt repo, so postgresql-16-pgvector installs cleanly.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Extensions are created on first boot of an empty data volume.
COPY init/ /docker-entrypoint-initdb.d/
