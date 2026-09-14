"""Seed the database with the India/MMDR reference pack and demo concessions.

Idempotent and safe to re-run: records are matched on natural keys (mineral
code, holder registration number, lease number, obligation code), so running
twice refreshes dates rather than duplicating the register.

Usage::

    uv run python -m app.db.seed
    uv run python -m app.db.seed --no-filings   # leave the calendar untouched
"""

from __future__ import annotations

import argparse
import logging
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.db import reference_pack as pack
from app.models.enums import ObligationStatus
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.mineral import Mineral
from app.models.obligation import LeaseObligation, Obligation
from app.services import geo
from app.services.calendar import default_window, generate_instances

logger = logging.getLogger(__name__)

#: Fixed seed so the simulated filing history is reproducible across runs.
_HISTORY_SEED = 20260913


def _stable_uuid(kind: str, key: str) -> uuid.UUID:
    """Deterministic UUIDs make seeded data reproducible and diff-friendly."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mining-governance:{kind}:{key}")


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
def upsert_minerals(session: Session) -> dict[str, Mineral]:
    existing = {m.code: m for m in session.scalars(select(Mineral)).all()}

    for spec in pack.MINERALS:
        code = spec["code"]
        mineral = existing.get(code)
        if mineral is None:
            mineral = Mineral(id=_stable_uuid("mineral", code), **spec)
            session.add(mineral)
            existing[code] = mineral
        else:
            for field, value in spec.items():
                setattr(mineral, field, value)

    session.flush()
    logger.info("Minerals ready: %s", len(existing))
    return existing


def upsert_holders(session: Session) -> list[LeaseHolder]:
    existing = {
        h.registration_number: h
        for h in session.scalars(select(LeaseHolder)).all()
        if h.registration_number
    }

    for spec in pack.HOLDERS:
        registration = spec["registration_number"]
        holder = existing.get(registration)
        if holder is None:
            holder = LeaseHolder(id=_stable_uuid("holder", registration), **spec)
            session.add(holder)
            existing[registration] = holder
        else:
            for field, value in spec.items():
                setattr(holder, field, value)

    session.flush()
    holders = [existing[spec["registration_number"]] for spec in pack.HOLDERS]
    logger.info("Lease holders ready: %s", len(holders))
    return holders


def upsert_obligations(session: Session) -> list[Obligation]:
    existing = {o.code: o for o in session.scalars(select(Obligation)).all()}

    for spec in pack.OBLIGATIONS:
        code = spec["code"]
        obligation = existing.get(code)
        if obligation is None:
            obligation = Obligation(id=_stable_uuid("obligation", code), **spec)
            session.add(obligation)
            existing[code] = obligation
        else:
            for field, value in spec.items():
                setattr(obligation, field, value)

    session.flush()
    logger.info("Obligation rules ready: %s", len(existing))
    return list(existing.values())


# ---------------------------------------------------------------------------
# Concessions and clearances
# ---------------------------------------------------------------------------
def upsert_leases(
    session: Session,
    holders: list[LeaseHolder],
    minerals: dict[str, Mineral],
    today: date,
) -> list[Lease]:
    leases: list[Lease] = []

    for spec in pack.lease_definitions(today):
        lease_number = spec["lease_number"]
        lease = session.scalar(select(Lease).where(Lease.lease_number == lease_number))

        fields: dict[str, Any] = {
            key: value
            for key, value in spec.items()
            if key
            not in {
                "lat",
                "lon",
                "area_variance",
                "holder_index",
                "mineral_code",
                "licences",
            }
        }
        fields["holder_id"] = holders[spec["holder_index"]].id
        fields["mineral_id"] = minerals[spec["mineral_code"]].id

        if lease is None:
            lease = Lease(id=_stable_uuid("lease", lease_number), **fields)
            session.add(lease)
        else:
            for field, value in fields.items():
                setattr(lease, field, value)

        # Geometry is written as PostGIS expressions so the same conversion path
        # is exercised as in the API, and the seeded area is what PostGIS computes.
        lease.boundary = geo.geojson_to_multipolygon(
            pack.lease_box(
                spec["lat"],
                spec["lon"],
                float(spec["area_hectares"]),
                area_scale=spec.get("area_variance", 1.0),
            )
        )
        lease.centroid = geo.geojson_to_point(
            {"type": "Point", "coordinates": [spec["lon"], spec["lat"]]}
        )

        leases.append(lease)
        _upsert_licences(session, lease, spec["licences"], today)

    session.flush()
    logger.info("Leases ready: %s", len(leases))
    return leases


def _upsert_licences(
    session: Session,
    lease: Lease,
    licence_specs: list[dict[str, Any]],
    today: date,
) -> None:
    existing = {
        licence.reference_number: licence
        for licence in session.scalars(select(Licence).where(Licence.lease_id == lease.id)).all()
    }

    for licence_spec in licence_specs:
        reference = licence_spec["reference_number"]
        licence = existing.get(reference)
        if licence is None:
            session.add(
                Licence(
                    lease_id=lease.id,
                    status=_licence_status(licence_spec, today),
                    **licence_spec,
                )
            )
        else:
            for field, value in licence_spec.items():
                setattr(licence, field, value)
            licence.status = _licence_status(licence_spec, today)


def _licence_status(licence_spec: dict[str, Any], today: date) -> str:
    """Derive stored status from expiry, mirroring how the scorer reads it."""
    valid_to = licence_spec.get("valid_to")
    if valid_to is None:
        return "valid"
    if valid_to < today:
        return "expired"
    if valid_to <= today + timedelta(days=90):
        return "expiring_soon"
    return "valid"


# ---------------------------------------------------------------------------
# Calendar history
# ---------------------------------------------------------------------------
def simulate_filing_history(session: Session, leases: list[Lease], today: date) -> dict[str, int]:
    """Give past-due entries a plausible filing history.

    A portfolio where nothing has ever been filed cannot demonstrate a
    compliance score, so this fabricates a realistic mix: most filings made on
    time, some late, and a minority genuinely outstanding.

    Deterministic via a fixed RNG seed, so the dashboard is stable across runs.
    """
    rng = random.Random(_HISTORY_SEED)
    counts = {"submitted": 0, "late": 0, "overdue": 0}

    instances = session.scalars(
        select(LeaseObligation).where(LeaseObligation.due_date < today)
    ).all()

    for instance in instances:
        # Suspended and lapsed concessions realistically stop filing; leaving
        # them outstanding is what makes the risk view meaningful.
        roll = rng.random()
        if roll < 0.76:
            # Filed, on time or slightly late.
            lateness = rng.choice([0, 0, 0, 1, 2, 3, 9, 24])
            submitted = instance.due_date + timedelta(days=lateness)
            if submitted > today:
                submitted = today
            instance.status = ObligationStatus.SUBMITTED
            instance.submitted_at = datetime.combine(submitted, datetime.min.time(), tzinfo=UTC)
            instance.submitted_by = "seed-data"
            counts["submitted" if lateness == 0 else "late"] += 1
        else:
            instance.status = ObligationStatus.OVERDUE
            counts["overdue"] += 1

    # A handful of entries are formally exempt, to exercise that path too.
    for instance in instances[::37]:
        if instance.status is ObligationStatus.OVERDUE:
            instance.status = ObligationStatus.WAIVED
            instance.waiver_reason = "Exempted by state authority order (seed data)"
            counts["overdue"] -= 1

    session.flush()
    return counts


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def seed(session: Session, *, with_filings: bool = True) -> dict[str, Any]:
    """Apply the reference pack and demo data. Returns a summary."""
    today = date.today()

    minerals = upsert_minerals(session)
    holders = upsert_holders(session)
    templates = upsert_obligations(session)
    leases = upsert_leases(session, holders, minerals, today)

    window_start, window_end = default_window(today)
    generated = 0
    for lease in leases:
        generated += generate_instances(session, lease, templates, window_start, window_end)
    session.flush()

    filings = simulate_filing_history(session, leases, today) if with_filings else {}

    session.commit()

    return {
        "minerals": len(minerals),
        "holders": len(holders),
        "obligation_rules": len(templates),
        "leases": len(leases),
        "calendar_entries_created": generated,
        "calendar_window": (window_start, window_end),
        "filings": filings,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Seed the compliance database")
    parser.add_argument(
        "--no-filings",
        action="store_true",
        help="Load reference data and leases but leave the calendar untouched",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        summary = seed(session, with_filings=not args.no_filings)

    print("\nSeed complete:")
    for key, value in summary.items():
        print(f"  {key:28} {value}")


if __name__ == "__main__":
    main()
