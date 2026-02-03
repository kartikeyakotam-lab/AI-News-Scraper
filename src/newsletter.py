import os
import logging
from datetime import datetime
from typing import Optional
import base64

logger = logging.getLogger(__name__)

# SendGrid import - will fail gracefully if not installed
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logger.warning("SendGrid not installed. Run: pip install sendgrid")


class Newsletter:
    """Sends email newsletters with AI news updates."""

    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('SENDGRID_FROM_EMAIL', 'kartikainewsscraper@example.com')
        self.to_email = os.getenv('NEWSLETTER_TO_EMAIL', 'kartikeyakotam@gmail.com')
        self.client = None

        if SENDGRID_AVAILABLE and self.api_key:
            self.client = SendGridAPIClient(self.api_key)

    def is_available(self) -> bool:
        """Check if newsletter sending is available."""
        return self.client is not None

    def _generate_html(self, articles: list[dict], date_str: str) -> str:
        """Generate HTML email content in TLDR AI style."""

        # Build articles HTML
        articles_html = ""
        for i, article in enumerate(articles, 1):
            title = article.get('title', 'Untitled')
            url = article.get('url', '#')
            source = article.get('source_name', 'Unknown')
            tldr = article.get('tldr', article.get('summary', 'No summary available.')[:200])
            impacted_stocks = article.get('impacted_stocks', [])

            # Build stocks badges
            stocks_html = ""
            if impacted_stocks:
                stocks_badges = " ".join([
                    f'<span style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 4px; margin-bottom: 4px;">{s["ticker"]}</span>'
                    for s in impacted_stocks
                ])
                stocks_html = f'''
                <div style="margin-top: 8px;">
                    <span style="color: #6b7280; font-size: 12px; margin-right: 8px;">📊 Impacted:</span>
                    {stocks_badges}
                </div>
                '''

                # Add reasons
                reasons_html = "<ul style='margin: 8px 0 0 0; padding-left: 20px; font-size: 12px; color: #6b7280;'>"
                for s in impacted_stocks:
                    reasons_html += f"<li><strong>{s['ticker']}</strong>: {s.get('reason', 'Potentially impacted')}</li>"
                reasons_html += "</ul>"
                stocks_html += reasons_html

            articles_html += f'''
            <div style="background: white; border-radius: 16px; padding: 20px; margin-bottom: 16px; border: 1px solid #e5e7eb; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="background: #f3f4f6; color: #4b5563; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;">{source}</span>
                    <span style="color: #9ca3af; font-size: 12px;">#{i}</span>
                </div>
                <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600;">
                    <a href="{url}" style="color: #1f2937; text-decoration: none;" target="_blank">{title}</a>
                </h3>
                <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.5;">{tldr}</p>
                {stocks_html}
                <a href="{url}" style="display: inline-block; margin-top: 12px; color: #8b5cf6; font-size: 13px; font-weight: 500; text-decoration: none;" target="_blank">
                    Read more →
                </a>
            </div>
            '''

        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kartik AI News - {date_str}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: linear-gradient(135deg, #f5f3ff 0%, #ffffff 50%, #ecfeff 100%);">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="text-align: center; padding: 30px 0;">
            <div style="display: inline-block; background: linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%); width: 60px; height: 60px; border-radius: 20px; margin-bottom: 16px; line-height: 60px; font-size: 28px;">
                🤖
            </div>
            <h1 style="margin: 0; font-size: 28px; font-weight: 700; background: linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                Kartik AI News
            </h1>
            <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 14px;">
                {date_str} • {len(articles)} new articles
            </p>
        </div>

        <!-- Summary -->
        <div style="background: linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%); border-radius: 16px; padding: 20px; margin-bottom: 24px; color: white;">
            <h2 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">📰 Today's AI News Digest</h2>
            <p style="margin: 0; font-size: 14px; opacity: 0.9;">
                Your personalized roundup of the latest AI developments from foundational model labs and top SaaS companies, with stock impact analysis.
            </p>
        </div>

        <!-- Articles -->
        <div>
            {articles_html}
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 30px 0; border-top: 1px solid #e5e7eb; margin-top: 20px;">
            <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 12px;">
                Powered by Claude AI • Tracking Raimo Lenschow's Software Coverage
            </p>
            <p style="margin: 0; color: #9ca3af; font-size: 11px;">
                AI News Scraper • Built with ❤️
            </p>
        </div>
    </div>
</body>
</html>
'''
        return html

    def send_newsletter(self, articles: list[dict], subject: Optional[str] = None) -> dict:
        """
        Send newsletter email with new articles.

        Args:
            articles: List of articles with tldr and impacted_stocks
            subject: Optional custom subject line

        Returns:
            Dict with 'success' and 'message'
        """
        if not self.is_available():
            return {
                "success": False,
                "message": "Newsletter not available. Check SENDGRID_API_KEY."
            }

        if not articles:
            return {
                "success": False,
                "message": "No articles to send."
            }

        # Generate date string
        date_str = datetime.now().strftime("%B %d, %Y")

        # Default subject
        if not subject:
            subject = f"🤖 Kartik AI News - {len(articles)} New Articles ({date_str})"

        # Generate HTML content
        html_content = self._generate_html(articles, date_str)

        try:
            message = Mail(
                from_email=Email(self.from_email, "Kartik AI News"),
                to_emails=To(self.to_email),
                subject=subject,
                html_content=HtmlContent(html_content)
            )

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Newsletter sent successfully to {self.to_email}")
                return {
                    "success": True,
                    "message": f"Newsletter sent to {self.to_email}",
                    "articles_count": len(articles)
                }
            else:
                logger.error(f"SendGrid error: {response.status_code}")
                return {
                    "success": False,
                    "message": f"SendGrid error: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Newsletter send error: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    def send_test_email(self) -> dict:
        """Send a test email to verify configuration."""
        test_articles = [
            {
                "title": "Test Article - AI News Scraper is Working!",
                "url": "https://example.com",
                "source_name": "Test Source",
                "tldr": "This is a test email to verify your Kartik AI News newsletter is configured correctly. If you're reading this, everything is working! 🎉",
                "impacted_stocks": [
                    {"ticker": "MSFT", "reason": "Test stock impact"},
                    {"ticker": "CRM", "reason": "Another test impact"}
                ]
            }
        ]

        return self.send_newsletter(
            test_articles,
            subject="🧪 Kartik AI News - Test Email"
        )
