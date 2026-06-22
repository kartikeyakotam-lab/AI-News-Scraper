"""
Demo data generator for testing the sentiment pipeline without live API calls.

Run: python main.py sentiment --demo
"""
import random
from datetime import datetime, timezone
from .config import TICKERS

SAMPLE_STOCKTWITS_POSTS = {
    "bullish": [
        "YOLO calls on {ticker}, this thing is going to moon 🚀",
        "{ticker} chart looks incredible, breakout incoming",
        "Loading up on {ticker} calls for this week, conviction play",
        "Nobody is talking about {ticker} enough, this is the trade",
        "{ticker} is about to rip, retail hasn't caught on yet",
    ],
    "bearish": [
        "{ticker} is cooked, insiders selling, avoid",
        "Took profits on {ticker}, chart is breaking down",
        "{ticker} puts printing, this is not looking good",
        "Getting out of {ticker}, risk/reward terrible right now",
        "{ticker} is overvalued at these levels, puts make sense",
    ],
    "neutral": [
        "Watching {ticker} closely here, waiting for confirmation",
        "{ticker} moving sideways, need a catalyst",
        "Not sure about {ticker} direction, staying flat",
    ],
}

SAMPLE_REDDIT_POSTS = [
    {"title": "DD: Why {ticker} is the play of the week [Long]", "score_base": 800},
    {"title": "{ticker} earnings play — here's my thesis (with positions)", "score_base": 600},
    {"title": "Bought {ticker} calls, wish me luck boys 🦍", "score_base": 400},
    {"title": "Unpopular opinion: {ticker} is overrated at current levels", "score_base": 350},
    {"title": "Technical analysis on {ticker} — key levels to watch", "score_base": 250},
    {"title": "Anyone else loading {ticker} before the catalyst?", "score_base": 200},
]

SAMPLE_HEADLINES = [
    "{company} Stock Surges on Strong Quarterly Results",
    "Analysts Upgrade {company} to Buy, Raise Price Target",
    "{company} Partners with Major Tech Firm in AI Deal",
    "{company} Q3 Revenue Beats Estimates by 15%",
    "Institutional Investors Increase {company} Holdings",
    "{company} Announces Share Buyback Program",
    "{company} Faces Regulatory Scrutiny Over New Product",
    "{company} Stock Falls After Mixed Earnings Report",
    "Short Sellers Target {company} Amid Valuation Concerns",
    "{company} CEO Sells $50M in Shares",
]


