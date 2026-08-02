"""Unit tests for Document Summary URL page text extraction."""

from services.knowledge.url_page_fetch import _extract_html_body_text


def test_extract_html_body_prefers_article_and_drops_nav() -> None:
    """Article body is kept; nav/footer noise is removed."""
    html = """
    <html>
      <head><title>Lesson Plan</title>
        <meta property="og:title" content="Photosynthesis Lesson" />
      </head>
      <body>
        <nav>Home About Contact</nav>
        <article>
          <h1>Photosynthesis</h1>
          <p>Plants convert light into energy.</p>
        </article>
        <footer>Copyright</footer>
      </body>
    </html>
    """
    text, title = _extract_html_body_text(html)
    assert title == "Photosynthesis Lesson"
    assert "Photosynthesis" in text
    assert "Plants convert light into energy." in text
    assert "Home About Contact" not in text
    assert "Copyright" not in text


def test_extract_html_body_falls_back_to_main() -> None:
    """When article is absent, main content is used."""
    html = """
    <html><head><title>Notes</title></head>
    <body>
      <main><p>Bridge map practice worksheet.</p></main>
      <aside>Related ads</aside>
    </body></html>
    """
    text, title = _extract_html_body_text(html)
    assert title == "Notes"
    assert "Bridge map practice worksheet." in text
    assert "Related ads" not in text
