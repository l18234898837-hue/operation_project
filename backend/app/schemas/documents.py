from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, Field


DocumentTypeLiteral = Literal["PDF", "Word", "Excel", "Markdown", "TXT"]
DocumentCategoryLiteral = Literal[
    "inverter",
    "inspection",
    "grid-quality",
    "modules",
    "manual",
    "cases",
    "standards",
    "uncategorized",
]
DocumentParseStatusLiteral = Literal["uploaded", "processing", "ready", "failed"]
DocumentEnableStatusLiteral = Literal["enabled", "disabled"]


class DocumentItemSchema(BaseModel):
    id: uuid.UUID
    name: str
    type: DocumentTypeLiteral
    category: DocumentCategoryLiteral
    parseStatus: DocumentParseStatusLiteral
    enableStatus: DocumentEnableStatusLiteral
    updatedAt: str
    failureReason: str | None
    progress: int | None = Field(ge=0, le=100)


class DocumentEnableRequest(BaseModel):
    enabled: bool


class DocumentUploadErrorSchema(BaseModel):
    message: str
