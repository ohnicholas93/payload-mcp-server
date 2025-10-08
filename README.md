# Payload CMS MCP Server

## Overview

This is a Model Context Protocol (MCP) server that enables AI assistants and tools to interact directly with your Payload CMS instance. It provides a set of secure, authenticated tools for common operations like creating, searching, and updating objects in your Payload collections via the REST API.

The server handles authentication automatically, including JWT token management and browser-based login flows if needed. It's designed to be lightweight, configurable, and easy to integrate into development workflows (e.g., with VS Code and Kilocode).

## Features

- **Create Objects**: Add new documents to any collection, supporting single objects or batches.
- **Search Objects**: Query collections with filters (MongoDB-like `where` clauses), pagination, sorting, localization, and population of related fields.
- **Update Objects**: Modify existing documents by ID, with support for partial updates.
- **Authentication Handling**: Automatic JWT token refresh, stored credentials, and interactive browser login for seamless auth.
- **Localization Support**: Works with Payload's i18n features; specify locales in tool calls.
- **Error Handling**: Comprehensive exceptions for validation, auth, API, and connection issues.
- **Configurable**: Override Payload host, timeouts, SSL, and logging via environment variables.

## Tool Schemas

The available tools and their input schemas (JSON Schema format) are listed below. These define the parameters for each tool call.

### create_object
**Description**: Create one or multiple new object(s) in a specified collection.

```json
{
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
      "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, only the ONE default locale will be used"
    }
  },
  "required": ["collection_name", "data"]
}
```

### search_objects
**Description**: Search objects in a collection.

```json
{
  "type": "object",
  "properties": {
    "collection_name": {
      "type": "string",
      "description": "Name of the collection to search in"
    },
    "query": {
      "type": "object",
      "description": "Search query parameters (MongoDB-like where clause)"
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
      "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, only the ONE default locale will be used"
    }
  },
  "required": ["collection_name"]
}
```

### update_object
**Description**: Update an object by ID.

```json
{
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
      "description": "Locale code for the operation (e.g., 'en', 'es'). If not provided and localization is enabled, only the ONE default locale will be used"
    }
  },
  "required": ["collection_name", "object_id", "data"]
}
```

## Prerequisites

Before setting up and using this MCP server, ensure the following:

1. **Python 3.8+**: The server is built with Python and requires version 3.8 or higher.
2. **Running Payload CMS Instance**: 
   - Your Payload CMS must be up and running.
   - Default assumption: Accessible at `http://localhost:3000/api`.
   - By the time the first tool call is made (e.g., from your MCP client), the Payload instance must already be accessible.
   - If your Payload is hosted elsewhere (e.g., remote server), configure the base URL via environment variables (see Configuration section).
3. **MCP-Compatible Client**: 
   - An MCP client like Kilocode in VS Code, Cursor, or similar AI development tools that support MCP servers.
   - Ensure your client can execute external commands (e.g., run the server binary).

**Note**: No additional database setup or Payload configuration is needed beyond having a working instance. The server does not start or manage Payload for you—handle that separately.

## Installation

1. **Clone the Repository**:
   ```
   git clone https://github.com/your-org/payload-mcp.git
   cd payload-mcp
   ```

2. **Install Dependencies**:
   Install the required Python packages. This includes MCP protocol support, HTTP client, and configuration libraries.
   ```
   pip install -r requirements.txt
   ```

   Alternatively, install the full package (recommended for global use):
   ```
   pip install .
   ```
   This makes the `payload-mcp-server` command available in your PATH.

3. **Set Up Environment**:
   Copy the example environment file and customize it:
   ```
   cp .env.example .env
   ```
   Edit `.env` as needed (see Configuration below). Add `.env` to your `.gitignore` if not already (it is by default).

## Configuration

The server uses Pydantic for type-safe configuration loaded from environment variables. Most users can rely on defaults, but customize via `.env` for non-local setups.

### Key Environment Variables

From `.env.example`:

