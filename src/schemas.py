from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
	role: Literal["user", "assistant", "system"]
	content: str


class TranscriptRequest(BaseModel):
	user_id: str
	history: List[Message]
	metadata: Optional[dict[str, Any]] = None


class StoreMemoryItem(BaseModel):
	id: str
	content: str
	layer: Literal["short-term", "semantic", "long-term"]
	type: Literal["explicit", "implicit"]
	confidence: float
	ttl: Optional[int] = None
	timestamp: Optional[datetime] = None
	metadata: Optional[dict[str, Any]] = None


class StoreResponse(BaseModel):
	memories_created: int
	ids: List[str]
	summary: Optional[str] = None
	memories: Optional[List[StoreMemoryItem]] = None


class RetrieveItem(BaseModel):
	id: str
	content: str
	layer: Literal["short-term", "semantic", "long-term"]
	type: Literal["explicit", "implicit"]
	score: float
	metadata: Optional[dict[str, Any]] = None


class Pagination(BaseModel):
	limit: int = 10
	offset: int = 0
	total: int = 0


class RetrieveResponse(BaseModel):
	results: List[RetrieveItem]
	pagination: Pagination


class ForgetRequest(BaseModel):
	scopes: List[Literal["short-term", "semantic", "long-term"]] = Field(default_factory=list)
	dry_run: bool = False


class MaintenanceRequest(BaseModel):
	jobs: List[Literal["ttl_cleanup", "promotion", "compaction"]] = Field(default_factory=list)
	since_hours: Optional[int] = None


class MaintenanceResponse(BaseModel):
	jobs_started: List[str]
	status: Literal["running", "queued"] = "running"
	started_at: datetime = Field(default_factory=datetime.utcnow)


# Structured retrieval
class StructuredRetrieveRequest(BaseModel):
	user_id: str
	query: Optional[str] = None
	limit: int = Field(default=50, ge=1, le=100)


class StructuredRetrieveResponse(BaseModel):
	emotions: List[RetrieveItem] = Field(default_factory=list)
	behaviors: List[RetrieveItem] = Field(default_factory=list)
	personal: List[RetrieveItem] = Field(default_factory=list)
	professional: List[RetrieveItem] = Field(default_factory=list)
	habits: List[RetrieveItem] = Field(default_factory=list)
	skills_tools: List[RetrieveItem] = Field(default_factory=list)
	projects: List[RetrieveItem] = Field(default_factory=list)
	relationships: List[RetrieveItem] = Field(default_factory=list)
	learning_journal: List[RetrieveItem] = Field(default_factory=list)
	other: List[RetrieveItem] = Field(default_factory=list)

