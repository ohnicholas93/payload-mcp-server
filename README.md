# Payload CMS MCP Server

A Model Context Protocol (MCP) server for interacting with Payload CMS through its REST API.

## Features

This MCP server provides the following tools for interacting with Payload CMS, with full support for localization:

1. **create_object** - Creates a Payload object for a specific collection
2. **search_objects** - Searches objects based on query and collection
3. **update_object** - Updates an object by ID

1. **create_object** - Creates a Payload object for a specific collection
2. **search_objects** - Searches objects based on query and collection
3. **update_object** - Updates an object by ID

## Quick Start

This MCP server is designed to work out-of-the-box with a default Payload CMS installation at `http://localhost:3000`. No configuration is needed for basic usage!

### Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd nitrous.payload-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python -m payload_mcp.server
```

That's it! The server will connect to your local Payload CMS instance and prompt for authentication when needed.

## Configuration

While the server works with default settings, you can customize it using environment variables. Copy `.env.example` to `.env` and modify as needed:

```bash
cp .env.example .env
```

### Basic Configuration

For most users, the default configuration will work fine. The server will:

- Connect to `http://localhost:3000/api` by default
- Prompt for login when no JWT token is provided
- Automatically handle authentication with a browser popup

### Advanced Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `PAYLOAD_MCP_PAYLOAD__BASE_URL` | Base URL for Payload CMS API | `http://localhost:3000/api` |
| `PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN` | JWT token for authentication (optional) | None |
| `PAYLOAD_MCP_PAYLOAD__TIMEOUT` | Request timeout in seconds | `30` |
| `PAYLOAD_MCP_PAYLOAD__VERIFY_SSL` | Whether to verify SSL certificates | `false` |
| `PAYLOAD_MCP_PAYLOAD__BYPASS_PROXY` | Whether to bypass proxy for localhost | `true` |
| `PAYLOAD_MCP_LOG_LEVEL` | Logging level | `INFO` |

### Authentication

The server provides two authentication methods:

1. **Automatic Authentication (Recommended)**: If no JWT token is provided, the server will automatically open a browser window for login when needed.

2. **Manual JWT Token**: Set `PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN` in your environment if you have a pre-generated token.

#### Example with Manual JWT

```env
PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN=your_jwt_token_here
```

#### Example with Remote Payload CMS

```env
PAYLOAD_MCP_PAYLOAD__BASE_URL=https://your-payload-cms.com/api
PAYLOAD_MCP_PAYLOAD__VERIFY_SSL=true
```

## Usage

### Running the Server

To run the MCP server with default settings:

```bash
python -m payload_mcp.server
```

The server will automatically:
- Connect to `http://localhost:3000/api`
- Prompt for authentication when needed (opens a browser window)
- Use the authentication token for subsequent requests

### Using with Claude Desktop

To use this MCP server with Claude Desktop, add the following to your Claude Desktop configuration file:

#### Basic Configuration (Recommended)

```json
{
  "mcpServers": {
    "payload-mcp": {
      "command": "python",
      "args": ["-m", "payload_mcp.server"],
      "cwd": "<swap to root directory of the mcp server>"
    }
  }
}

```

The server will automatically handle authentication with your local Payload CMS instance.

#### Advanced Configuration (Remote or Custom Setup)

```json
{
  "mcpServers": {
    "payload-mcp": {
      "command": "python",
      "args": ["-m", "payload_mcp.server"],
      "cwd": "<swap to root directory of the mcp server>",
      "env": {
        "PAYLOAD_MCP_PAYLOAD__BASE_URL": "https://your-payload-cms.com/api",
        "PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN": "your_jwt_token_here",
        "PAYLOAD_MCP_PAYLOAD__VERIFY_SSL": "true"
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
- `locale` (string, optional): Locale code for the operation (e.g., 'en', 'es'). If not provided, Payload CMS uses its default fallback behavior.

**Example:**
```python
result = await session.call_tool("create_object", {
  "collection_name": "posts",
  "data": {
    "title": "My New Post",
    "content": "This is the content of my post"
  },
  "locale": "en"
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
- `locale` (string, optional): Locale code for the operation (e.g., 'en', 'es'). If not provided, Payload CMS uses its default fallback behavior.

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
  "sort": "-createdAt",
  "locale": "es"
})
```

#### update_object
Updates an object by ID.

**Parameters:**
- `collection_name` (string, required): Name of the collection containing the object
- `object_id` (string, required): ID of the object to update
- `data` (object, required): Updated object data
- `locale` (string, optional): Locale code for the operation (e.g., 'en', 'es'). If not provided, Payload CMS uses its default fallback behavior.

**Example:**
```python
result = await session.call_tool("update_object", {
  "collection_name": "posts",
  "object_id": "1234567890",
  "data": {
    "title": "Updated Post Title"
  },
  "locale": "de"
})
```

## Authentication Flow

The server provides a seamless authentication experience:

1. **No Configuration Needed**: If no JWT token is provided, the server will attempt to make requests
2. **Automatic Login**: When authentication is required, the server will:
   - Start a local authentication server
   - Open a browser window with a login form
   - Capture the authentication token upon successful login
   - Use the token for subsequent requests
3. **Manual JWT**: If you prefer to use a pre-generated token, set `PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN`

### Troubleshooting Authentication

- **Browser doesn't open**: Check that you have a default browser installed
- **Login fails**: Verify your Payload CMS credentials and collection name (default: "users")
- **Connection issues**: Ensure your Payload CMS is running and accessible at the configured URL

## Development

### Project Structure

```
nitrous.payload-mcp/
├── payload_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server implementation
│   ├── client.py          # Payload CMS API client
│   ├── config.py          # Configuration management
│   ├── auth_manager.py    # Authentication management
│   ├── auth_server.py     # Browser-based authentication server
│   └── exceptions.py      # Custom exceptions
├── requirements.txt       # Python dependencies
├── setup.py              # Package setup
├── .env.example          # Example environment configuration
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

## Common Use Cases

### Local Development

For local development with Payload CMS running on localhost:3000, no configuration is needed:

```bash
git clone <repository-url>
cd nitrous.payload-mcp
pip install -r requirements.txt
python -m payload_mcp.server
```

### Production/Remote Setup

For connecting to a remote Payload CMS instance:

```env
PAYLOAD_MCP_PAYLOAD__BASE_URL=https://cms.yourdomain.com/api
PAYLOAD_MCP_PAYLOAD__VERIFY_SSL=true
```

### Custom Authentication Collection

If your authentication uses a different collection name (not "users"), the server will use the collection name specified in the browser authentication form.