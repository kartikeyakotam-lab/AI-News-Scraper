"""
Top 25 retail investor tickers tracked for weekly options sentiment plays.

Selection criteria:
- High retail interest and discussion volume on social platforms
- Liquid options markets (tight spreads, weekly expirations available)
- Mix of meme names, high-beta growth, and mega-caps with retail following
"""

TICKERS = [
    {
        "ticker": "TSLA",
        "name": "Tesla",
        "sector": "EV/Tech",
        "tags": ["ev", "meme", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA",
        "sector": "Semiconductors",
        "tags": ["ai", "gpu", "high_retail_interest", "options_liquid"],
    },
    {
        "ticker": "AAPL",
        "name": "Apple",
        "sector": "Consumer Tech",
        "tags": ["mega_cap", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "AMD",
        "name": "Advanced Micro Devices",
        "sector": "Semiconductors",
        "tags": ["ai", "gpu", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "PLTR",
        "name": "Palantir",
        "sector": "Data/AI",
        "tags": ["ai", "data", "retail_favorite", "meme", "options_liquid"],
    },
    {
        "ticker": "GME",
        "name": "GameStop",
        "sector": "Retail",
        "tags": ["meme", "short_squeeze", "retail_driven", "options_liquid"],
    },
    {
        "ticker": "AMC",
        "name": "AMC Entertainment",
        "sector": "Entertainment",
        "tags": ["meme", "short_squeeze", "options_liquid"],
    },
    {
        "ticker": "SOFI",
        "name": "SoFi Technologies",
        "sector": "FinTech",
        "tags": ["fintech", "retail_favorite"],
    },
    {
        "ticker": "COIN",
        "name": "Coinbase Global",
        "sector": "Crypto/FinTech",
        "tags": ["crypto", "fintech", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "HOOD",
        "name": "Robinhood Markets",
        "sector": "FinTech",
        "tags": ["fintech", "retail_platform"],
    },
    {
        "ticker": "RIVN",
        "name": "Rivian Automotive",
        "sector": "EV",
        "tags": ["ev", "retail_favorite"],
    },
    {
        "ticker": "NIO",
        "name": "NIO Inc",
        "sector": "EV",
        "tags": ["ev", "china", "retail_favorite"],
    },
    {
        "ticker": "MSTR",
        "name": "MicroStrategy",
        "sector": "Bitcoin/Tech",
        "tags": ["bitcoin", "crypto", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "AMZN",
        "name": "Amazon",
        "sector": "E-Commerce/Cloud",
        "tags": ["mega_cap", "ai", "options_liquid"],
    },
    {
        "ticker": "META",
        "name": "Meta Platforms",
        "sector": "Social Media/AI",
        "tags": ["mega_cap", "ai", "options_liquid"],
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft",
        "sector": "Cloud/AI",
        "tags": ["mega_cap", "ai", "options_liquid"],
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet",
        "sector": "Cloud/AI/Ads",
        "tags": ["mega_cap", "ai", "options_liquid"],
    },
    {
        "ticker": "SPY",
        "name": "SPDR S&P 500 ETF",
        "sector": "ETF",
        "tags": ["etf", "options_liquid", "macro"],
    },
    {
        "ticker": "QQQ",
        "name": "Invesco Nasdaq ETF",
        "sector": "ETF",
        "tags": ["etf", "options_liquid", "macro"],
    },
    {
        "ticker": "ARKK",
        "name": "ARK Innovation ETF",
        "sector": "ETF",
        "tags": ["etf", "growth", "retail_favorite"],
    },
    {
        "ticker": "F",
        "name": "Ford Motor",
        "sector": "Auto/EV",
        "tags": ["ev", "auto", "retail_favorite"],
    },
    {
        "ticker": "DIS",
        "name": "Walt Disney",
        "sector": "Entertainment",
        "tags": ["entertainment", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "INTC",
        "name": "Intel",
        "sector": "Semiconductors",
        "tags": ["semis", "turnaround", "retail_favorite"],
    },
    {
        "ticker": "SMCI",
        "name": "Super Micro Computer",
        "sector": "AI Infrastructure",
        "tags": ["ai", "servers", "retail_favorite", "options_liquid"],
    },
    {
        "ticker": "BBAI",
        "name": "BigBear.ai",
        "sector": "AI/Defense",
        "tags": ["ai", "defense", "meme", "retail_favorite"],
    },
]

# Ticker lookup dict for fast access
TICKER_MAP = {t["ticker"]: t for t in TICKERS}
