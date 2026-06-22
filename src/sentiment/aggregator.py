import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import TICKERS
from .sources.stocktwits import StockTwitsSource
from .sources.reddit import RedditSource
from .sources.twitter import TwitterSource
from .sources.yahoo_finance import YahooFinanceSource
from .sources.finviz import FinvizSource
from .sources.alpha_vantage import AlphaVantageSource
from .analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)

SENTIMENT_DATA_DIR = Path("data/sentiment")


class SentimentAggregator:
    """Pulls signals from all configured sources, runs Claude analysis, and stores results."""

    def __init__(self):
        self.stocktwits = StockTwitsSource()
        self.reddit = RedditSource()
        self.twitter = TwitterSource()
        self.yahoo = YahooFinanceSource()
        self.finviz = FinvizSource()
        self.alpha_vantage = AlphaVantageSource()
        self.analyzer = SentimentAnalyzer()
        SENTIMENT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def source_status(self) -> dict:
        """Report which sources are configured and active."""
        return {
            "stocktwits": self.stocktwits.is_available(),
            "reddit": self.reddit.is_available(),
            "twitter": self.twitter.is_available(),
            "yahoo_finance": True,  # Always attempted (free, no key)
            "finviz": True,  # Always attempted (free, no key)
            "alpha_vantage": self.alpha_vantage.is_available(),
        }

    def run_ticker(self, ticker: str, ticker_info: dict) -> dict:
        """Run full sentiment collection and Claude analysis for one ticker."""
        raw_signals = {}

        # StockTwits (STOCKTWITS_ACCESS_TOKEN)
        raw_signals["stocktwits"] = self.stocktwits.get_ticker_stream(ticker)
        time.sleep(0.3)

        # Reddit (REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET)
        raw_signals["reddit"] = self.reddit.get_ticker_data(ticker)
        time.sleep(0.5)

        # Twitter (TWITTER_BEARER_TOKEN)
        raw_signals["twitter"] = self.twitter.search_ticker(ticker)

        # Yahoo Finance (free)
        raw_signals["yahoo_finance"] = self.yahoo.get_ticker_data(ticker)
        time.sleep(0.3)

        # Finviz (free)
        raw_signals["finviz"] = self.finviz.get_ticker_data(ticker)
        time.sleep(0.3)

        # Alpha Vantage (ALPHA_VANTAGE_API_KEY)
        if self.alpha_vantage.is_available():
            raw_signals["alpha_vantage"] = self.alpha_vantage.get_news_sentiment(ticker)
            time.sleep(0.5)

        # Claude analysis
        analysis = self.analyzer.analyze_ticker(
            ticker, ticker_info.get("name", ticker), raw_signals
        )

        return {
            "ticker": ticker,
            "name": ticker_info.get("name", ticker),
            "sector": ticker_info.get("sector", ""),
            "tags": ticker_info.get("tags", []),
            "raw_signals": raw_signals,
            "analysis": analysis,
            "run_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_demo(self, tickers: list = None) -> list:
        """Run with realistic mock data (no network calls required)."""
        from .demo_data import generate_demo_signals

        target = tickers or TICKERS
        results = []

        for ticker_info in target:
            ticker = ticker_info["ticker"]
            raw_signals = generate_demo_signals(ticker, ticker_info)
            analysis = self.analyzer.analyze_ticker(
                ticker, ticker_info["name"], raw_signals
            )
            results.append({
                "ticker": ticker,
                "name": ticker_info["name"],
                "sector": ticker_info["sector"],
                "tags": ticker_info["tags"],
                "raw_signals": raw_signals,
                "analysis": analysis,
                "run_at": datetime.now(timezone.utc).isoformat(),
                "_demo": True,
            })
            time.sleep(0.15)

        self._save_results(results)
        return results

    def run_all(self, tickers: list = None, progress_callback=None) -> list:
        """Run sentiment collection for all tickers."""
        target = tickers or TICKERS
        results = []
        total = len(target)

        for i, ticker_info in enumerate(target):
            ticker = ticker_info["ticker"]

            if progress_callback:
                progress_callback(ticker, i + 1, total)

            try:
                result = self.run_ticker(ticker, ticker_info)
                results.append(result)
                score = result["analysis"].get("score", 0)
                label = result["analysis"].get("sentiment_label", "?")
                logger.info(f"  {ticker}: score={score:+d} ({label})")
            except Exception as e:
                logger.error(f"Failed processing {ticker}: {e}", exc_info=True)

            if i < total - 1:
                time.sleep(1.0)

        self._save_results(results)
        return results

    def run_single(self, ticker: str) -> dict:
        """Run sentiment for a single ticker."""
        from .config import TICKER_MAP

        ticker = ticker.upper()
        ticker_info = TICKER_MAP.get(
            ticker, {"ticker": ticker, "name": ticker, "sector": "", "tags": []}
        )
        result = self.run_ticker(ticker, ticker_info)

        existing = self.load_latest()
        existing = [r for r in existing if r["ticker"] != ticker]
        existing.append(result)
        self._save_results(existing)
        return result

    def _save_results(self, results: list):
        """Save timestamped archive + rolling latest."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_file = SENTIMENT_DATA_DIR / f"sentiment_{timestamp}.json"
        latest_file = SENTIMENT_DATA_DIR / "latest.json"

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ticker_count": len(results),
            "results": results,
        }

        with open(archive_file, "w") as f:
            json.dump(data, f, indent=2)
        with open(latest_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved: {archive_file.name}")

    def load_latest(self) -> list:
        latest_file = SENTIMENT_DATA_DIR / "latest.json"
        if not latest_file.exists():
            return []
        try:
            with open(latest_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Error loading latest sentiment: {e}")
            return []

    def load_history(self, limit: int = 7) -> list:
        files = sorted(SENTIMENT_DATA_DIR.glob("sentiment_*.json"), reverse=True)
        history = []
        for f in files[:limit]:
            try:
                with open(f) as fh:
                    raw = json.load(fh)
                results = raw.get("results", raw) if isinstance(raw, dict) else raw
                history.append({
                    "file": f.name,
                    "generated_at": raw.get("generated_at", "") if isinstance(raw, dict) else "",
                    "results": results,
                })
            except Exception:
                continue
        return history

    def get_trending_on_stocktwits(self) -> list:
        return self.stocktwits.get_trending()