- **Payload CMS Connection**:
  - `PAYLOAD_MCP_PAYLOAD__BASE_URL`: Base API URL (default: `http://localhost:3000/api`). Override for remote hosts, e.g., `https://your-site.com/api`.
  - `PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN`: Optional JWT token for pre-authenticated access. If omitted, browser login will be used on first need.
  - `PAYLOAD_MCP_PAYLOAD__TIMEOUT`: Request timeout in seconds (default: 30).
  - `PAYLOAD_MCP_PAYLOAD__VERIFY_SSL`: Enable SSL verification (default: false for local dev; set to `true` for HTTPS production).
  - `PAYLOAD_MCP_PAYLOAD__BYPASS_PROXY`: Bypass proxies for localhost (default: true).

- **Server Settings**:
  - `PAYLOAD_MCP_LOG_LEVEL`: Logging verbosity (default: `INFO`; options: `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`).

**Example `.env` for Remote Payload**:
```
PAYLOAD_MCP_PAYLOAD__BASE_URL=https://myapp.com/api
PAYLOAD_MCP_PAYLOAD__AUTH_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
PAYLOAD_MCP_PAYLOAD__VERIFY_SSL=true
PAYLOAD_MCP_LOG_LEVEL=DEBUG
```

Reload the server after config changes.

## Running the Server

1. **Start the MCP Server**:
   After installation, run:
   ```
   payload-mcp-server
   ```
   
   Or directly from source:
   ```
   python -m payload_mcp.server
   ```

   - The server initializes, loads config, and tests basic connectivity (logs any issues but continues).
   - It listens on stdio for MCP protocol communication.
   - Logs will show connection status and any auth prompts.

2. **Background/Production**:
   - For persistent runs, use tools like `nohup`, `screen`, or systemd.
   - Example: `nohup payload-mcp-server > server.log 2>&1 &`

The server does **not** require Payload to be running during startup—only when tools are called. However, ensure Payload is accessible before tool use.

## Integrating with MCP Client

1. **Add to Client** (e.g., VS Code with Kilocode):
   - Open your MCP client settings (e.g., in VS Code: Ctrl+Shift+P > "Kilocode: Edit MCP Config").
   - Add a new server configuration to your MCP settings file (usually `mcp.json` or similar).
   - Use the following example configuration, replacing `<swap to root directory of the mcp server>` with the actual path to this project's root directory:

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

   - Save the settings and restart/reload your MCP client.
   - The client will automatically start the server when needed and list the available tools (e.g., `create_object`, `search_objects`, `update_object`).

2. **Verify Integration**:
   - In your MCP client, query for available tools. You should see the Payload CMS tools listed.
   - Test a simple tool call, like searching a collection, to ensure authentication and connectivity work.
   - If browser auth is triggered, follow the prompts to log in to your Payload instance.

## Usage Examples

Once integrated, you can use the tools in your AI assistant prompts. Examples:

- **Create an Object**:
  ```
  Use the create_object tool to add a new user to the 'users' collection with name: "John Doe" and email: "john@example.com".
  ```

- **Search Objects**:
  ```
  Search the 'posts' collection for items where title contains "Payload" and limit to 5 results.
  ```

- **Update an Object**:
  ```
  Update the user with ID "123" in the 'users' collection to set email to "john@newemail.com".
  ```

The tools support advanced parameters like locales, population, and complex queries—refer to the tool schemas above for full details.

## Troubleshooting

- **Connection Errors**: Ensure Payload is running and accessible at the configured URL. Check logs for details.
- **Authentication Issues**: Provide a valid JWT token in `.env` or allow browser login. Verify your Payload user has necessary permissions.
- **Tool Not Found**: Restart the MCP client after adding the server config.
- **Logs**: Set `PAYLOAD_MCP_LOG_LEVEL=DEBUG` for verbose output.
- **Windows/PowerShell**: Commands use standard syntax; use `python.exe` if `python` is ambiguous.

## Contributing

- Fork the repo and create a pull request.
- Install dev dependencies if adding features.
- Follow PEP 8 style and add tests where applicable.

## License

MIT License. See [LICENSE](LICENSE) for details (add if needed).

For support, check the Payload CMS docs or open an issue.