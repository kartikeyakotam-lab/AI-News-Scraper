import schedule
import time
import logging
import os
from datetime import datetime

from .scraper import Scraper
from .storage import Storage
from .deduplicator import Deduplicator

logger = logging.getLogger(__name__)


def run_scrape_job():
    """Execute a full scrape of all sources."""
    logger.info(f"Starting scheduled scrape at {datetime.now().isoformat()}")

    try:
        scraper = Scraper()
        storage = Storage()
        deduplicator = Deduplicator(storage)

        # Scrape all sources
        results = scraper.scrape_all()

        total_new = 0
        for source_name, articles in results.items():
            if articles:
                # Merge with existing, filtering duplicates
                merged = deduplicator.merge_articles(source_name, articles)
                # Save merged articles
                storage.save_articles(source_name, merged)
                total_new += len(articles) - deduplicator.get_duplicate_count(source_name, articles)

        # Update combined file
        storage.update_combined_file()

        logger.info(f"Scrape complete. Added {total_new} new articles total.")

    except Exception as e:
        logger.error(f"Scrape job failed: {e}")


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

    def run_once(self):
        """Run the scrape job once immediately."""
        run_scrape_job()

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
