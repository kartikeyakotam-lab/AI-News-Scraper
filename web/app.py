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
from src.sentiment.agent import SentimentAgent
from src.sentiment.aggregator import SentimentAggregator

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
sentiment_aggregator = SentimentAggregator()


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


# ─── Sentiment API ────────────────────────────────────────────────────────────

@app.get("/api/sentiment/latest")
async def get_latest_sentiment(
    sort: str = Query("score", description="Sort by: score | ticker | volume"),
    limit: int = Query(25, ge=1, le=25),
):
    """Return the most recent sentiment results for all tracked tickers."""
    results = sentiment_aggregator.load_latest()
    if not results:
        return {"results": [], "message": "No sentiment data yet. Run sentiment scan first."}

    if sort == "ticker":
        results = sorted(results, key=lambda r: r["ticker"])
    elif sort == "volume":
        results = sorted(
            results,
            key=lambda r: r["raw_signals"].get("stocktwits", {}).get("total_messages", 0),
            reverse=True,
        )
    else:  # score — most extreme first
        results = sorted(results, key=lambda r: abs(r["analysis"].get("score", 0)), reverse=True)

    results = results[:limit]

    return {
        "count": len(results),
        "sort": sort,
        "results": [
            {
                "ticker": r["ticker"],
                "name": r["name"],
                "sector": r["sector"],
                "score": r["analysis"].get("score", 0),
                "sentiment_label": r["analysis"].get("sentiment_label", ""),
                "confidence": r["analysis"].get("confidence", ""),
                "volume_signal": r["analysis"].get("volume_signal", ""),
                "narrative": r["analysis"].get("narrative", ""),
                "options_implication": r["analysis"].get("options_implication", ""),
                "key_themes": r["analysis"].get("key_themes", []),
                "stocktwits_messages": r["raw_signals"].get("stocktwits", {}).get("total_messages", 0),
                "stocktwits_bullish": r["raw_signals"].get("stocktwits", {}).get("bullish", 0),
                "stocktwits_bearish": r["raw_signals"].get("stocktwits", {}).get("bearish", 0),
                "reddit_posts": r["raw_signals"].get("reddit", {}).get("total_posts", 0),
                "reddit_score": r["raw_signals"].get("reddit", {}).get("total_score", 0),
                "run_at": r.get("run_at", ""),
            }
            for r in results
        ],
    }


@app.get("/api/sentiment/{ticker}")
async def get_ticker_sentiment(ticker: str):
    """Return full sentiment detail for a single ticker."""
    results = sentiment_aggregator.load_latest()
    ticker = ticker.upper()
    match = next((r for r in results if r["ticker"] == ticker), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"No sentiment data for {ticker}. Run sentiment scan first.",
        )
    return match


@app.post("/api/sentiment/scan")
async def trigger_sentiment_scan(
    background_tasks: BackgroundTasks,
    tickers: Optional[str] = Query(None, description="Comma-separated tickers, e.g. TSLA,NVDA"),
):
    """Trigger a background sentiment scan."""
    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None

    def do_scan():
        agent = SentimentAgent()
        agent.run(tickers=ticker_list, verbose=False)

    background_tasks.add_task(do_scan)
    return {
        "status": "started",
        "message": f"Sentiment scan started for {ticker_list or 'all 25 tickers'}",
    }


@app.get("/api/sentiment/plays/latest")
async def get_latest_plays():
    """Return the most recently generated options plays."""
    from pathlib import Path
    import json

    plays_file = Path("data/sentiment/latest_plays.json")
    if not plays_file.exists():
        raise HTTPException(
            status_code=404,
            detail="No options plays generated yet. Run options-plays command first.",
        )
    with open(plays_file) as f:
        return json.load(f)


@app.post("/api/sentiment/plays/generate")
async def generate_plays(
    background_tasks: BackgroundTasks,
    top_n: int = Query(10, ge=1, le=25),
):
    """Trigger background generation of options plays from latest sentiment data."""

    def do_generate():
        agent = SentimentAgent()
        agent.get_options_plays(top_n=top_n, verbose=False)

    background_tasks.add_task(do_generate)
    return {
        "status": "started",
        "message": f"Generating options plays from top {top_n} movers...",
    }


@app.get("/api/sentiment/trending")
async def get_trending():
    """Get tickers currently trending on StockTwits."""
    trending = sentiment_aggregator.get_trending_on_stocktwits()
    return {"trending": trending, "count": len(trending)}


def create_app():
    """Factory function for creating the app."""
    return app
