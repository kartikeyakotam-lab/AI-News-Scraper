import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from src.storage import Storage
from src.ai_search import AISearch
from src.scraper import Scraper
from src.deduplicator import Deduplicator

# Initialize FastAPI app
app = FastAPI(
    title="AI News Scraper",
    description="Scrape and search AI news with Claude-powered insights",
    version="1.0.0"
)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Set up templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Initialize services
storage = Storage()
ai_search = AISearch(storage)


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    max_articles: Optional[int] = 100


class SearchResponse(BaseModel):
    success: bool
    response: str
    articles_searched: Optional[int] = None
    query: Optional[str] = None
    error: Optional[str] = None


# Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/articles")
async def get_articles(
    source: Optional[str] = Query(None, description="Filter by source name"),
    limit: int = Query(50, ge=1, le=200, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get articles with optional filtering."""
    if source:
        articles = storage.get_articles_by_source(source, limit=limit + offset)
    else:
        articles = storage.get_recent_articles(limit=limit + offset)

    # Apply offset
    articles = articles[offset:offset + limit]

    return {
        "articles": articles,
        "count": len(articles),
        "source": source,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str):
    """Get a single article by ID."""
    article = storage.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.get("/api/sources")
async def get_sources():
    """Get list of all sources with article counts."""
    stats = storage.get_stats()
    return {
        "sources": [
            {"name": name, "count": count}
            for name, count in stats["sources"].items()
        ],
        "total_articles": stats["total_articles"],
        "last_updated": stats["last_updated"]
    }


@app.get("/api/stats")
async def get_stats():
    """Get storage statistics."""
    return storage.get_stats()


@app.post("/api/search", response_model=SearchResponse)
async def search_articles(request: SearchRequest):
    """Perform AI-powered search across articles."""
    if not ai_search.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI search is not available. Please configure ANTHROPIC_API_KEY."
        )

    result = ai_search.search(request.query, max_articles=request.max_articles)
    return SearchResponse(**result)


@app.post("/api/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks):
    """Trigger a manual scrape of all sources."""

    def do_scrape():
        scraper = Scraper()
        deduplicator = Deduplicator(storage)

        results = scraper.scrape_all()

        for source_name, articles in results.items():
            if articles:
                merged = deduplicator.merge_articles(source_name, articles)
                storage.save_articles(source_name, merged)

        storage.update_combined_file()

    background_tasks.add_task(do_scrape)

    return {
        "status": "started",
        "message": "Scrape job started in background"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ai_search_available": ai_search.is_available()
    }


def create_app():
    """Factory function for creating the app."""
    return app
