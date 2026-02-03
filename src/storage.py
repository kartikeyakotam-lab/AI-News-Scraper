import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from .parsers.base import Article

logger = logging.getLogger(__name__)


class Storage:
    """JSON file storage handler for articles."""

    def __init__(self, data_dir: str = "data/articles"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_source_file(self, source_name: str) -> Path:
        """Get the file path for a source's articles."""
        return self.data_dir / f"{source_name}.json"

    def _get_combined_file(self) -> Path:
        """Get the path for the combined articles file."""
        return self.data_dir / "all_articles.json"

    def load_articles(self, source_name: str) -> list[dict]:
        """Load articles for a specific source."""
        file_path = self._get_source_file(source_name)

        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading {file_path}: {e}")
            return []

    def save_articles(self, source_name: str, articles: list[Article]) -> int:
        """
        Save articles for a specific source.

        Args:
            source_name: Name of the source
            articles: List of Article objects to save

        Returns:
            Number of articles saved
        """
        file_path = self._get_source_file(source_name)

        # Convert to dictionaries
        article_dicts = [a.to_dict() for a in articles]

        try:
            # Write atomically by writing to temp file first
            temp_path = file_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(article_dicts, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)

            logger.info(f"Saved {len(articles)} articles to {file_path}")
            return len(articles)
        except IOError as e:
            logger.error(f"Error saving to {file_path}: {e}")
            return 0

    def load_all_articles(self) -> list[dict]:
        """Load all articles from all sources."""
        combined_file = self._get_combined_file()

        if combined_file.exists():
            try:
                with open(combined_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading combined file: {e}")

        # Fallback: load from individual files
        all_articles = []
        for file_path in self.data_dir.glob("*.json"):
            if file_path.name != "all_articles.json":
                articles = self.load_articles(file_path.stem)
                all_articles.extend(articles)

        return all_articles

    def update_combined_file(self) -> int:
        """
        Update the combined articles file from all source files.

        Returns:
            Total number of articles in combined file
        """
        all_articles = []
        seen_ids = set()

        for file_path in self.data_dir.glob("*.json"):
            if file_path.name == "all_articles.json":
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    articles = json.load(f)
                    for article in articles:
                        article_id = article.get('id')
                        if article_id and article_id not in seen_ids:
                            all_articles.append(article)
                            seen_ids.add(article_id)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading {file_path}: {e}")

        # Sort by scraped_at date (newest first)
        all_articles.sort(
            key=lambda x: x.get('scraped_at', ''),
            reverse=True
        )

        # Save combined file
        combined_file = self._get_combined_file()
        try:
            with open(combined_file, 'w', encoding='utf-8') as f:
                json.dump(all_articles, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated combined file with {len(all_articles)} articles")
        except IOError as e:
            logger.error(f"Error saving combined file: {e}")

        return len(all_articles)

    def get_article_by_id(self, article_id: str) -> Optional[dict]:
        """Get a single article by its ID."""
        articles = self.load_all_articles()
        for article in articles:
            if article.get('id') == article_id:
                return article
        return None

    def get_articles_by_source(self, source_name: str, limit: int = 50) -> list[dict]:
        """Get articles from a specific source."""
        articles = self.load_articles(source_name)
        return articles[:limit]

    def get_recent_articles(self, limit: int = 50) -> list[dict]:
        """Get most recent articles across all sources."""
        articles = self.load_all_articles()
        return articles[:limit]

    def get_stats(self) -> dict:
        """Get storage statistics."""
        stats = {
            "total_articles": 0,
            "sources": {},
            "last_updated": None
        }

        for file_path in self.data_dir.glob("*.json"):
            if file_path.name == "all_articles.json":
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    articles = json.load(f)
                    source_name = file_path.stem
                    count = len(articles)
                    stats["sources"][source_name] = count
                    stats["total_articles"] += count

                    # Track most recent update
                    if articles:
                        latest = max(a.get('scraped_at', '') for a in articles)
                        if not stats["last_updated"] or latest > stats["last_updated"]:
                            stats["last_updated"] = latest
            except (json.JSONDecodeError, IOError):
                continue

        return stats
