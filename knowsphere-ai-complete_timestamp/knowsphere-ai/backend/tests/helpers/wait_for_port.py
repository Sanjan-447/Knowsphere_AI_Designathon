"""
Waits for a subprocess-spawned mock server to actually be ready to accept
connections, instead of a fixed time.sleep(N) — which is exactly the kind
of assumption that causes intermittent, hard-to-reproduce test flakiness
under variable system load (confirmed here: the same test suite, same
order, passed on one run and failed on the next with a fixed sleep(1)).
Polling with a short real connection attempt is deterministic; a fixed
sleep is a guess.
"""
import socket
import time


def wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise TimeoutError(f"Server at {host}:{port} did not become ready within {timeout}s (last error: {last_error})")
