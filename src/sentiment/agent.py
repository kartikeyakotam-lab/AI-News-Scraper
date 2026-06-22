import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .aggregator import SentimentAggregator
from .options_advisor import OptionsAdvisor
from .config import TICKERS, TICKER_MAP

logger = logging.getLogger(__name__)

SENTIMENT_DATA_DIR = Path("data/sentiment")


class SentimentAgent:
    """
    Main orchestrator for the retail investor sentiment tracking agent.

    Workflow:
      1. Pull signals from StockTwits, Reddit, Twitter, Yahoo Finance, Finviz,
         and Alpha Vantage for each of the top 25 retail investor tickers
      2. Claude analyzes each ticker's raw signals into a structured sentiment score
      3. OptionsAdvisor synthesizes top movers into this week's options plays
      4. Results saved to data/sentiment/

    Sources and required credentials:
      StockTwits  — STOCKTWITS_ACCESS_TOKEN  (free at stocktwits.com/developers)
      Reddit      — REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET  (free at reddit.com/prefs/apps)
      Twitter/X   — TWITTER_BEARER_TOKEN  (paid, ~$100/mo Basic tier)
      Yahoo Finance — no key required
      Finviz      — no key required
      Alpha Vantage — ALPHA_VANTAGE_API_KEY  (free tier: 25 req/day at alphavantage.co)
    """

    def __init__(self):
        self.aggregator = SentimentAggregator()
        self.advisor = OptionsAdvisor()

    def run(
        self,
        tickers: list = None,
        verbose: bool = True,
        demo: bool = False,
    ) -> list:
        """
        Run full sentiment scan.

        Args:
            tickers: Optional list of ticker symbols to restrict scan
            verbose: Print progress and leaderboard
            demo: Use realistic mock data instead of live API calls

        Returns:
            List of analyzed ticker result dicts
        """
        target_configs = TICKERS
        if tickers:
            upper = [t.upper() for t in tickers]
            target_configs = [t for t in TICKERS if t["ticker"] in upper]
            known = {t["ticker"] for t in target_configs}
            for t in upper:
                if t not in known:
                    target_configs.append({"ticker": t, "name": t, "sector": "", "tags": []})

        total = len(target_configs)

        if verbose:
            status = self.aggregator.source_status()
            active = [k for k, v in status.items() if v]
            print(f"\n{'=' * 65}")
            print("  Retail Investor Sentiment Agent")
            print(f"  Tracking {total} tickers")
            if demo:
                print("  Mode: DEMO (realistic mock data)")
            else:
                print(f"  Active sources: {', '.join(active)}")
                inactive = [k for k, v in status.items() if not v]
                if inactive:
                    print(f"  Inactive (no credentials): {', '.join(inactive)}")
            print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"{'=' * 65}\n")

        if demo:
            results = self.aggregator.run_demo(target_configs)
        else:
            def _progress(ticker, idx, tot):
                if verbose:
                    print(f"[{idx:02d}/{tot}] {ticker}...", end="  ", flush=True)

            results = self.aggregator.run_all(target_configs, progress_callback=_progress)
            if verbose:
                print()

        if verbose:
            self._print_leaderboard(results)

        return results

    def get_options_plays(
        self, top_n: int = 10, results: list = None, verbose: bool = True
    ) -> dict:
        """
        Generate this week's options plays from sentiment data.

        Args:
            top_n: Number of top signal movers to evaluate
            results: Pre-computed results; loads latest saved data if None
            verbose: Print formatted report

        Returns:
            Options plays dict
        """
        if results is None:
            results = self.aggregator.load_latest()

        if not results:
            msg = "No sentiment data. Run 'python main.py sentiment' first."
            if verbose:
                print(f"\nError: {msg}")
            return {"error": msg, "plays": []}

        if verbose:
            demo_note = " [DEMO DATA]" if results and results[0].get("_demo") else ""
            print(f"\nGenerating options plays from {len(results)} tickers{demo_note}...")

        plays_data = self.advisor.generate_plays(results, top_n=top_n)

        if verbose:
            print(self.advisor.format_report(plays_data))

        self._save_plays(plays_data)
        return plays_data

    def get_ticker_detail(self, ticker: str, demo: bool = False) -> dict:
        """Run a single-ticker deep-dive."""
        ticker = ticker.upper()
        print(f"\nRunning deep-dive for ${ticker}...")

        if demo:
            ticker_info = TICKER_MAP.get(ticker, {"ticker": ticker, "name": ticker, "sector": "", "tags": []})
            from .demo_data import generate_demo_signals
            raw_signals = generate_demo_signals(ticker, ticker_info)
            analysis = self.aggregator.analyzer.analyze_ticker(ticker, ticker_info["name"], raw_signals)
            result = {
                "ticker": ticker,
                "name": ticker_info["name"],
                "sector": ticker_info.get("sector", ""),
                "tags": ticker_info.get("tags", []),
                "raw_signals": raw_signals,
                "analysis": analysis,
                "run_at": datetime.now(timezone.utc).isoformat(),
                "_demo": True,
            }
        else:
            result = self.aggregator.run_single(ticker)

        self._print_ticker_detail(result)
        return result

    def get_trending(self) -> list:
        """Get live trending tickers from StockTwits."""
        trending = self.aggregator.get_trending_on_stocktwits()
        if trending:
            print(f"\nCurrently trending on StockTwits: {', '.join(trending[:15])}")
        else:
            print("\nStockTwits trending unavailable (set STOCKTWITS_ACCESS_TOKEN)")
        return trending

    def show_source_status(self):
        """Print which data sources are configured."""
        status = self.aggregator.source_status()
        print("\nData Source Configuration:")
        print("─" * 50)
        creds = {
            "stocktwits": "STOCKTWITS_ACCESS_TOKEN",
            "reddit": "REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET",
            "twitter": "TWITTER_BEARER_TOKEN",
            "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
        }
        for source, active in status.items():
            state = "✓ active" if active else "✗ not configured"
            cred = f"  ({creds[source]})" if source in creds and not active else ""
            print(f"  {source:<20} {state}{cred}")
        print()

    def load_latest_results(self) -> list:
        return self.aggregator.load_latest()

    def _print_leaderboard(self, results: list):
        sorted_r = sorted(results, key=lambda r: r["analysis"].get("score", 0), reverse=True)

        print(f"\n{'─' * 72}")
        print(f"  {'TICKER':<8} {'SCORE':>6}  {'SIGNAL':<15} {'CONF':<8} {'VOL':<10}  ST   RD")
        print(f"{'─' * 72}")

        for r in sorted_r:
            ticker = r["ticker"]
            a = r["analysis"]
            score = a.get("score", 0)
            label = a.get("sentiment_label", "N/A")[:14]
            conf = a.get("confidence", "?")[:7]
            vol = a.get("volume_signal", "?")[:9]
            st = r["raw_signals"].get("stocktwits", {})
            rd = r["raw_signals"].get("reddit", {})
            st_msgs = st.get("total_messages", 0)
            rd_posts = rd.get("total_posts", 0)
            arrow = "▲" if score > 0 else "▼" if score < 0 else "─"
            print(
                f"  {ticker:<8} {score:>+6}  {label:<15} {conf:<8} {vol:<10} "
                f"{st_msgs:>4} {rd_posts:>4}  {arrow}"
            )

        print(f"{'─' * 72}\n")

    def _print_ticker_detail(self, result: dict):
        ticker = result["ticker"]
        name = result["name"]
        a = result["analysis"]

        print(f"\n{'=' * 65}")
        print(f"  ${ticker} — {name}")
        print(f"  Score: {a.get('score', 0):+d}  |  {a.get('sentiment_label', '').upper()}  |  Confidence: {a.get('confidence', '?')}")
        print(f"  Volume Signal: {a.get('volume_signal', '?')}")
        if result.get("_demo"):
            print("  [DEMO DATA]")
        print(f"{'=' * 65}")

        print(f"\nNarrative:\n  {a.get('narrative', 'N/A')}")

        themes = a.get("key_themes", [])
        if themes:
            print(f"\nKey Themes: {', '.join(themes)}")

        quote = a.get("notable_quote")
        if quote:
            print(f"\nNotable:\n  \"{quote}\"")

        print(f"\nOptions Implication:\n  {a.get('options_implication', 'N/A')}")

        st = result["raw_signals"].get("stocktwits", {})
        rd = result["raw_signals"].get("reddit", {})
        tw = result["raw_signals"].get("twitter", {})
        yf = result["raw_signals"].get("yahoo_finance", {})

        print(f"\n{'─' * 65}  Raw Signals:")
        if not st.get("unavailable"):
            print(f"  StockTwits: {st.get('total_messages', 0)} msgs | {st.get('bullish', 0)}↑ {st.get('bearish', 0)}↓")
        else:
            print("  StockTwits: not configured")
        if not rd.get("unavailable"):
            print(f"  Reddit:     {rd.get('total_posts', 0)} posts | {rd.get('total_score', 0):,} upvotes | {rd.get('total_comments', 0):,} comments")
        else:
            print("  Reddit:     not configured")
        if not tw.get("unavailable"):
            print(f"  Twitter:    {tw.get('total_tweets', 0)} tweets | {tw.get('total_likes', 0):,} likes")
        if yf and not yf.get("error"):
            print(f"  Yahoo:      ${yf.get('price', 0):.2f} ({yf.get('pct_change', 0):+.2f}%) | {yf.get('total_articles', 0)} articles")
        print(f"{'─' * 65}\n")

    def _save_plays(self, plays_data: dict):
        SENTIMENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_file = SENTIMENT_DATA_DIR / f"options_plays_{timestamp}.json"
        latest_plays = SENTIMENT_DATA_DIR / "latest_plays.json"

        with open(out_file, "w") as f:
            json.dump(plays_data, f, indent=2)
        with open(latest_plays, "w") as f:
            json.dump(plays_data, f, indent=2)

        logger.info(f"Saved plays: {out_file.name}")
