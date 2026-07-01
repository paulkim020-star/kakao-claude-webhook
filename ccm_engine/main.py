"""
CCM 엔진 - 성경 주제 기반 CCM 가사/Suno 프롬프트 생성 CLI
=================================================

사용법:
  python3 ccm_engine/main.py --theme "하나님의 자비하심" [--genre "CCM 발라드"] [--tone 정통|MZ] [--output result.md]

파이프라인 (4단계, 모두 Claude API 호출):
  1. 주제 관련 성경 구절 찾기
  2. 원곡 가사 작성 (Verse/Chorus/Bridge/Outro)
  3. humanizer 스킬 기준으로 AI 작문 패턴 교정
  4. Suno용 스타일 프롬프트 생성

[필요한 사전 준비물]
  .env 파일 또는 환경변수에 ANTHROPIC_API_KEY=sk-ant-... 설정

주의: 1단계에서 찾은 성경 구절은 LLM이 생성한 것이라 실제 성경 본문과
표현이 다를 수 있습니다. 사용 전 반드시 성경 원문으로 대조하세요.
"""

import argparse
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUMANIZER_SKILL_PATH = os.path.join(_REPO_ROOT, ".agents", "skills", "humanizer", "SKILL.md")


def _client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.", file=sys.stderr)
        sys.exit(1)
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _ask(client: anthropic.Anthropic, system: str, prompt: str, max_tokens: int) -> str:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def find_verses(client: anthropic.Anthropic, theme: str) -> str:
    system = "당신은 성경 구절 검색을 돕는 도우미입니다. 정확한 출처(장:절)를 반드시 표기하세요."
    prompt = (
        f"'{theme}'을 주제로 한 성경 구절을 6~10개 찾아 목록으로 정리해줘. "
        "각 항목은 '- 출처: 짧은 인용 또는 요약' 형식으로."
    )
    return _ask(client, system, prompt, max_tokens=800)


def write_lyrics(client: anthropic.Anthropic, theme: str, verses: str, tone: str) -> str:
    tone_hint = "정통 CCM/워십 발라드 톤" if tone == "정통" else "요즘 MZ세대 말투, 캐주얼하고 트렌디한 톤"
    system = "당신은 한국어 CCM 작사가입니다. 성경 구절의 의미를 보존하면서 오리지널 가사를 창작합니다."
    prompt = (
        f"다음 성경 구절들을 참고해서 '{theme}'을 주제로 한 오리지널 한국어 CCM 가사를 써줘.\n\n"
        f"{verses}\n\n"
        f"조건: {tone_hint}. 구조는 [Verse 1] [Chorus] [Verse 2] [Chorus] [Bridge] [Outro] [Chorus] 형식으로. "
        "각 줄은 서술어가 있는 완결된 문장(또는 두 줄에 걸친 완결 문장)으로 써서 뚝뚝 끊기지 않게 해줘."
    )
    return _ask(client, system, prompt, max_tokens=1200)


def humanize_lyrics(client: anthropic.Anthropic, lyrics: str) -> str:
    if not os.path.exists(HUMANIZER_SKILL_PATH):
        return lyrics
    with open(HUMANIZER_SKILL_PATH, encoding="utf-8") as f:
        skill_instructions = f.read()
    prompt = (
        "다음 가사를 스킬 지침에 따라 분석하고 자연스러운 버전으로 재작성해줘. "
        "결과에는 재작성된 최종 가사만 포함해줘(분석 리포트 생략):\n\n" + lyrics
    )
    return _ask(client, skill_instructions, prompt, max_tokens=1200)


def build_suno_prompt(client: anthropic.Anthropic, lyrics: str, genre: str) -> str:
    system = "당신은 Suno AI 음악 생성 프롬프트를 작성하는 전문가입니다."
    prompt = (
        f"다음 가사에 어울리는 Suno 스타일 프롬프트(영어, 장르/악기/보컬/템포/무드 태그 나열)를 "
        f"한 문단으로 써줘. 장르 힌트: {genre}.\n\n가사:\n{lyrics}"
    )
    return _ask(client, system, prompt, max_tokens=300)


def run_pipeline(theme: str, genre: str, tone: str) -> str:
    client = _client()
    verses = find_verses(client, theme)
    lyrics = write_lyrics(client, theme, verses, tone)
    natural_lyrics = humanize_lyrics(client, lyrics)
    suno_prompt = build_suno_prompt(client, natural_lyrics, genre)

    return (
        f"# CCM 엔진 결과: {theme}\n\n"
        f"## 1. 참고 성경 구절\n{verses}\n\n"
        f"## 2. 가사 (humanizer 교정 완료)\n{natural_lyrics}\n\n"
        f"## 3. Suno 스타일 프롬프트\n{suno_prompt}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="성경 주제로 CCM 가사와 Suno 프롬프트를 생성하는 CLI")
    parser.add_argument("--theme", required=True, help="가사 주제 (예: '하나님의 자비하심')")
    parser.add_argument("--genre", default="CCM 발라드", help="음악 장르/스타일 힌트")
    parser.add_argument("--tone", choices=["정통", "MZ"], default="정통", help="가사 톤")
    parser.add_argument("--output", help="결과를 저장할 파일 경로 (.md)")
    args = parser.parse_args()

    result = run_pipeline(args.theme, args.genre, args.tone)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"결과를 {args.output}에 저장했습니다.")
    else:
        print(result)


if __name__ == "__main__":
    main()
