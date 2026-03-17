from app.core.config import FeedSource
from app.services import html_source_service as html_module
from app.services.html_source_service import HTMLSourceService


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
        html = """
        <html>
          <body>
            <article>
              <a href="/news/post-1">Post One</a>
              <time datetime="2026-03-01T10:00:00Z"></time>
              <p>Summary one.</p>
            </article>
            <article>
              <a href="/news/post-2">Post Two</a>
              <time>February 10, 2026</time>
              <p>Summary two.</p>
            </article>
            <article>
              <a href="/engineering/post-3">Engineering</a>
            </article>
          </body>
        </html>
        """
        return DummyResponse(html)


async def test_html_source_parser_extracts_news_items(monkeypatch) -> None:
    monkeypatch.setattr(html_module.httpx, "AsyncClient", DummyAsyncClient)

    source = FeedSource(
        id="anthropic_news",
        name="Anthropic News",
        type="html",
        url="https://www.anthropic.com/news",
        max_items=20,
    )
    service = HTMLSourceService()

    items = await service.fetch_source_items(source)

    assert len(items) == 2
    assert items[0].title == "Post One"
    assert str(items[0].link) == "https://www.anthropic.com/news/post-1"
    assert items[0].summary == "Summary one."
    assert items[0].published_at is not None
    assert items[0].id.startswith("anthropic_news:")


async def test_html_source_items_respect_source_limit(monkeypatch) -> None:
    class ManyItemsClient(DummyAsyncClient):
        async def get(self, url: str) -> DummyResponse:
            cards = "".join(
                [
                    (
                        "<article class='card_blog_list_wrap'>"
                        f"<h3 class='card_blog_list_title'>Blog {i}</h3>"
                        f"<div class='u-display-none'>March {(i % 28) + 1}, 2026</div>"
                        f"<a class='clickable_link' href='/blog/post-{i}'>Read more</a>"
                        "</article>"
                    )
                    for i in range(30)
                ]
            )
            return DummyResponse(f"<html><body>{cards}</body></html>")

    monkeypatch.setattr(html_module.httpx, "AsyncClient", ManyItemsClient)

    source = FeedSource(
        id="claude_blog",
        name="Claude Blog",
        type="html",
        url="https://claude.com/blog",
        max_items=20,
    )
    service = HTMLSourceService()

    items = await service.fetch_source_items(source)

    assert len(items) == 20
    assert all(item.title for item in items)
    assert all(item.published_at is not None for item in items)


async def test_anthropic_news_extracts_clean_title_and_date(monkeypatch) -> None:
    class AnthropicNewsClient(DummyAsyncClient):
        async def get(self, url: str) -> DummyResponse:
            html = """
            <html>
              <body>
                <div class="FeaturedGrid-module-scss-module__W1FydW__featuredItem">
                  <a class="FeaturedGrid-module-scss-module__W1FydW__content" href="/news/where-stand-department-war">
                    <h2 class="headline-4 FeaturedGrid-module-scss-module__W1FydW__featuredTitle">
                      Where things stand with the Department of War
                    </h2>
                    <span class="caption bold">Announcements</span>
                    <time class="FeaturedGrid-module-scss-module__W1FydW__date caption bold">Mar 5, 2026</time>
                    <p class="body-3 serif FeaturedGrid-module-scss-module__W1FydW__body">A statement from Dario Amodei.</p>
                  </a>
                </div>
                <ul class="PublicationList-module-scss-module__KxYrHG__list">
                  <li>
                    <a class="PublicationList-module-scss-module__KxYrHG__listItem" href="/news/the-anthropic-institute">
                      <time class="PublicationList-module-scss-module__KxYrHG__date body-3">Mar 11, 2026</time>
                      <span class="PublicationList-module-scss-module__KxYrHG__subject body-3">Announcements</span>
                      <span class="PublicationList-module-scss-module__KxYrHG__title body-3">Introducing The Anthropic Institute</span>
                    </a>
                  </li>
                </ul>
              </body>
            </html>
            """
            return DummyResponse(html)

    monkeypatch.setattr(html_module.httpx, "AsyncClient", AnthropicNewsClient)

    source = FeedSource(
        id="anthropic_news",
        name="Anthropic News",
        type="html",
        url="https://www.anthropic.com/news",
        max_items=20,
    )
    service = HTMLSourceService()

    items = await service.fetch_source_items(source)

    assert len(items) == 2
    assert items[0].title == "Introducing The Anthropic Institute"
    assert items[0].published_at is not None
    assert items[1].title == "Where things stand with the Department of War"
    assert items[1].published_at is not None


