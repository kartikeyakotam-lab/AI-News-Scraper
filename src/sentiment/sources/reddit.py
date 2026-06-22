import os
import logging
import time
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Subreddits ordered by retail options relevance
SUBREDDITS = ["wallstreetbets", "stocks", "options", "investing", "stockmarket"]
REDDIT_OAUTH_BASE = "https://oauth.reddit.com"


class RedditSource:
    """
    Pulls retail discussion from Reddit.

    Authentication options (in priority order):
    1. PRAW OAuth: set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
       → Register at reddit.com/prefs/apps (free, script type)
    2. Falls back gracefully to empty results if no credentials

    Register in 2 minutes: reddit.com/prefs/apps → 'are you a developer?' → 'create app'
    Type: 'script', redirect: http://localhost:8080
    """

    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv(
            "REDDIT_USER_AGENT",
            "SentimentAgent/1.0 (options sentiment tracker)",
        )
        self._access_token = None
        self._token_expiry = 0

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def is_available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        """Fetch or refresh OAuth2 client-credentials token."""
        now = time.time()
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token

        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": self.user_agent},
            timeout=10,
        )
        r.raise_for_status()
        token_data = r.json()
        self._access_token = token_data["access_token"]
        self._token_expiry = now + token_data.get("expires_in", 3600)
        return self._access_token

    def search_subreddit(
        self,
        ticker: str,
        subreddit: str,
        time_filter: str = "week",
        limit: int = 25,
    ) -> list:
        """Search for posts mentioning ticker in a subreddit (requires OAuth)."""
        if not self.is_available():
            return []

        try:
            token = self._get_token()
            headers = {
                "Authorization": f"bearer {token}",
                "User-Agent": self.user_agent,
            }
            url = f"{REDDIT_OAUTH_BASE}/r/{subreddit}/search"
            params = {
                "q": f"${ticker} OR {ticker}",
                "sort": "top",
                "t": time_filter,
                "limit": limit,
                "restrict_sr": "true",
            }
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            children = r.json().get("data", {}).get("children", [])
            return self._parse_posts(children)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            logger.warning(f"Reddit HTTP {status} for {ticker}/{subreddit}")
            return []
        except Exception as e:
            logger.error(f"Reddit search error for {ticker}/{subreddit}: {e}")
            return []

    def _parse_posts(self, children: list) -> list:
        posts = []
        for child in children:
            post = child.get("data", {})
            posts.append(
                {
                    "title": post.get("title", ""),
                    "text": post.get("selftext", "")[:400],
                    "score": post.get("score", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0.0),
                    "num_comments": post.get("num_comments", 0),
                    "subreddit": post.get("subreddit", ""),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "created_utc": post.get("created_utc", 0),
                    "author": post.get("author", ""),
                    "flair": post.get("link_flair_text", ""),
                }
            )
        return posts

    def get_ticker_data(self, ticker: str, subreddits: list = None) -> dict:
        """Aggregate Reddit data across key subreddits for a ticker."""
        if not self.is_available():
            return self._empty_result(ticker, unavailable=True)

        target_subs = subreddits or SUBREDDITS[:3]
        all_posts = []

        for sub in target_subs:
            posts = self.search_subreddit(ticker, sub)
            all_posts.extend(posts)
            time.sleep(0.5)

        if not all_posts:
            return self._empty_result(ticker)

        # Deduplicate by URL, sort by score
        seen_urls = set()
        unique_posts = []
        for p in all_posts:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                unique_posts.append(p)

        unique_posts.sort(key=lambda p: p.get("score", 0), reverse=True)

        total_score = sum(p.get("score", 0) for p in unique_posts)
        total_comments = sum(p.get("num_comments", 0) for p in unique_posts)
        avg_ratio = (
            sum(p.get("upvote_ratio", 0) for p in unique_posts) / len(unique_posts)
            if unique_posts
            else 0
        )

        return {
            "ticker": ticker,
            "platform": "reddit",
            "total_posts": len(unique_posts),
            "total_score": total_score,
            "total_comments": total_comments,
            "avg_upvote_ratio": round(avg_ratio, 3),
            "subreddits_searched": target_subs,
            "top_posts": unique_posts[:5],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _empty_result(self, ticker: str, unavailable: bool = False) -> dict:
        return {
            "ticker": ticker,
            "platform": "reddit",
            "total_posts": 0,
            "total_score": 0,
            "total_comments": 0,
            "avg_upvote_ratio": 0.0,
            "subreddits_searched": [],
            "top_posts": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "unavailable": unavailable,
            "error": not unavailable,
        }
