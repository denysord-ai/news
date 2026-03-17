from typing import Protocol

from app.core.config import FeedSource
from app.models.news import NewsItem


class SourceProvider(Protocol):
    async def fetch_items(self, source_config: FeedSource) -> list[NewsItem]:
        ...
