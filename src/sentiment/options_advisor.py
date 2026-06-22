import os
import json
import re
import logging
from datetime import datetime, timezone

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class OptionsAdvisor:
    """Generates actionable weekly options plays from aggregated sentiment data."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key) if api_key else None

    def is_available(self) -> bool:
        return self.client is not None

    def generate_plays(self, sentiment_results: list, top_n: int = 10) -> dict:
        """
        Generate weekly options plays from sentiment results.

        Args:
            sentiment_results: List of analyzed ticker result dicts
            top_n: Number of top sentiment movers to consider for plays

        Returns:
            Dict with market_overview, plays list, avoid_list, generated_at
        """
        if not sentiment_results:
            return {"error": "No sentiment results to analyze", "plays": []}

        if not self.is_available():
            return self._rule_based_plays(sentiment_results, top_n)

        # Rank by absolute signal strength
        sorted_results = sorted(
            sentiment_results,
            key=lambda r: abs(r["analysis"].get("score", 0)),
            reverse=True,
        )
        top_movers = sorted_results[:top_n]

        context = self._build_mover_context(top_movers)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d (%A)")

        prompt = f"""You are a veteran retail options strategist. You specialize in weekly plays (0-7 DTE) driven by social media momentum and retail investor sentiment.

Today is {today}. You are setting up plays for THIS WEEK's options expiration.

Here is the retail sentiment data for the top movers right now:

{context}

