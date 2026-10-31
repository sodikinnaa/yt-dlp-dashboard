# Social Metrics MCP Server (URL / SSE & Stdio)

Model Context Protocol (MCP) server for extracting and analyzing social media engagement metrics (views, likes, comments, shares, engagement rates) across YouTube, TikTok, Instagram Reels, and Twitter/X.

Supports **both URL-based SSE transport** and **local Stdio transport**.

---

## 🌐 1. URL / SSE Transport (Recommended)

Server ini berjalan aktif pada port `8343`. Anda dapat menghubungkannya secara remote tanpa perlu menginstall Python di mesin client.

- **MCP SSE URL**: `http://103.42.245.208:8343/sse?api_key=YOUR_API_KEY`

### A. Cursor Configuration (Settings &rarr; MCP)
1. Buka **Cursor Settings** &rarr; **Features** &rarr; **MCP**.
2. Klik **Add New MCP Server**:
   - **Name**: `social-metrics`
   - **Type**: `sse`
   - **URL**: `http://103.42.245.208:8343/sse?api_key=pk_live_f42385569e270251a1dfb62ddc8cf880`

---

### B. Claude Desktop / OpenCode / Windsurf (`claude_desktop_config.json` / `opencode.json`)

```json
{
  "mcpServers": {
    "social-metrics": {
      "url": "http://103.42.245.208:8343/sse?api_key=pk_live_f42385569e270251a1dfb62ddc8cf880"
    }
  }
}
```

---

## 💻 2. Local Stdio Transport (Alternative)

Jika ingin menjalankan script python secara lokal:

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

---

## 🧰 Available Tools

### `analyze_social_posts`
Extract engagement metrics from one or many social media URLs.

**Parameters:**
- `urls` *(array of strings, required)*: List of post/video URLs.
- `api_key` *(string, optional)*: Explicit API key if not already provided via URL query string.

**Contoh Prompt AI:**
> *"Berapa views dan likes dari video TikTok ini: https://www.tiktok.com/@saneraurus/video/7698805832145751303"*
