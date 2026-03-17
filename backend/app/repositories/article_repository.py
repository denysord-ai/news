from datetime import UTC, datetime
import hashlib

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Article
from app.models.news import NewsItem


class ArticleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_articles(self, limit: int | None = None, offset: int | None = None) -> list[NewsItem]:
        stmt = select(Article).order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        rows = self._db.execute(stmt).scalars().all()
        return [self._to_news_item(row) for row in rows]

    def upsert_articles(self, items: list[NewsItem]) -> tuple[int, int]:
        if not items:
            return 0, 0

        unique_items_by_url: dict[str, NewsItem] = {}
        for item in items:
            unique_items_by_url[str(item.link)] = item

        deduplicated_items = list(unique_items_by_url.values())
        urls = list(unique_items_by_url.keys())
        existing_rows = self._db.execute(select(Article).where(Article.url.in_(urls))).scalars().all()
        existing_by_url = {row.url: row for row in existing_rows}
        existing_urls = set(existing_by_url.keys())

        now = datetime.now(UTC)
        records = [
            {
                "article_id": item.id,
                "url": str(item.link),
                "source_id": item.source_id,
                "source_name": item.source_name,
                "title": item.title,
                "summary": item.summary or None,
                "published_at": item.published_at,
                "announced_at": item.announced_at,
                "original_published_at": item.original_published_at,
                "updated_at": item.updated_at,
                "author": item.author,
                "tags": item.tags,
                "created_at": now,
                "updated_record_at": now,
                "last_seen_at": now,
            }
            for item in deduplicated_items
        ]

        if self._db.bind is not None and self._db.bind.dialect.name == "postgresql":
            stmt = pg_insert(Article).values(records)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=[Article.url],
                set_={
                    "article_id": stmt.excluded.article_id,
                    "source_id": stmt.excluded.source_id,
                    "source_name": stmt.excluded.source_name,
                    "title": stmt.excluded.title,
                    "summary": stmt.excluded.summary,
                    "published_at": stmt.excluded.published_at,
                    "announced_at": stmt.excluded.announced_at,
                    "original_published_at": stmt.excluded.original_published_at,
                    "updated_at": stmt.excluded.updated_at,
                    "author": stmt.excluded.author,
                    "tags": stmt.excluded.tags,
                    "updated_record_at": now,
                    "last_seen_at": now,
                },
            )
            self._db.execute(upsert_stmt)
        else:
            for record in records:
                existing = existing_by_url.get(record["url"])
                if existing is None:
                    self._db.add(Article(**record))
                    continue

                existing.article_id = record["article_id"]
                existing.source_id = record["source_id"]
                existing.source_name = record["source_name"]
                existing.title = record["title"]
                existing.summary = record["summary"]
                existing.published_at = record["published_at"]
                existing.announced_at = record["announced_at"]
                existing.original_published_at = record["original_published_at"]
                existing.updated_at = record["updated_at"]
                existing.author = record["author"]
                existing.tags = record["tags"]
                existing.updated_record_at = now
                existing.last_seen_at = now

        self._db.commit()

        inserted = sum(1 for url in urls if url not in existing_urls)
        updated = len(urls) - inserted
        return inserted, updated

    @staticmethod
    def _to_news_item(article: Article) -> NewsItem:
        stable_hash = hashlib.sha256(article.url.encode("utf-8")).hexdigest()[:16]
        fallback_id = article.article_id or f"{article.source_id}:{stable_hash}"
        return NewsItem(
            id=fallback_id,
            source_id=article.source_id,
            source_name=article.source_name,
            title=article.title,
            link=article.url,
            summary=article.summary or "",
            published_at=article.published_at,
            announced_at=article.announced_at,
            original_published_at=article.original_published_at,
            updated_at=article.updated_at,
            author=article.author,
            tags=article.tags,
        )
