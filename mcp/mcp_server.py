#!/usr/bin/env python3
import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor

# Add web directory to path for scraper and db modules
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(REPO_ROOT, "web")
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

from db import validate_api_key, ENV
from scraper import extract_metrics

SERVER_INFO = {
    "name": "social-metrics-mcp",
    "version": "1.0.0"
}

PROTOCOL_VERSION = "2024-11-05"

executor = ThreadPoolExecutor(max_workers=6)

def resolve_api_key(args_key=None):
    if args_key and args_key.strip():
        return args_key.strip()
    env_key = os.environ.get("SOCIAL_METRICS_API_KEY") or os.environ.get("DEFAULT_API_KEY") or ENV.get("DEFAULT_API_KEY")
    if env_key:
        return env_key.strip()
    return None

def handle_list_tools():
    return {
        "tools": [
            {
                "name": "analyze_social_posts",
                "description": "Analyze and extract engagement metrics (views, likes, comments, shares, engagement rate) for a single post or multiple social media posts (YouTube, TikTok, Instagram Reels, Twitter/X, Facebook) in parallel. Requires a valid API Key.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of social media post/video URLs to analyze."
                        },
                        "api_key": {
                            "type": "string",
                            "description": "Optional API Key (pk_live_...). If omitted, uses SOCIAL_METRICS_API_KEY from environment."
                        }
                    },
                    "required": ["urls"]
                }
            }
        ]
    }

def handle_call_tool(params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name != "analyze_social_posts":
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": f"Unknown tool: {tool_name}"
                }
            ]
        }

    # Validate API Key
    provided_key = resolve_api_key(arguments.get("api_key"))
    if not provided_key or not validate_api_key(provided_key):
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "Authentication Error: A valid API Key (pk_live_...) is required. Set SOCIAL_METRICS_API_KEY in your MCP client env or provide 'api_key' in arguments."
                }
            ]
        }

    raw_urls = arguments.get("urls", [])
    if isinstance(raw_urls, str):
        raw_urls = [raw_urls]

    clean_urls = [u.strip() for u in raw_urls if isinstance(u, str) and u.strip().startswith(('http://', 'https://'))]

    if not clean_urls:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "Validation Error: 'urls' must contain at least one valid HTTP/HTTPS URL."
                }
            ]
        }

    # Parallel scraping limit to 20
    target_urls = clean_urls[:20]
    futures = [executor.submit(extract_metrics, u) for u in target_urls]
    results = [f.result() for f in futures]

    # Aggregate summaries
    total_views = sum(r.get("views", 0) for r in results if r.get("status") == "success")
    total_likes = sum(r.get("likes", 0) for r in results if r.get("status") == "success")
    total_comments = sum(r.get("comments", 0) for r in results if r.get("status") == "success")
    total_shares = sum(r.get("shares", 0) for r in results if r.get("status") == "success")
    success_count = sum(1 for r in results if r.get("status") == "success")

    summary_payload = {
        "status": "success",
        "total_posts": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "aggregated_metrics": {
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares
        },
        "posts": results
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(summary_payload, ensure_ascii=False, indent=2)
            }
        ]
    }

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            # Initialize handshake
            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": SERVER_INFO
                    }
                }
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }
            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": handle_list_tools()
                }
            elif method == "tools/call":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": handle_call_tool(params)
                }
            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