async def test_anthropic_engineering_extracts_title_link_and_date(monkeypatch) -> None:
    class AnthropicEngineeringClient(DummyAsyncClient):
        async def get(self, url: str) -> DummyResponse:
            if "eval-awareness-browsecomp" in url:
                detail_html = """
                <html><body>
                  <script>
                    self.__next_f.push([1,"6:[\\"$\\",\\"$L17\\",null,{\\"article\\":{\\"_createdAt\\":\\"2026-03-06T17:00:55Z\\"}}]"]);
                  </script>
                </body></html>
                """
                return DummyResponse(detail_html)

            listing_html = """
            <html>
              <body>
                <article class="ArticleList-module-scss-module___tpu-a__article">
                  <a class="ArticleList-module-scss-module___tpu-a__cardLink" href="/engineering/eval-awareness-browsecomp">
                    Eval awareness in Claude Opus 4.6’s BrowseComp performance
                  </a>
                  <div class="ArticleList-module-scss-module___tpu-a__content">
                    <h3 class="headline-4">Eval awareness in Claude Opus 4.6’s BrowseComp performance</h3>
                  </div>
                </article>
                <article class="ArticleList-module-scss-module___tpu-a__article">
                  <a class="ArticleList-module-scss-module___tpu-a__cardLink" href="/engineering/building-c-compiler">
                    Building a C compiler with a team of parallel Claudes
                  </a>
                  <div class="ArticleList-module-scss-module___tpu-a__content">
                    <h3 class="headline-4">Building a C compiler with a team of parallel Claudes</h3>
                    <div class="body-2 ArticleList-module-scss-module___tpu-a__date">Feb 05, 2026</div>
                  </div>
                </article>
              </body>
            </html>
            """
            return DummyResponse(listing_html)

    monkeypatch.setattr(html_module.httpx, "AsyncClient", AnthropicEngineeringClient)

    source = FeedSource(
        id="anthropic_engineering",
        name="Anthropic Engineering",
        type="html",
        url="https://www.anthropic.com/engineering",
        max_items=20,
    )
    service = HTMLSourceService()

    items = await service.fetch_source_items(source)

    assert len(items) == 2
    assert all(item.title for item in items)
    assert all(item.published_at is not None for item in items)
    assert all("/engineering/" in str(item.link) for item in items)


async def test_devin_cognition_extracts_title_link_and_optional_date(monkeypatch) -> None:
    class DevinCognitionClient(DummyAsyncClient):
        async def get(self, url: str) -> DummyResponse:
            html = """
            <html>
              <body>
                <ul>
                  <li class="blog-post-list__list-item">
                    <a class="o-blog-preview" href="/blog/introducing-devin-2-2">
                      <span class="o-blog-preview__meta-date">February 24, 2026 <span class="o-blog-preview__meta-author">The Cognition Team</span></span>
                      <h3 class="o-blog-preview__title">Introducing Devin 2.2</h3>
                      <p class="o-blog-preview__intro">Update details.</p>
                    </a>
                  </li>
                  <li class="blog-post-list__list-item">
                    <a class="o-blog-preview" href="/blog/cognition-for-government">
                      <h3 class="o-blog-preview__title">Introducing Cognition for Government</h3>
                    </a>
                  </li>
                  <li class="blog-post-list__list-item">
                    <a class="o-blog-preview" href="/blog/Product%20Updates/1">
                      <h3 class="o-blog-preview__title">Category page should be ignored</h3>
                    </a>
                  </li>
                </ul>
              </body>
            </html>
            """
            return DummyResponse(html)

    monkeypatch.setattr(html_module.httpx, "AsyncClient", DevinCognitionClient)

    source = FeedSource(
        id="devin_cognition",
        name="Cognition (Devin)",
        type="html",
        url="https://cognition.ai/blog/1",
        max_items=20,
    )
    service = HTMLSourceService()

    items = await service.fetch_source_items(source)

    assert len(items) == 2
    assert items[0].title == "Introducing Devin 2.2"
    assert str(items[0].link) == "https://cognition.ai/blog/introducing-devin-2-2"
    assert items[0].published_at is not None
    assert items[1].title == "Introducing Cognition for Government"
    assert str(items[1].link) == "https://cognition.ai/blog/cognition-for-government"
