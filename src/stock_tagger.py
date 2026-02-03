import os
import logging
import yaml
from pathlib import Path
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class StockTagger:
    """Uses Claude to analyze articles and tag impacted stocks from Raimo's coverage."""

    def __init__(self, stocks_config_path: str = "config/stocks.yaml"):
        self.stocks = self._load_stocks(stocks_config_path)
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set. Stock tagging will be disabled.")
            return
        self.client = Anthropic(api_key=api_key)

    def _load_stocks(self, config_path: str) -> list[dict]:
        """Load stocks from YAML config."""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Stocks config not found: {config_path}")
            return []

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('stocks', [])

    def is_available(self) -> bool:
        """Check if stock tagging is available."""
        return self.client is not None and len(self.stocks) > 0

    def _build_stocks_context(self) -> str:
        """Build context string describing all stocks."""
        lines = ["Here are the software stocks to consider:\n"]
        for stock in self.stocks:
            keywords = ", ".join(stock.get('keywords', []))
            lines.append(f"- {stock['ticker']} ({stock['name']}): {stock['sector']} - Keywords: {keywords}")
        return "\n".join(lines)

    def tag_article(self, article: dict) -> dict:
        """
        Analyze an article and tag which stocks it impacts.

        Args:
            article: Article dict with title, summary, source, url

        Returns:
            Dict with 'impacted_stocks', 'tldr', and 'analysis'
        """
        if not self.is_available():
            return {
                "impacted_stocks": [],
                "tldr": article.get('summary', '')[:200],
                "analysis": "Stock tagging unavailable"
            }

        title = article.get('title', 'Untitled')
        summary = article.get('summary', 'No summary')
        source = article.get('source_name', 'Unknown')
        url = article.get('url', '')

        stocks_context = self._build_stocks_context()

        prompt = f"""Analyze this AI news article and determine which software stocks from Raimo Lenschow's Barclays coverage list would be impacted.

{stocks_context}

ARTICLE:
Title: {title}
Source: {source}
Summary: {summary}
URL: {url}

Please provide:
1. A TLDR summary (1-2 sentences, like TLDR AI newsletter style - concise, informative, slightly witty)
2. List of impacted stock tickers (only from the list above, can be empty if none directly impacted)
3. Brief explanation of why each stock is impacted (1 sentence each)

Respond in this exact JSON format:
{{
    "tldr": "Your 1-2 sentence TLDR summary here",
    "impacted_stocks": [
        {{"ticker": "MSFT", "reason": "Microsoft's Copilot competes directly with this new AI feature"}},
        {{"ticker": "CRM", "reason": "Salesforce could integrate similar AI capabilities"}}
    ]
}}

If no stocks are clearly impacted, return an empty array for impacted_stocks.
Only include stocks that have a clear, direct connection to the news - don't stretch to include tangentially related stocks."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse the response
            response_text = response.content[0].text

            # Try to extract JSON from response
            import json
            import re

            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "tldr": result.get('tldr', summary[:200]),
                    "impacted_stocks": result.get('impacted_stocks', []),
                    "analysis": "Success"
                }
            else:
                return {
                    "tldr": summary[:200] if summary else title[:200],
                    "impacted_stocks": [],
                    "analysis": "Could not parse response"
                }

        except Exception as e:
            logger.error(f"Stock tagging error: {e}")
            return {
                "tldr": summary[:200] if summary else title[:200],
                "impacted_stocks": [],
                "analysis": f"Error: {str(e)}"
            }

    def tag_articles(self, articles: list[dict]) -> list[dict]:
        """
        Tag multiple articles with stock impacts.

        Args:
            articles: List of article dicts

        Returns:
            List of articles with added 'tldr' and 'impacted_stocks' fields
        """
        tagged_articles = []

        for article in articles:
            result = self.tag_article(article)

            # Add tagging results to article
            tagged_article = article.copy()
            tagged_article['tldr'] = result['tldr']
            tagged_article['impacted_stocks'] = result['impacted_stocks']

            tagged_articles.append(tagged_article)
            logger.info(f"Tagged article: {article.get('title', 'Untitled')[:50]}... - {len(result['impacted_stocks'])} stocks")

        return tagged_articles

    def get_stock_info(self, ticker: str) -> dict:
        """Get info about a specific stock."""
        for stock in self.stocks:
            if stock['ticker'] == ticker:
                return stock
        return None

    def get_all_tickers(self) -> list[str]:
        """Get list of all covered tickers."""
        return [s['ticker'] for s in self.stocks]
