import json
import unittest
from unittest.mock import patch

import mcp.types as types

import payload_mcp.server as server_module


class FakePayloadClient:
    async def search_objects(self, **kwargs):
        return {"kind": "collection", "kwargs": kwargs}

    async def get_object(self, **kwargs):
        return {"kind": "document", "kwargs": kwargs}

    async def get_global(self, **kwargs):
        return {"kind": "global", "kwargs": kwargs}


class ResourceSupportTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_capabilities_include_resources(self):
        capabilities = server_module.server.get_capabilities(server_module.NotificationOptions(), {})

        self.assertIsNotNone(capabilities.resources)

    async def test_list_resources_exposes_json_resources(self):
        resources = await server_module.handle_list_resources()

        self.assertEqual(3, len(resources))
        self.assertTrue(all(resource.mimeType == "application/json" for resource in resources))
        self.assertEqual("payload://server/info", str(resources[0].uri))

    async def test_list_resource_templates_expose_json_templates(self):
        templates = await server_module.handle_list_resource_templates()

        self.assertEqual(3, len(templates))
        self.assertTrue(all(template.mimeType == "application/json" for template in templates))
        self.assertEqual("payload://collections/{collection}", templates[0].uriTemplate)

    async def test_read_resource_returns_application_json_for_server_info(self):
        handler = server_module.server.request_handlers[types.ReadResourceRequest]
        request = types.ReadResourceRequest(
            params=types.ReadResourceRequestParams(uri="payload://server/info")
        )

        result = await handler(request)
        content = result.root.contents[0]

        self.assertEqual("application/json", content.mimeType)
        payload = json.loads(content.text)
        self.assertEqual("payload-mcp-server", payload["server_name"])

    async def test_collection_resource_routes_through_search_objects(self):
        with patch.object(
            server_module,
            "get_payload_client",
            return_value=FakePayloadClient(),
        ):
            contents = await server_module.handle_read_resource(
                'payload://collections/posts?limit=5&where={"status":{"equals":"published"}}'
            )

        self.assertEqual("application/json", contents[0].mime_type)
        payload = json.loads(contents[0].content)
        self.assertEqual("collection", payload["kind"])
        self.assertEqual("posts", payload["kwargs"]["collection_name"])
        self.assertEqual(5, payload["kwargs"]["limit"])
        self.assertEqual({"status": {"equals": "published"}}, payload["kwargs"]["where"])

    async def test_collection_resource_accepts_url_encoded_json_query_params(self):
        with patch.object(
            server_module,
            "get_payload_client",
            return_value=FakePayloadClient(),
        ):
            contents = await server_module.handle_read_resource(
                "payload://collections/posts?where=%7B%22status%22%3A%7B%22equals%22%3A%22published%22%7D%7D"
            )

        payload = json.loads(contents[0].content)
        self.assertEqual({"status": {"equals": "published"}}, payload["kwargs"]["where"])

    async def test_document_resource_routes_through_get_object(self):
        with patch.object(
            server_module,
            "get_payload_client",
            return_value=FakePayloadClient(),
        ):
            contents = await server_module.handle_read_resource(
                "payload://collections/posts/123?depth=2&draft=true"
            )

        payload = json.loads(contents[0].content)
        self.assertEqual("document", payload["kind"])
        self.assertEqual("123", payload["kwargs"]["object_id"])
        self.assertEqual(2, payload["kwargs"]["depth"])
        self.assertTrue(payload["kwargs"]["draft"])

    async def test_global_resource_routes_through_get_global(self):
        with patch.object(
            server_module,
            "get_payload_client",
            return_value=FakePayloadClient(),
        ):
            contents = await server_module.handle_read_resource(
                "payload://globals/header?locale=en&depth=1"
            )

        payload = json.loads(contents[0].content)
        self.assertEqual("global", payload["kind"])
        self.assertEqual("header", payload["kwargs"]["slug"])
        self.assertEqual("en", payload["kwargs"]["locale"])
        self.assertEqual(1, payload["kwargs"]["depth"])

    async def test_invalid_json_query_param_raises_value_error(self):
        with patch.object(
            server_module,
            "get_payload_client",
            return_value=FakePayloadClient(),
        ):
            with self.assertRaisesRegex(ValueError, "must be valid JSON"):
                await server_module.handle_read_resource(
                    "payload://collections/posts?where=not-json"
                )


if __name__ == "__main__":
    unittest.main()
