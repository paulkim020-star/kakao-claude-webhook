# 동화책 생성 독립 모듈 (storybook)
# writer.py   - 작가 에이전트: Claude로 페이지별 본문 + 장면 묘사(image_prompt) 생성
# painter.py  - 화가 에이전트: image_prompt -> 이미지(OpenAI gpt-image-1), 키 없으면 텍스트 대체
# build.py    - 작가 -> 화가 -> 자체 완결형 HTML 동화책 조립/출력
# __main__.py - CLI: python -m storybook "주제" --pages N --out book.html
