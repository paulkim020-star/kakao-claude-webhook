"""실행: python -m ebook  (기본 http://127.0.0.1:8765, 브라우저 자동 열기)"""

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF 서재")
    parser.add_argument("--host", default="127.0.0.1",
                        help="같은 와이파이의 다른 기기에서도 쓰려면 0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.no_browser:
        url = f"http://127.0.0.1:{args.port}"
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run("ebook.app:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
