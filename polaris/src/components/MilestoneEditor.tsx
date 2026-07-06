import { useState } from 'react'
import { useStore, MAX_MILESTONES } from '../store'
import { Card } from './Card'

// §3 Milestone5 (5년 이정표, 최대 4개) 관리 모달.
export function MilestoneEditor({ onClose }: { onClose: () => void }) {
  const vision = useStore((s) => s.vision)
  const milestones = useStore((s) => s.milestones)
  const addMilestone = useStore((s) => s.addMilestone)
  const removeMilestone = useStore((s) => s.removeMilestone)

  const nextYear = new Date().getFullYear() + 5
  const [title, setTitle] = useState('')
  const [year, setYear] = useState(nextYear)
  const [keyword, setKeyword] = useState(vision?.keywords[0] ?? '')

  const full = milestones.length >= MAX_MILESTONES

  const save = () => {
    if (!title.trim()) return
    const ok = addMilestone({
      title: title.trim(),
      targetYear: year,
      visionKeyword: keyword,
    })
    if (ok) setTitle('')
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: 'var(--paper)' }}>
      <div className="mx-auto max-w-[440px] px-5 py-8">
        <button type="button" onClick={onClose} className="mb-4 text-sm text-ink-soft">
          ← 닫기
        </button>
        <h1 className="font-display text-xl">5년 이정표</h1>
        <p className="mt-1 text-sm text-ink-soft">
          북극성으로 가는 길목의 별. 최대 {MAX_MILESTONES}개.
        </p>

        <div className="mt-6 space-y-3">
          {milestones.map((m) => (
            <Card key={m.id} className="flex items-center gap-3 p-4">
              <span
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full font-num text-xs"
                style={{ background: 'var(--dawn-soft)', color: 'var(--ink)' }}
              >
                {m.targetYear % 100}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{m.title}</p>
                {m.visionKeyword && (
                  <p className="text-xs text-ink-soft">{m.visionKeyword}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => removeMilestone(m.id)}
                className="text-xs text-ink-soft"
              >
                놓아주기
              </button>
            </Card>
          ))}
        </div>

        {full ? (
          <p className="mt-4 text-center text-sm text-ink-soft">
            이정표는 4개까지예요.
          </p>
        ) : (
          <Card className="mt-4 space-y-3 p-4">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="예: 출간 작가가 되어 있다"
              className="w-full rounded-lg border border-line bg-transparent px-3 py-2 text-base outline-none"
            />
            <div className="flex items-center gap-3">
              <label className="text-sm text-ink-soft">목표 연도</label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="font-num w-24 rounded-lg border border-line bg-transparent px-3 py-2 text-sm outline-none"
              />
            </div>
            {vision && vision.keywords.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {vision.keywords.map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setKeyword(k)}
                    className="rounded-full border px-3 py-1.5 text-sm"
                    style={{
                      borderColor: keyword === k ? 'var(--ink)' : 'var(--line)',
                      color: keyword === k ? 'var(--ink)' : 'var(--ink-soft)',
                    }}
                  >
                    {k}
                  </button>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={save}
              disabled={!title.trim()}
              className="h-10 w-full rounded-full text-sm font-medium text-white disabled:opacity-30"
              style={{ background: 'var(--dawn)' }}
            >
              이정표 새기기
            </button>
          </Card>
        )}
      </div>
    </div>
  )
}
