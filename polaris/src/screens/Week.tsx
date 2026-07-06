import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { addDays, todayKey, weekdayIndex } from '../lib/dates'
import { areaColor } from '../lib/meta'
import { Card } from '../components/Card'
import { TaskRow } from '../components/TaskRow'

const DOW = ['월', '화', '수', '목', '금', '토', '일']

export function Week() {
  const tasks = useStore((s) => s.tasks)
  const goals = useStore((s) => s.yearlyGoals)
  const setDate = useStore((s) => s.setDate)
  const [focus, setFocus] = useState<string[]>([])
  const [showInbox, setShowInbox] = useState(false)

  const today = todayKey()
  const monday = useMemo(() => {
    const back = (weekdayIndex(today) + 6) % 7
    return addDays(today, -back)
  }, [today])
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(monday, i)),
    [monday],
  )
  const inbox = tasks.filter((t) => t.date === null && !t.done)

  const toggleFocus = (id: string) =>
    setFocus((f) => (f.includes(id) ? f.filter((x) => x !== id) : [...f, id]))

  return (
    <div className="mx-auto max-w-[440px] px-5 pb-28 pt-3">
      <header className="mb-4">
        <h1 className="font-display text-2xl">이번 주</h1>
      </header>

      {/* 이번 주의 초점 */}
      {goals.length > 0 && (
        <section className="mb-5">
          <p className="mb-2 text-sm text-ink-soft">
            이번 주에 진전시킬 목표
          </p>
          <div className="flex flex-wrap gap-2">
            {goals.map((g) => {
              const on = focus.includes(g.id)
              return (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => toggleFocus(g.id)}
                  className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm"
                  style={{
                    borderColor: on ? areaColor(g.area) : 'var(--line)',
                    color: on ? 'var(--ink)' : 'var(--ink-soft)',
                    background: on ? 'var(--paper-raised)' : 'transparent',
                  }}
                >
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: areaColor(g.area) }}
                  />
                  {g.title}
                </button>
              )
            })}
          </div>
        </section>
      )}

      {/* 미니 주간 바 */}
      <div className="mb-4 flex gap-1.5">
        {days.map((d, i) => {
          const count = tasks.filter((t) => t.date === d && !t.done).length
          const isToday = d === today
          return (
            <div key={d} className="flex-1 text-center">
              <div
                className="text-xs"
                style={{ color: isToday ? 'var(--dawn)' : 'var(--ink-soft)' }}
              >
                {DOW[i]}
              </div>
              <div
                className="mx-auto mt-1 h-1.5 w-1.5 rounded-full"
                style={{
                  background: count ? 'var(--dawn)' : 'var(--line)',
                  opacity: count ? Math.min(1, 0.4 + count * 0.2) : 1,
                }}
              />
            </div>
          )
        })}
      </div>

      {/* 요일별 리스트 */}
      <div className="space-y-3">
        {days.map((d, i) => {
          const dayTasks = tasks.filter((t) => t.date === d)
          if (dayTasks.length === 0) return null
          return (
            <div key={d}>
              <div className="mb-1 flex items-center gap-2 px-1">
                <span
                  className="text-sm font-medium"
                  style={{ color: d === today ? 'var(--dawn)' : 'var(--ink)' }}
                >
                  {DOW[i]}요일
                </span>
              </div>
              <Card className="px-4 py-1">
                {dayTasks.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </Card>
            </div>
          )
        })}
      </div>

      {/* 인박스 서랍 — 개수 배지 없음, 빚이 아니라 서랍 */}
      <section className="mt-6">
        <button
          type="button"
          onClick={() => setShowInbox((v) => !v)}
          className="flex items-center gap-2 text-sm text-ink-soft"
        >
          <span>{showInbox ? '▽' : '▷'}</span> 인박스 (언젠가)
        </button>
        {showInbox && (
          <Card className="animate-fade-up mt-2 p-4">
            {inbox.length === 0 ? (
              <p className="text-sm text-ink-soft">
                비어 있어요. 죄책감 없는 보관함이에요.
              </p>
            ) : (
              <div className="space-y-2">
                {inbox.map((t) => (
                  <div key={t.id} className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm">
                      {t.title}
                    </span>
                    <button
                      type="button"
                      onClick={() => setDate(t.id, today)}
                      className="rounded-full border border-line px-3 py-1 text-xs text-ink-soft"
                    >
                      오늘로
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </section>
    </div>
  )
}
