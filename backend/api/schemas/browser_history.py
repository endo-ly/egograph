"""Browser history ingest API schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrowserHistoryItemRequest(BaseModel):
    """Browser history item request schema."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    visit_time: datetime
    title: str | None = None
    visit_id: str | None = None
    referring_visit_id: str | None = None
    transition: str | None = None
    visit_count: int | None = Field(default=None, ge=0)


class BrowserHistoryIngestRequest(BaseModel):
    """Browser history ingest request schema."""

    model_config = ConfigDict(extra="forbid")

    sync_id: UUID
    source_device: str = Field(min_length=1)
    browser: Literal["edge", "brave", "chrome"]
    profile: str = Field(min_length=1)
    synced_at: datetime
    items: list[BrowserHistoryItemRequest] = Field(max_length=1000)


class BrowserHistoryIngestResponse(BaseModel):
    """Browser history ingest response schema."""

    sync_id: str
    accepted: int
    raw_saved: bool
    events_saved: bool
    received_at: datetime
