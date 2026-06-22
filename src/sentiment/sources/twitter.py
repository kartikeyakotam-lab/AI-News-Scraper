import os
import logging
import requests
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

TWITTER_V2_BASE = "https://api.twitter.com/2"


class TwitterSource:
    """
    Pulls sentiment data from Twitter/X via v2 API.

    Requires TWITTER_BEARER_TOKEN (Basic tier or above — ~$100/mo).
    Falls back gracefully to empty results if token not set.
    """

    def __init__(self):
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        self.session = requests.Session()
        if self.bearer_token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.bearer_token}",
                    "User-Agent": "SentimentAgent/1.0",
                }
            )

    def is_available(self) -> bool:
        return bool(self.bearer_token)

    def search_ticker(self, ticker: str, max_results: int = 100) -> dict:
        """Search for tweets mentioning the cashtag, focused on options/trading language."""
        if not self.is_available():
            return self._empty_result(ticker, unavailable=True)

        # Filter to trading-relevant tweets only
        query = (
            f"${ticker} (calls OR puts OR options OR bullish OR bearish OR yolo OR"
            f" 🚀 OR 🐻 OR 💎 OR buy OR sell) -is:retweet lang:en"
        )
        start_time = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")

        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "public_metrics,created_at,text,author_id",
            "start_time": start_time,
        }

        try:
            r = self.session.get(
                f"{TWITTER_V2_BASE}/tweets/search/recent", params=params, timeout=15
            )
            r.raise_for_status()
            data = r.json()

            tweets = data.get("data", [])
            meta = data.get("meta", {})

            total_likes = sum(
                t.get("public_metrics", {}).get("like_count", 0) for t in tweets
            )
            total_retweets = sum(
                t.get("public_metrics", {}).get("retweet_count", 0) for t in tweets
            )
            total_replies = sum(
                t.get("public_metrics", {}).get("reply_count", 0) for t in tweets
            )

            top_tweets = sorted(
                tweets,
                key=lambda t: t.get("public_metrics", {}).get("like_count", 0),
                reverse=True,
            )[:5]

            return {
                "ticker": ticker,
                "platform": "twitter",
                "total_tweets": meta.get("result_count", len(tweets)),
                "total_likes": total_likes,
                "total_retweets": total_retweets,
                "total_replies": total_replies,
                "top_tweets": [
                    {
                        "text": t.get("text", "")[:200],
                        "likes": t.get("public_metrics", {}).get("like_count", 0),
                        "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
                        "created_at": t.get("created_at", ""),
                    }
                    for t in top_tweets
                ],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning(f"Twitter rate limited for {ticker}")
            elif e.response is not None and e.response.status_code in (401, 403):
                logger.warning("Twitter auth failed — check TWITTER_BEARER_TOKEN")
            else:
                logger.error(f"Twitter HTTP error for {ticker}: {e}")
            return self._empty_result(ticker)
        except Exception as e:
            logger.error(f"Twitter error for {ticker}: {e}")
            return self._empty_result(ticker)

    def _empty_result(self, ticker: str, unavailable: bool = False) -> dict:
        return {
            "ticker": ticker,
            "platform": "twitter",
            "total_tweets": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "total_replies": 0,
            "top_tweets": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "unavailable": unavailable,
            "error": not unavailable,
        }
