from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class Article:
    """Represents a scraped article."""
    id: str
    title: str
    url: str
    source: str
    source_name: str
    published_date: Optional[str]
    summary: Optional[str]
    scraped_at: str

    @classmethod
    def create(cls, title: str, url: str, source: str, source_name: str,
               published_date: Optional[str] = None, summary: Optional[str] = None) -> 'Article':
        """Factory method to create an article with auto-generated id and timestamp."""
        article_id = hashlib.sha256(url.encode()).hexdigest()[:16]
        scraped_at = datetime.utcnow().isoformat() + "Z"
        return cls(
            id=article_id,
            title=title,
            url=url,
            source=source,
            source_name=source_name,
            published_date=published_date,
            summary=summary,
            scraped_at=scraped_at
        )

    def to_dict(self) -> dict:
        """Convert article to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "source_name": self.source_name,
            "published_date": self.published_date,
            "summary": self.summary,
            "scraped_at": self.scraped_at
        }


class BaseParser(ABC):
    """Abstract base class for all parsers."""

    def __init__(self, source_config: dict):
        self.source_config = source_config
        self.source_name = source_config.get('name', 'unknown')
        self.display_name = source_config.get('display_name', self.source_name)

    @abstractmethod
    def parse(self, content: str) -> list[Article]:
        """
        Parse content and extract articles.

        Args:
            content: Raw HTML or XML content to parse

        Returns:
            List of Article objects
        """
        pass

    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean and normalize text content."""
        if not text:
            return None
        return ' '.join(text.split()).strip()

    def truncate_summary(self, text: Optional[str], max_length: int = 300) -> Optional[str]:
        """Truncate summary to max length with ellipsis."""
        if not text:
            return None
        text = self.clean_text(text)
        if text and len(text) > max_length:
            return text[:max_length - 3] + "..."
        return text
