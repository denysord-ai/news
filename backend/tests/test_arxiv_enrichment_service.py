from datetime import UTC, datetime

from app.models.news import NewsItem
from app.services.arxiv_enrichment_service import ArxivEnrichmentService, ArxivMetadata


def test_extract_arxiv_id_from_supported_formats() -> None:
    service = ArxivEnrichmentService()

    assert service.extract_arxiv_id("https://arxiv.org/abs/2503.12345") == "2503.12345"
    assert service.extract_arxiv_id("https://arxiv.org/pdf/2503.12345v2.pdf") == "2503.12345"
    assert service.extract_arxiv_id("http://arxiv.org/abs/cs/0112017") == "cs/0112017"
    assert service.extract_arxiv_id("not-an-arxiv-link") is None


def test_parse_arxiv_atom_response() -> None:
    xml_payload = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2503.12345v2</id>
        <published>2025-03-01T12:00:00Z</published>
        <updated>2026-03-02T12:00:00Z</updated>
        <title>  Sample Paper Title  </title>
        <summary>  Sample summary text.  </summary>
        <author><name>Author One</name></author>
        <author><name>Author Two</name></author>
      </entry>
    </feed>
    """

    service = ArxivEnrichmentService()
    parsed = service.parse_api_response(xml_payload)

    assert "2503.12345" in parsed
    metadata = parsed["2503.12345"]
    assert metadata.title == "Sample Paper Title"
    assert metadata.summary == "Sample summary text."
    assert metadata.authors == ["Author One", "Author Two"]
    assert metadata.published == datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
    assert metadata.updated == datetime(2026, 3, 2, 12, 0, tzinfo=UTC)


async def test_enrich_items_applies_priority_and_extra_fields(monkeypatch) -> None:
    service = ArxivEnrichmentService()

    async def fake_fetch_metadata(arxiv_ids: list[str]) -> dict[str, ArxivMetadata]:
        assert arxiv_ids == ["2503.12345"]
        return {
            "2503.12345": ArxivMetadata(
                arxiv_id="2503.12345",
                published=datetime(2025, 3, 1, 12, 0, tzinfo=UTC),
                updated=datetime(2026, 3, 2, 12, 0, tzinfo=UTC),
                title="Canonical Title",
                summary="Canonical summary",
                authors=["Alice", "Bob"],
            )
        }

    monkeypatch.setattr(service, "fetch_metadata", fake_fetch_metadata)

    rss_announced_at = datetime(2026, 2, 20, 8, 0, tzinfo=UTC)
    arxiv_item = NewsItem(
        id="arxiv:1",
        source_id="arxiv_ai",
        source_name="arXiv AI",
        title="RSS Title",
        link="https://arxiv.org/abs/2503.12345",
        summary="RSS summary",
        published_at=rss_announced_at,
    )
    non_arxiv_item = NewsItem(
        id="openai:1",
        source_id="openai",
        source_name="OpenAI",
        title="OpenAI Title",
        link="https://openai.com/news/1",
        summary="OpenAI summary",
        published_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    enriched = await service.enrich_items([arxiv_item, non_arxiv_item])

    assert len(enriched) == 2

    updated_arxiv = enriched[0]
    assert updated_arxiv.title == "Canonical Title"
    assert updated_arxiv.summary == "Canonical summary"
    assert updated_arxiv.author == "Alice, Bob"
    assert updated_arxiv.announced_at == rss_announced_at
    assert updated_arxiv.original_published_at == datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
    assert updated_arxiv.updated_at == datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    assert updated_arxiv.published_at == datetime(2025, 3, 1, 12, 0, tzinfo=UTC)

    unchanged_non_arxiv = enriched[1]
    assert unchanged_non_arxiv.source_id == "openai"
    assert unchanged_non_arxiv.announced_at is None
    assert unchanged_non_arxiv.original_published_at is None
    assert unchanged_non_arxiv.updated_at is None
