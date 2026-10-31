import http.server
import json
import os
import sys
import queue
import secrets
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie

from db import (
    init_db, authenticate_admin, create_admin_session, get_admin_from_session,
    delete_admin_session, validate_api_key, list_api_keys, create_api_key,
    toggle_api_key, delete_api_key, ENV
)
from scraper import extract_metrics, detect_platform

PORT = int(os.environ.get("PORT") or ENV.get("PORT", 8343))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
executor = ThreadPoolExecutor(max_workers=8)

# MCP Active SSE Sessions storage: session_id -> { "queue": queue.Queue(), "api_key": str }
mcp_sessions = {}
mcp_sessions_lock = threading.Lock()

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_INFO = {
    "name": "social-metrics-mcp",
    "version": "1.0.0"
}

def mcp_handle_request(req, api_key_valid=False):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": MCP_SERVER_INFO
            }
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "analyze_social_posts",
                        "description": "Analyze and extract engagement metrics (views, likes, comments, shares, engagement rate) for a single post or multiple social media posts (YouTube, TikTok, Instagram Reels, Twitter/X, Facebook) in parallel. Requires valid API Key via header, query param, or tool arguments.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "urls": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of post/video URLs to analyze."
                                },
                                "api_key": {
                                    "type": "string",
                                    "description": "Optional API Key (pk_live_...). Can also be set in URL query ?api_key=... or Authorization header."
                                }
                            },
                            "required": ["urls"]
                        }
                    }
                ]
            }
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name != "analyze_social_posts":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]
                }
            }

        # Check API Key validity
        call_key = arguments.get("api_key")
        is_authed = api_key_valid or (call_key and validate_api_key(call_key))
        if not is_authed:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{
                        "type": "text",
                        "text": "Authentication Error: A valid API Key (pk_live_...) is required. Pass it in SSE URL query string ?api_key=... or in tool arguments 'api_key'."
                    }]
                }
            }

        raw_urls = arguments.get("urls", [])
        if isinstance(raw_urls, str):
            raw_urls = [raw_urls]
        clean_urls = [u.strip() for u in raw_urls if isinstance(u, str) and u.strip().startswith(('http://', 'https://'))]

        if not clean_urls:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "Validation Error: 'urls' must contain at least one valid HTTP/HTTPS URL."}]
                }
            }

        target_urls = clean_urls[:20]
        futures = [executor.submit(extract_metrics, u) for u in target_urls]
        results = [f.result() for f in futures]

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
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(summary_payload, ensure_ascii=False, indent=2)
                    }
                ]
            }
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }


class SecureApiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Clean stdout

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, data, status=200, set_cookie=None):
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        if set_cookie:
            self.send_header('Set-Cookie', set_cookie)
        self.end_headers()
        self.wfile.write(payload)

    def get_auth_admin(self):
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
            if 'admin_session' in cookie:
                return get_admin_from_session(cookie['admin_session'].value)
        except Exception:
            return None
        return None

    def check_api_key(self, parsed_query=None):
        key = self.headers.get('X-API-Key')
        if key and validate_api_key(key):
            return True

        auth = self.headers.get('Authorization')
        if auth and validate_api_key(auth):
            return True

        if parsed_query and 'api_key' in parsed_query:
            if validate_api_key(parsed_query['api_key'][0]):
                return True

        return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Healthcheck
        if path == '/api/health':
            return self.send_json({
                'status': 'ok',
                'service': 'Social Media Metrics API & MCP Server',
                'engine': 'yt-dlp',
                'upstream_credit': 'https://github.com/yt-dlp/yt-dlp',
                'port': PORT,
                'mcp_sse_endpoint': f'/sse'
            })

        # MCP SSE TRANSPORT (URL-based MCP)
        if path == '/sse':
            is_valid_key = self.check_api_key(query)
            session_id = secrets.token_hex(16)
            msg_queue = queue.Queue()

            with mcp_sessions_lock:
                mcp_sessions[session_id] = {
                    "queue": msg_queue,
                    "authed": is_valid_key
                }

            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            # Send endpoint event for client POST targets
            endpoint_msg = f"/mcp/messages?sessionId={session_id}"
            initial_event = f"event: endpoint\ndata: {endpoint_msg}\n\n".encode('utf-8')
            self.wfile.write(initial_event)
            self.wfile.flush()

            try:
                while True:
                    try:
                        msg = msg_queue.get(timeout=20)
                        if msg is None: # Close signal
                            break
                        event_payload = f"event: message\ndata: {json.dumps(msg)}\n\n".encode('utf-8')
                        self.wfile.write(event_payload)
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive comment
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with mcp_sessions_lock:
                    if session_id in mcp_sessions:
                        del mcp_sessions[session_id]
            return

        # Admin Auth Check
        if path == '/api/admin/me':
            admin = self.get_auth_admin()
            if not admin:
                return self.send_json({'authenticated': False}, 401)
            return self.send_json({'authenticated': True, 'admin': admin})

        # Admin: Get Keys
        if path == '/api/admin/keys':
            admin = self.get_auth_admin()
            if not admin:
                return self.send_json({'error': 'Unauthorized Admin'}, 401)
            return self.send_json({'keys': list_api_keys()})

        # Protected Metrics Extraction via GET: /api/extract?url=...&api_key=...
        if path == '/api/extract':
            if not self.check_api_key(query):
                return self.send_json({
                    'status': 'error',
                    'error': 'Unauthorized: Valid X-API-Key header or ?api_key= parameter required.'
                }, 401)

            target_url = query.get('url', [''])[0].strip()
            if not target_url:
                return self.send_json({'status': 'error', 'error': 'Parameter ?url= is required'}, 400)
            res = extract_metrics(target_url)
            status_code = 200 if res.get('status') == 'success' else 422
            return self.send_json(res, status_code)

        # Serve Frontend Documentation & Key Manager UI
        if path == '/' or path == '':
            file_path = os.path.join(STATIC_DIR, 'index.html')
        else:
            clean_path = path.lstrip('/')
            file_path = os.path.join(STATIC_DIR, clean_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            content_type = 'text/plain'
            if file_path.endswith('.html'):
                content_type = 'text/html; charset=utf-8'
            elif file_path.endswith('.css'):
                content_type = 'text/css'
            elif file_path.endswith('.js'):
                content_type = 'application/javascript'
            elif file_path.endswith('.json'):
                content_type = 'application/json'

            with open(file_path, 'rb') as f:
                data = f.read()

            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_json({'error': 'Not Found'}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        body = {}
        if post_data:
            try:
                body = json.loads(post_data.decode('utf-8'))
            except Exception:
                return self.send_json({'status': 'error', 'error': 'Malformed JSON body'}, 400)

        # MCP SSE Client Message Ingestion
        if path == '/mcp/messages':
            session_id = query.get('sessionId', [''])[0]
            with mcp_sessions_lock:
                sess = mcp_sessions.get(session_id)

            if not sess:
                return self.send_json({"error": "MCP Session not found or closed"}, 404)

            # Check if this POST message brings an API Key
            auth_ok = sess.get("authed") or self.check_api_key(query)
            response_msg = mcp_handle_request(body, api_key_valid=auth_ok)

            if response_msg:
                sess["queue"].put(response_msg)

            self.send_response(202)
            self.send_cors_headers()
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Accepted")
            return

        # Admin Login
        if path == '/api/admin/login':
            username = body.get('username', '').strip()
            password = body.get('password', '').strip()
            admin = authenticate_admin(username, password)
            if not admin:
                return self.send_json({'error': 'Invalid username or password'}, 401)

            token = create_admin_session(admin['id'])
            cookie = f"admin_session={token}; Path=/; HttpOnly; SameSite=Lax"
            return self.send_json({'message': 'Login successful', 'admin': admin}, 200, set_cookie=cookie)

        # Admin Logout
        if path == '/api/admin/logout':
            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                if 'admin_session' in cookie:
                    delete_admin_session(cookie['admin_session'].value)
            expire_cookie = "admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            return self.send_json({'message': 'Logout successful'}, 200, set_cookie=expire_cookie)

        # Admin: Create Key
        if path == '/api/admin/keys/create':
            admin = self.get_auth_admin()
            if not admin:
                return self.send_json({'error': 'Unauthorized Admin'}, 401)
            name = body.get('name', 'Client App')
            result = create_api_key(name)
            return self.send_json({'message': 'Key created', 'key': result}, 201)

        # Admin: Toggle Key
        if path == '/api/admin/keys/toggle':
            admin = self.get_auth_admin()
            if not admin:
                return self.send_json({'error': 'Unauthorized Admin'}, 401)
            key_id = body.get('id')
            new_status = toggle_api_key(key_id)
            return self.send_json({'message': 'Status updated', 'is_active': new_status})

        # Admin: Delete Key
        if path == '/api/admin/keys/delete':
            admin = self.get_auth_admin()
            if not admin:
                return self.send_json({'error': 'Unauthorized Admin'}, 401)
            key_id = body.get('id')
            delete_api_key(key_id)
            return self.send_json({'message': 'Key deleted'})

        # PROTECTED ENDPOINT: POST /api/extract
        if path == '/api/extract':
            req_key = self.headers.get('X-API-Key') or body.get('api_key')
            if not validate_api_key(req_key) and not self.check_api_key(query):
                return self.send_json({
                    'status': 'error',
                    'error': 'Unauthorized: Valid X-API-Key header or api_key field required.'
                }, 401)

            target_url = body.get('url', '').strip()
            if not target_url:
                return self.send_json({'status': 'error', 'error': 'Field "url" is required'}, 400)
            res = extract_metrics(target_url)
            status_code = 200 if res.get('status') == 'success' else 422
            return self.send_json(res, status_code)

        # PROTECTED ENDPOINT: POST /api/extract/batch
        if path == '/api/extract/batch':
            req_key = self.headers.get('X-API-Key') or body.get('api_key')
            if not validate_api_key(req_key) and not self.check_api_key(query):
                return self.send_json({
                    'status': 'error',
                    'error': 'Unauthorized: Valid X-API-Key header required.'
                }, 401)

            urls = body.get('urls', [])
            if not isinstance(urls, list) or len(urls) == 0:
                return self.send_json({'status': 'error', 'error': 'Field "urls" must be a non-empty array'}, 400)

            target_urls = urls[:30]
            futures = [executor.submit(extract_metrics, u) for u in target_urls]
            results = [f.result() for f in futures]

            success_count = sum(1 for r in results if r.get('status') == 'success')
            return self.send_json({
                'status': 'success',
                'total': len(results),
                'successful': success_count,
                'failed': len(results) - success_count,
                'data': results
            }, 200)

        return self.send_json({'status': 'error', 'error': 'Endpoint not found'}, 404)

def run():
    init_db()
    server_address = ('0.0.0.0', PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, SecureApiHandler)
    print(f"MetricsPulse Protected API & MCP SSE Server running at http://0.0.0.0:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

if __name__ == '__main__':
    run()
