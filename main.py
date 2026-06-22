#!/usr/bin/env python3
"""
AI News Scraper - CLI Entry Point

Commands:
    run      - Run scraper once immediately
    serve    - Start the web server
    schedule - Start the scheduler daemon
    list     - Show recent articles in terminal
"""

import argparse
import sys
import logging
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)


def cmd_run(args):
    """Run the scraper once."""
    from src.scraper import Scraper
    from src.storage import Storage
    from src.deduplicator import Deduplicator

    print("Starting AI News Scraper...")

    scraper = Scraper()
    storage = Storage()
    deduplicator = Deduplicator(storage)

    # Scrape all sources
    results = scraper.scrape_all()

    total_new = 0
    for source_name, articles in results.items():
        if articles:
            # Get count of truly new articles
            new_count = len(articles) - deduplicator.get_duplicate_count(source_name, articles)
            total_new += new_count

            # Merge and save
            merged = deduplicator.merge_articles(source_name, articles)
            storage.save_articles(source_name, merged)
            print(f"  {source_name}: {len(articles)} found, {new_count} new")

    # Update combined file
    total = storage.update_combined_file()

    print(f"\nScrape complete!")
    print(f"  Total articles: {total}")
    print(f"  New articles: {total_new}")


def cmd_serve(args):
    """Start the web server."""
    import uvicorn

    host = args.host or '0.0.0.0'
    port = args.port or 8000

    print(f"Starting web server at http://{host}:{port}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        reload=args.reload
    )


def cmd_schedule(args):
    """Start the scheduler daemon."""
    from src.scheduler import NewsScheduler

    interval = args.interval or 4

    print(f"Starting scheduler (every {interval} hours)")
    print("Press Ctrl+C to stop")

    scheduler = NewsScheduler(interval_hours=interval)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nScheduler stopped")


def cmd_list(args):
    """List recent articles in the terminal."""
    from src.storage import Storage

    storage = Storage()
    limit = args.limit or 20

    if args.source:
        articles = storage.get_articles_by_source(args.source, limit=limit)
        print(f"\nRecent articles from {args.source}:")
    else:
        articles = storage.get_recent_articles(limit=limit)
        print(f"\nRecent articles (all sources):")

    if not articles:
        print("  No articles found. Run 'python main.py run' to scrape.")
        return

    print("-" * 60)
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:55]
        source = article.get('source_name', 'Unknown')
        date = article.get('published_date', 'Unknown')[:10]

        print(f"{i:2}. [{source}] {title}")
        print(f"    {date} - {article.get('url', '')[:50]}...")
        print()


def cmd_search(args):
    """Search articles using AI."""
    from src.storage import Storage
    from src.ai_search import AISearch

    storage = Storage()
    ai = AISearch(storage)

    if not ai.is_available():
        print("Error: ANTHROPIC_API_KEY not set. AI search is unavailable.")
        sys.exit(1)

    query = ' '.join(args.query)
    print(f"Searching: {query}\n")

    result = ai.search(query)

    if result['success']:
        print(result['response'])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


def cmd_stats(args):
    """Show storage statistics."""
    from src.storage import Storage

    storage = Storage()
    stats = storage.get_stats()

    print("\nAI News Scraper Statistics")
    print("=" * 40)
    print(f"Total articles: {stats['total_articles']}")
    print(f"Last updated: {stats['last_updated'] or 'Never'}")
    print("\nArticles by source:")

    for source, count in sorted(stats['sources'].items()):
        print(f"  {source}: {count}")


def cmd_test_email(args):
    """Send a test email to verify SendGrid configuration."""
    from src.newsletter import Newsletter

    newsletter = Newsletter()

    if not newsletter.is_available():
        print("Error: Newsletter not available.")
        print("Check SENDGRID_API_KEY in your .env file.")
        return

    print("Sending test email...")
    result = newsletter.send_test_email()

    if result['success']:
        print(f"Success! Test email sent to {newsletter.to_email}")
    else:
        print(f"Failed: {result['message']}")


def cmd_retag(args):
    """Re-tag all existing articles with stock impacts."""
    from src.storage import Storage
    from src.stock_tagger import StockTagger
    import json

    storage = Storage()
    tagger = StockTagger()

    if not tagger.is_available():
        print("Error: Stock tagger not available. Check ANTHROPIC_API_KEY.")
        return

    limit = args.limit or 50
    articles = storage.get_recent_articles(limit=limit)

    print(f"Re-tagging {len(articles)} articles with stock impacts...")

    tagged_count = 0
    for i, article in enumerate(articles, 1):
        if article.get('impacted_stocks'):
            print(f"  {i}. Already tagged: {article['title'][:40]}...")
            continue

        print(f"  {i}. Tagging: {article['title'][:40]}...")
        result = tagger.tag_article(article)

        article['tldr'] = result['tldr']
        article['impacted_stocks'] = result['impacted_stocks']
        tagged_count += 1

        if result['impacted_stocks']:
            stocks = [s['ticker'] for s in result['impacted_stocks']]
            print(f"      -> Stocks: {', '.join(stocks)}")

    # Save updated articles back to combined file
    combined_file = storage._get_combined_file()
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Tagged {tagged_count} articles.")


