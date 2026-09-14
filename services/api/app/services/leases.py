"""Lease reads, filtering and serialisation.

Geometry is rendered by PostGIS in the select list and assembled into plain
dicts here, because an ORM instance carries raw WKB that the API must never
expose. Pagination interacts with the derived compliance score, so the order of
operations is: filter -> score -> sort -> paginate.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import LeaseStatus, LeaseType, RiskLevel
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.mineral import Mineral
from app.services import geo
from app.services.compliance import score_leases

#: Scalar fields copied straight from the ORM instance into the API payload.
_LEASE_FIELDS = (
    "id",
    "lease_number",
    "name",
    "lease_type",
    "status",
    "village",
    "district",
    "state",
    "country",
    "area_hectares",
    "grant_date",
    "effective_from",
    "effective_to",
    "royalty_basis",
    "royalty_rate",
    "royalty_unit",
    "annual_production_tonnes",
    "notes",
    "holder_id",
    "mineral_id",
    "created_at",
    "updated_at",
)

_SORTABLE = {
    "lease_number": Lease.lease_number,
    "name": Lease.name,
    "district": Lease.district,
    "state": Lease.state,
    "effective_to": Lease.effective_to,
    "area_hectares": Lease.area_hectares,
    "created_at": Lease.created_at,
}


def _spatial_select() -> Select:
    """Select a lease plus its PostGIS-rendered geometry, ready to serialise."""
    return select(
        Lease,
        geo.as_geojson(Lease.boundary).label("boundary_geojson"),
        geo.point_lat(Lease.centroid).label("centroid_lat"),
        geo.point_lon(Lease.centroid).label("centroid_lon"),
        geo.area_hectares(Lease.boundary).label("surveyed_area_hectares"),
    )


def _serialize_lease(row: Any) -> dict[str, Any]:
    """Flatten a spatial select row into a LeaseRead-shaped dict."""
    lease: Lease = row[0]
    payload = {field: getattr(lease, field) for field in _LEASE_FIELDS}

    payload["boundary"] = geo.load_geojson(row.boundary_geojson)

    lat, lon = row.centroid_lat, row.centroid_lon
    payload["centroid"] = {"lat": lat, "lon": lon} if lat is not None and lon is not None else None

    area = row.surveyed_area_hectares
    payload["surveyed_area_hectares"] = float(area) if area is not None else None

    payload["holder"] = lease.holder
    payload["mineral"] = lease.mineral
    return payload


def get_lease(session: Session, lease_id: uuid.UUID) -> dict[str, Any] | None:
    """Fetch a single lease with its geometry rendered."""
    row = session.execute(
        _spatial_select()
        .where(Lease.id == lease_id)
        .options(joinedload(Lease.holder), joinedload(Lease.mineral))
    ).first()
    return _serialize_lease(row) if row else None


def _apply_filters(
    stmt: Select,
    *,
    q: str | None,
    state: str | None,
    district: str | None,
    status: list[LeaseStatus] | None,
    lease_type: list[LeaseType] | None,
    holder_id: uuid.UUID | None,
    mineral_id: uuid.UUID | None,
    expiring_within_days: int | None,
    as_of: date,
    bbox: tuple[float, float, float, float] | None,
) -> Select:
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Lease.lease_number.ilike(pattern),
                Lease.name.ilike(pattern),
                Lease.village.ilike(pattern),
            )
        )
    if state:
        stmt = stmt.where(Lease.state.ilike(state))
    if district:
        stmt = stmt.where(Lease.district.ilike(district))
    if status:
        stmt = stmt.where(Lease.status.in_(status))
    if lease_type:
        stmt = stmt.where(Lease.lease_type.in_(lease_type))
    if holder_id:
        stmt = stmt.where(Lease.holder_id == holder_id)
    if mineral_id:
        stmt = stmt.where(Lease.mineral_id == mineral_id)
    if expiring_within_days is not None:
        horizon = as_of + timedelta(days=expiring_within_days)
        stmt = stmt.where(
            Lease.effective_to.is_not(None),
            Lease.effective_to >= as_of,
            Lease.effective_to <= horizon,
        )
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        # Fall back to the centroid so leases staked as a point still appear.
        stmt = stmt.where(
            func.ST_Intersects(func.coalesce(Lease.boundary, Lease.centroid), envelope)
        )
    return stmt


def list_leases(
    session: Session,
    *,
    limit: int,
    offset: int,
    as_of: date,
    warning_days: int,
    q: str | None = None,
    state: str | None = None,
    district: str | None = None,
    status: list[LeaseStatus] | None = None,
    lease_type: list[LeaseType] | None = None,
    holder_id: uuid.UUID | None = None,
    mineral_id: uuid.UUID | None = None,
    expiring_within_days: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    risk_level: list[RiskLevel] | None = None,
    sort: str = "lease_number",
    descending: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Return one page of leases annotated with their compliance posture.

    Scoring happens across the whole filtered set before pagination, so a
    ``risk_level`` filter matches every qualifying lease rather than only those
    that happened to land on the requested page.
    """
    filters: dict[str, Any] = {
        "q": q,
        "state": state,
        "district": district,
        "status": status,
        "lease_type": lease_type,
        "holder_id": holder_id,
        "mineral_id": mineral_id,
        "expiring_within_days": expiring_within_days,
        "as_of": as_of,
        "bbox": bbox,
    }

    # One pass to collect ids; the sort key rides along so no second query is
    # needed for column ordering.
    order_column = _SORTABLE.get(sort, Lease.lease_number)
    rows = session.execute(
        _apply_filters(select(Lease.id, order_column), **filters).order_by(order_column.asc())
    ).all()
    matching_ids = [row[0] for row in rows]

    scores = score_leases(session, as_of, matching_ids, warning_days)

    if risk_level:
        matching_ids = [
            lease_id for lease_id in matching_ids if scores[lease_id].risk_level in risk_level
        ]

    total = len(matching_ids)

    if sort == "compliance_score":
        matching_ids.sort(key=lambda lease_id: scores[lease_id].score, reverse=descending)
    elif sort in _SORTABLE:
        sort_keys = {row[0]: row[1] for row in rows}
        # Rows with no value (e.g. no stated expiry) are held back and appended,
        # so they never head a "most urgent" list in either direction.
        present = [lease_id for lease_id in matching_ids if sort_keys[lease_id] is not None]
        absent = [lease_id for lease_id in matching_ids if sort_keys[lease_id] is None]
        present.sort(key=lambda lease_id: sort_keys[lease_id], reverse=descending)
        matching_ids = present + absent

    page_ids = matching_ids[offset : offset + limit]
    if not page_ids:
        return [], total

    rows = session.execute(
        _spatial_select()
        .where(Lease.id.in_(page_ids))
        .options(joinedload(Lease.holder), joinedload(Lease.mineral))
    ).all()

    by_id = {row[0].id: row for row in rows}
    ordered_rows = [by_id[lease_id] for lease_id in page_ids if lease_id in by_id]

    items: list[dict[str, Any]] = []
    for row in ordered_rows:
        payload = _serialize_lease(row)
        # Flattened names keep the list and map payloads free of nested objects.
        payload["holder_name"] = row[0].holder.name if row[0].holder else None
        payload["mineral_name"] = row[0].mineral.name if row[0].mineral else None
        assessment = scores[row[0].id]
        payload["compliance_score"] = assessment.score
        payload["risk_level"] = assessment.risk_level
        payload["overdue_obligations"] = assessment.overdue_obligations
        payload["expiring_licences"] = assessment.expiring_licences
        payload["expired_licences"] = assessment.expired_licences
        items.append(payload)

    return items, total


