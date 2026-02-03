import feedparser
from datetime import datetime
from typing import Optional
from .base import BaseParser, Article


class RSSParser(BaseParser):
    """Parser for RSS and Atom feeds."""

    def parse(self, content: str) -> list[Article]:
        """Parse RSS/Atom feed content and extract articles."""
        articles = []
        feed = feedparser.parse(content)

        for entry in feed.entries:
            try:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)
            except Exception as e:
                print(f"Error parsing RSS entry: {e}")
                continue

        return articles

    def _parse_entry(self, entry) -> Optional[Article]:
        """Parse a single RSS feed entry."""
        title = self.clean_text(getattr(entry, 'title', None))
        link = getattr(entry, 'link', None)

        if not title or not link:
            return None

        # Extract published date
        published_date = self._extract_date(entry)

        # Extract summary
        summary = self._extract_summary(entry)

        return Article.create(
            title=title,
            url=link,
            source=self.source_name,
            source_name=self.display_name,
            published_date=published_date,
            summary=self.truncate_summary(summary)
        )

    def _extract_date(self, entry) -> Optional[str]:
        """Extract and format publication date from RSS entry."""
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            date_tuple = getattr(entry, field, None)
            if date_tuple:
                try:
                    dt = datetime(*date_tuple[:6])
                    return dt.isoformat() + "Z"
                except Exception:
                    continue

        # Try string date fields
        string_fields = ['published', 'updated', 'created']
        for field in string_fields:
            date_str = getattr(entry, field, None)
            if date_str:
                return date_str

        return None

    def _extract_summary(self, entry) -> Optional[str]:
        """Extract summary/description from RSS entry."""
        # Try summary first
        summary = getattr(entry, 'summary', None)
        if summary:
            # Strip HTML tags for cleaner text
            return self._strip_html(summary)

        # Try description
        description = getattr(entry, 'description', None)
        if description:
            return self._strip_html(description)

        # Try content
        content = getattr(entry, 'content', None)
        if content and len(content) > 0:
            return self._strip_html(content[0].get('value', ''))

        return None

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags from text."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        return soup.get_text(separator=' ', strip=True)
