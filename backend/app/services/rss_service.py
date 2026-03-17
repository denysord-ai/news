import calendar
import hashlib
from datetime import UTC, datetime
from time import struct_time
from typing import Any, Mapping

import feedparser
import httpx
from pydantic import ValidationError

from app.core.config import FeedSource
from app.models.news import NewsItem


class RssSourceProvider:
    async def fetch_items(self, source_config: FeedSource) -> list[NewsItem]:
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(str(source_config.url))
            response.raise_for_status()

        parsed = feedparser.parse(response.text)
        entries = parsed.entries if hasattr(parsed, "entries") else []

        normalized = [
            item
            for entry in entries
            if (item := self._normalize_entry(source=source_config, entry=entry)) is not None
        ]

        normalized.sort(
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return normalized[: source_config.max_items]

    def _normalize_entry(self, source: FeedSource, entry: Mapping[str, Any]) -> NewsItem | None:
        title = self._entry_get(entry, "title")
        link = self._entry_get(entry, "link")
        guid = self._entry_get(entry, "id") or self._entry_get(entry, "guid")

        if not title or not link:
            return None

        item_key = str(guid or link)
        stable_hash = hashlib.sha256(item_key.encode("utf-8")).hexdigest()[:16]
        item_id = f"{source.id}:{stable_hash}"

        tags_raw = self._entry_get(entry, "tags") or []
        tags = [
            tag.get("term")
            for tag in tags_raw
            if isinstance(tag, Mapping) and tag.get("term")
        ]

        try:
            return NewsItem(
                id=item_id,
                source_id=source.id,
                source_name=source.name,
                title=str(title),
                link=str(link),
                summary=str(self._entry_get(entry, "summary") or ""),
                published_at=self._parse_entry_date(entry),
                author=self._entry_get(entry, "author"),
                tags=tags or None,
            )
        except ValidationError:
            return None

    def _parse_entry_date(self, entry: Mapping[str, Any]) -> datetime | None:
        published_struct = self._entry_get(entry, "published_parsed")
        if isinstance(published_struct, struct_time):
            return datetime.fromtimestamp(calendar.timegm(published_struct), tz=UTC)

        updated_struct = self._entry_get(entry, "updated_parsed")
        if isinstance(updated_struct, struct_time):
            return datetime.fromtimestamp(calendar.timegm(updated_struct), tz=UTC)

        published_raw = self._entry_get(entry, "published")
        if isinstance(published_raw, str):
            try:
                parsed_dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if parsed_dt.tzinfo is None:
                    return parsed_dt.replace(tzinfo=UTC)
                return parsed_dt.astimezone(UTC)
            except ValueError:
                return None

        return None

    @staticmethod
    def _entry_get(entry: Mapping[str, Any], key: str) -> Any:
        if isinstance(entry, Mapping):
            value = entry.get(key)
            if value is not None:
                return value

        return getattr(entry, key, None)


class RSSService(RssSourceProvider):
    async def fetch_source_items(self, source: FeedSource) -> list[NewsItem]:
        return await self.fetch_items(source)
