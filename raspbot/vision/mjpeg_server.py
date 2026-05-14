"""
Thread-safe MJPEG-over-HTTP server.

Use it to view the debug video from another machine (e.g. your laptop) while
the Pi runs headless over SSH. No external dependencies — pure stdlib + cv2.

Usage:
    server = MJPEGServer(port=8080)
    server.start()
    ...
    server.push("main", annotated_frame)
    server.push("mask", mask_frame)
    ...
    server.stop()

URLs:
    http://<pi-ip>:8080/             → side-by-side HTML page
    http://<pi-ip>:8080/stream.mjpg  → annotated stream
    http://<pi-ip>:8080/mask.mjpg    → mask stream
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np


_INDEX_HTML = b"""<!DOCTYPE html>
<html><head><title>Raspbot Line Follow</title>
<style>
  body { background: #111; color: #eee; font-family: monospace;
         margin: 0; padding: 1em; }
  h1 { margin: 0 0 0.5em 0; font-size: 1.1em; }
  h2 { margin: 0.4em 0; font-size: 0.95em; color: #9cf; }
  .row { display: flex; flex-wrap: wrap; gap: 1em; }
  .col { flex: 1; min-width: 320px; }
  img { width: 100%; height: auto; border: 1px solid #444;
        image-rendering: pixelated; }
</style></head><body>
  <h1>Raspbot Line Follow &mdash; Live</h1>
  <div class="row">
    <div class="col"><h2>Annotated</h2><img src="/stream.mjpg"></div>
    <div class="col"><h2>White-line mask</h2><img src="/mask.mjpg"></div>
  </div>
</body></html>"""


class MJPEGServer:
    def __init__(
        self,
        port: int = 8080,
        fps_cap: int = 15,
        jpeg_quality: int = 75,
    ) -> None:
        self.port = port
        self.fps_cap = max(1, fps_cap)
        self.jpeg_quality = jpeg_quality
        self._frames: dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def push(self, stream: str, frame: np.ndarray) -> None:
        ok, buf = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            return
        with self._lock:
            self._frames[stream] = buf.tobytes()

    def _get(self, stream: str) -> bytes | None:
        with self._lock:
            return self._frames.get(stream)

    def start(self) -> None:
        server_self = self
        stream_map = {"/stream.mjpg": "main", "/mask.mjpg": "mask"}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Content-Length", str(len(_INDEX_HTML)))
                    self.end_headers()
                    self.wfile.write(_INDEX_HTML)
                    return

                if self.path not in stream_map:
                    self.send_error(404)
                    return

                stream_name = stream_map[self.path]
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.end_headers()

                interval = 1.0 / server_self.fps_cap

                try:
                    while True:
                        data = server_self._get(stream_name)
                        if data is None:
                            time.sleep(0.05)
                            continue

                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(data)}\r\n\r\n".encode()
                        )
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                        time.sleep(interval)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
