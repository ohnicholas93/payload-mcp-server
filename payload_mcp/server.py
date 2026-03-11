"""
Main MCP server for Payload CMS integration.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .client import PayloadClient
from .config import ServerConfig
from .exceptions import PayloadMCPError, ConfigurationError
from .auth_manager import AuthManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("payload-mcp-server")

# Global server instance
server = Server("payload-mcp-server")

# Global client instance
client: Optional[PayloadClient] = None

# Global auth manager instance
auth_manager: Optional[AuthManager] = None

SERVER_INFO_URI = "payload://server/info"
AUTH_STATUS_URI = "payload://server/auth"
RESOURCE_GUIDE_URI = "payload://server/resources"

COLLECTION_TEMPLATE_URI = "payload://collections/{collection}"
DOCUMENT_TEMPLATE_URI = "payload://collections/{collection}/{id}"
GLOBAL_TEMPLATE_URI = "payload://globals/{slug}"


@dataclass
class ResourceContent:
    """Compatibility shape for the low-level MCP read_resource wrapper."""

    content: str
    mime_type: str
    meta: Optional[Dict[str, Any]] = None


async def initialize_client(config: ServerConfig) -> PayloadClient:
    """Initialize the Payload CMS client with connection test."""
    global client, auth_manager
    
    if client is None:
        logger.info(f"Initializing Payload client for {config.payload.base_url}")
        client = PayloadClient(config.payload)
        
        # Initialize auth manager
        auth_manager = AuthManager(config.payload)
        
        # Set up auth callback to update client headers when token changes
        def update_client_headers(new_token: str):
            if client:
                client.auth_token = new_token
                client.headers["Authorization"] = f"JWT {new_token}"
                logger.info("Client headers updated with new token")
        
        auth_manager.add_auth_callback(update_client_headers)
        
        # Set auth manager in client for token refresh
        client.set_auth_manager(auth_manager)
        
        # Test connection to Payload CMS API
        # try:
        #     logger.info("Testing connection to Payload CMS API...")
        #     result = await client._make_request("GET", "users")
        #     logger.info(f"Connection test successful: Retrieved {len(result.get('docs', []))} users")
        #     logger.debug(f"API Response: {result}")
        # except Exception as e:
        #     logger.error(f"Connection test failed: {str(e)}")
        #     logger.error(f"Error type: {type(e).__name__}")
            # Don't raise the exception, just log it so the server can continue
            # but the user will know there's a connection issue
        
        logger.info(f"Payload client initialization completed")
    
    return client


async def get_payload_client() -> PayloadClient:
    """Load configuration and initialize the shared Payload client."""
    config = ServerConfig.from_env()
    return await initialize_client(config)


def to_pretty_json(data: Any) -> str:
    """Render resource content as stable, readable JSON."""
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def json_resource(data: Any, meta: Optional[Dict[str, Any]] = None) -> List[ResourceContent]:
    """Build JSON-typed resource contents for the MCP low-level server."""
    return [ResourceContent(content=to_pretty_json(data), mime_type="application/json", meta=meta)]


def get_query_value(query: Dict[str, List[str]], key: str, alias: Optional[str] = None) -> Optional[str]:
    """Return the last value for a query parameter."""
    values = query.get(key)
    if not values and alias:
        values = query.get(alias)
    if not values:
        return None
    return values[-1]


def parse_json_param(query: Dict[str, List[str]], key: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object query parameter."""
    raw_value = get_query_value(query, key)
    if raw_value is None:
        return None

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Query parameter '{key}' must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Query parameter '{key}' must decode to a JSON object")

    return parsed


def parse_int_param(query: Dict[str, List[str]], key: str, alias: Optional[str] = None) -> Optional[int]:
    """Parse an integer query parameter."""
    raw_value = get_query_value(query, key, alias)
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Query parameter '{key}' must be an integer") from exc


def parse_bool_param(query: Dict[str, List[str]], key: str) -> Optional[bool]:
    """Parse a boolean query parameter."""
    raw_value = get_query_value(query, key)
    if raw_value is None:
        return None

    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"Query parameter '{key}' must be a boolean")


