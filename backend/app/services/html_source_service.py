import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from app.core.config import FeedSource
from app.models.news import NewsItem

logger = logging.getLogger(__name__)


class HtmlSourceProvider:
    async def fetch_items(self, source_config: FeedSource) -> list[NewsItem]:
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(str(source_config.url))
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        base_url = str(source_config.url)

        if source_config.id == "anthropic_news":
            raw_entries = self._parse_anthropic_news_page(soup=soup, base_url=base_url)
        elif source_config.id == "anthropic_engineering":
            raw_entries = await self._parse_anthropic_engineering_page(
                soup=soup,
                base_url=base_url,
                client=client,
            )
        elif source_config.id == "claude_blog":
            raw_entries = self._parse_claude_blog_page(soup=soup, base_url=base_url)
        elif source_config.id == "devin_cognition":
            raw_entries = self._parse_devin_cognition_page(soup=soup, base_url=base_url)
        else:
            raw_entries = self._parse_listing_page(soup=soup, base_url=base_url, path_hint="")

        items: list[NewsItem] = []
        for entry in raw_entries:
            item = self._normalize_entry(source=source_config, entry=entry)
            if item is not None:
                items.append(item)

        items.sort(
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return items[: source_config.max_items]

    def _parse_listing_page(
        self,
        soup: BeautifulSoup,
        base_url: str,
        path_hint: str,
    ) -> list[dict[str, str | None]]:
        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc

        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()

        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            if not href:
                continue

            absolute_link = urljoin(base_url, href)
            parsed_link = urlparse(absolute_link)
            if parsed_link.netloc != domain:
                continue

            if path_hint and path_hint not in parsed_link.path:
                continue

            title = anchor.get_text(" ", strip=True)
            if not title:
                continue

            if absolute_link in seen_links:
                continue
            seen_links.add(absolute_link)

            article_node = self._find_article_context(anchor)
            summary = self._extract_summary(article_node)
            published_text = self._extract_published_text(article_node)

            entries.append(
                {
                    "title": title,
                    "link": absolute_link,
                    "summary": summary,
                    "published": published_text,
                }
            )

        return entries

    def _parse_anthropic_news_page(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, str | None]]:
        parsed_base = urlparse(base_url)
        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()

        for anchor in soup.select("a[href*='/news/']"):
            href = anchor.get("href")
            if not href:
                continue

            absolute_link = urljoin(base_url, href)
            parsed_link = urlparse(absolute_link)
            if parsed_link.netloc != parsed_base.netloc:
                continue
            if "/news/" not in parsed_link.path:
                continue
            if absolute_link in seen_links:
                continue

            card = (
                anchor.find_parent("li")
                or anchor.find_parent("div")
                or anchor.find_parent("article")
                or anchor
            )

            title = self._extract_anthropic_news_title(anchor=anchor, card=card)
            if not title:
                continue

            summary = self._extract_summary(card)
            published_text = self._extract_published_text(card)

            seen_links.add(absolute_link)
            entries.append(
                {
                    "title": title,
                    "link": absolute_link,
                    "summary": summary,
                    "published": published_text,
                }
            )

        return entries

    def _extract_anthropic_news_title(self, anchor: Tag, card: Tag) -> str:
        # Anthropic News uses separate title elements for featured and list cards.
        title_node = card.select_one(
            "[class*='featuredTitle'], [class*='PublicationList'][class*='title'], [class*='__title']"
        )
        if title_node is not None:
            title_text = title_node.get_text(" ", strip=True)
            if title_text:
                return title_text

        raw_text = anchor.get_text(" ", strip=True)
        if not raw_text:
            return ""

        # Fallback: remove leading date/category fragments if present in combined anchor text.
        if len(raw_text) > 220:
            return raw_text[:220].strip()

        return raw_text

    def _parse_claude_blog_page(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, str | None]]:
        parsed_base = urlparse(base_url)
        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()

        for card in soup.select("article.card_blog_list_wrap"):
            link_node = card.select_one("a.clickable_link[href]")
            title_node = card.select_one(".card_blog_list_title")

            if link_node is None or title_node is None:
                continue

            href = link_node.get("href")
            if not href:
                continue

            absolute_link = urljoin(base_url, href)
            parsed_link = urlparse(absolute_link)
            if parsed_link.netloc != parsed_base.netloc:
                continue
            if "/blog/" not in parsed_link.path:
                continue
            if "/blog/category/" in parsed_link.path:
                continue
            if absolute_link in seen_links:
                continue

            title = title_node.get_text(" ", strip=True)
            if not title:
                continue

            date_node = card.select_one(".u-display-none")
            published_text = date_node.get_text(" ", strip=True) if date_node is not None else None

            summary_node = card.select_one("p")
            summary = summary_node.get_text(" ", strip=True) if summary_node is not None else ""

            seen_links.add(absolute_link)
            entries.append(
                {
                    "title": title,
                    "link": absolute_link,
                    "summary": summary,
                    "published": published_text,
                }
            )

        return entries

    def _parse_devin_cognition_page(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, str | None]]:
        parsed_base = urlparse(base_url)
        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()

        for card in soup.select("li.blog-post-list__list-item"):
            link_node = card.select_one("a.o-blog-preview[href]")
            if link_node is None:
                continue

            href = link_node.get("href")
            if not href:
                continue

            absolute_link = urljoin(base_url, href)
            parsed_link = urlparse(absolute_link)
            if parsed_link.netloc != parsed_base.netloc:
                continue

            path_parts = [part for part in parsed_link.path.split("/") if part]
            # Keep only post pages: /blog/<slug>
            if len(path_parts) != 2 or path_parts[0] != "blog" or path_parts[1].isdigit():
                continue
            if absolute_link in seen_links:
                continue

            title_node = card.select_one("h3.o-blog-preview__title")
            if title_node is None:
                continue
            title = title_node.get_text(" ", strip=True)
            if not title:
                continue

            date_text = self._extract_cognition_date(card)

            summary_node = card.select_one("p.o-blog-preview__intro")
            summary = summary_node.get_text(" ", strip=True) if summary_node is not None else ""

            seen_links.add(absolute_link)
            entries.append(
                {
                    "title": title,
                    "link": absolute_link,
                    "summary": summary,
                    "published": date_text,
                }
            )

        return entries

    def _extract_cognition_date(self, card: Tag) -> str | None:
        date_node = card.select_one(".o-blog-preview__meta-date")
        if date_node is None:
            return None

        text = date_node.get_text(" ", strip=True)
        match = re.search(r"[A-Za-z]+ \d{1,2}, \d{4}", text)
        if match:
            return match.group(0)

        return None

    async def _parse_anthropic_engineering_page(
        self,
        soup: BeautifulSoup,
        base_url: str,
        client: httpx.AsyncClient,
    ) -> list[dict[str, str | None]]:
        parsed_base = urlparse(base_url)
        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()
        missing_date_indexes: list[tuple[int, str]] = []

        for card in soup.select("article[class*='ArticleList-module'][class*='__article']"):
            link_node = card.select_one("a[class*='__cardLink'][href]")
            if link_node is None:
                continue

            href = link_node.get("href")
            if not href:
                continue

            absolute_link = urljoin(base_url, href)
            parsed_link = urlparse(absolute_link)
            if parsed_link.netloc != parsed_base.netloc:
                continue
            if "/engineering/" not in parsed_link.path:
                continue
            if absolute_link in seen_links:
                continue

            title_node = card.select_one("h2, h3")
            title = title_node.get_text(" ", strip=True) if title_node is not None else ""
            if not title:
                continue

            summary_node = card.select_one("p[class*='__summary'], p")
            summary = summary_node.get_text(" ", strip=True) if summary_node is not None else ""

            date_node = card.select_one("[class*='__date']")
            published_text = date_node.get_text(" ", strip=True) if date_node is not None else None

            seen_links.add(absolute_link)
            entries.append(
                {
                    "title": title,
                    "link": absolute_link,
                    "summary": summary,
                    "published": published_text,
                }
            )

            if not published_text:
                missing_date_indexes.append((len(entries) - 1, absolute_link))

        if missing_date_indexes:
            tasks = [self._fetch_engineering_article_date(client=client, article_url=url) for _, url in missing_date_indexes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (index, _url), result in zip(missing_date_indexes, results):
                if isinstance(result, Exception):
                    continue
                if result:
                    entries[index]["published"] = result

        # Keep only entries with a concrete date to satisfy stable downstream sorting and UI rendering.
        return [entry for entry in entries if entry.get("published")]

    async def _fetch_engineering_article_date(
        self,
        client: httpx.AsyncClient,
        article_url: str,
    ) -> str | None:
        try:
            response = await client.get(article_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        html = response.text
        patterns = [
            r'"article":\{.*?"_createdAt":"([^"]+)"',
            r'\\"article\\":\{.*?\\"_createdAt\\":\\"([^"]+)\\"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.DOTALL)
            if match:
                return match.group(1)

        return None

    def _normalize_entry(
        self,
        source: FeedSource,
        entry: dict[str, str | None],
    ) -> NewsItem | None:
        title = entry.get("title")
        link = entry.get("link")

        if not title or not link:
            return None

        stable_hash = hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]
        item_id = f"{source.id}:{stable_hash}"

        try:
            return NewsItem(
                id=item_id,
                source_id=source.id,
                source_name=source.name,
                title=title,
                link=link,
                summary=entry.get("summary") or "",
                published_at=self._parse_date(entry.get("published")),
                author=None,
                tags=None,
            )
        except ValidationError:
            logger.debug("Skipping invalid HTML entry for source=%s link=%s", source.id, link)
            return None

    def _find_article_context(self, anchor: Tag) -> Tag:
        return anchor.find_parent("article") or anchor.find_parent("li") or anchor.parent or anchor

    def _extract_summary(self, node: Tag) -> str:
        paragraph = node.find("p")
        if paragraph is None:
            return ""

        return paragraph.get_text(" ", strip=True)

    def _extract_published_text(self, node: Tag) -> str | None:
        time_tag = node.find("time")
        if time_tag is not None:
            return (time_tag.get("datetime") or time_tag.get_text(" ", strip=True) or "").strip() or None

        for candidate in self._candidate_text_nodes(node):
            parsed = self._parse_date(candidate)
            if parsed is not None:
                return candidate

        return None

    def _candidate_text_nodes(self, node: Tag) -> Iterable[str]:
        for text_node in node.stripped_strings:
            text = text_node.strip()
            if text:
                yield text

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None

        raw = value.strip()
        if not raw:
            return None

        iso_candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso_candidate)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            pass

        try:
            parsed = parsedate_to_datetime(raw)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except (TypeError, ValueError):
            pass

        known_formats = [
            "%B %d, %Y",
            "%b %d, %Y",
            "%B %d %Y",
            "%b %d %Y",
            "%Y-%m-%d",
        ]
        for fmt in known_formats:
            try:
                parsed = datetime.strptime(raw, fmt)
                return parsed.replace(tzinfo=UTC)
            except ValueError:
                continue

        return None


class HTMLSourceService(HtmlSourceProvider):
    async def fetch_source_items(self, source: FeedSource) -> list[NewsItem]:
        return await self.fetch_items(source)
