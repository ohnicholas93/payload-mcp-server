# Payload CMS MCP Server

A Model Context Protocol (MCP) server for interacting with Payload CMS through its REST API.

## Features

This MCP server provides the following tools for interacting with Payload CMS:

1. **create_object** - Creates a Payload object for a specific collection
2. **search_objects** - Searches objects based on query and collection
3. **update_object** - Updates an object by ID

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd nitrous.payload-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The server can be configured using environment variables. Create a `.env` file in the project root:

```env
# Payload CMS Configuration
PAYLOAD_MCP_PAYLOAD__BASE_URL=http://localhost:3000/api
PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN=your_jwt_token_here
PAYLOAD_MCP_PAYLOAD__TIMEOUT=30
PAYLOAD_MCP_PAYLOAD__VERIFY_SSL=true

# Server Configuration
PAYLOAD_MCP_LOG_LEVEL=INFO
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `PAYLOAD_MCP_PAYLOAD__BASE_URL` | Base URL for Payload CMS API | `http://localhost:3000/api` |
| `PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN` | JWT token for authentication | None |
| `PAYLOAD_MCP_PAYLOAD__TIMEOUT` | Request timeout in seconds | `30` |
| `PAYLOAD_MCP_PAYLOAD__VERIFY_SSL` | Whether to verify SSL certificates | `true` |
| `PAYLOAD_MCP_LOG_LEVEL` | Logging level | `INFO` |

## Usage

### Running the Server

To run the MCP server:

```bash
python -m payload_mcp.server
```

### Using with Claude Desktop

To use this MCP server with Claude Desktop, add the following to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "payload-cms": {
      "command": "python",
      "args": ["-m", "payload_mcp.server"],
      "env": {
        "PAYLOAD_MCP_PAYLOAD__BASE_URL": "http://localhost:3000/api",
        "PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN": "your_jwt_token_here"
      }
    }
  }
}
```

### Available Tools

#### create_object
Creates a new object in a specified collection.

**Parameters:**
- `collection_name` (string, required): Name of the collection to create object in
- `data` (object, required): Object data to create

**Example:**
```python
result = await session.call_tool("create_object", {
  "collection_name": "posts",
  "data": {
    "title": "My New Post",
    "content": "This is the content of my post"
  }
})
```

#### search_objects
Searches objects in a collection.

**Parameters:**
- `collection_name` (string, required): Name of the collection to search in
- `query` (object, optional): Search query parameters
- `limit` (integer, optional): Maximum number of results to return
- `page` (integer, optional): Page number for pagination
- `sort` (string, optional): Sort field and direction

**Example:**
```python
result = await session.call_tool("search_objects", {
  "collection_name": "posts",
  "query": {
    "where": {
      "status": {
        "equals": "published"
      }
    }
  },
  "limit": 10,
  "sort": "-createdAt"
})
```

#### update_object
Updates an object by ID.

**Parameters:**
- `collection_name` (string, required): Name of the collection containing the object
- `object_id` (string, required): ID of the object to update
- `data` (object, required): Updated object data

**Example:**
```python
result = await session.call_tool("update_object", {
  "collection_name": "posts",
  "object_id": "1234567890",
  "data": {
    "title": "Updated Post Title"
  }
})
```

## Development

### Project Structure

```
nitrous.payload-mcp/
├── payload_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server implementation
│   ├── client.py          # Payload CMS API client
│   ├── config.py          # Configuration management
│   └── exceptions.py      # Custom exceptions
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the repository.