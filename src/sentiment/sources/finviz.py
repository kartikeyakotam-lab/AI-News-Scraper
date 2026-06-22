import logging
import requests
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

FINVIZ_BASE = "https://finviz.com"

FINVIZ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://finviz.com/",
    "DNT": "1",
}

# Sentiment keywords for headline scoring
POSITIVE_WORDS = {
    "surge", "rally", "jump", "soar", "gain", "rise", "beat", "record", "bullish",
    "upgrade", "buy", "outperform", "strong", "growth", "profit", "boom", "launch",
    "win", "award", "partnership", "deal", "expand", "increase", "high",
}
NEGATIVE_WORDS = {
    "fall", "drop", "plunge", "slide", "crash", "miss", "loss", "downgrade",
    "sell", "bearish", "weak", "concern", "warning", "decline", "cut", "layoff",
    "fine", "lawsuit", "investigation", "fraud", "recall", "fail", "low",
}


class FinvizSource:
    """
    Scrapes Finviz for news headlines and basic options stats per ticker.
    No auth required — free to scrape.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(FINVIZ_HEADERS)

    def get_ticker_news(self, ticker: str) -> list:
        """Scrape recent news headlines from Finviz ticker page."""
        url = f"{FINVIZ_BASE}/quote.ashx?t={ticker}"
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            html = r.text

            # Extract news table rows
            news_section = re.search(
                r'<table[^>]*id="news-table"[^>]*>(.*?)</table>',
                html,
                re.DOTALL,
            )
            if not news_section:
                # Try alternative pattern
                news_section = re.search(
                    r'news-table.*?<table(.*?)</table>',
                    html,
                    re.DOTALL,
                )

            if not news_section:
                return []

            table_html = news_section.group(1)
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)

            news_items = []
            current_date = ""
            for row in rows:
                # Extract date/time cell
                date_match = re.search(
                    r'<td[^>]*>\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^<]*?|Today|Yesterday)\s*</td>',
                    row,
                )
                if date_match:
                    current_date = date_match.group(1).strip()

                # Extract headline and URL
                link_match = re.search(
                    r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*news-link[^"]*"[^>]*>([^<]+)</a>',
                    row,
                )
                if not link_match:
                    # Fallback pattern for external links
                    link_match = re.search(
                        r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]{10,})</a>',
                        row,
                    )

                if link_match:
                    url_found = link_match.group(1)
                    headline = link_match.group(2).strip()

                    # Source extraction
                    source_match = re.search(r'<span[^>]*>([^<]+)</span>', row)
                    source = source_match.group(1).strip() if source_match else ""

                    if headline and len(headline) > 10:
                        news_items.append(
                            {
                                "headline": headline,
                                "source": source,
                                "url": url_found,
                                "date": current_date,
                            }
                        )

            return news_items[:15]

        except Exception as e:
            logger.error(f"Finviz scrape error for {ticker}: {e}")
            return []

    def score_headlines(self, news_items: list) -> dict:
        """Score headlines for sentiment."""
        bull_count = 0
        bear_count = 0
        for item in news_items:
            headline_lower = item.get("headline", "").lower()
            if any(w in headline_lower for w in POSITIVE_WORDS):
                bull_count += 1
            if any(w in headline_lower for w in NEGATIVE_WORDS):
                bear_count += 1
        return {"bullish_headlines": bull_count, "bearish_headlines": bear_count}

    def get_ticker_data(self, ticker: str) -> dict:
        """Return Finviz news and headline sentiment for a ticker."""
        news = self.get_ticker_news(ticker)
        scores = self.score_headlines(news)

        return {
            "ticker": ticker,
            "platform": "finviz",
            "total_articles": len(news),
            "bullish_headlines": scores["bullish_headlines"],
            "bearish_headlines": scores["bearish_headlines"],
            "recent_news": news[:6],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
