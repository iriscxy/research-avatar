import unittest
from io import BytesIO
from unittest.mock import patch

from research_avatar.tools import fetch_fulltext


class FetchFulltextPrivacyTests(unittest.TestCase):
    def test_http_rejects_non_web_schemes(self):
        with patch("research_avatar.tools.fetch_fulltext.urllib.request.urlopen") as opener:
            self.assertIsNone(fetch_fulltext.http("file:///etc/passwd"))
        opener.assert_not_called()

    def test_http_rejects_oversized_text_response(self):
        response = BytesIO(b"x" * (10 * 1024 * 1024 + 1))
        response.__enter__ = lambda value: value
        response.__exit__ = lambda *_args: None
        with patch("research_avatar.tools.fetch_fulltext.urllib.request.urlopen", return_value=response):
            self.assertIsNone(fetch_fulltext.http("https://example.test/large", retries=1))

    def test_arxiv_parser_rejects_entity_declarations(self):
        payload = '<!DOCTYPE x [<!ENTITY y "boom">]><feed>&y;</feed>'
        with patch.object(fetch_fulltext, "http", return_value=payload):
            self.assertEqual(fetch_fulltext.arxiv_lookup("A paper"), (None, None))

    def test_crossref_contact_email_is_optional(self):
        with (
            patch.object(fetch_fulltext, "MAILTO", ""),
            patch.object(fetch_fulltext, "http", return_value="") as request,
        ):
            fetch_fulltext.crossref_lookup("A paper")
        self.assertNotIn("mailto=", request.call_args.args[0])

    def test_unpaywall_is_disabled_without_contact_email(self):
        with (
            patch.object(fetch_fulltext, "MAILTO", ""),
            patch.object(fetch_fulltext, "http") as request,
        ):
            self.assertIsNone(fetch_fulltext.unpaywall_pdf("10.1000/example"))
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
