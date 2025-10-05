"""
Main MCP server for Payload CMS integration.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .client import PayloadClient
from .config import ServerConfig
from .exceptions import PayloadMCPError, ConfigurationError

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


async def initialize_client(config: ServerConfig) -> PayloadClient:
    """Initialize the Payload CMS client with connection test."""
    global client
    
    if client is None:
        logger.info(f"Initializing Payload client for {config.payload.base_url}")
        client = PayloadClient(config.payload)
        
        # Test connection to Payload CMS API
        try:
            logger.info("Testing connection to Payload CMS API...")
            result = await client._make_request("GET", "users")
            logger.info(f"Connection test successful: Retrieved {len(result.get('docs', []))} users")
            logger.debug(f"API Response: {result}")
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            # Don't raise the exception, just log it so the server can continue
            # but the user will know there's a connection issue
        
        logger.info(f"Payload client initialization completed")
    
    return client


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="create_object",
            description="Create a new object in a specified collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the collection to create object in"
                    },
                    "data": {
                        "type": "object",
                        "description": "Object data to create"
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
                    }
                },
                "required": ["collection_name", "object_id", "data"]
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
            
            if not collection_name:
                raise ValueError("collection_name is required")
            if not data:
                raise ValueError("data is required")
            
            result = await payload_client.create_object(collection_name, data)
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
            
            result = await payload_client.search_objects(
                collection_name=collection_name,
                where=query,
                limit=limit,
                page=page,
                sort=sort
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "update_object":
            collection_name = arguments.get("collection_name")
            object_id = arguments.get("object_id")
            data = arguments.get("data")
            
            if not collection_name:
                raise ValueError("collection_name is required")
            if not object_id:
                raise ValueError("object_id is required")
            if not data:
                raise ValueError("data is required")
            
            result = await payload_client.update_object(collection_name, object_id, data)
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