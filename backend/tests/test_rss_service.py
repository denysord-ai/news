from app.core.config import FeedSource
from app.services.rss_service import RSSService


def test_normalize_entry_builds_expected_item_and_stable_id() -> None:
    source = FeedSource(id="openai", name="OpenAI", url="https://openai.com/news/rss.xml", max_items=20)
    entry = {
        "title": "Release",
        "link": "https://openai.com/news/release",
        "id": "guid-123",
        "summary": "Summary text",
        "author": "OpenAI",
        "published": "2026-03-12T10:00:00Z",
        "tags": [{"term": "Research"}, {"term": "Product"}],
    }

    service = RSSService()
    item = service._normalize_entry(source=source, entry=entry)

    assert item is not None
    assert item.id.startswith("openai:")
    assert item.source_id == "openai"
    assert item.source_name == "OpenAI"
    assert item.title == "Release"
    assert str(item.link) == "https://openai.com/news/release"
    assert item.summary == "Summary text"
    assert item.author == "OpenAI"
    assert item.tags == ["Research", "Product"]
    assert item.published_at is not None


def test_normalize_entry_returns_none_when_required_fields_missing() -> None:
    source = FeedSource(id="openai", name="OpenAI", url="https://openai.com/news/rss.xml", max_items=20)
    service = RSSService()

    assert service._normalize_entry(source=source, entry={"title": "Missing link"}) is None
    assert service._normalize_entry(source=source, entry={"link": "https://example.com"}) is None


def test_normalize_entry_returns_none_for_invalid_link() -> None:
    source = FeedSource(id="openai", name="OpenAI", url="https://openai.com/news/rss.xml", max_items=20)
    service = RSSService()

    entry = {
        "title": "Bad Link",
        "link": "not-a-url",
        "id": "bad-guid",
    }

    assert service._normalize_entry(source=source, entry=entry) is None
