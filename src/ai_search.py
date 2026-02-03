import os
import logging
from datetime import datetime
from anthropic import Anthropic

from .storage import Storage

logger = logging.getLogger(__name__)


class AISearch:
    """Claude-powered intelligent search across scraped articles."""

    def __init__(self, storage: Storage = None):
        self.storage = storage or Storage()
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set. AI search will be disabled.")
            return

        self.client = Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        """Check if AI search is available."""
        return self.client is not None

    def _build_context(self, max_articles: int = 100) -> str:
        """Build context string from recent articles."""
        articles = self.storage.get_recent_articles(limit=max_articles)

        if not articles:
            return "No articles available."

        context_parts = []
        for article in articles:
            part = f"""
---
Title: {article.get('title', 'Untitled')}
Source: {article.get('source_name', 'Unknown')}
Date: {article.get('published_date', 'Unknown')}
URL: {article.get('url', '')}
Summary: {article.get('summary', 'No summary available.')}
---"""
            context_parts.append(part)

        return "\n".join(context_parts)

    def search(self, query: str, max_articles: int = 100) -> dict:
        """
        Perform intelligent search using Claude.

        Args:
            query: Natural language search query
            max_articles: Maximum number of articles to include in context

        Returns:
            Dictionary with 'response' and 'success' keys
        """
        if not self.is_available():
            return {
                "success": False,
                "response": "AI search is not available. Please set ANTHROPIC_API_KEY.",
                "error": "API key not configured"
            }

        # Build context from articles
        context = self._build_context(max_articles)

        # Build the prompt
        system_prompt = """You are an AI assistant helping users explore and understand news about AI companies, foundational model labs, and SaaS startups.

You have access to a collection of recently scraped news articles. When answering questions:
- Be concise and informative
- Reference specific articles when relevant
- If information isn't in the provided articles, say so clearly
- Format your response nicely with bullet points or sections when appropriate
- Include relevant URLs so users can read the full articles"""

        user_message = f"""Here are the recent AI news articles I have access to:

{context}

User's question: {query}

Please answer based on the articles above. If the answer isn't in these articles, let me know."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            answer = response.content[0].text

            return {
                "success": True,
                "response": answer,
                "articles_searched": len(self.storage.get_recent_articles(limit=max_articles)),
                "query": query,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"AI search error: {e}")
            return {
                "success": False,
                "response": f"An error occurred during search: {str(e)}",
                "error": str(e)
            }

    def summarize_recent(self, hours: int = 24) -> dict:
        """
        Get an AI-generated summary of recent news.

        Args:
            hours: Look back this many hours

        Returns:
            Dictionary with summary response
        """
        return self.search(
            f"Summarize the most important AI news and announcements from the past {hours} hours. "
            "Highlight any major model releases, company updates, or significant developments."
        )

    def compare_companies(self, companies: list[str]) -> dict:
        """
        Compare recent news between companies.

        Args:
            companies: List of company names to compare

        Returns:
            Dictionary with comparison response
        """
        company_list = ", ".join(companies)
        return self.search(
            f"Compare the recent news and announcements from these companies: {company_list}. "
            "What has each company been focusing on? Any notable differences or similarities?"
        )

    def get_topic_insights(self, topic: str) -> dict:
        """
        Get insights about a specific topic from the news.

        Args:
            topic: Topic to analyze (e.g., "multimodal models", "AI safety")

        Returns:
            Dictionary with insights response
        """
        return self.search(
            f"What are the recent developments and discussions about '{topic}' in AI? "
            "Summarize key points and mention which companies are involved."
        )
