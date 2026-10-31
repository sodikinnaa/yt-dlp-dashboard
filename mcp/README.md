# Social Metrics MCP Server

Model Context Protocol (MCP) server for extracting and analyzing social media engagement metrics (views, likes, comments, shares, engagement rates) across YouTube, TikTok, Instagram Reels, and Twitter/X.

## Features
- **Batch Processing**: Parallel extraction for single or multiple posts.
- **Key Protected**: Validates client requests against the SQLite `api_keys` database or environment config.
- **Protocol**: Standard JSON-RPC 2.0 over `stdio`.

---

## 🛠️ Configuration & Setup

### 1. Claude Desktop
Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "social-metrics": {
      "command": "python3",
      "args": [
        "/home/dev/workspace/sodikin/mcp-general/yt-dlp-dashboard/mcp/mcp_server.py"
      ],
      "env": {
        "SOCIAL_METRICS_API_KEY": "pk_live_f42385569e270251a1dfb62ddc8cf880"
      }
    }
  }
}
```

### 2. Cursor
Go to **Settings** &rarr; **Features** &rarr; **MCP** &rarr; **Add New MCP Server**:
- **Name**: `social-metrics`
- **Type**: `command`
- **Command**: `python3 /home/dev/workspace/sodikin/mcp-general/yt-dlp-dashboard/mcp/mcp_server.py`
- **Env**: `SOCIAL_METRICS_API_KEY=pk_live_f42385569e270251a1dfb62ddc8cf880`

### 3. OpenCode / Generic Agent
Add to `opencode.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "social-metrics": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/home/dev/workspace/sodikin/mcp-general/yt-dlp-dashboard/mcp/mcp_server.py"
      ],
      "env": {
        "SOCIAL_METRICS_API_KEY": "pk_live_f42385569e270251a1dfb62ddc8cf880"
      }
    }
  }
}
```

---

## 🧰 Available Tools

### `analyze_social_posts`
Extract engagement metrics from one or many social media URLs.

**Parameters:**
- `urls` *(array of strings, required)*: List of post/video URLs.
- `api_key` *(string, optional)*: Explicit API key if not set via environment.

**Example Agent Usage:**
> *"Agent, analyze how this TikTok video performed: https://www.tiktok.com/@saneraurus/video/7698805832145751303"*
