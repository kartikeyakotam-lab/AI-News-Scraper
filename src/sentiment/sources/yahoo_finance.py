import logging
import time
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Multiple fallback endpoints for Yahoo Finance
YF_ENDPOINTS = [
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
]

YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://finance.yahoo.com",
    "Referer": "https://finance.yahoo.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# Headline sentiment keyword sets
POSITIVE_WORDS = {
    "surge", "rally", "jump", "soar", "gain", "rise", "beat", "record", "bullish",
    "upgrade", "buy", "outperform", "strong", "growth", "profit", "boom", "win",
    "award", "partnership", "deal", "expand", "high", "record", "milestone",
}
NEGATIVE_WORDS = {
    "fall", "drop", "plunge", "slide", "crash", "miss", "loss", "downgrade",
    "sell", "bearish", "weak", "concern", "warning", "decline", "cut", "layoff",
    "fine", "lawsuit", "investigation", "fraud", "recall", "fail", "low", "trouble",
}


class YahooFinanceSource:
    """
    Pulls news and price data from Yahoo Finance.

    Uses yfinance-style request patterns. Works without API key.
    Requires network access to finance.yahoo.com.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(YF_HEADERS)
        # Warm up cookie
        self._crumb = None

    def _get_crumb(self) -> str:
        """Fetch Yahoo Finance crumb for authenticated API access."""
        if self._crumb:
            return self._crumb
        try:
            r = self.session.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                timeout=10,
            )
            if r.status_code == 200 and r.text:
                self._crumb = r.text.strip()
                return self._crumb
        except Exception:
            pass
        return ""

    def get_ticker_news(self, ticker: str, count: int = 10) -> list:
        """Fetch recent news for a ticker via Yahoo Finance search API."""
        crumb = self._get_crumb()
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {
            "q": ticker,
            "newsCount": count,
            "quotesCount": 0,
            "enableFuzzyQuery": False,
        }
        if crumb:
            params["crumb"] = crumb

        for base in YF_ENDPOINTS:
            try:
                r = self.session.get(
                    f"{base}/v1/finance/search",
                    params=params,
                    timeout=15,
                )
                r.raise_for_status()
                news_items = r.json().get("news", [])
                return [
                    {
                        "title": n.get("title", ""),
                        "publisher": n.get("publisher", ""),
                        "link": n.get("link", ""),
                        "published_at": datetime.fromtimestamp(
                            n.get("providerPublishTime", 0), tz=timezone.utc
                        ).isoformat()
                        if n.get("providerPublishTime")
                        else "",
                        "summary": n.get("summary", "")[:300],
                    }
                    for n in news_items
                ]
            except Exception as e:
                logger.debug(f"Yahoo Finance news endpoint {base} failed for {ticker}: {e}")
                continue

        logger.warning(f"Yahoo Finance news unavailable for {ticker}")
        return []

    def get_ticker_quote(self, ticker: str) -> dict:
        """Fetch current price and basic stats."""
        for base in YF_ENDPOINTS:
            try:
                r = self.session.get(
                    f"{base}/v8/finance/chart/{ticker}",
                    params={"interval": "1d", "range": "5d"},
                    timeout=15,
                )
                r.raise_for_status()
                result = r.json().get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    return {
                        "price": meta.get("regularMarketPrice", 0),
                        "prev_close": meta.get("chartPreviousClose", 0),
                        "52w_high": meta.get("fiftyTwoWeekHigh", 0),
                        "52w_low": meta.get("fiftyTwoWeekLow", 0),
                    }
            except Exception as e:
                logger.debug(f"Yahoo Finance quote endpoint {base} failed for {ticker}: {e}")
                continue
        return {}

    def score_headlines(self, news: list) -> tuple:
        bull = sum(
            1
            for n in news
            if any(w in n.get("title", "").lower() for w in POSITIVE_WORDS)
        )
        bear = sum(
            1
            for n in news
            if any(w in n.get("title", "").lower() for w in NEGATIVE_WORDS)
        )
        return bull, bear

    def get_ticker_data(self, ticker: str) -> dict:
        """Aggregate Yahoo Finance news + price data for a ticker."""
        news = self.get_ticker_news(ticker)
        time.sleep(0.2)
        quote = self.get_ticker_quote(ticker)

        price = quote.get("price", 0)
        prev = quote.get("prev_close", 0)
        pct_change = (price - prev) / prev * 100 if price and prev else 0

        bull, bear = self.score_headlines(news)

        return {
            "ticker": ticker,
            "platform": "yahoo_finance",
            "total_articles": len(news),
            "headline_bullish": bull,
            "headline_bearish": bear,
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "pct_change": round(pct_change, 2),
            "52w_high": quote.get("52w_high", 0),
            "52w_low": quote.get("52w_low", 0),
            "recent_news": news[:6],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
