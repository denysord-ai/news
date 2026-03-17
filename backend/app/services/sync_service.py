from pydantic import BaseModel

from app.repositories.article_repository import ArticleRepository
from app.services.news_service import NewsService


class SyncSummary(BaseModel):
    status: str
    total_fetched: int
    inserted: int
    updated: int
    failed_sources: int


class SyncService:
    def __init__(self, news_service: NewsService, article_repository: ArticleRepository) -> None:
        self._news_service = news_service
        self._article_repository = article_repository

    async def sync_articles(self) -> SyncSummary:
        items, failed_sources = await self._news_service.fetch_live_news_with_stats()
        inserted, updated = self._article_repository.upsert_articles(items)

        status = "ok"
        if not items and failed_sources > 0:
            status = "failed"
        elif not items:
            status = "empty"
        elif failed_sources > 0:
            status = "partial"

        return SyncSummary(
            status=status,
            total_fetched=len(items),
            inserted=inserted,
            updated=updated,
            failed_sources=failed_sources,
        )
