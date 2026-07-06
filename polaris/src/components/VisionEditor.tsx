import { useState } from 'react'
import { useStore } from '../store'

// §4.6 10년 비전 작성 화면 — 종이 질감의 전체 화면 에디터, 프롬프트 워터마크.
const PROMPTS = [
  '10년 뒤 평범한 화요일, 당신은 아침에 무엇을 하나요?',
  '누구와 함께 있나요?',
  '무엇이 더는 걱정이 아니게 되었나요?',
]

export function VisionEditor({ onClose }: { onClose: () => void }) {
  const vision = useStore((s) => s.vision)
  const save = useStore((s) => s.saveVision)
  const [text, setText] = useState(vision?.narrative ?? '')
  const [keywords, setKeywords] = useState((vision?.keywords ?? []).join(', '))

  const submit = () => {
    const kw = keywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean)
      .slice(0, 5)
    save(text.trim(), kw)
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      style={{ background: 'var(--paper)' }}
    >
      <div className="mx-auto max-w-[540px] px-6 py-8">
        <button
          type="button"
          onClick={onClose}
          className="mb-4 text-sm text-ink-soft"
        >
          ← 닫기
        </button>
        <h1 className="font-display text-xl">북극성을 그려요</h1>
        <p className="mt-1 text-sm text-ink-soft">
          10년 뒤의 하루를 상상해서 편지처럼 써보세요.
        </p>

        <div className="relative mt-6">
          {!text && (
            <div className="pointer-events-none absolute inset-0 space-y-2 p-1 text-lg leading-relaxed text-ink-soft opacity-40">
              {PROMPTS.map((p) => (
                <p key={p} className="font-display">
                  {p}
                </p>
              ))}
            </div>
          )}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="font-display w-full resize-none rounded-card border border-line bg-paper-raised p-4 text-lg leading-relaxed outline-none"
            style={{ minHeight: 260 }}
          />
        </div>

        <label className="mt-6 block text-sm text-ink-soft">
          키워드 최대 5개 — 별자리의 별 이름이 됩니다
        </label>
        <input
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="글, 성장, 자유 (쉼표로 구분)"
          className="mt-2 w-full rounded-card border border-line bg-paper-raised px-4 py-3 text-base outline-none"
        />

        <button
          type="button"
          onClick={submit}
          disabled={!text.trim()}
          className="mt-8 h-12 w-full rounded-full text-base font-medium text-white disabled:opacity-30"
          style={{ background: 'var(--dawn)' }}
        >
          북극성 새기기
        </button>
      </div>
    </div>
  )
}
