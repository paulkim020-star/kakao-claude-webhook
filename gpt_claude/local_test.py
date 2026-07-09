"""
로컬 GPT <-> Claude 대화 테스트 (터미널 실행용)
==============================================
API 키만 환경변수로 넣으면 터미널에서 바로 두 모델의 대화를 볼 수 있다.

실행:
    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m gpt_claude.local_test "인공지능의 미래" --rounds 3

옵션:
    --rounds N        각 모델이 몇 번씩 말할지 (기본 3 -> 총 6턴)
    --first GPT|Claude  누가 먼저 말할지 (기본 GPT)
"""
import argparse

from gpt_claude.conversation import Turn, run_dialogue


def main() -> None:
    parser = argparse.ArgumentParser(description="GPT와 Claude가 주제를 놓고 대화합니다.")
    parser.add_argument("topic", help="대화 주제")
    parser.add_argument("--rounds", type=int, default=3, help="각 모델의 발언 횟수 (기본 3)")
    parser.add_argument("--first", choices=["GPT", "Claude"], default="GPT", help="먼저 말할 모델")
    args = parser.parse_args()

    print(f"\n=== 주제: {args.topic} ===\n")

    def show(turn: Turn) -> None:
        print(f"[{turn.speaker}] {turn.text}\n")

    run_dialogue(args.topic, rounds=args.rounds, first=args.first, on_turn=show)


if __name__ == "__main__":
    main()
