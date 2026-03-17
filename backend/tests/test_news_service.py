from datetime import UTC, datetime

from app.core.config import AppConfig, FeedSource
from app.models.news import NewsItem
from app.services.news_service import NewsService


class FakeRSSService:
    async def fetch_items(self, source: FeedSource) -> list[NewsItem]:
        if source.id == "broken":
            raise RuntimeError("source failed")

        if source.id == "alpha":
            return [
                NewsItem(
                    id="alpha:1",
                    source_id="alpha",
                    source_name="Alpha",
                    title="Older",
                    link="https://example.com/a1",
                    summary="",
                    published_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                NewsItem(
                    id="alpha:2",
                    source_id="alpha",
                    source_name="Alpha",
                    title="No date",
                    link="https://example.com/a2",
                    summary="",
                    published_at=None,
                ),
            ]

        return [
            NewsItem(
                id="beta:1",
                source_id="beta",
                source_name="Beta",
                title="Newest",
                link="https://example.com/b1",
                summary="",
                published_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        ]


class FakeHTMLSourceService:
    async def fetch_items(self, source: FeedSource) -> list[NewsItem]:
        if source.id == "anthropic_news":
            return [
                NewsItem(
                    id="anthropic_news:1",
                    source_id="anthropic_news",
                    source_name="Anthropic News",
                    title="Newest HTML",
                    link="https://www.anthropic.com/news/newest",
                    summary="",
                    published_at=datetime(2026, 3, 1, tzinfo=UTC),
                )
            ]
        return []


class FailingArxivEnrichmentService:
    async def enrich_items(self, items: list[NewsItem]) -> list[NewsItem]:
        raise RuntimeError("arxiv enrichment failed")


async def test_get_aggregated_news_sorts_desc_and_ignores_source_failures() -> None:
    app_config = AppConfig(
        sources=[
            FeedSource(id="alpha", name="Alpha", type="rss", url="https://example.com/a.xml", max_items=20),
            FeedSource(
                id="broken",
                name="Broken",
                type="rss",
                url="https://example.com/broken.xml",
                max_items=20,
            ),
            FeedSource(id="beta", name="Beta", type="rss", url="https://example.com/b.xml", max_items=20),
            FeedSource(
                id="anthropic_news",
                name="Anthropic News",
                type="html",
                url="https://www.anthropic.com/news",
                max_items=20,
            ),
        ]
    )
    service = NewsService(
        app_config=app_config,
        providers={
            "rss": FakeRSSService(),
            "html": FakeHTMLSourceService(),
        },
    )

    items = await service.get_aggregated_news()

    assert [item.id for item in items] == ["anthropic_news:1", "beta:1", "alpha:1", "alpha:2"]


async def test_get_aggregated_news_keeps_original_items_when_arxiv_enrichment_fails() -> None:
    class ArxivOnlyRSSProvider:
        async def fetch_items(self, source: FeedSource) -> list[NewsItem]:
            return [
                NewsItem(
                    id="arxiv_ai:1",
                    source_id="arxiv_ai",
                    source_name="arXiv AI",
                    title="RSS arXiv title",
                    link="https://arxiv.org/abs/2503.12345",
                    summary="",
                    published_at=datetime(2026, 3, 1, tzinfo=UTC),
                )
            ]

    app_config = AppConfig(
        sources=[
            FeedSource(
                id="arxiv_ai",
                name="arXiv AI",
                type="rss",
                url="https://export.arxiv.org/rss/cs.AI",
                max_items=20,
            )
        ]
    )
    service = NewsService(
        app_config=app_config,
        providers={"rss": ArxivOnlyRSSProvider(), "html": FakeHTMLSourceService()},
        arxiv_enrichment_service=FailingArxivEnrichmentService(),
    )

    items = await service.get_aggregated_news()

    assert len(items) == 1
    assert items[0].source_id == "arxiv_ai"
    assert items[0].title == "RSS arXiv title"
