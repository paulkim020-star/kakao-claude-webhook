# CLAUDE.md

This file guides Claude Code when working in this repository.

## Project Overview

A FastAPI webhook server that bridges Kakao i 오픈빌더 (Kakao's chatbot builder) skills
with the Claude API. Flow: KakaoTalk user message -> Kakao Open Builder -> POST
`/kakao/webhook` -> this server calls Claude -> response is wrapped in Kakao's
skill response JSON format (`simpleText`) and returned.

- `main.py` - the entire server (FastAPI app, Kakao payload parsing, Claude call,
  in-memory per-user conversation history).
- `requirements.txt` - pinned dependencies (fastapi, uvicorn, anthropic, httpx,
  python-dotenv).

### Running locally

```
pip install -r requirements.txt
# .env with ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Key constraints to keep in mind

- Kakao's skill server expects a response within ~5 seconds, or it times out. Don't
  add slow synchronous work to the webhook path without considering Kakao's
  `useCallback` async response option.
- Conversation history is a plain in-memory dict (`_conversation_store`), capped at
  `MAX_HISTORY_TURNS`. It resets on restart/scale-out - this is a known, accepted
  limitation for this simple deployment, not a bug to silently "fix" with Redis
  unless asked.
- `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, and `SYSTEM_PROMPT` are configured via
  environment variables with defaults in `main.py`.

## Working Guidelines

These behavioral guidelines reduce common LLM coding mistakes. They bias toward
caution over speed - use judgment on trivial tasks.

### 1. Think Before Coding

Don't assume, don't hide confusion, surface tradeoffs.

- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them - don't silently pick one.
- If a simpler approach exists, say so and push back when warranted.
- If something is unclear, stop, name what's confusing, and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for scenarios that can't happen.
- If a change could be much shorter, rewrite it shorter.

Ask: "Would a senior engineer call this overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must; clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style (including this file's Korean comments in `main.py`), even
  if you'd write it differently.
- If you notice unrelated dead code, mention it - don't delete it unasked.
- Remove imports/variables/functions that your own change made unused; leave
  pre-existing dead code alone.
- Every changed line should trace directly to the request.

### 4. Goal-Driven Execution

Define success criteria, then loop until verified.

- "Add validation" -> write tests/checks for invalid inputs, then make them pass.
- "Fix the bug" -> reproduce it first, then verify the fix resolves it.
- "Refactor X" -> confirm behavior is unchanged before and after.
- For multi-step tasks, state a brief plan with a verification step per item, e.g.:

```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
```

Since this repo currently has no automated tests, verification for webhook changes
means manually exercising `/kakao/webhook` (e.g. with `curl` or `httpx`) against a
sample Kakao payload, not just reading the code.