def generate_demo_signals(ticker: str, ticker_info: dict, seed: int = None) -> dict:
    """
    Generate realistic mock signals for a ticker.

    Sentiment is deterministic per ticker (based on ticker hash) so
    repeated runs give consistent results for testing.
    """
    rng = random.Random(seed if seed is not None else hash(ticker) % 10000)
    name = ticker_info.get("name", ticker)
    is_meme = "meme" in ticker_info.get("tags", [])

    # Base sentiment bias: fraction of labeled msgs that are bullish (0.0 = all bear, 1.0 = all bull)
    if is_meme:
        bias = rng.uniform(0.35, 0.80)  # Meme stocks skew bullish on ST
    else:
        bias = rng.uniform(0.20, 0.65)  # Mix of bull/bear for other names

    # StockTwits mock
    total_msgs = rng.randint(30, 300) if is_meme else rng.randint(10, 80)
    labeled = int(total_msgs * rng.uniform(0.4, 0.7))
    bullish = max(0, int(labeled * bias))
    bearish = max(0, labeled - bullish)

    st_posts = []
    for _ in range(min(5, total_msgs)):
        if rng.random() < bias:
            template = rng.choice(SAMPLE_STOCKTWITS_POSTS["bullish"])
            sentiment = "Bullish"
        else:
            template = rng.choice(SAMPLE_STOCKTWITS_POSTS["bearish"])
            sentiment = "Bearish"
        st_posts.append({
            "text": template.format(ticker=ticker),
            "sentiment": sentiment,
            "likes": rng.randint(0, 50),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "username": f"trader_{rng.randint(1000, 9999)}",
        })

    stocktwits = {
        "ticker": ticker,
        "platform": "stocktwits",
        "total_messages": total_msgs,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": total_msgs - labeled,
        "sentiment_ratio": round((bullish - bearish) / max(labeled, 1), 4),
        "watchlist_count": rng.randint(5000, 200000),
        "top_posts": st_posts,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Reddit mock
    rd_posts = []
    num_posts = rng.randint(5, 40) if is_meme else rng.randint(1, 15)
    total_score = 0
    total_comments = 0
    for template_data in rng.choices(SAMPLE_REDDIT_POSTS, k=min(num_posts, 5)):
        score = int(template_data["score_base"] * rng.uniform(0.3, 2.0) * (1.5 if is_meme else 1.0))
        comments = int(score * rng.uniform(0.1, 0.4))
        total_score += score
        total_comments += comments
        rd_posts.append({
            "title": template_data["title"].format(ticker=ticker),
            "score": score,
            "num_comments": comments,
            "subreddit": rng.choice(["wallstreetbets", "stocks", "options"]),
            "url": f"https://reddit.com/r/wallstreetbets/comments/{ticker.lower()}_{rng.randint(10000, 99999)}",
            "upvote_ratio": round(rng.uniform(0.6, 0.95), 2),
            "text": "",
            "created_utc": 0,
            "flair": "DD" if rng.random() > 0.7 else "Discussion",
        })
    rd_posts.sort(key=lambda p: p["score"], reverse=True)

    reddit = {
        "ticker": ticker,
        "platform": "reddit",
        "total_posts": num_posts,
        "total_score": total_score,
        "total_comments": total_comments,
        "avg_upvote_ratio": round(rng.uniform(0.7, 0.9), 3),
        "subreddits_searched": ["wallstreetbets", "stocks", "options"],
        "top_posts": rd_posts,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Twitter mock
    has_twitter = rng.random() > 0.3  # 70% chance Twitter data present
    tweet_count = rng.randint(50, 2000) if (has_twitter and is_meme) else rng.randint(10, 300)
    twitter = {
        "ticker": ticker,
        "platform": "twitter",
        "total_tweets": tweet_count if has_twitter else 0,
        "total_likes": int(tweet_count * rng.uniform(2, 15)) if has_twitter else 0,
        "total_retweets": int(tweet_count * rng.uniform(0.3, 2)) if has_twitter else 0,
        "top_tweets": [
            {
                "text": f"${ticker} {'🚀' * rng.randint(1,3)} {'calls' if rng.random() > 0.4 else 'to the moon'}",
                "likes": rng.randint(10, 500),
            }
            for _ in range(3)
        ] if has_twitter else [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "unavailable": not has_twitter,
    }

    # Yahoo Finance / news mock
    price_base = {"TSLA": 248, "NVDA": 143, "AAPL": 196, "AMD": 128, "PLTR": 32,
                  "GME": 22, "AMC": 4, "SOFI": 9, "COIN": 185, "HOOD": 21,
                  "RIVN": 11, "NIO": 6, "MSTR": 380, "AMZN": 195, "META": 530,
                  "MSFT": 442, "GOOGL": 175, "SPY": 545, "QQQ": 471, "ARKK": 48,
                  "F": 10, "DIS": 98, "INTC": 21, "SMCI": 42, "BBAI": 3}.get(ticker, 100)
    price = round(price_base * rng.uniform(0.97, 1.03), 2)
    prev_close = round(price * rng.uniform(0.97, 1.03), 2)

    num_headlines = rng.randint(3, 10)
    headlines = []
    bull_hl = 0
    bear_hl = 0
    for _ in range(num_headlines):
        h = rng.choice(SAMPLE_HEADLINES).format(company=name, ticker=ticker)
        is_bull = "Surges" in h or "Beats" in h or "Upgrade" in h or "Partners" in h or "Buyback" in h
        is_bear = "Falls" in h or "Regulatory" in h or "Sells" in h or "Short" in h or "Concerns" in h
        if is_bull:
            bull_hl += 1
        if is_bear:
            bear_hl += 1
        headlines.append({"title": h, "publisher": rng.choice(["Reuters", "Bloomberg", "CNBC", "Benzinga"]), "link": "#"})

    yahoo_finance = {
        "ticker": ticker,
        "platform": "yahoo_finance",
        "total_articles": num_headlines,
        "headline_bullish": bull_hl,
        "headline_bearish": bear_hl,
        "price": price,
        "prev_close": prev_close,
        "pct_change": round((price - prev_close) / prev_close * 100, 2),
        "52w_high": round(price_base * rng.uniform(1.1, 1.6), 2),
        "52w_low": round(price_base * rng.uniform(0.4, 0.85), 2),
        "recent_news": headlines[:5],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    finviz = {
        "ticker": ticker,
        "platform": "finviz",
        "total_articles": rng.randint(3, 12),
        "bullish_headlines": bull_hl,
        "bearish_headlines": bear_hl,
        "recent_news": [{"headline": h["title"], "source": h["publisher"], "url": "#", "date": "Today"} for h in headlines[:4]],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "stocktwits": stocktwits,
        "reddit": reddit,
        "twitter": twitter,
        "yahoo_finance": yahoo_finance,
        "finviz": finviz,
    }


def generate_demo_results() -> list:
    """Generate a full set of demo results for all 25 tickers."""
    from .analyzer import SentimentAnalyzer
    import time

    analyzer = SentimentAnalyzer()
    results = []

    for ticker_info in TICKERS:
        ticker = ticker_info["ticker"]
        raw_signals = generate_demo_signals(ticker, ticker_info)
        analysis = analyzer.analyze_ticker(ticker, ticker_info["name"], raw_signals)
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
        time.sleep(0.2)  # Small delay between Claude calls

    return results
