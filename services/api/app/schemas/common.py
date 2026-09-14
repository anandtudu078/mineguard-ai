"""Shared schema primitives."""

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Base for read models populated directly from ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """Offset pagination envelope."""

    items: list[T]
    total: int = Field(description="Total rows matching the filter, ignoring pagination")
    limit: int
    offset: int


class LatLon(BaseModel):
    """A WGS84 coordinate pair, as consumed by the map layer."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Message(BaseModel):
    """Simple acknowledgement payload."""

    detail: str
