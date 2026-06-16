"""Pydantic request/response models (LLD §1)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app import settings


class UserProfile(BaseModel):
    userId: str
    email: str
    role: str = "user"
    timezone: str = "America/Los_Angeles"
    summaryTimePref: str = "17:00"
    lensCount: int = 0
    firstSignIn: bool = False


class UserUpdate(BaseModel):
    timezone: Optional[str] = None
    summaryTimePref: Optional[str] = None

    @field_validator("summaryTimePref")
    @classmethod
    def valid_time(cls, v):
        if v is None:
            return v
        h, m = v.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError("summaryTimePref must be HH:MM")
        return v

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, v):
        if v is None:
            return v
        from zoneinfo import ZoneInfo

        ZoneInfo(v)  # raises if unknown
        return v


class LensCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    topicIds: list[str] = Field(max_length=settings.MAX_TOPICS_PER_LENS)
    trackedAssetIds: list[str] = Field(
        default_factory=list, max_length=settings.MAX_ASSETS_PER_LENS
    )


class LensUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    topicIds: Optional[list[str]] = Field(default=None, max_length=settings.MAX_TOPICS_PER_LENS)
    trackedAssetIds: Optional[list[str]] = Field(
        default=None, max_length=settings.MAX_ASSETS_PER_LENS
    )


class Lens(BaseModel):
    lensId: str
    name: str
    topicIds: list[str]
    trackedAssetIds: list[str]
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class FeedItem(BaseModel):
    articleId: str
    topicId: str
    publishedAt: str
    title: str
    abstraction: Optional[str] = None
    excerpt: str
    source: str
    url: str


class FeedPage(BaseModel):
    items: list[FeedItem]
    nextCursor: Optional[str] = None


class AssetMove(BaseModel):
    assetId: str
    symbol: str
    move: float
    open: float
    close: float


class Summary(BaseModel):
    date: str
    lensId: str
    body: str
    assetMoves: list[AssetMove] = []
    rationale: str = ""
    editedByUser: bool = False
    generatedAt: Optional[str] = None
    version: int = 1


class SummaryEdit(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    version: int


class ChatAttachment(BaseModel):
    title: str = Field(max_length=400)
    source: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=2000)
    url: str = Field(default="", max_length=1000)


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=10)


class ChatResponse(BaseModel):
    messageId: str
    response: str


class FeedbackCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    context: Optional[str] = Field(default=None, max_length=1000)


class AdminMetrics(BaseModel):
    userCount: int
    signinsToday: int
    activeToday: int


class SuggestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SuggestResponse(BaseModel):
    topicIds: list[str]
    assetIds: list[str]
