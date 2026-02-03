from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Optional
from .base import BaseParser, Article


class BlogParser(BaseParser):
    """Parser for HTML blog pages using CSS selectors."""

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.selectors = source_config.get('selectors', {})
        self.base_url = source_config.get('url', '')

    def parse(self, content: str) -> list[Article]:
        """Parse HTML content and extract articles."""
        articles = []
        soup = BeautifulSoup(content, 'lxml')

        # Find article containers
        article_selector = self.selectors.get('article_list', 'article')
        article_elements = soup.select(article_selector)

        # If no articles found with primary selector, try common patterns
        if not article_elements:
            article_elements = self._find_article_containers(soup)

        for element in article_elements:
            try:
                article = self._parse_article_element(element)
                if article:
                    articles.append(article)
            except Exception as e:
                print(f"Error parsing article element: {e}")
                continue

        return articles

    def _find_article_containers(self, soup: BeautifulSoup) -> list:
        """Fallback method to find article containers using common patterns."""
        patterns = [
            'article',
            '[class*="post"]',
            '[class*="article"]',
            '[class*="card"]',
            '[class*="entry"]',
            '[class*="news-item"]',
            '.blog-post',
            '.post-item'
        ]

        for pattern in patterns:
            elements = soup.select(pattern)
            if elements:
                return elements

        return []

    def _parse_article_element(self, element) -> Optional[Article]:
        """Parse a single article element."""
        # Extract title
        title = self._extract_title(element)
        if not title:
            return None

        # Extract link
        link = self._extract_link(element)
        if not link:
            return None

        # Make absolute URL
        link = urljoin(self.base_url, link)

        # Extract date
        published_date = self._extract_date(element)

        # Extract summary
        summary = self._extract_summary(element)

        return Article.create(
            title=title,
            url=link,
            source=self.source_name,
            source_name=self.display_name,
            published_date=published_date,
            summary=self.truncate_summary(summary)
        )

    def _extract_title(self, element) -> Optional[str]:
        """Extract title from article element."""
        selector = self.selectors.get('title', 'h1, h2, h3, [class*="title"]')

        # Try configured selector
        title_el = element.select_one(selector)
        if title_el:
            return self.clean_text(title_el.get_text())

        # Fallback: look for any heading
        for tag in ['h1', 'h2', 'h3', 'h4']:
            heading = element.find(tag)
            if heading:
                return self.clean_text(heading.get_text())

        # Last resort: try the first link text
        link = element.find('a')
        if link and link.get_text().strip():
            return self.clean_text(link.get_text())

        return None

    def _extract_link(self, element) -> Optional[str]:
        """Extract link from article element."""
        selector = self.selectors.get('link', 'a')

        # Try to find link in title first
        title_selector = self.selectors.get('title', 'h1, h2, h3')
        title_el = element.select_one(title_selector)
        if title_el:
            link = title_el.find('a')
            if link and link.get('href'):
                return link.get('href')

        # Try configured selector
        link_el = element.select_one(selector)
        if link_el and link_el.get('href'):
            href = link_el.get('href')
            # Skip anchor links and javascript
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                return href

        return None

    def _extract_date(self, element) -> Optional[str]:
        """Extract publication date from article element."""
        selector = self.selectors.get('date', 'time, [class*="date"], [datetime]')

        # Try time element with datetime attribute
        time_el = element.find('time')
        if time_el and time_el.get('datetime'):
            return time_el.get('datetime')

        # Try configured selector
        date_el = element.select_one(selector)
        if date_el:
            # Check for datetime attribute
            if date_el.get('datetime'):
                return date_el.get('datetime')
            # Get text content
            date_text = self.clean_text(date_el.get_text())
            if date_text:
                return date_text

        return None

    def _extract_summary(self, element) -> Optional[str]:
        """Extract summary/description from article element."""
        selector = self.selectors.get('summary', 'p, [class*="description"], [class*="excerpt"]')

        # Try configured selector
        summary_el = element.select_one(selector)
        if summary_el:
            text = self.clean_text(summary_el.get_text())
            if text and len(text) > 20:  # Skip very short text
                return text

        # Fallback: get first paragraph with substantial content
        for p in element.find_all('p'):
            text = self.clean_text(p.get_text())
            if text and len(text) > 50:
                return text

        return None
