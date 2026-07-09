# 동화책 생성 모듈 (작가/화가 두 에이전트)
# db.py      - SQLite 스키마/연결 (책, 페이지)
# writer.py  - 작가 에이전트: Claude로 페이지별 이야기 + 삽화 프롬프트 생성
# painter.py - 화가 에이전트: 삽화 프롬프트 -> 이미지 API (키 없으면 플레이스홀더)
# web.py     - 동화책 생성/열람 웹 (/storybook)
