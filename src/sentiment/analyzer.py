import os
import json
import re
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Uses Claude to synthesize raw social signal data into a structured sentiment score."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.info("ANTHROPIC_API_KEY not set — using heuristic fallback scorer")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def analyze_ticker(self, ticker: str, ticker_name: str, raw_signals: dict) -> dict:
        """
        Analyze multi-source raw signals and return a structured sentiment assessment.

        Sources in raw_signals:
          - stocktwits: native bullish/bearish labels (requires STOCKTWITS_ACCESS_TOKEN)
          - reddit: WSB/stocks discussion (requires REDDIT_CLIENT_ID + SECRET)
          - twitter: cashtag mention volume (requires TWITTER_BEARER_TOKEN)
          - yahoo_finance: news headlines + price context (free)
          - finviz: news headlines (free, scraped)

        Returns dict with: score, confidence, sentiment_label, volume_signal,
                           key_themes, narrative, notable_quote, options_implication
        """
        if not self.is_available():
            return self._fallback_score(raw_signals)

        context = self._build_signal_context(ticker, ticker_name, raw_signals)

        prompt = f"""You are a retail investor sentiment analyst specializing in weekly options trading signals.
Analyze the following data for ${ticker} ({ticker_name}) and produce a structured sentiment assessment.

{context}

Respond ONLY in this exact JSON format (no markdown, no extra text):
{{
    "score": <integer -100 (extreme bearish) to +100 (extreme bullish)>,
    "confidence": <"high" | "medium" | "low">,
    "sentiment_label": <"very_bullish" | "bullish" | "neutral" | "bearish" | "very_bearish">,
    "volume_signal": <"surge" | "elevated" | "normal" | "low">,
    "key_themes": ["<theme1>", "<theme2>", "<theme3>"],
    "narrative": "<2-3 sentences: what retail sentiment looks like right now and why>",
    "notable_quote": "<most representative post/headline, or null>",
    "options_implication": "<what this signal implies for weekly options — direction, IV, strategy type>"
}}

Scoring guide:
  +80 to +100: Extreme bullish frenzy, coordinated retail buying
  +50 to +79:  Strong bullish momentum, clear directional bias
  +20 to +49:  Mild bullish lean
  -19 to +19:  Mixed / neutral — no clear edge
  -20 to -49:  Mild bearish lean
  -50 to -79:  Strong negative sentiment
  -80 to -100: Panic or heavy bearish pressure

Use "high" confidence ONLY when multiple sources agree AND volume is significant.
Use "low" confidence when only 1-2 sources have data or signals conflict.
Weight social sources (StockTwits, Reddit, Twitter) more heavily than news headlines for sentiment score.
News headlines from Yahoo/Finviz are context — use them to explain the sentiment, not as primary score drivers."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                result = json.loads(json_match.group())
                result["score"] = max(-100, min(100, int(result.get("score", 0))))
                return result
            logger.warning(f"Could not parse JSON for {ticker}")
            return self._fallback_score(raw_signals)
        except Exception as e:
            logger.error(f"Analyzer error for {ticker}: {e}")
            return self._fallback_score(raw_signals)

    def _build_signal_context(self, ticker: str, ticker_name: str, raw_signals: dict) -> str:
        lines = [f"=== Signals for ${ticker} ({ticker_name}) ===\n"]

        # StockTwits
        st = raw_signals.get("stocktwits", {})
        if st and not st.get("unavailable") and not st.get("error"):
            total = st.get("total_messages", 0)
            bull = st.get("bullish", 0)
            bear = st.get("bearish", 0)
            wl = st.get("watchlist_count", 0)
            lines.append(f"STOCKTWITS — {total} messages:")
            lines.append(
                f"  Sentiment: {bull} Bullish / {bear} Bearish / {total - bull - bear} Neutral"
            )
            if wl:
                lines.append(f"  Watchlist count: {wl:,}")
            for post in st.get("top_posts", [])[:4]:
                tag = f"[{post['sentiment']}] " if post.get("sentiment") else ""
                likes_str = f" ❤{post['likes']}" if post.get("likes") else ""
                lines.append(f"  • {tag}{post.get('text', '')[:180]}{likes_str}")
            lines.append("")
        elif st and st.get("unavailable"):
            lines.append("STOCKTWITS — not configured (STOCKTWITS_ACCESS_TOKEN not set)\n")

        # Reddit
        rd = raw_signals.get("reddit", {})
        if rd and not rd.get("unavailable") and not rd.get("error"):
            lines.append(
                f"REDDIT — {rd.get('total_posts', 0)} posts | "
                f"{rd.get('total_score', 0):,} upvotes | "
                f"{rd.get('total_comments', 0):,} comments | "
                f"avg ratio {rd.get('avg_upvote_ratio', 0):.0%}"
            )
            for post in rd.get("top_posts", [])[:4]:
                lines.append(
                    f"  • [r/{post.get('subreddit', '')}] "
                    f"\"{post.get('title', '')[:120]}\" "
                    f"(+{post.get('score', 0)}, {post.get('num_comments', 0)} comments)"
                )
            lines.append("")
        elif rd and rd.get("unavailable"):
            lines.append("REDDIT — not configured (REDDIT_CLIENT_ID/SECRET not set)\n")

        # Twitter
        tw = raw_signals.get("twitter", {})
        if tw and not tw.get("unavailable") and not tw.get("error"):
            lines.append(
                f"TWITTER — {tw.get('total_tweets', 0)} tweets | "
                f"{tw.get('total_likes', 0):,} likes | "
                f"{tw.get('total_retweets', 0):,} RTs"
            )
            for t in tw.get("top_tweets", [])[:3]:
                lines.append(f"  • {t.get('text', '')[:160]} (❤{t.get('likes', 0)})")
            lines.append("")
        elif tw and tw.get("unavailable"):
            lines.append("TWITTER — not configured (TWITTER_BEARER_TOKEN not set)\n")

        # Yahoo Finance
        yf = raw_signals.get("yahoo_finance", {})
        if yf and not yf.get("error"):
            price = yf.get("price", 0)
            pct = yf.get("pct_change", 0)
            pct_str = f"{pct:+.2f}%" if pct else "N/A"
            lines.append(
                f"YAHOO FINANCE — Price: ${price:.2f} ({pct_str} today) | "
                f"{yf.get('total_articles', 0)} recent news articles | "
                f"Headlines: {yf.get('headline_bullish', 0)} positive / {yf.get('headline_bearish', 0)} negative"
            )
            for article in yf.get("recent_news", [])[:4]:
                lines.append(
                    f"  • [{article.get('publisher', '')}] {article.get('title', '')[:130]}"
                )
            lines.append("")

        # Finviz
        fv = raw_signals.get("finviz", {})
        if fv and not fv.get("error"):
            lines.append(
                f"FINVIZ — {fv.get('total_articles', 0)} articles | "
                f"Headlines: {fv.get('bullish_headlines', 0)} positive / {fv.get('bearish_headlines', 0)} negative"
            )
            for item in fv.get("recent_news", [])[:4]:
                lines.append(
                    f"  • [{item.get('source', '')}] {item.get('headline', '')[:130]}"
                )
            lines.append("")

        return "\n".join(lines)

    def _fallback_score(self, raw_signals: dict) -> dict:
        """Simple rule-based score when Claude is unavailable."""
        # Try to derive from StockTwits if available
        st = raw_signals.get("stocktwits", {})
        ratio = st.get("sentiment_ratio", 0.0)

        # Supplement with news headlines
        yf = raw_signals.get("yahoo_finance", {})
        fv = raw_signals.get("finviz", {})
        bull_news = yf.get("headline_bullish", 0) + fv.get("bullish_headlines", 0)
        bear_news = yf.get("headline_bearish", 0) + fv.get("bearish_headlines", 0)
        total_news = bull_news + bear_news
        news_ratio = (bull_news - bear_news) / total_news if total_news > 0 else 0

        # Weighted combo: social (60%) + news (40%)
        combined = ratio * 0.6 + news_ratio * 0.4
        score = int(combined * 60)

        label_map = [(50, "very_bullish"), (20, "bullish"), (-20, "neutral"), (-50, "bearish")]
        label = "very_bearish"
        for threshold, lbl in label_map:
            if score >= threshold:
                label = lbl
                break

        return {
            "score": max(-100, min(100, score)),
            "confidence": "low",
            "sentiment_label": label,
            "volume_signal": "normal",
            "key_themes": [],
            "narrative": "Fallback heuristic score — Claude API unavailable.",
            "notable_quote": None,
            "options_implication": "Insufficient data for options recommendation.",
        }
