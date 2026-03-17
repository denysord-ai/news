from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import config
from app.db.session import get_db
from app.models.news import FeedSourceResponse, HealthResponse, NewsItem
from app.repositories.article_repository import ArticleRepository
from app.services.html_source_service import HtmlSourceProvider
from app.services.news_service import NewsService
from app.services.rss_service import RssSourceProvider
from app.services.sync_service import SyncService, SyncSummary

router = APIRouter(prefix="/api", tags=["api"])

rss_provider = RssSourceProvider()
html_provider = HtmlSourceProvider()
news_service = NewsService(
    app_config=config,
    providers={
        "rss": rss_provider,
        "html": html_provider,
    },
)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/sources", response_model=list[FeedSourceResponse])
async def sources() -> list[FeedSourceResponse]:
    return [FeedSourceResponse(**source.model_dump()) for source in config.sources]


@router.get("/news", response_model=list[NewsItem])
def news(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[NewsItem]:
    repository = ArticleRepository(db)
    return repository.list_articles(limit=limit, offset=offset)


@router.post("/sync", response_model=SyncSummary)
async def sync(db: Session = Depends(get_db)) -> SyncSummary:
    repository = ArticleRepository(db)
    sync_service = SyncService(news_service=news_service, article_repository=repository)
    return await sync_service.sync_articles()
