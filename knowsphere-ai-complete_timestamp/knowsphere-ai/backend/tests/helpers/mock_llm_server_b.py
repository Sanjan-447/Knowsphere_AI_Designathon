import json, time
from http.server import BaseHTTPRequestHandler, HTTPServer

class MockHandlerB(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        json.loads(self.rfile.read(length) or b"{}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {"choices": [{"message": {"role": "assistant", "content": "Hello from PROVIDER B (simulating a premium key)."}}]}
        self.wfile.write(json.dumps(resp).encode())

if __name__ == "__main__":
    import sys
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8878
    HTTPServer(("127.0.0.1", port_arg), MockHandlerB).serve_forever()
