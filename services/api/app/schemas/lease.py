"""Schemas for the lease aggregate."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LeaseStatus, LeaseType, RoyaltyBasis
from app.schemas.common import LatLon, ORMModel
from app.schemas.reference import HolderRead, MineralRead

#: A GeoJSON geometry object, e.g. {"type": "Polygon", "coordinates": [...]}.
GeoJSON = dict[str, Any]


class LeaseBase(BaseModel):
    lease_number: str = Field(max_length=64)
    name: str = Field(max_length=200)
    lease_type: LeaseType = LeaseType.MINING_LEASE
    status: LeaseStatus = LeaseStatus.PENDING

    area_hectares: Decimal | None = Field(default=None, ge=0)
    village: str | None = None
    district: str = Field(max_length=120)
    state: str = Field(max_length=120)
    country: str = "India"

    grant_date: date | None = None
    effective_from: date
    effective_to: date | None = None

    royalty_basis: RoyaltyBasis | None = None
    royalty_rate: Decimal | None = Field(default=None, ge=0)
    royalty_unit: str | None = None

    annual_production_tonnes: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _term_is_ordered(self) -> "LeaseBase":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if (
            self.grant_date is not None
            and self.effective_from is not None
            and self.grant_date > self.effective_from
        ):
            raise ValueError("grant_date must not follow effective_from")
        return self


class LeaseCreate(LeaseBase):
    """Payload for registering a concession."""

    holder_id: uuid.UUID
    mineral_id: uuid.UUID

    #: Surveyed boundary, supplied by the map draw tool as GeoJSON.
    boundary: GeoJSON | None = None
    centroid: GeoJSON | None = None

    @field_validator("boundary")
    @classmethod
    def _boundary_is_areal(cls, value: GeoJSON | None) -> GeoJSON | None:
        if value is None:
            return None
        geom_type = value.get("type")
        if geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("boundary must be a GeoJSON Polygon or MultiPolygon")
        if not value.get("coordinates"):
            raise ValueError("boundary coordinates must not be empty")
        return normalize_to_multipolygon(value)

    @field_validator("centroid")
    @classmethod
    def _centroid_is_a_point(cls, value: GeoJSON | None) -> GeoJSON | None:
        if value is None:
            return None
        if value.get("type") != "Point":
            raise ValueError("centroid must be a GeoJSON Point")
        coords = value.get("coordinates")
        if not isinstance(coords, list) or len(coords) != 2:
            raise ValueError("centroid coordinates must be [lon, lat]")
        return value


class LeaseUpdate(BaseModel):
    """Partial update. Unset fields are left untouched."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    lease_type: LeaseType | None = None
    status: LeaseStatus | None = None
    holder_id: uuid.UUID | None = None
    mineral_id: uuid.UUID | None = None
    area_hectares: Decimal | None = Field(default=None, ge=0)
    village: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    grant_date: date | None = None
    royalty_basis: RoyaltyBasis | None = None
    royalty_rate: Decimal | None = Field(default=None, ge=0)
    royalty_unit: str | None = None
    annual_production_tonnes: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    boundary: GeoJSON | None = None
    centroid: GeoJSON | None = None

    @field_validator("boundary")
    @classmethod
    def _boundary_is_areal(cls, value: GeoJSON | None) -> GeoJSON | None:
        if value is None:
            return None
        if value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("boundary must be a GeoJSON Polygon or MultiPolygon")
        return normalize_to_multipolygon(value)


class LeaseRead(LeaseBase, ORMModel):
    id: uuid.UUID
    holder_id: uuid.UUID
    mineral_id: uuid.UUID
    boundary: GeoJSON | None = None
    centroid: LatLon | None = None
    #: Area recomputed by PostGIS from the boundary, for reconciliation against
    #: the area stated in the lease deed.
    surveyed_area_hectares: float | None = None
    holder: HolderRead | None = None
    mineral: MineralRead | None = None
    created_at: datetime
    updated_at: datetime


class LeaseListItem(BaseModel):
    """Slim projection for list and map views."""

    id: uuid.UUID
    lease_number: str
    name: str
    lease_type: LeaseType
    status: LeaseStatus
    district: str
    state: str
    area_hectares: Decimal | None = None
    effective_from: date
    effective_to: date | None = None
    holder_name: str | None = None
    mineral_name: str | None = None
    centroid: LatLon | None = None
    compliance_score: float | None = None
    risk_level: str | None = None
    overdue_obligations: int = 0
    expiring_licences: int = 0
    expired_licences: int = 0


def normalize_to_multipolygon(geometry: GeoJSON) -> GeoJSON:
    """Coerce a Polygon into a MultiPolygon.

    The column is typed MULTIPOLYGON so that a lease split by a road or river
    is representable. Wrapping here means callers can always send a Polygon.
    """
    if geometry.get("type") == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geometry["coordinates"]]}
    return geometry
