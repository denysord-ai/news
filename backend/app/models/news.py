from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class NewsItem(BaseModel):
    id: str
    source_id: str
    source_name: str
    title: str
    link: HttpUrl
    summary: str
    published_at: datetime | None
    announced_at: datetime | None = None
    original_published_at: datetime | None = None
    updated_at: datetime | None = None
    author: str | None = None
    tags: list[str] | None = None


class HealthResponse(BaseModel):
    status: str


class FeedSourceResponse(BaseModel):
    id: str
    name: str
    type: Literal["rss", "html"]
    url: HttpUrl
    max_items: int
