import os
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"


class StockTwitsSource:
    """
    Pulls retail sentiment from StockTwits API.

    Requires STOCKTWITS_ACCESS_TOKEN (free — register at stocktwits.com/developers).
    Falls back gracefully to empty results if token not set.
    """

    def __init__(self):
        self.access_token = os.getenv("STOCKTWITS_ACCESS_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SentimentAgent/1.0"})

    def is_available(self) -> bool:
        return bool(self.access_token)

    def get_ticker_stream(self, ticker: str, limit: int = 30) -> dict:
        """Fetch recent messages and sentiment labels for a ticker."""
        if not self.is_available():
            logger.debug(f"StockTwits: no access token — skipping {ticker}")
            return self._empty_result(ticker, unavailable=True)

        url = f"{STOCKTWITS_BASE}/streams/symbol/{ticker}.json"
        params = {"limit": min(limit, 30), "access_token": self.access_token}

        try:
            r = self.session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()

            messages = data.get("messages", [])
            bullish = sum(
                1
                for m in messages
                if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish"
            )
            bearish = sum(
                1
                for m in messages
                if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish"
            )
            neutral = len(messages) - bullish - bearish

            total_labeled = bullish + bearish
            sentiment_ratio = (bullish - bearish) / total_labeled if total_labeled > 0 else 0.0

            top_posts = []
            for m in messages[:10]:
                top_posts.append(
                    {
                        "text": m.get("body", "")[:200],
                        "sentiment": m.get("entities", {}).get("sentiment", {}).get("basic"),
                        "likes": m.get("likes", {}).get("total", 0),
                        "created_at": m.get("created_at", ""),
                        "username": m.get("user", {}).get("username", ""),
                    }
                )

            symbol_info = data.get("symbol", {})

            return {
                "ticker": ticker,
                "platform": "stocktwits",
                "total_messages": len(messages),
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
                "sentiment_ratio": round(sentiment_ratio, 4),
                "watchlist_count": symbol_info.get("watchlist_count", 0),
                "top_posts": top_posts,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            if status == 429:
                logger.warning(f"StockTwits rate limited for {ticker}")
            elif status == 401:
                logger.error("StockTwits auth failed — check STOCKTWITS_ACCESS_TOKEN")
            else:
                logger.error(f"StockTwits HTTP {status} for {ticker}: {e}")
            return self._empty_result(ticker)
        except Exception as e:
            logger.error(f"StockTwits error for {ticker}: {e}")
            return self._empty_result(ticker)

    def get_trending(self) -> list:
        """Get currently trending tickers on StockTwits."""
        if not self.is_available():
            return []

        url = f"{STOCKTWITS_BASE}/trending/symbols.json"
        params = {"access_token": self.access_token}
        try:
            r = self.session.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            return [s["symbol"] for s in data.get("symbols", [])]
        except Exception as e:
            logger.error(f"StockTwits trending error: {e}")
            return []

    def _empty_result(self, ticker: str, unavailable: bool = False) -> dict:
        return {
            "ticker": ticker,
            "platform": "stocktwits",
            "total_messages": 0,
            "bullish": 0,
            "bearish": 0,
            "neutral": 0,
            "sentiment_ratio": 0.0,
            "watchlist_count": 0,
            "top_posts": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "unavailable": unavailable,
            "error": not unavailable,
        }
