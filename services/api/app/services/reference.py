"""Shared helpers for reference-data and aggregate writes."""

from typing import Any

from sqlalchemy.orm import Session


def apply_partial_update(
    instance: Any, payload: Any, *, exclude: set[str] | None = None
) -> list[str]:
    """Assign only the fields the caller actually sent.

    ``exclude_unset`` is what makes PATCH semantics correct: an omitted field is
    left alone, while an explicitly-sent ``null`` clears the value. Treating
    those two cases identically is the classic partial-update bug.
    """
    skip = exclude or set()
    changed: list[str] = []
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in skip:
            continue
        setattr(instance, field, value)
        changed.append(field)
    return changed


def touch(session: Session, instance: Any) -> None:
    """Flush a single instance so constraint violations surface at the call site."""
    session.add(instance)
    session.flush()
