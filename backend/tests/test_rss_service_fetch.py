from types import SimpleNamespace
from time import gmtime

from app.core.config import FeedSource
from app.services import rss_service as rss_module
from app.services.rss_service import RSSService


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class DummyAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str) -> DummyResponse:
        return DummyResponse("<xml/>")


def _build_entries(count: int) -> list[dict]:
    entries: list[dict] = []
    base_ts = 1_710_000_000
    for i in range(count):
        entries.append(
            {
                "title": f"Item {i}",
                "link": f"https://example.com/{i}",
                "id": f"guid-{i}",
                "summary": "Summary",
                "published_parsed": gmtime(base_ts + i),
            }
        )
    return entries


async def test_fetch_source_items_caps_to_max_and_sorts_desc(monkeypatch) -> None:
    monkeypatch.setattr(rss_module.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(
        rss_module.feedparser,
        "parse",
        lambda _text: SimpleNamespace(entries=_build_entries(25)),
    )

    source = FeedSource(
        id="openai",
        name="OpenAI",
        url="https://openai.com/news/rss.xml",
        max_items=20,
    )
    service = RSSService()

    items = await service.fetch_source_items(source)

    assert len(items) == 20
    assert all(item.source_id == "openai" for item in items)

    published = [item.published_at for item in items]
    assert published == sorted(published, reverse=True)
