# 🚀 Social Metrics MCP Server Guide

Server **Model Context Protocol (MCP)** resmi untuk ekstraksi dan analisis metrik postingan media sosial (TikTok, YouTube, Instagram Reels, Twitter/X, Facebook) bagi AI Agent (Cursor, Claude Desktop, OpenCode, Windsurf).

> **Core Engine Credit**: Powered by open-source extractors from [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## 🔒 Security & Best Practice Autentikasi

> **PENTING (Security Best Practice):**  
> Jangan menaruh API Key di dalam URL query parameter (`?api_key=...`) di environment produksi karena dapat terekspos di log web server atau proxy cache. Gunakan **HTTP Headers (`X-API-Key` atau `Authorization: Bearer`)** atau environment variable lokal.

---

## 🌐 1. Konfigurasi Client MCP (URL / SSE Transport)

Server aktif melayani koneksi SSE di:
```text
http://103.42.245.208:8343/sse
```

### A. Cursor IDE (Recommended: HTTP Headers)
1. Buka **Cursor Settings** &rarr; **Features** &rarr; **MCP**.
2. Klik **Add New MCP Server**:
   - **Name**: `social-metrics`
   - **Type**: `sse`
   - **URL**: `http://103.42.245.208:8343/sse`
   - **Headers**:
     ```json
     {
       "X-API-Key": "pk_live_f42385569e270251a1dfb62ddc8cf880"
     }
     ```

---

### B. Claude Desktop / OpenCode / Windsurf (`claude_desktop_config.json` / `opencode.json`)

#### Format Rekomendasi (Dengan Custom Headers):
```json
{
  "mcpServers": {
    "social-metrics": {
      "url": "http://103.42.245.208:8343/sse",
      "headers": {
        "X-API-Key": "pk_live_f42385569e270251a1dfb62ddc8cf880"
      }
    }
  }
}
```

#### Format Alternatif (Fallback Query Param):
Jika client MCP yang Anda gunakan belum mendukung field `headers`, gunakan query parameter:
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

## 💻 2. Konfigurasi Client MCP (Local Stdio Subprocess)

Jika ingin menjalankan engine python secara offline/lokal di mesin Anda sendiri:

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

## 🧰 Daftar Tool yang Tersedia

### `analyze_social_posts`
Menganalisis metrik postingan media sosial baik satu link maupun banyak link (batch) secara paralel.

#### Parameter Input:
| Parameter | Tipe | Wajib | Deskripsi |
|---|---|---|---|
| `urls` | `array of strings` | **Ya** | Daftar URL postingan/video publik (TikTok, YouTube, IG, Twitter/X). |
| `api_key` | `string` | Tidak | API Key eksplisit jika client belum menyertakannya di header/env. |

#### Contoh Respon Tool JSON:
```json
{
  "status": "success",
  "total_posts": 2,
  "successful": 2,
  "failed": 0,
  "aggregated_metrics": {
    "total_views": 2304192000,
    "total_likes": 19616800,
    "total_comments": 2400689,
    "total_shares": 20555
  },
  "posts": [
    {
      "status": "success",
      "platform": "tiktok",
      "url": "https://www.tiktok.com/@saneraurus/video/7698805832145751303",
      "title": "NEGARA PARA PEJABAT #resetindonesia",
      "author": "saneraurus",
      "views": 472576,
      "likes": 126653,
      "comments": 689,
      "shares": 20555,
      "engagement_rate": 31.296
    }
  ]
}
```

---

## 💬 Contoh Prompt untuk AI Agent Anda

Setelah server MCP terpasang, Anda bisa langsung berinteraksi dengan AI di Cursor / Claude:

- *"Tolong cek berapa total views dan likes dari video TikTok ini: https://www.tiktok.com/@saneraurus/video/7698805832145751303"*
- *"Bandingkan performa engagement antara video YouTube ini https://youtube.com/watch?v=... dan video TikTok ini https://tiktok.com/@... "*
- *"Hitung engagement rate rata-rata dari 5 video kompetitor berikut: [list URLs]"*