def cmd_sentiment(args):
    """Run retail investor sentiment scan across top 25 names."""
    from src.sentiment.agent import SentimentAgent

    agent = SentimentAgent()
    tickers = args.ticker if args.ticker else None
    demo = getattr(args, 'demo', False)
    results = agent.run(tickers=tickers, verbose=True, demo=demo)

    if args.json:
        import json
        print(json.dumps(results, indent=2))

    print(f"Sentiment scan complete — {len(results)} tickers analyzed.")
    print("Run 'python main.py options-plays' to generate this week's options plays.")


def cmd_options_plays(args):
    """Generate weekly options plays from latest sentiment data."""
    from src.sentiment.agent import SentimentAgent

    agent = SentimentAgent()
    top_n = args.top or 10
    demo = getattr(args, 'demo', False)

    if args.refresh:
        print("Refreshing sentiment data first...")
        results = agent.run(verbose=True, demo=demo)
    else:
        results = None

    plays = agent.get_options_plays(top_n=top_n, results=results, verbose=True)

    if args.json:
        import json
        print(json.dumps(plays, indent=2))


def cmd_sentiment_detail(args):
    """Deep-dive sentiment for a single ticker."""
    from src.sentiment.agent import SentimentAgent

    agent = SentimentAgent()
    demo = getattr(args, 'demo', False)
    agent.get_ticker_detail(args.ticker, demo=demo)


def cmd_trending(args):
    """Show currently trending tickers on StockTwits."""
    from src.sentiment.agent import SentimentAgent

    agent = SentimentAgent()
    agent.get_trending()


def cmd_sentiment_sources(args):
    """Show which data sources are configured."""
    from src.sentiment.agent import SentimentAgent

    agent = SentimentAgent()
    agent.show_source_status()


def main():
    parser = argparse.ArgumentParser(
        description='AI News Scraper - Collect and search AI news with Claude',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run scraper once')

    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start web server')
    serve_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    serve_parser.add_argument('--port', type=int, default=8000, help='Port to listen on')
    serve_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')

    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Start scheduler daemon')
    schedule_parser.add_argument('--interval', type=int, help='Scrape interval in hours')

    # List command
    list_parser = subparsers.add_parser('list', help='List recent articles')
    list_parser.add_argument('--source', help='Filter by source name')
    list_parser.add_argument('--limit', type=int, default=20, help='Number of articles')

    # Search command
    search_parser = subparsers.add_parser('search', help='AI-powered search')
    search_parser.add_argument('query', nargs='+', help='Search query')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')

    # Test email command
    test_email_parser = subparsers.add_parser('test-email', help='Send test email')

    # Retag command
    retag_parser = subparsers.add_parser('retag', help='Re-tag articles with stock impacts')
    retag_parser.add_argument('--limit', type=int, default=50, help='Number of articles to tag')

    # Sentiment command
    sentiment_parser = subparsers.add_parser(
        'sentiment', help='Run retail investor sentiment scan (top 25 names)'
    )
    sentiment_parser.add_argument(
        '--ticker', nargs='+', metavar='TICKER',
        help='Limit scan to specific ticker(s), e.g. --ticker TSLA NVDA GME'
    )
    sentiment_parser.add_argument(
        '--demo', action='store_true',
        help='Use realistic mock data (no API keys required)'
    )
    sentiment_parser.add_argument(
        '--json', action='store_true', help='Also dump raw JSON output'
    )

    # Options plays command
    plays_parser = subparsers.add_parser(
        'options-plays', help='Generate weekly options plays from sentiment data'
    )
    plays_parser.add_argument(
        '--top', type=int, default=10, metavar='N',
        help='Number of top movers to consider (default: 10)'
    )
    plays_parser.add_argument(
        '--refresh', action='store_true',
        help='Re-run sentiment scan before generating plays'
    )
    plays_parser.add_argument(
        '--demo', action='store_true',
        help='Use realistic mock data (no API keys required)'
    )
    plays_parser.add_argument(
        '--json', action='store_true', help='Also dump raw JSON output'
    )

    # Sentiment detail command
    detail_parser = subparsers.add_parser(
        'sentiment-detail', help='Deep-dive sentiment for a single ticker'
    )
    detail_parser.add_argument('ticker', help='Ticker symbol, e.g. TSLA')
    detail_parser.add_argument('--demo', action='store_true', help='Use mock data')

    # Trending command
    trending_parser = subparsers.add_parser(
        'trending', help='Show currently trending tickers on StockTwits'
    )

    # Source status command
    subparsers.add_parser(
        'sentiment-sources', help='Show which sentiment data sources are configured'
    )

    args = parser.parse_args()

    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'serve':
        cmd_serve(args)
    elif args.command == 'schedule':
        cmd_schedule(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'search':
        cmd_search(args)
    elif args.command == 'stats':
        cmd_stats(args)
    elif args.command == 'test-email':
        cmd_test_email(args)
    elif args.command == 'retag':
        cmd_retag(args)
    elif args.command == 'sentiment':
        cmd_sentiment(args)
    elif args.command == 'options-plays':
        cmd_options_plays(args)
    elif args.command == 'sentiment-detail':
        cmd_sentiment_detail(args)
    elif args.command == 'trending':
        cmd_trending(args)
    elif args.command == 'sentiment-sources':
        cmd_sentiment_sources(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