def get_static_resources() -> List[types.Resource]:
    """Return concrete resources that are always available."""
    return [
        types.Resource(
            uri=SERVER_INFO_URI,
            name="Payload Server Info",
            title="Payload MCP Server Info",
            description="Configuration summary and server metadata for this Payload MCP server.",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AUTH_STATUS_URI,
            name="Payload Auth Status",
            title="Payload Authentication Status",
            description="Authentication state summary for the configured Payload connection.",
            mimeType="application/json",
        ),
        types.Resource(
            uri=RESOURCE_GUIDE_URI,
            name="Payload Resource Guide",
            title="Payload Resource Guide",
            description="How to read collection, document, and global resources from this server.",
            mimeType="application/json",
        ),
    ]


def get_resource_templates() -> List[types.ResourceTemplate]:
    """Return URI templates for Payload-backed resources."""
    return [
        types.ResourceTemplate(
            uriTemplate=COLLECTION_TEMPLATE_URI,
            name="Payload Collection Query",
            title="Payload Collection Query",
            description=(
                "Read a collection listing. Optional query params: limit, page, sort, depth, locale, "
                "fallback-locale, trash, where, select, populate, joins. Object-like params must be JSON."
            ),
            mimeType="application/json",
        ),
        types.ResourceTemplate(
            uriTemplate=DOCUMENT_TEMPLATE_URI,
            name="Payload Document",
            title="Payload Document",
            description=(
                "Read a single collection document by ID. Optional query params: depth, locale, "
                "fallback-locale, draft, select, populate, joins. Object-like params must be JSON."
            ),
            mimeType="application/json",
        ),
        types.ResourceTemplate(
            uriTemplate=GLOBAL_TEMPLATE_URI,
            name="Payload Global",
            title="Payload Global",
            description=(
                "Read a global document by slug. Optional query params: depth, locale, "
                "fallback-locale, select, populate. Object-like params must be JSON."
            ),
            mimeType="application/json",
        ),
    ]


def build_resource_guide() -> Dict[str, Any]:
    """Describe the available resources and URI formats."""
    return {
        "resources": [SERVER_INFO_URI, AUTH_STATUS_URI, RESOURCE_GUIDE_URI],
        "templates": [
            {
                "uriTemplate": COLLECTION_TEMPLATE_URI,
                "example": "payload://collections/posts?limit=5&sort=-updatedAt",
                "notes": [
                    "Use JSON-encoded query params for where, select, populate, and joins.",
                    "Collection reads return the same payload as the search_objects tool.",
                ],
            },
            {
                "uriTemplate": DOCUMENT_TEMPLATE_URI,
                "example": "payload://collections/posts/123?depth=1",
                "notes": [
                    "Document reads return the same payload as a direct REST GET by ID.",
                ],
            },
            {
                "uriTemplate": GLOBAL_TEMPLATE_URI,
                "example": "payload://globals/header?depth=1",
                "notes": [
                    "Global reads return the same payload as the get_global tool.",
                ],
            },
        ],
    }


