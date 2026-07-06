import { useState } from 'react'
import { useStore } from '../store'
import { Card } from './Card'
import type { Task } from '../types'

// §4.2 3회 이월 규칙: carryCount >= 3인 태스크에 앱이 먼저 말을 건다.
// 미룸을 실패가 아니라 신호로 다룬다.
export function CarryThriceCard({ task }: { task: Task }) {
  const split = useStore((s) => s.splitTask)
  const setDate = useStore((s) => s.setDate)
  const remove = useStore((s) => s.removeTask)
  const [splitting, setSplitting] = useState(false)
  const [a, setA] = useState('')
  const [b, setB] = useState('')

  return (
    <Card className="animate-fade-up mb-6 p-5">
      <p className="font-display text-lg">세 번 함께 넘어왔어요.</p>
      <p className="mt-1 text-sm text-ink-soft">
        「{task.title}」 — 더 잘게 쪼갤까요, 인박스에 쉬게 할까요, 놓아줄까요?
      </p>

      {splitting ? (
        <div className="mt-4 space-y-2">
          <input
            value={a}
            onChange={(e) => setA(e.target.value)}
            placeholder="더 작은 첫 걸음"
            className="w-full rounded-lg border border-line bg-transparent px-3 py-2 text-sm outline-none"
          />
          <input
            value={b}
            onChange={(e) => setB(e.target.value)}
            placeholder="그 다음 걸음"
            className="w-full rounded-lg border border-line bg-transparent px-3 py-2 text-sm outline-none"
          />
          <button
            type="button"
            disabled={!a.trim() && !b.trim()}
            onClick={() => split(task.id, [a, b])}
            className="h-10 w-full rounded-full text-sm font-medium text-white disabled:opacity-30"
            style={{ background: 'var(--dawn)' }}
          >
            쪼개기
          </button>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSplitting(true)}
            className="rounded-full px-4 py-2 text-sm font-medium text-white"
            style={{ background: 'var(--dawn)' }}
          >
            쪼개기
          </button>
          <button
            type="button"
            onClick={() => setDate(task.id, null)}
            className="rounded-full border border-line px-4 py-2 text-sm text-ink-soft"
          >
            인박스로
          </button>
          <button
            type="button"
            onClick={() => remove(task.id)}
            className="rounded-full border border-line px-4 py-2 text-sm text-ink-soft"
          >
            놓아주기
          </button>
        </div>
      )}
    </Card>
  )
}