def lease_feature_collection(
    session: Session,
    *,
    as_of: date,
    warning_days: int,
    q: str | None = None,
    state: str | None = None,
    district: str | None = None,
    status: list[LeaseStatus] | None = None,
    lease_type: list[LeaseType] | None = None,
    risk_level: list[RiskLevel] | None = None,
    expiring_within_days: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Every matching lease as a GeoJSON FeatureCollection.

    Returning one collection rather than a request per lease is what makes the
    map usable: a register of a few hundred concessions would otherwise be a
    few hundred round trips.

    Geometry falls back to the centroid when no boundary has been surveyed, so
    a lease that exists but is not yet surveyed still appears on the map.
    """
    filters: dict[str, Any] = {
        "q": q,
        "state": state,
        "district": district,
        "status": status,
        "lease_type": lease_type,
        "holder_id": None,
        "mineral_id": None,
        "expiring_within_days": expiring_within_days,
        "as_of": as_of,
        "bbox": bbox,
    }

    stmt = (
        _apply_filters(
            select(
                Lease.id,
                Lease.lease_number,
                Lease.name,
                Lease.status,
                Lease.lease_type,
                Lease.district,
                Lease.state,
                Lease.area_hectares,
                Lease.effective_to,
                LeaseHolder.name.label("holder_name"),
                Mineral.name.label("mineral_name"),
                func.coalesce(
                    geo.as_geojson(Lease.boundary), geo.as_geojson(Lease.centroid)
                ).label("geometry"),
            )
            .select_from(Lease)
            .join(LeaseHolder, LeaseHolder.id == Lease.holder_id)
            .join(Mineral, Mineral.id == Lease.mineral_id),
            **filters,
        )
        .limit(limit)
    )

    rows = session.execute(stmt).all()
    scores = score_leases(session, as_of, [row.id for row in rows], warning_days)

    features: list[dict[str, Any]] = []
    for row in rows:
        assessment = scores[row.id]
        if risk_level and assessment.risk_level not in risk_level:
            continue
        if row.geometry is None:
            continue

        features.append(
            {
                "type": "Feature",
                "id": str(row.id),
                "geometry": json.loads(row.geometry),
                "properties": {
                    "id": str(row.id),
                    "lease_number": row.lease_number,
                    "name": row.name,
                    "status": row.status.value,
                    "lease_type": row.lease_type.value,
                    "district": row.district,
                    "state": row.state,
                    "area_hectares": float(row.area_hectares)
                    if row.area_hectares is not None
                    else None,
                    "effective_to": row.effective_to.isoformat()
                    if row.effective_to
                    else None,
                    "holder_name": row.holder_name,
                    "mineral_name": row.mineral_name,
                    "compliance_score": assessment.score,
                    "risk_level": assessment.risk_level.value,
                    "overdue_obligations": assessment.overdue_obligations,
                    "expired_licences": assessment.expired_licences,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def expiring_leases(
    session: Session, as_of: date, within_days: int = 90, limit: int = 100
) -> list[dict[str, Any]]:
    """Leases whose term lapses soon, worst-first by deadline."""
    horizon = as_of + timedelta(days=within_days)
    rows = session.execute(
        _spatial_select()
        .where(
            Lease.effective_to.is_not(None),
            Lease.effective_to >= as_of,
            Lease.effective_to <= horizon,
        )
        .order_by(Lease.effective_to.asc())
        .limit(limit)
        .options(joinedload(Lease.holder), joinedload(Lease.mineral))
    ).all()
    return [_serialize_lease(row) for row in rows]
