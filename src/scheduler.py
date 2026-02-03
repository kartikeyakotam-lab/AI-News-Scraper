import schedule
import time
import logging
import os
from datetime import datetime

from .scraper import Scraper
from .storage import Storage
from .deduplicator import Deduplicator
from .stock_tagger import StockTagger
from .newsletter import Newsletter

logger = logging.getLogger(__name__)


def run_scrape_job(send_newsletter: bool = True):
    """Execute a full scrape of all sources with stock tagging and newsletter."""
    logger.info(f"Starting scheduled scrape at {datetime.now().isoformat()}")

    try:
        scraper = Scraper()
        storage = Storage()
        deduplicator = Deduplicator(storage)
        stock_tagger = StockTagger()
        newsletter = Newsletter()

        # Scrape all sources
        results = scraper.scrape_all()

        # Track new articles for newsletter
        all_new_articles = []

        for source_name, articles in results.items():
            if articles:
                # Get count of truly new articles before merging
                new_count = len(articles) - deduplicator.get_duplicate_count(source_name, articles)

                # Filter to only new articles (for tagging)
                existing_urls = {a.get('url') for a in storage.load_articles(source_name)}
                new_articles = [a for a in articles if a.url not in existing_urls]

                # Tag new articles with stock impacts
                if new_articles and stock_tagger.is_available():
                    logger.info(f"Tagging {len(new_articles)} new articles from {source_name}")
                    for article in new_articles:
                        tag_result = stock_tagger.tag_article(article.to_dict())
                        # Store tagged data
                        tagged_dict = article.to_dict()
                        tagged_dict['tldr'] = tag_result['tldr']
                        tagged_dict['impacted_stocks'] = tag_result['impacted_stocks']
                        all_new_articles.append(tagged_dict)

                # Merge with existing, filtering duplicates
                merged = deduplicator.merge_articles(source_name, articles)
                # Save merged articles
                storage.save_articles(source_name, merged)

                if new_count > 0:
                    logger.info(f"Added {new_count} new articles from {source_name}")

        # Update combined file
        total = storage.update_combined_file()

        logger.info(f"Scrape complete. {len(all_new_articles)} new articles total.")

        # Send newsletter if there are new articles
        if send_newsletter and all_new_articles and newsletter.is_available():
            logger.info(f"Sending newsletter with {len(all_new_articles)} new articles...")
            result = newsletter.send_newsletter(all_new_articles)
            if result['success']:
                logger.info(f"Newsletter sent successfully!")
            else:
                logger.warning(f"Newsletter failed: {result['message']}")
        elif all_new_articles and not newsletter.is_available():
            logger.warning("Newsletter not available - check SENDGRID_API_KEY")

        return {
            "total_articles": total,
            "new_articles": len(all_new_articles),
            "newsletter_sent": send_newsletter and newsletter.is_available() and len(all_new_articles) > 0
        }

    except Exception as e:
        logger.error(f"Scrape job failed: {e}")
        return {"error": str(e)}


class NewsScheduler:
    """Scheduler for automatic news scraping."""

    def __init__(self, interval_hours: int = None):
        self.interval_hours = interval_hours or int(os.getenv('SCRAPE_INTERVAL_HOURS', 4))
        self.running = False

    def setup(self):
        """Set up the scheduled job."""
        schedule.clear()
        schedule.every(self.interval_hours).hours.do(run_scrape_job)
        logger.info(f"Scheduled scraping every {self.interval_hours} hours")

    def run_once(self, send_newsletter: bool = True):
        """Run the scrape job once immediately."""
        return run_scrape_job(send_newsletter=send_newsletter)

    def start(self):
        """Start the scheduler loop."""
        self.setup()

        # Run immediately on start
        logger.info("Running initial scrape...")
        run_scrape_job()

        logger.info("Starting scheduler loop...")
        self.running = True

        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def stop(self):
        """Stop the scheduler loop."""
        self.running = False
        logger.info("Scheduler stopped")

    def get_next_run(self) -> str:
        """Get the time of the next scheduled run."""
        jobs = schedule.get_jobs()
        if jobs:
            next_run = jobs[0].next_run
            return next_run.isoformat() if next_run else "Not scheduled"
        return "No jobs scheduled"

    def get_status(self) -> dict:
        """Get scheduler status information."""
        return {
            "running": self.running,
            "interval_hours": self.interval_hours,
            "next_run": self.get_next_run(),
            "job_count": len(schedule.get_jobs())
        }