Generate a specific, actionable weekly options playbook. Rules:
1. Only recommend plays with CLEAR directional or volatility signal
2. Prefer defined-risk strategies (spreads, debit spreads, long options) — naked positions need explicit sizing warning
3. Focus on highly liquid names with tight option spreads
4. Note IV environment — if IV is likely elevated after a sentiment surge, prefer spreads over long options
5. Skip names with mixed/neutral signals (score between -25 and +25 unless there's a volatility play)

Respond ONLY in this exact JSON (no markdown, no extra text):
{{
    "market_overview": "<2-3 sentences on the overall retail sentiment mood this week and what it means for options positioning>",
    "plays": [
        {{
            "ticker": "<TICKER>",
            "score": <sentiment score integer>,
            "conviction": "<high|medium|low>",
            "direction": "<bullish|bearish|neutral_volatility>",
            "strategy": "<specific strategy name, e.g. 'ATM call debit spread', 'Long weekly call', 'Straddle', 'Put debit spread'>",
            "strike_guidance": "<e.g. 'Buy ATM, sell 2 strikes OTM' or 'ATM straddle' or '$145/$150 call spread'>",
            "expiry_guidance": "<e.g. 'This Friday', '5-7 DTE', 'Current week expiry'>",
            "thesis": "<2-3 sentences: sentiment signal, what drives the play, entry catalyst>",
            "risk": "<the main risk that invalidates this play>",
            "max_loss_note": "<e.g. 'Defined risk — limited to premium paid' or 'Capped loss on spread'>",
            "iv_note": "<advice on IV — e.g. 'IV likely elevated; prefer spread over naked long' or 'IV appears normal, long options reasonable'>"
        }}
    ],
    "avoid_list": ["<TICKER1>", "<TICKER2>"],
    "avoid_reason": "<why to avoid those tickers this week — mixed signals, earnings risk, thin options liquidity, etc.>",
    "generated_at": "{datetime.now(timezone.utc).isoformat()}"
}}

Quality > quantity. 3-6 strong plays beats 10 weak ones."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                result = json.loads(json_match.group())
                result["generated_at"] = datetime.now(timezone.utc).isoformat()
                return result
            logger.warning("Could not parse options advisor JSON response")
            return {"error": "Could not parse response", "plays": [], "raw": text}
        except Exception as e:
            logger.error(f"Options advisor error: {e}")
            return {"error": str(e), "plays": []}

    def _build_mover_context(self, movers: list) -> str:
        lines = []
        for r in movers:
            ticker = r["ticker"]
            name = r["name"]
            analysis = r["analysis"]
            score = analysis.get("score", 0)
            label = analysis.get("sentiment_label", "unknown")
            confidence = analysis.get("confidence", "?")
            volume_signal = analysis.get("volume_signal", "?")
            narrative = analysis.get("narrative", "")
            options_impl = analysis.get("options_implication", "")
            themes = ", ".join(analysis.get("key_themes", []))

            st = r["raw_signals"].get("stocktwits", {})
            rd = r["raw_signals"].get("reddit", {})
            tw = r["raw_signals"].get("twitter", {})

            tw_line = ""
            if tw and not tw.get("unavailable"):
                tw_line = f"  Twitter: {tw.get('total_tweets', 0)} tweets, {tw.get('total_likes', 0):,} likes"

            lines.append(
                f"""
${ticker} ({name}) | Score: {score:+d} | {label.upper()} | Confidence: {confidence} | Volume: {volume_signal}
  StockTwits: {st.get('total_messages', 0)} msgs | {st.get('bullish', 0)} bull / {st.get('bearish', 0)} bear
  Reddit: {rd.get('total_posts', 0)} posts | {rd.get('total_score', 0):,} upvotes | {rd.get('total_comments', 0):,} comments{tw_line}
  Key themes: {themes or 'none identified'}
  Narrative: {narrative}
  Options signal: {options_impl}"""
            )
        return "\n".join(lines)

    def _rule_based_plays(self, sentiment_results: list, top_n: int) -> dict:
        """Rule-based fallback play generator when Claude API is unavailable."""
        sorted_r = sorted(
            sentiment_results,
            key=lambda r: abs(r["analysis"].get("score", 0)),
            reverse=True,
        )
        plays = []
        avoid = []

        for r in sorted_r[:top_n]:
            score = r["analysis"].get("score", 0)
            label = r["analysis"].get("sentiment_label", "neutral")
            ticker = r["ticker"]

            if abs(score) < 25:
                if abs(score) > 15:
                    avoid.append(ticker)
                continue

            if score >= 50:
                strategy = "ATM weekly call"
                direction = "bullish"
                conviction = "high"
            elif score >= 25:
                strategy = "ATM call debit spread"
                direction = "bullish"
                conviction = "medium"
            elif score <= -50:
                strategy = "ATM weekly put"
                direction = "bearish"
                conviction = "high"
            elif score <= -25:
                strategy = "ATM put debit spread"
                direction = "bearish"
                conviction = "medium"
            else:
                continue

            plays.append({
                "ticker": ticker,
                "score": score,
                "conviction": conviction,
                "direction": direction,
                "strategy": strategy,
                "strike_guidance": "ATM or 1 strike OTM",
                "expiry_guidance": "This Friday (weekly expiry)",
                "thesis": f"Retail sentiment score {score:+d} ({label}) from social signal aggregation.",
                "risk": "Sentiment can reverse quickly — size positions appropriately.",
                "max_loss_note": "Defined risk — limited to premium paid (for spreads, limited to spread width).",
                "iv_note": "Check IV rank before entry — prefer spreads if IV rank > 50%.",
            })

        total_bull = sum(1 for r in sentiment_results if r["analysis"].get("score", 0) > 10)
        total_bear = sum(1 for r in sentiment_results if r["analysis"].get("score", 0) < -10)
        mood = "bullish" if total_bull > total_bear else "bearish" if total_bear > total_bull else "mixed"

        return {
            "market_overview": (
                f"Rule-based analysis (ANTHROPIC_API_KEY not configured). "
                f"Overall retail mood appears {mood} — {total_bull} tickers bullish, "
                f"{total_bear} bearish across the tracked universe."
            ),
            "plays": plays,
            "avoid_list": avoid,
            "avoid_reason": "Mixed signals — insufficient directional conviction for weekly options.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "_rule_based": True,
        }

    def format_report(self, plays_data: dict) -> str:
        """Format plays data as a clean, readable text report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "=" * 70,
            "  WEEKLY OPTIONS PLAYS  —  RETAIL SENTIMENT SIGNAL",
            f"  {now_str}",
            "=" * 70,
            "",
            "MARKET OVERVIEW",
            "─" * 70,
            plays_data.get("market_overview", "N/A"),
            "",
        ]

        plays = plays_data.get("plays", [])
        if not plays:
            lines.append("No plays generated this week.")
        else:
            lines.append(f"PLAYS ({len(plays)} identified)")
            lines.append("─" * 70)

            for i, play in enumerate(plays, 1):
                direction_emoji = (
                    "▲" if play.get("direction") == "bullish"
                    else "▼" if play.get("direction") == "bearish"
                    else "↔"
                )
                conviction = play.get("conviction", "?").upper()
                lines.extend(
                    [
                        "",
                        f"#{i}  {play['ticker']}  {direction_emoji}  {play.get('strategy', '')}  [{conviction}]",
                        f"    Strikes:  {play.get('strike_guidance', 'N/A')}",
                        f"    Expiry:   {play.get('expiry_guidance', 'N/A')}",
                        f"    Thesis:   {play.get('thesis', '')}",
                        f"    Risk:     {play.get('risk', 'N/A')}",
                        f"    Max Loss: {play.get('max_loss_note', 'N/A')}",
                        f"    IV Note:  {play.get('iv_note', 'N/A')}",
                        f"    Score:    {play.get('score', 0):+d} sentiment",
                        "─" * 70,
                    ]
                )

        avoid = plays_data.get("avoid_list", [])
        if avoid:
            lines.extend(
                [
                    "",
                    f"AVOID THIS WEEK:  {', '.join(avoid)}",
                    f"  {plays_data.get('avoid_reason', '')}",
                ]
            )

        lines.extend(
            [
                "",
                "─" * 70,
                "DISCLAIMER: Educational purposes only. Not financial advice.",
                "Options trading carries substantial risk of loss. Size positions",
                "appropriately and never risk more than you can afford to lose.",
                "─" * 70,
            ]
        )
        return "\n".join(lines)
