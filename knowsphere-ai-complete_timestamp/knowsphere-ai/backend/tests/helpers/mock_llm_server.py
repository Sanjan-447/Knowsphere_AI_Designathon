"""
Versatile mock OpenAI-compatible server for testing error handling and
citation edge cases. Behavior is controlled by a magic trigger word in the
user's question:

  TRIGGER_500       -> returns HTTP 500
  TRIGGER_401       -> returns HTTP 401 (invalid key simulation)
  TRIGGER_MALFORMED -> returns HTTP 200 with a non-JSON body
  TRIGGER_TIMEOUT   -> sleeps 5s before responding (pair with a short client timeout)
  TRIGGER_CITE_ALL  -> cites every [n] marker found in the context, not just the first
  (anything else)   -> normal behavior: cites the first marker found, or the
                       fallback sentence if no markers are present
"""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path.startswith("/embeddings"):
            self._handle_embeddings(body)
            return

        stream = body.get("stream", False)
        messages = body.get("messages", [])
        all_content = "\n".join(m.get("content", "") for m in messages)
        user_content = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        if "TRIGGER_500" in user_content:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "internal server error (simulated)"}).encode())
            return

        if "TRIGGER_401" in user_content:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid api key (simulated)"}).encode())
            return

        if "TRIGGER_MALFORMED" in user_content:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{not valid json at all !!!")
            return

        if "TRIGGER_TIMEOUT" in user_content:
            time.sleep(5)
            # falls through to normal response after the sleep, in case the
            # client's timeout is longer than this in some test

        markers = sorted({int(m) for m in re.findall(r"\[(\d+)\]", all_content)})
        if not markers:
            answer = "The requested information is not available in the enterprise knowledge base."
        elif "TRIGGER_CITE_ALL" in user_content:
            cites = " ".join(f"[{m}]" for m in markers)
            answer = f"Based on all provided sources: {cites}"
        else:
            answer = f"Based on the provided context, here is the answer [{markers[0]}]."

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for word in answer.split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.01)
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "choices": [{"message": {"role": "assistant", "content": answer}}],
                "usage": {"prompt_tokens": len(all_content) // 4, "completion_tokens": len(answer.split())},
            }
            self.wfile.write(json.dumps(resp).encode())

    def _handle_embeddings(self, body):
        inputs = body.get("input", [])
        text_blob = " ".join(inputs) if isinstance(inputs, list) else str(inputs)

        if "TRIGGER_EMBED_500" in text_blob:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "internal server error (simulated)"}).encode())
            return

        if "TRIGGER_EMBED_MALFORMED" in text_blob:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{not valid json !!")
            return

        # Normal case: return a fixed-size fake embedding vector per input.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        data = [{"index": i, "embedding": [0.01 * i] * 1536} for i in range(len(inputs) if isinstance(inputs, list) else 1)]
        self.wfile.write(json.dumps({"data": data}).encode())


def run_mock_server(port: int = 8877):
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    server.serve_forever()


if __name__ == "__main__":
    import sys
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8877
    run_mock_server(port_arg)
