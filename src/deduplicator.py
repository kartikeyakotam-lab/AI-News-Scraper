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

    def _has_valid_date(self, article: Article) -> bool:
        """Check if article has a valid date."""
        date = article.published_date or article.scraped_at
        if not date:
            return False
        if date == '1970-01-01' or str(date).startswith('1970'):
            return False
        return True

    def filter_new_articles(self, source_name: str, articles: list[Article]) -> list[Article]:
        """
        Filter out articles that already exist in storage or don't have valid dates.

        Args:
            source_name: Name of the source
            articles: List of newly scraped articles

        Returns:
            List of articles that are new (not already stored) and have valid dates
        """
        existing_urls = self._get_existing_urls(source_name)
        new_articles = []
        no_date_count = 0

        for article in articles:
            # Skip articles without valid dates
            if not self._has_valid_date(article):
                no_date_count += 1
                continue

            if article.url not in existing_urls:
                new_articles.append(article)
                # Add to cache so subsequent calls in same session see it
                existing_urls.add(article.url)

        skipped = len(articles) - len(new_articles) - no_date_count
        if skipped > 0:
            logger.info(f"Filtered out {skipped} duplicate articles for {source_name}")
        if no_date_count > 0:
            logger.info(f"Filtered out {no_date_count} articles without dates for {source_name}")

        return new_articles

    def merge_articles(self, source_name: str, new_articles: list[Article]) -> list[Article]:
        """
        Merge new articles with existing ones, maintaining order.
        Only keeps articles with valid dates.

        Args:
            source_name: Name of the source
            new_articles: List of new articles to add

        Returns:
            Combined list with new articles first, then existing (all with valid dates)
        """
        # Load existing articles as Article objects
        existing_dicts = self.storage.load_articles(source_name)

        # Filter out duplicates and articles without dates from new articles
        new_filtered = self.filter_new_articles(source_name, new_articles)

        # Convert existing to Article objects and filter out those without dates
        existing_articles = [self._dict_to_article(d) for d in existing_dicts]
        existing_with_dates = [a for a in existing_articles if self._has_valid_date(a)]

        removed_no_date = len(existing_articles) - len(existing_with_dates)
        if removed_no_date > 0:
            logger.info(f"Removed {removed_no_date} existing articles without dates for {source_name}")

        if not new_filtered:
            logger.info(f"No new articles to add for {source_name}")
            return existing_with_dates

        # Combine: new articles first, then existing
        combined = new_filtered + existing_with_dates

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
