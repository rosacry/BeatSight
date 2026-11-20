"""Serve one local review folder with byte ranges for reliable audio seeking."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re


class ReviewHandler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(403, "Open the review/review.html page directly")
        return None

    def send_head(self):
        self.remaining = None
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return super().send_head()
        length = path.stat().st_size
        start, end, status = 0, length - 1, 200
        header = self.headers.get("Range")
        if header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
            if not match or not any(match.groups()):
                self.send_error(416, "Unsupported byte range")
                return None
            if match[1]:
                start = int(match[1])
                end = min(int(match[2]), length - 1) if match[2] else length - 1
            else:
                start = max(0, length - int(match[2]))
            if start > end or start >= length:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{length}")
                self.end_headers()
                return None
            status = 206
        handle = path.open("rb")
        handle.seek(start)
        self.remaining = end - start + 1
        self.send_response(status)
        self.send_header("Content-type", self.guess_type(str(path)))
        self.send_header("Content-Length", str(self.remaining))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{length}")
        self.end_headers()
        return handle

    def copyfile(self, source, outputfile):
        if self.remaining is None:
            return super().copyfile(source, outputfile)
        try:
            while self.remaining:
                chunk = source.read(min(65536, self.remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                self.remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Browsers cancel old byte-range requests during seeking.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.drive.upper() != "C:" or not (root / "review/review.html").is_file():
        raise ValueError("Choose a scoped C: experiment containing review/review.html")
    handler = lambda *a, **kw: ReviewHandler(*a, directory=str(root), **kw)
    print(f"Local review: http://127.0.0.1:{args.port}/review/review.html", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
