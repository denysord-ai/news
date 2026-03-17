import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import AppConfig, FeedSource
from app.models.news import NewsItem
from app.services.arxiv_enrichment_service import ArxivEnrichmentService
from app.services.source_provider import SourceProvider

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(
        self,
        app_config: AppConfig,
        providers: dict[str, SourceProvider],
        arxiv_enrichment_service: ArxivEnrichmentService | None = None,
    ) -> None:
        self._app_config = app_config
        self._providers = providers
        self._arxiv_enrichment_service = arxiv_enrichment_service or ArxivEnrichmentService()

    async def get_aggregated_news(self) -> list[NewsItem]:
        items, _failed_sources = await self.fetch_live_news_with_stats()
        return items

    async def fetch_live_news_with_stats(self) -> tuple[list[NewsItem], int]:
        tasks = [self._fetch_for_source(source) for source in self._app_config.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[NewsItem] = []
        failed_sources = 0
        for source, result in zip(self._app_config.sources, results):
            if isinstance(result, Exception):
                logger.exception("Failed to fetch source id=%s type=%s", source.id, source.type, exc_info=result)
                failed_sources += 1
                continue
            merged.extend(result)

        try:
            merged = await self._arxiv_enrichment_service.enrich_items(merged)
        except Exception:
            logger.exception("Failed arXiv enrichment step; returning original RSS items")

        merged.sort(
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return merged, failed_sources

    async def _fetch_for_source(self, source: FeedSource) -> list[NewsItem]:
        provider = self._providers.get(source.type)
        if provider is not None:
            return await provider.fetch_items(source)

        logger.warning("Unsupported source type for id=%s type=%s", source.id, source.type)
        return []
