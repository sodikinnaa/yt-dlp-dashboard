import http.server
import json
import os
import sys
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
        # 1. Check Header: X-API-Key
        key = self.headers.get('X-API-Key')
        if key and validate_api_key(key):
            return True

        # 2. Check Header: Authorization (Bearer ...)
        auth = self.headers.get('Authorization')
        if auth and validate_api_key(auth):
            return True

        # 3. Check Query parameter: ?api_key=...
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
                'service': 'Social Media Metrics API (Secured)',
                'engine': 'yt-dlp',
                'port': PORT
            })

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
    print(f"MetricsPulse Protected API Server running at http://0.0.0.0:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

if __name__ == '__main__':
    run()
