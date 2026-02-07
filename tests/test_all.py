"""Tests for Moltbook scraper module."""

import pytest

# These tests work offline by mocking HTTP responses


class TestScraperHelpers:
    """Test helper functions that don't require API access."""

    def test_headers_include_auth(self):
        """Verify auth header format."""
        import os
        os.environ["MOLTBOOK_API_KEY"] = "test_key_123"

        from scrapers.moltbook_scraper import _headers
        h = _headers()

        assert "Authorization" in h
        assert h["Authorization"] == "Bearer test_key_123"
        assert h["Content-Type"] == "application/json"

    def test_base_url_uses_www(self):
        """Ensure base URL includes www to avoid redirect issues."""
        from scrapers.moltbook_scraper import BASE_URL
        assert "www.moltbook.com" in BASE_URL


class TestAnalyzer:
    """Test trend analyzer functions."""

    def test_keyword_extraction(self):
        from analyzers.trend_analyzer import extract_keywords

        posts = [
            {"title": "Blockchain security is important", "content": "We need better security for blockchain agents."},
            {"title": "Blockchain agents are powerful", "content": "Blockchain technology enables powerful autonomous agents."},
        ]

        keywords = extract_keywords(posts, top_n=5)
        assert len(keywords) > 0
        assert keywords[0]["count"] > 0

        # "blockchain" should be a top keyword
        kw_words = [k["keyword"] for k in keywords]
        assert "blockchain" in kw_words or "security" in kw_words

    def test_empty_posts(self):
        from analyzers.trend_analyzer import extract_keywords
        keywords = extract_keywords([], top_n=5)
        assert keywords == []


class TestSentiment:
    """Test sentiment analyzer."""

    def test_positive_text(self):
        from analyzers.sentiment_analyzer import score_text
        result = score_text("This is amazing and wonderful and brilliant!")
        assert result["label"] == "positive"
        assert result["positive"] > 0

    def test_negative_text(self):
        from analyzers.sentiment_analyzer import score_text
        result = score_text("This is terrible and horrible and dangerous!")
        assert result["label"] == "negative"
        assert result["negative"] > 0

    def test_neutral_text(self):
        from analyzers.sentiment_analyzer import score_text
        result = score_text("The cat sat on the mat.")
        assert result["label"] == "neutral"


class TestERC8004:
    """Test ERC-8004 client functions."""

    def test_registration_file_generation(self):
        from blockchain.erc8004_client import generate_registration_file

        reg = generate_registration_file(
            name="TestAgent",
            description="A test agent",
            web_endpoint="https://example.com",
        )

        assert reg["name"] == "TestAgent"
        assert "eip-8004" in reg["type"]
        assert len(reg["services"]) == 1
        assert reg["services"][0]["name"] == "web"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
