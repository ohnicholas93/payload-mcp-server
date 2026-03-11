import unittest
from unittest.mock import patch

from payload_mcp.auth_server import AuthServer


class AuthServerBrowserOpenTests(unittest.TestCase):
    @patch.object(AuthServer, "_open_with_platform_fallback", return_value=False)
    @patch.object(AuthServer, "_open_with_webbrowser", return_value=True)
    def test_open_browser_prefers_webbrowser_when_available(self, open_webbrowser, open_fallback):
        server = AuthServer(port=9876)

        result = server.open_browser()

        self.assertTrue(result)
        open_webbrowser.assert_called_once_with("http://localhost:9876")
        open_fallback.assert_not_called()

    @patch.object(AuthServer, "_open_with_platform_fallback", return_value=True)
    @patch.object(AuthServer, "_open_with_webbrowser", return_value=False)
    def test_open_browser_uses_platform_fallback_when_needed(self, open_webbrowser, open_fallback):
        server = AuthServer(port=9876)

        result = server.open_browser()

        self.assertTrue(result)
        open_webbrowser.assert_called_once_with("http://localhost:9876")
        open_fallback.assert_called_once_with("http://localhost:9876")

    @patch.object(AuthServer, "_open_with_platform_fallback", return_value=False)
    @patch.object(AuthServer, "_open_with_webbrowser", return_value=False)
    def test_open_browser_returns_false_when_all_launchers_fail(self, open_webbrowser, open_fallback):
        server = AuthServer(port=9876)

        result = server.open_browser()

        self.assertFalse(result)
        open_webbrowser.assert_called_once_with("http://localhost:9876")
        open_fallback.assert_called_once_with("http://localhost:9876")


if __name__ == "__main__":
    unittest.main()
