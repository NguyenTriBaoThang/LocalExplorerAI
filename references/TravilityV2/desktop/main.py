"""Mở Travility trong cửa sổ desktop.

uv run python main.py                        # bản build client/dist
uv run python main.py http://localhost:5173  # khi đang dev client
"""
import sys
from pathlib import Path

import webview

DIST = Path(__file__).resolve().parent.parent / "client" / "dist" / "index.html"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else str(DIST)
    if not url.startswith("http") and not DIST.exists():
        sys.exit("Chưa có client/dist — chạy `cd client && npm run build` trước.")
    webview.create_window("Travility", url, width=1440, height=900, min_size=(1100, 700))
    webview.start(http_server=True, private_mode=False)


if __name__ == "__main__":
    main()
