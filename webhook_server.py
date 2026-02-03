#!/usr/bin/env python3
"""
GitHub Webhook Server for Auto-Deployment
Listens for push events and runs deploy.sh
"""

import subprocess
import hmac
import hashlib
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', 'your-secret-here')
DEPLOY_SCRIPT = '/opt/ai-news-scraper/deploy.sh'
PORT = 9000


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get('X-Hub-Signature-256', '')
        if not self.verify_signature(payload, signature):
            print("Invalid signature!")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Invalid signature')
            return

        # Parse payload
        try:
            data = json.loads(payload)
            ref = data.get('ref', '')

            # Only deploy on push to main branch
            if ref == 'refs/heads/main':
                print("Push to main detected! Deploying...")
                result = subprocess.run(
                    [DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True
                )
                print(f"Deploy output: {result.stdout}")
                if result.stderr:
                    print(f"Deploy errors: {result.stderr}")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Deployed successfully!')
            else:
                print(f"Push to {ref}, ignoring...")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Ignored (not main branch)')

        except Exception as e:
            print(f"Error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def verify_signature(self, payload, signature):
        if not signature or not WEBHOOK_SECRET:
            return WEBHOOK_SECRET == 'your-secret-here'  # Skip verification if no secret

        expected = 'sha256=' + hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def log_message(self, format, *args):
        print(f"[Webhook] {args[0]}")


if __name__ == '__main__':
    print(f"Starting webhook server on port {PORT}...")
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    server.serve_forever()
