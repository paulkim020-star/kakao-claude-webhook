import { useMemo } from 'react'
import { useStore } from '../store'
import { todayKey } from '../lib/dates'
import { Card } from './Card'

// §4.2 아침 리추얼(첫 진입 시 1회): 어제 미완료 태스크를 카드로.
// "3개가 남았어요. 오늘로 가져올까요, 놓아줄까요?" — 죄책감 대신 선택의 언어.
// 반복 태스크는 나타나지 않는다(자동 소멸).
export function MorningRitual() {
  const tasks = useStore((s) => s.tasks)
  const lastRitual = useStore((s) => s.lastRitual)
  const carry = useStore((s) => s.carryToToday)
  const release = useStore((s) => s.removeTask)
  const markSeen = useStore((s) => s.markRitualSeen)
  const today = todayKey()

  const leftovers = useMemo(
    () =>
      tasks.filter(
        (t) =>
          !t.done && t.recurring === 'none' && t.date !== null && t.date < today,
      ),
    [tasks, today],
  )

  if (lastRitual === today || leftovers.length === 0) return null

  return (
    <Card className="animate-fade-up mb-6 p-5" >
      <p className="font-display text-lg">
        {leftovers.length}개가 남았어요.
      </p>
      <p className="mt-1 text-sm text-ink-soft">
        오늘로 가져올까요, 놓아줄까요?
      </p>

      <div className="mt-4 space-y-2">
        {leftovers.map((t) => (
          <div
            key={t.id}
            className="flex items-center gap-2 border-t border-line pt-2 first:border-t-0 first:pt-0"
          >
            <span className="min-w-0 flex-1 truncate text-sm">{t.title}</span>
            <button
              type="button"
              onClick={() => carry(t.id)}
              className="rounded-full px-3 py-1 text-xs font-medium text-white"
              style={{ background: 'var(--dawn)' }}
            >
              가져오기
            </button>
            <button
              type="button"
              onClick={() => release(t.id)}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink-soft"
            >
              놓아주기
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={markSeen}
        className="mt-4 text-xs text-ink-soft underline underline-offset-2"
      >
        나중에 볼게요
      </button>
    </Card>
  )
}
