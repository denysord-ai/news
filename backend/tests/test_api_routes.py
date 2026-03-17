from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.models.news import NewsItem

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sources_endpoint_contains_openai_source() -> None:
    response = client.get("/api/sources")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == "openai"
    assert payload[0]["type"] == "rss"
    assert payload[0]["max_items"] == 20


class FakeNewsService:
    def list_articles(self, limit=None, offset=None) -> list[NewsItem]:
        return [
            NewsItem(
                id="beta:1",
                source_id="beta",
                source_name="Beta",
                title="New",
                link="https://example.com/new",
                summary="",
                published_at=datetime(2026, 2, 2, tzinfo=UTC),
            ),
            NewsItem(
                id="alpha:1",
                source_id="alpha",
                source_name="Alpha",
                title="Old",
                link="https://example.com/old",
                summary="",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            NewsItem(
                id="alpha:2",
                source_id="alpha",
                source_name="Alpha",
                title="No Date",
                link="https://example.com/no-date",
                summary="",
                published_at=None,
            ),
        ]


def test_news_response_shape_and_sorting(monkeypatch) -> None:
    monkeypatch.setattr(routes.ArticleRepository, "list_articles", FakeNewsService.list_articles)
    response = client.get("/api/news")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)

    required_keys = {
        "id",
        "source_id",
        "source_name",
        "title",
        "link",
        "summary",
        "published_at",
        "announced_at",
        "original_published_at",
        "updated_at",
        "author",
        "tags",
    }

    for item in payload:
        assert required_keys.issubset(item.keys())

    published_values = [
        datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")).astimezone(UTC)
        for item in payload
        if item["published_at"] is not None
    ]
    assert published_values == sorted(published_values, reverse=True)


def test_sync_endpoint_returns_summary(monkeypatch) -> None:
    class FakeSyncService:
        def __init__(self, news_service, article_repository) -> None:
            return None

        async def sync_articles(self):
            return {
                "status": "ok",
                "total_fetched": 10,
                "inserted": 6,
                "updated": 4,
                "failed_sources": 1,
            }

    monkeypatch.setattr(routes, "SyncService", FakeSyncService)
    response = client.post("/api/sync")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "total_fetched": 10,
        "inserted": 6,
        "updated": 4,
        "failed_sources": 1,
    }
