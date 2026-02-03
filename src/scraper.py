import requests
import requests_cache
import time
import logging
from pathlib import Path
from typing import Optional
import yaml

from .parsers import RSSParser, BlogParser
from .parsers.base import Article

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Scraper:
    """Core web scraper for fetching and parsing news sources."""

    def __init__(self, config_path: str = "config/sources.yaml", use_cache: bool = True):
        self.config = self._load_config(config_path)
        self.sources = self.config.get('sources', [])
        self.defaults = self.config.get('defaults', {})

        # Set up session with optional caching
        if use_cache:
            cache_path = Path("data/.cache")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.session = requests_cache.CachedSession(
                str(cache_path),
                expire_after=3600  # Cache for 1 hour
            )
        else:
            self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'User-Agent': self.defaults.get('user_agent', 'AI-News-Scraper/1.0'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return {'sources': [], 'defaults': {}}

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def fetch(self, url: str, timeout: Optional[int] = None) -> Optional[str]:
        """
        Fetch content from a URL.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            Response content as string, or None if failed
        """
        timeout = timeout or self.defaults.get('request_timeout', 30)

        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def scrape_source(self, source: dict) -> list[Article]:
        """
        Scrape a single source.

        Args:
            source: Source configuration dictionary

        Returns:
            List of scraped articles
        """
        name = source.get('name', 'unknown')
        url = source.get('url')
        source_type = source.get('type', 'html')

        logger.info(f"Scraping {name} from {url}")

        # Fetch content
        content = self.fetch(url)
        if not content:
            logger.warning(f"No content received from {name}")
            return []

        # Select appropriate parser
        if source_type == 'rss':
            parser = RSSParser(source)
        else:
            parser = BlogParser(source)

        # Parse content
        articles = parser.parse(content)
        logger.info(f"Found {len(articles)} articles from {name}")

        # Apply max articles limit
        max_articles = self.defaults.get('max_articles_per_source', 50)
        return articles[:max_articles]

    def scrape_all(self) -> dict[str, list[Article]]:
        """
        Scrape all configured sources.

        Returns:
            Dictionary mapping source names to lists of articles
        """
        results = {}

        for source in self.sources:
            name = source.get('name', 'unknown')
            rate_limit = source.get('rate_limit_seconds', 1)

            try:
                articles = self.scrape_source(source)
                results[name] = articles
            except Exception as e:
                logger.error(f"Error scraping {name}: {e}")
                results[name] = []

            # Respect rate limit
            time.sleep(rate_limit)

        return results

    def scrape_by_name(self, source_name: str) -> list[Article]:
        """
        Scrape a specific source by name.

        Args:
            source_name: Name of the source to scrape

        Returns:
            List of scraped articles
        """
        for source in self.sources:
            if source.get('name') == source_name:
                return self.scrape_source(source)

        logger.warning(f"Source not found: {source_name}")
        return []

    def get_source_names(self) -> list[str]:
        """Get list of all configured source names."""
        return [s.get('name', 'unknown') for s in self.sources]