@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List concrete resources exposed by this server."""
    return get_static_resources()


@server.list_resource_templates()
async def handle_list_resource_templates() -> List[types.ResourceTemplate]:
    """List URI templates for Payload-backed resources."""
    return get_resource_templates()


@server.read_resource()
async def handle_read_resource(uri: Any) -> List[ResourceContent]:
    """Read a resource identified by a payload:// URI."""
    parsed = urlparse(str(uri))
    query = parse_qs(parsed.query)

    if parsed.scheme != "payload":
        raise ValueError(f"Unsupported resource scheme: {parsed.scheme}")

    path_parts = [unquote(part) for part in parsed.path.split("/") if part]

    if parsed.netloc == "server":
        config = ServerConfig.from_env()

        if parsed.path == "/info":
            return json_resource(
                {
                    "server_name": "payload-mcp-server",
                    "server_version": "0.1.0",
                    "payload": {
                        "base_url": config.payload.base_url,
                        "timeout": config.payload.timeout,
                        "verify_ssl": config.payload.verify_ssl,
                        "bypass_proxy": config.payload.bypass_proxy,
                    },
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "resource_templates": True,
                    },
                }
            )

        if parsed.path == "/auth":
            return json_resource(
                {
                    "base_url": config.payload.base_url,
                    "auth_token_configured": bool(config.payload.auth_token),
                    "browser_auth_initialized": auth_manager is not None,
                    "client_initialized": client is not None,
                }
            )

        if parsed.path == "/resources":
            return json_resource(build_resource_guide())

        raise ValueError(f"Unknown server resource: {parsed.path}")

    payload_client = await get_payload_client()

    if parsed.netloc == "collections":
        if not path_parts:
            return json_resource(build_resource_guide())

        collection_name = path_parts[0]

        if len(path_parts) == 1:
            result = await payload_client.search_objects(
                collection_name=collection_name,
                where=parse_json_param(query, "where"),
                limit=parse_int_param(query, "limit"),
                page=parse_int_param(query, "page"),
                sort=get_query_value(query, "sort"),
                depth=parse_int_param(query, "depth"),
                locale=get_query_value(query, "locale"),
                fallback_locale=get_query_value(query, "fallback-locale", "fallback_locale"),
                select=parse_json_param(query, "select"),
                populate=parse_json_param(query, "populate"),
                joins=parse_json_param(query, "joins"),
                trash=parse_bool_param(query, "trash"),
            )
            return json_resource(result)

        if len(path_parts) == 2:
            result = await payload_client.get_object(
                collection_name=collection_name,
                object_id=path_parts[1],
                depth=parse_int_param(query, "depth"),
                locale=get_query_value(query, "locale"),
                fallback_locale=get_query_value(query, "fallback-locale", "fallback_locale"),
                select=parse_json_param(query, "select"),
                populate=parse_json_param(query, "populate"),
                joins=parse_json_param(query, "joins"),
                draft=parse_bool_param(query, "draft"),
            )
            return json_resource(result)

        raise ValueError("Collection resource URIs must be payload://collections/{collection} or payload://collections/{collection}/{id}")

    if parsed.netloc == "globals":
        if len(path_parts) != 1:
            raise ValueError("Global resource URIs must be payload://globals/{slug}")

        result = await payload_client.get_global(
            slug=path_parts[0],
            locale=get_query_value(query, "locale"),
            depth=parse_int_param(query, "depth"),
            fallback_locale=get_query_value(query, "fallback-locale", "fallback_locale"),
            select=parse_json_param(query, "select"),
            populate=parse_json_param(query, "populate"),
        )
        return json_resource(result)

    raise ValueError(f"Unsupported resource host: {parsed.netloc}")


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="create_object",
            description="Create one or multiple new object(s) in a specified collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the collection to create object in"
                    },
                    "data": {
                        "oneOf": [
                            {
                                "type": "object",
                                "description": "Object data to create"
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "object"
                                },
                                "description": "Array of objects to create"
                            }
                        ],
                        "description": "Object data or array of objects to create"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, **only the ONE default locale will be used**"
                    }
                },
                "required": ["collection_name", "data"]
            }
        ),
        types.Tool(
            name="search_objects",
            description="Search objects in a collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the collection to search in"
                    },
                    "query": {
                        "type": "object",
                        "description": "Search query parameters"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return"
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number for pagination"
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort field and direction"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, **only the ONE default locale will be used**"
                    }
                },
                "required": ["collection_name"]
            }
        ),
        types.Tool(
            name="update_object",
            description="Update an object by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the collection containing the object"
                    },
                    "object_id": {
                        "type": "string",
                        "description": "ID of the object to update"
                    },
                    "data": {
                        "type": "object",
                        "description": "Updated object data"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, **only the ONE default locale will be used**"
                    }
                },
                "required": ["collection_name", "object_id", "data"]
            }
        ),
        types.Tool(
            name="get_global",
            description="Get a global document by its slug",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "The slug of the global to retrieve"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, **only the ONE default locale will be used**"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Controls the depth of population for relationships"
                    },
                    "fallback_locale": {
                        "type": "string",
                        "description": "Specifies a fallback locale if the requested locale is not available"
                    },
                    "select": {
                        "type": "object",
                        "description": "Fields to include in the result"
                    },
                    "populate": {
                        "type": "object",
                        "description": "Fields to populate from related documents"
                    }
                },
                "required": ["slug"]
            }
        ),
        types.Tool(
            name="update_global",
            description="Update a global document by its slug",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "The slug of the global to update"
                    },
                    "data": {
                        "type": "object",
                        "description": "Updated global data"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, **only the ONE default locale will be used**"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Controls the depth of population for relationships in response"
                    },
                    "fallback_locale": {
                        "type": "string",
                        "description": "Specifies a fallback locale if the requested locale is not available"
                    }
                },
                "required": ["slug", "data"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Optional[Dict[str, Any]]
) -> List[types.TextContent]:
    """Handle tool calls."""
    try:
        # Initialize client if not already done
        config = ServerConfig.from_env()
        payload_client = await initialize_client(config)
        
        if name == "create_object":
            collection_name = arguments.get("collection_name")
            data = arguments.get("data")
            locale = arguments.get("locale")
            
            if not collection_name:
                raise ValueError("collection_name is required")
            if not data:
                raise ValueError("data is required")
            
            # Check if data is an array of objects
            if isinstance(data, list):
                # Handle array of objects
                results = []
                for item in data:
                    result = await payload_client.create_object(collection_name, item, locale)
                    results.append(result)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(results, indent=2)
                )]
            else:
                # Handle single object
                result = await payload_client.create_object(collection_name, data, locale)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
        
        elif name == "search_objects":
            collection_name = arguments.get("collection_name")
            if not collection_name:
                raise ValueError("collection_name is required")
            
            query = arguments.get("query")
            limit = arguments.get("limit")
            page = arguments.get("page")
            sort = arguments.get("sort")
            locale = arguments.get("locale")
            
            result = await payload_client.search_objects(
                collection_name=collection_name,
                where=query,
                limit=limit,
                page=page,
                sort=sort,
                locale=locale
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "update_object":
            collection_name = arguments.get("collection_name")
            object_id = arguments.get("object_id")
            data = arguments.get("data")
            locale = arguments.get("locale")
            
            if not collection_name:
                raise ValueError("collection_name is required")
            if not object_id:
                raise ValueError("object_id is required")
            if not data:
                raise ValueError("data is required")
            
            result = await payload_client.update_object(collection_name, object_id, data, locale)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_global":
            slug = arguments.get("slug")
            locale = arguments.get("locale")
            depth = arguments.get("depth")
            fallback_locale = arguments.get("fallback_locale")
            select = arguments.get("select")
            populate = arguments.get("populate")
            
            if not slug:
                raise ValueError("slug is required")
            
            result = await payload_client.get_global(
                slug=slug,
                locale=locale,
                depth=depth,
                fallback_locale=fallback_locale,
                select=select,
                populate=populate
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "update_global":
            slug = arguments.get("slug")
            data = arguments.get("data")
            locale = arguments.get("locale")
            depth = arguments.get("depth")
            fallback_locale = arguments.get("fallback_locale")
            
            if not slug:
                raise ValueError("slug is required")
            if not data:
                raise ValueError("data is required")
            
            result = await payload_client.update_global(
                slug=slug,
                data=data,
                locale=locale,
                depth=depth,
                fallback_locale=fallback_locale
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except PayloadMCPError as e:
        logger.error(f"Payload MCP error: {e.message}")
        return [types.TextContent(
            type="text",
            text=f"Error: {e.message}"
        )]
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return [types.TextContent(
            type="text",
            text=f"Unexpected error: {str(e)}"
        )]


async def main():
    """Main entry point for the MCP server."""
    try:
        # Load configuration
        config = ServerConfig.from_env()
        
        # Set log level
        logger.setLevel(getattr(logging, config.log_level.upper()))
        
        logger.info("Starting Payload MCP Server")
        
        # Initialize client and test connection during server startup
        try:
            await initialize_client(config)
        except Exception as e:
            logger.error(f"Failed to initialize client during server startup: {str(e)}")
            # Continue with server startup even if client initialization fails
        
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="payload-mcp-server",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    )
                )
            )
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e.message}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
