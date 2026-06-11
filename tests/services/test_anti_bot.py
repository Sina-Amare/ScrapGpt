from app.services.anti_bot import anti_bot_challenge_reason


def test_detects_cloudflare_challenge_page():
    html = """
    <html>
      <title>Just a moment...</title>
      <script src="/cdn-cgi/challenge-platform/h/b/orchestrate/jsch/v1"></script>
      <body>Checking if the site connection is secure</body>
    </html>
    """

    assert anti_bot_challenge_reason(html, "https://example.com/") == "cloudflare_challenge"


def test_ignores_normal_cloudflare_asset_reference():
    html = """
    <html>
      <body>
        <h1>Research articles</h1>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/app.js"></script>
      </body>
    </html>
    """

    assert anti_bot_challenge_reason(html, "https://example.com/") is None
