import sys
import types
import unittest
from unittest.mock import patch


if "httpx" not in sys.modules:
    fake_httpx = types.ModuleType("httpx")

    class _AsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_httpx.AsyncClient = _AsyncClient
    fake_httpx.ConnectError = Exception
    fake_httpx.TimeoutException = Exception
    fake_httpx.HTTPError = Exception
    sys.modules["httpx"] = fake_httpx

if "pydantic" not in sys.modules:
    fake_pydantic = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **kwargs):
            for key, value in self.__class__.__dict__.items():
                if key.startswith("_") or callable(value):
                    continue
                setattr(self, key, value)
            for key, value in kwargs.items():
                setattr(self, key, value)

    def _field(*, default=None, default_factory=None, description=None):
        if default_factory is not None:
            return default_factory()
        return default

    fake_pydantic.BaseModel = _BaseModel
    fake_pydantic.Field = _field
    sys.modules["pydantic"] = fake_pydantic

if "pydantic_settings" not in sys.modules:
    fake_pydantic_settings = types.ModuleType("pydantic_settings")

    class _BaseSettings(sys.modules["pydantic"].BaseModel):
        pass

    fake_pydantic_settings.BaseSettings = _BaseSettings
    sys.modules["pydantic_settings"] = fake_pydantic_settings

from payload_mcp.auth_manager import AuthManager
from payload_mcp.config import PayloadConfig


class FakeAuthServer:
    def __init__(self):
        self.stop_calls = 0

    def set_auth_manager(self, auth_manager, auth_callback=None):
        self.auth_manager = auth_manager
        self.auth_callback = auth_callback

    def start(self):
        return True

    def open_browser(self):
        return False

    def get_url(self):
        return "http://localhost:8765"

    def stop(self):
        self.stop_calls += 1


class AuthManagerBrowserLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_wait_timeout_stops_retained_auth_server(self):
        fake_server = FakeAuthServer()
        manager = AuthManager(PayloadConfig(base_url="http://localhost:3000/api"))

        with patch("payload_mcp.auth_server.AuthServer", return_value=fake_server):
            started = await manager.start_browser_auth()

        self.assertTrue(started)
        self.assertIs(manager._auth_server, fake_server)

        completed = await manager.wait_for_browser_auth(timeout=0.01)

        self.assertFalse(completed)
        self.assertIsNone(manager._auth_server)
        self.assertEqual(1, fake_server.stop_calls)


if __name__ == "__main__":
    unittest.main()
