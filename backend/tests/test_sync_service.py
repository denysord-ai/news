from datetime import UTC, datetime

from app.models.news import NewsItem
from app.services.sync_service import SyncService


class FakeNewsService:
    async def fetch_live_news_with_stats(self):
        return (
            [
                NewsItem(
                    id="item:1",
                    source_id="openai",
                    source_name="OpenAI",
                    title="Title",
                    link="https://example.com/1",
                    summary="",
                    published_at=datetime(2026, 3, 1, tzinfo=UTC),
                )
            ],
            1,
        )


class FakeArticleRepository:
    def upsert_articles(self, items):
        assert len(items) == 1
        return 1, 0


async def test_sync_service_returns_summary() -> None:
    service = SyncService(news_service=FakeNewsService(), article_repository=FakeArticleRepository())

    result = await service.sync_articles()

    assert result.status == "partial"
    assert result.total_fetched == 1
    assert result.inserted == 1
    assert result.updated == 0
    assert result.failed_sources == 1
