import os
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageSource:
    """
    Pulls news sentiment from Alpha Vantage News & Sentiment API.

    Free tier: 25 requests/day, 500/month.
    Premium tiers available for higher volume.

    Get a free key at: alphavantage.co/support/#api-key
    Set env var: ALPHA_VANTAGE_API_KEY
    """

    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SentimentAgent/1.0"})

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_news_sentiment(self, ticker: str, limit: int = 10) -> dict:
        """
        Fetch news articles with pre-computed sentiment scores from Alpha Vantage.

        Returns sentiment labels and scores for each article.
        """
        if not self.is_available():
            return self._empty_result(ticker, unavailable=True)

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "limit": limit,
            "sort": "RELEVANCE",
            "apikey": self.api_key,
        }

        try:
            r = self.session.get(AV_BASE, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()

            if "Information" in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Information']}")
                return self._empty_result(ticker)

            articles = data.get("feed", [])

            # Extract ticker-specific sentiment from each article
            processed = []
            overall_sentiment_scores = []
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0

            for article in articles:
                # Find this ticker's sentiment in the article
                ticker_sentiment = None
                for ts in article.get("ticker_sentiment", []):
                    if ts.get("ticker") == ticker:
                        ticker_sentiment = ts
                        break

                if ticker_sentiment:
                    label = ticker_sentiment.get("ticker_sentiment_label", "")
                    score = float(ticker_sentiment.get("ticker_sentiment_score", 0))
                    overall_sentiment_scores.append(score)

                    if "Bullish" in label:
                        bullish_count += 1
                    elif "Bearish" in label:
                        bearish_count += 1
                    else:
                        neutral_count += 1

                processed.append(
                    {
                        "title": article.get("title", ""),
                        "source": article.get("source", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("time_published", ""),
                        "overall_sentiment": article.get("overall_sentiment_label", ""),
                        "overall_score": float(article.get("overall_sentiment_score", 0)),
                        "ticker_sentiment": ticker_sentiment.get("ticker_sentiment_label", "") if ticker_sentiment else "",
                        "ticker_score": float(ticker_sentiment.get("ticker_sentiment_score", 0)) if ticker_sentiment else 0,
                        "relevance": float(ticker_sentiment.get("relevance_score", 0)) if ticker_sentiment else 0,
                    }
                )

            avg_score = (
                sum(overall_sentiment_scores) / len(overall_sentiment_scores)
                if overall_sentiment_scores
                else 0
            )

            return {
                "ticker": ticker,
                "platform": "alpha_vantage",
                "total_articles": len(processed),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
                "avg_sentiment_score": round(avg_score, 4),
                "articles": processed[:6],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Alpha Vantage error for {ticker}: {e}")
            return self._empty_result(ticker)

    def _empty_result(self, ticker: str, unavailable: bool = False) -> dict:
        return {
            "ticker": ticker,
            "platform": "alpha_vantage",
            "total_articles": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "avg_sentiment_score": 0.0,
            "articles": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "unavailable": unavailable,
            "error": not unavailable,
        }
