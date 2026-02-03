# AI News Scraper

A Python web scraper that collects news from AI foundational model labs and SaaS-related AI startups, with a modern web UI and Claude-powered intelligent search.

## Features

- **Multi-source scraping**: Collects news from OpenAI, Anthropic, Google DeepMind, Meta AI, Mistral, Cohere, and major tech news sites
- **AI-powered search**: Ask natural language questions about the news using Claude
- **Modern web UI**: Clean, responsive dashboard with filtering and search
- **Scheduled execution**: Automatic scraping every few hours
- **Deduplication**: Prevents storing duplicate articles

## Quick Start

### 1. Install dependencies

```bash
cd ai-news-scraper
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Run the scraper

```bash
# Scrape all sources once
python main.py run

# Start the web server
python main.py serve

# Open http://localhost:8000 in your browser
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py run` | Run scraper once |
| `python main.py serve` | Start web server (default: port 8000) |
| `python main.py schedule` | Start scheduler daemon |
| `python main.py list` | Show recent articles in terminal |
| `python main.py search <query>` | AI-powered search from terminal |
| `python main.py stats` | Show storage statistics |

### Command Options

```bash
# Serve on different port
python main.py serve --port 3000

# Schedule with custom interval
python main.py schedule --interval 6

# List articles from specific source
python main.py list --source openai --limit 10
```

## News Sources

### Foundational Model Labs
- OpenAI Blog
- Anthropic News
- Google DeepMind Blog
- Meta AI Blog
- Mistral AI News
- Cohere Blog

### AI/SaaS News
- The Verge AI
- TechCrunch AI
- VentureBeat AI

## Project Structure

```
ai-news-scraper/
├── config/
│   └── sources.yaml      # News source definitions
├── src/
│   ├── scraper.py        # Core scraping logic
│   ├── parsers/          # HTML and RSS parsers
│   ├── storage.py        # JSON file storage
│   ├── deduplicator.py   # Duplicate prevention
│   ├── scheduler.py      # Automatic scheduling
│   └── ai_search.py      # Claude AI integration
├── web/
│   ├── app.py            # FastAPI server
│   ├── templates/        # HTML templates
│   └── static/           # CSS and JavaScript
├── data/
│   └── articles/         # Scraped articles (JSON)
├── logs/                 # Log files
├── main.py               # CLI entry point
└── requirements.txt      # Dependencies
```

## VPS Deployment (Hostinger)

1. **Upload files** to your VPS via SSH/SFTP

2. **Set up Python environment**:
```bash
cd /path/to/ai-news-scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
nano .env  # Add your ANTHROPIC_API_KEY
```

4. **Set up cron for automatic scraping**:
```bash
crontab -e
# Add: 0 */4 * * * cd /path/to/ai-news-scraper && ./venv/bin/python main.py run >> logs/cron.log 2>&1
```

5. **Run web server with systemd** (recommended):
```bash
# Create /etc/systemd/system/ai-news-scraper.service
sudo systemctl enable ai-news-scraper
sudo systemctl start ai-news-scraper
```

6. **Set up nginx reverse proxy** (optional, for HTTPS):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Adding New Sources

Edit `config/sources.yaml` to add new sources:

```yaml
- name: new_source
  display_name: "New Source Name"
  url: "https://example.com/blog"
  type: html  # or 'rss'
  selectors:
    article_list: "article"
    title: "h2"
    link: "a"
    date: "time"
    summary: "p"
  rate_limit_seconds: 2
```

## License

MIT
