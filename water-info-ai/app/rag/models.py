"""Core RAG data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator


class RetrievalMode(str, Enum):
    ANSWER = "answer"
    PREFLIGHT_PLAN = "preflight_plan"
    PREFLIGHT_RISK = "preflight_risk"
    VALIDATION = "validation"


DOC_TYPES = {"regulation", "manual", "sop", "template", "case_study"}
AUTHORITY_LEVELS = {"national", "provincial", "municipal", "district"}


class MetadataFilter(BaseModel):
    doc_type: str | None = None
    region_code: str | None = None
    basin_code: str | None = None
    station_id: str | None = None
    effective_date: date | None = None
    expire_date: date | None = None
    authority_level: str | None = None
    risk_level_applicable: str | None = None
    include_expired: bool = False

    @field_validator("doc_type")
    @classmethod
    def _validate_doc_type(cls, value: str | None) -> str | None:
        if value is not None and value not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {sorted(DOC_TYPES)}")
        return value

    @field_validator("authority_level")
    @classmethod
    def _validate_authority_level(cls, value: str | None) -> str | None:
        if value is not None and value not in AUTHORITY_LEVELS:
            raise ValueError(f"authority_level must be one of {sorted(AUTHORITY_LEVELS)}")
        return value


@dataclass
class TextBlock:
    text: str
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class LoadedDocument:
    title: str
    mime: str
    raw_text: str
    blocks: list[TextBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ChunkCandidate:
    chunk_index: int
    content: str
    token_count: int
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    search_text: str = ""


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    document_title: str
    source_uri: str
    content: str
    heading_path: list[str] = field(default_factory=list)
    score: float = 0.0
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict = field(default_factory=dict)


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    return metadata.get(key)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def metadata_matches_filter(result: SearchResult | dict, metadata_filter: MetadataFilter | None) -> bool:
    if metadata_filter is None:
        metadata_filter = MetadataFilter()
    metadata = dict(result.get("metadata") or {}) if isinstance(result, dict) else dict(result.metadata or {})

    expire_date = _parse_date(_metadata_value(metadata, "expire_date"))
    if expire_date is not None and expire_date < date.today() and not metadata_filter.include_expired:
        return False

    for key in [
        "doc_type",
        "basin_code",
        "station_id",
        "authority_level",
        "risk_level_applicable",
    ]:
        expected = getattr(metadata_filter, key)
        if expected is not None and str(_metadata_value(metadata, key) or "") != str(expected):
            return False

    # Region is a priority scope: exact match passes; absent metadata is allowed
    # so legacy documents remain retrievable during incremental rollout.
    if metadata_filter.region_code is not None:
        region = _metadata_value(metadata, "region_code")
        if region and str(region) != metadata_filter.region_code:
            return False

    effective_date = metadata_filter.effective_date
    document_effective = _parse_date(_metadata_value(metadata, "effective_date"))
    if effective_date is not None and document_effective is not None and document_effective > effective_date:
        return False

    requested_expire = metadata_filter.expire_date
    if requested_expire is not None and expire_date is not None and expire_date < requested_expire:
        return False

    return True
