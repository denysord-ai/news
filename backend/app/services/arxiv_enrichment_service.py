import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
import xml.etree.ElementTree as ET

import httpx

from app.models.news import NewsItem

logger = logging.getLogger(__name__)


@dataclass
class ArxivMetadata:
    arxiv_id: str
    published: datetime | None
    updated: datetime | None
    title: str | None
    summary: str | None
    authors: list[str]


class ArxivEnrichmentService:
    API_URL = "http://export.arxiv.org/api/query"

    async def enrich_items(self, items: list[NewsItem]) -> list[NewsItem]:
        arxiv_item_ids: set[str] = set()
        item_to_arxiv_id: dict[str, str] = {}

        for item in items:
            if item.source_id != "arxiv_ai":
                continue

            arxiv_id = self.extract_arxiv_id(str(item.link))
            if not arxiv_id:
                continue

            item_to_arxiv_id[item.id] = arxiv_id
            arxiv_item_ids.add(arxiv_id)

        if not arxiv_item_ids:
            return items

        sorted_arxiv_ids = sorted(arxiv_item_ids)
        try:
            metadata_by_id = await self.fetch_metadata(sorted_arxiv_ids)
        except Exception:
            logger.exception(
                "Failed to fetch arXiv metadata for %s items; skipping enrichment",
                len(sorted_arxiv_ids),
            )
            return items

        enriched: list[NewsItem] = []
        for item in items:
            if item.source_id != "arxiv_ai":
                enriched.append(item)
                continue

            arxiv_id = item_to_arxiv_id.get(item.id)
            metadata = metadata_by_id.get(arxiv_id) if arxiv_id else None
            if metadata is None:
                enriched.append(item)
                continue

            announced_at = item.published_at
            original_published_at = metadata.published
            updated_at = metadata.updated
            # "Submitted" date is represented by arXiv API "published".
            published_at = original_published_at or updated_at or announced_at or item.published_at

            enriched.append(
                item.model_copy(
                    update={
                        "title": metadata.title or item.title,
                        "summary": metadata.summary or item.summary,
                        "author": ", ".join(metadata.authors) if metadata.authors else item.author,
                        "announced_at": announced_at,
                        "original_published_at": original_published_at,
                        "updated_at": updated_at,
                        "published_at": published_at,
                    }
                )
            )

        return enriched

    async def fetch_metadata(self, arxiv_ids: list[str]) -> dict[str, ArxivMetadata]:
        if not arxiv_ids:
            return {}

        id_list = ",".join(arxiv_ids)
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                self.API_URL,
                params={
                    "id_list": id_list,
                    "start": 0,
                    "max_results": len(arxiv_ids),
                },
            )
            response.raise_for_status()

        return self.parse_api_response(response.text)

    def parse_api_response(self, xml_payload: str) -> dict[str, ArxivMetadata]:
        root = ET.fromstring(xml_payload)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        metadata_by_id: dict[str, ArxivMetadata] = {}
        for entry in root.findall("atom:entry", ns):
            id_text = entry.findtext("atom:id", default="", namespaces=ns)
            arxiv_id = self.extract_arxiv_id(id_text)
            if not arxiv_id:
                continue

            title = self._clean_text(entry.findtext("atom:title", default="", namespaces=ns))
            summary = self._clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
            published = self._parse_iso_datetime(entry.findtext("atom:published", default="", namespaces=ns))
            updated = self._parse_iso_datetime(entry.findtext("atom:updated", default="", namespaces=ns))

            authors: list[str] = []
            for author_node in entry.findall("atom:author", ns):
                name = self._clean_text(author_node.findtext("atom:name", default="", namespaces=ns))
                if name:
                    authors.append(name)

            metadata_by_id[arxiv_id] = ArxivMetadata(
                arxiv_id=arxiv_id,
                published=published,
                updated=updated,
                title=title or None,
                summary=summary or None,
                authors=authors,
            )

        return metadata_by_id

    def extract_arxiv_id(self, raw_value: str) -> str | None:
        patterns = [
            r"arxiv\.org/(?:abs|pdf)/((?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)",
            r"^((?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)$",
        ]

        value = raw_value.strip().replace(".pdf", "")
        for pattern in patterns:
            match = re.search(pattern, value, flags=re.IGNORECASE)
            if not match:
                continue

            arxiv_id = match.group(1)
            return re.sub(r"v\d+$", "", arxiv_id, flags=re.IGNORECASE)

        return None

    def _parse_iso_datetime(self, value: str) -> datetime | None:
        raw = value.strip()
        if not raw:
            return None

        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            return None

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(value.split())
