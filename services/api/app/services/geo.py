"""Conversion between GeoJSON (API surface) and PostGIS geometry (storage).

All spatial work is pushed down to PostGIS rather than pulled into Python, so
the service needs no Shapely dependency and large boundaries never round-trip
through the interpreter.
"""

import json
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.elements import ColumnClause

GeoJSON = dict[str, Any]

#: One hectare in square metres.
_SQM_PER_HECTARE = 10_000.0


def geojson_to_multipolygon(value: GeoJSON | None) -> ColumnElement | None:
    """PostGIS expression normalising GeoJSON into MultiPolygon in WGS84.

    ``ST_Multi`` guarantees the result matches the column's declared type even
    when a caller sends a bare Polygon, which PostGIS would otherwise reject.
    """
    if value is None:
        return None
    return func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), 4326))


def geojson_to_point(value: GeoJSON | None) -> ColumnElement | None:
    """PostGIS expression for a GeoJSON Point in WGS84."""
    if value is None:
        return None
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), 4326)


def as_geojson(column: ColumnClause | ColumnElement) -> ColumnElement:
    """Render a geometry column as a GeoJSON string for transport."""
    return func.ST_AsGeoJSON(column)


def point_lat(column: ColumnClause | ColumnElement) -> ColumnElement:
    return func.ST_Y(column)


def point_lon(column: ColumnClause | ColumnElement) -> ColumnElement:
    return func.ST_X(column)


def area_hectares(column: ColumnClause | ColumnElement) -> ColumnElement:
    """Area of a boundary in hectares, measured on the spheroid.

    Casting to ``geography`` makes ``ST_Area`` return square metres on the
    spheroid instead of square degrees on the plane. That distinction matters:
    a degree of longitude is not a constant distance, so planar area would
    misreport the size of a lease by a factor that varies with latitude.
    """
    return func.ST_Area(cast(column, Geography())) / _SQM_PER_HECTARE


def load_geojson(raw: str | dict[str, Any] | None) -> GeoJSON | None:
    """Decode a GeoJSON value returned by PostGIS, tolerating NULL."""
    if raw is None:
        return None
    if isinstance(raw, dict):  # pragma: no cover - driver-dependent
        return raw
    return json.loads(raw)
