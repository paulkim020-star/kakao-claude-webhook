"""CLI - python -m storybook "주제" [--pages N] [--out book.html]"""
import argparse
import logging

from .build import build_storybook


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude로 그림 동화책을 만든다.")
    parser.add_argument("topic", help="동화 주제 (예: '달에 놀러 간 아기 토끼')")
    parser.add_argument("--pages", type=int, default=5, help="페이지 수 (기본 5)")
    parser.add_argument("--out", default="storybook.html", help="출력 HTML 경로")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    path = build_storybook(args.topic, args.pages, args.out)
    print(f"완성! -> {path}")


if __name__ == "__main__":
    main()
