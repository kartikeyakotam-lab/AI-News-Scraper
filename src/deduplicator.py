import logging
from typing import Set

from .parsers.base import Article
from .storage import Storage

logger = logging.getLogger(__name__)


class Deduplicator:
    """Handles deduplication of articles to prevent storing duplicates."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self._url_cache: dict[str, Set[str]] = {}

    def _get_existing_urls(self, source_name: str) -> Set[str]:
        """Get set of existing article URLs for a source."""
        if source_name not in self._url_cache:
            existing = self.storage.load_articles(source_name)
            self._url_cache[source_name] = {a.get('url', '') for a in existing}
        return self._url_cache[source_name]

    def filter_new_articles(self, source_name: str, articles: list[Article]) -> list[Article]:
        """
        Filter out articles that already exist in storage.

        Args:
            source_name: Name of the source
            articles: List of newly scraped articles

        Returns:
            List of articles that are new (not already stored)
        """
        existing_urls = self._get_existing_urls(source_name)
        new_articles = []

        for article in articles:
            if article.url not in existing_urls:
                new_articles.append(article)
                # Add to cache so subsequent calls in same session see it
                existing_urls.add(article.url)

        skipped = len(articles) - len(new_articles)
        if skipped > 0:
            logger.info(f"Filtered out {skipped} duplicate articles for {source_name}")

        return new_articles

    def merge_articles(self, source_name: str, new_articles: list[Article]) -> list[Article]:
        """
        Merge new articles with existing ones, maintaining order.

        Args:
            source_name: Name of the source
            new_articles: List of new articles to add

        Returns:
            Combined list with new articles first, then existing
        """
        # Load existing articles as Article objects
        existing_dicts = self.storage.load_articles(source_name)

        # Filter out duplicates from new articles
        new_filtered = self.filter_new_articles(source_name, new_articles)

        if not new_filtered:
            logger.info(f"No new articles to add for {source_name}")
            return [self._dict_to_article(d) for d in existing_dicts]

        # Combine: new articles first, then existing
        combined = new_filtered + [self._dict_to_article(d) for d in existing_dicts]

        logger.info(f"Added {len(new_filtered)} new articles for {source_name}")
        return combined

    def _dict_to_article(self, d: dict) -> Article:
        """Convert dictionary back to Article object."""
        return Article(
            id=d.get('id', ''),
            title=d.get('title', ''),
            url=d.get('url', ''),
            source=d.get('source', ''),
            source_name=d.get('source_name', ''),
            published_date=d.get('published_date'),
            summary=d.get('summary'),
            scraped_at=d.get('scraped_at', '')
        )

    def clear_cache(self):
        """Clear the URL cache to force reload from storage."""
        self._url_cache.clear()

    def get_duplicate_count(self, source_name: str, articles: list[Article]) -> int:
        """Get count of how many articles are duplicates."""
        existing_urls = self._get_existing_urls(source_name)
        return sum(1 for a in articles if a.url in existing_urls)
