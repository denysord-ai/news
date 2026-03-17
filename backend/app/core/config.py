from typing import Literal

from pydantic import BaseModel, HttpUrl


class FeedSource(BaseModel):
    id: str
    name: str
    type: Literal["rss", "html"] = "rss"
    url: HttpUrl
    max_items: int = 20


class AppConfig(BaseModel):
    sources: list[FeedSource]


config = AppConfig(
    sources=[
        FeedSource(
            id="openai",
            name="OpenAI",
            type="rss",
            url="https://openai.com/news/rss.xml",
            max_items=20,
        ),
        FeedSource(
            id="anthropic_news",
            name="Anthropic News",
            type="html",
            url="https://www.anthropic.com/news",
            max_items=20,
        ),
        FeedSource(
            id="anthropic_engineering",
            name="Anthropic Engineering",
            type="html",
            url="https://www.anthropic.com/engineering",
            max_items=20,
        ),
        FeedSource(
            id="claude_blog",
            name="Claude Blog",
            type="html",
            url="https://claude.com/blog",
            max_items=20,
        ),
        FeedSource(
            id="google_gemini",
            name="Google Gemini",
            type="rss",
            url="https://blog.google/products-and-platforms/products/gemini/rss/",
            max_items=20,
        ),
        FeedSource(
            id="google_ai",
            name="Google AI",
            type="rss",
            url="https://blog.google/innovation-and-ai/rss/",
            max_items=20,
        ),
        FeedSource(
            id="devin_cognition",
            name="Cognition (Devin)",
            type="html",
            url="https://cognition.ai/blog/1",
            max_items=20,
        ),
        FeedSource(
            id="arxiv_ai",
            name="arXiv AI",
            type="rss",
            url="https://export.arxiv.org/rss/cs.AI",
            max_items=20,
        ),
        FeedSource(
            id="huggingface_blog",
            name="HuggingFace Blog",
            type="rss",
            url="https://huggingface.co/blog/feed.xml",
            max_items=20,
        ),
    ]
)
