import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { addDays, todayKey, weekdayIndex } from '../lib/dates'
import { areaColor, goalColor } from '../lib/meta'
import { Card, GoalDot } from '../components/Card'
import { Checkbox } from '../components/Checkbox'
import { WeeklyPlanner } from '../components/WeeklyPlanner'
import { QuickAdd } from '../components/QuickAdd'
import type { Task } from '../types'

const DOW = ['월', '화', '수', '목', '금', '토', '일']

export function Week() {
  const tasks = useStore((s) => s.tasks)
  const goals = useStore((s) => s.yearlyGoals)
  const weeklyFocus = useStore((s) => s.weeklyFocus)
  const toggleFocus = useStore((s) => s.toggleWeeklyFocus)
  const setDate = useStore((s) => s.setDate)

  const [showInbox, setShowInbox] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [dragId, setDragId] = useState<string | null>(null)
  const [dropDay, setDropDay] = useState<string | null>(null)
  const [addDay, setAddDay] = useState<string | null>(null) // 이 날짜로 추가

  const today = todayKey()
  const monday = useMemo(
    () => addDays(today, -((weekdayIndex(today) + 6) % 7)),
    [today],
  )
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(monday, i)),
    [monday],
  )
  const inbox = tasks.filter((t) => t.date === null && !t.done)
  const focus = weeklyFocus[monday] ?? []
  const isSunday = weekdayIndex(today) === 0

  const drop = (day: string) => {
    if (dragId) setDate(dragId, day)
    setDragId(null)
    setDropDay(null)
  }

  return (
    <div className="mx-auto max-w-[440px] px-5 pb-28 pt-3">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="font-display text-2xl">이번 주</h1>
        <button
          type="button"
          onClick={() => setPlanning(true)}
          className="rounded-full border px-3 py-1.5 text-sm"
          style={{
            borderColor: isSunday ? 'var(--dawn)' : 'var(--line)',
            color: isSunday ? 'var(--dawn)' : 'var(--ink-soft)',
          }}
        >
          주간 계획
        </button>
      </header>

      {isSunday && (
        <button
          type="button"
          onClick={() => setPlanning(true)}
          className="mb-4 w-full rounded-card p-3 text-left text-sm"
          style={{ background: 'var(--dawn-soft)', color: 'var(--ink)' }}
        >
          10분이면 다음 주가 정리돼요.
        </button>
      )}

      {/* 이번 주의 초점 (영속) */}
      {goals.length > 0 && (
        <section className="mb-5">
          <p className="mb-2 text-sm text-ink-soft">이번 주에 진전시킬 목표</p>
          <div className="flex flex-wrap gap-2">
            {goals.map((g) => {
              const on = focus.includes(g.id)
              return (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => toggleFocus(monday, g.id)}
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

      {/* 요일별 리스트 (드래그 이동 + 탭 이동) */}
      <div className="space-y-3">
        {days.map((d, i) => {
          const dayTasks = tasks.filter((t) => t.date === d)
          const hasFocus = dayTasks.some(
            (t) => t.yearlyGoalId && focus.includes(t.yearlyGoalId),
          )
          const focusG = goals.find(
            (g) =>
              focus.includes(g.id) &&
              dayTasks.some((t) => t.yearlyGoalId === g.id),
          )
          const isDrop = dropDay === d
          return (
            <div
              key={d}
              onDragOver={(e) => {
                e.preventDefault()
                setDropDay(d)
              }}
              onDragLeave={() => setDropDay((cur) => (cur === d ? null : cur))}
              onDrop={() => drop(d)}
            >
              <div className="mb-1 flex items-center gap-2 px-1">
                <span
                  className="text-sm font-medium"
                  style={{ color: d === today ? 'var(--dawn)' : 'var(--ink)' }}
                >
                  {DOW[i]}요일
                </span>
                {hasFocus && focusG && (
                  <span
                    className="h-0.5 w-6 rounded-full"
                    style={{ background: areaColor(focusG.area) }}
                  />
                )}
                <button
                  type="button"
                  onClick={() => setAddDay(d)}
                  className="ml-auto rounded-full px-2 py-0.5 text-sm text-ink-soft"
                  aria-label={`${DOW[i]}요일에 추가`}
                >
                  + 추가
                </button>
              </div>
              <Card
                className={`px-4 py-1 transition-shadow ${
                  isDrop ? 'ring-2 ring-[var(--dawn)]' : ''
                }`}
              >
                {dayTasks.length === 0 ? (
                  isDrop ? (
                    <p className="py-3 text-sm text-ink-soft">여기로 옮겨요</p>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setAddDay(d)}
                      className="w-full py-3 text-left text-sm text-ink-soft"
                    >
                      + 이 날에 할 일 추가
                    </button>
                  )
                ) : (
                  dayTasks.map((t) => (
                    <WeekTaskItem
                      key={t.id}
                      task={t}
                      days={days}
                      onDragStart={() => setDragId(t.id)}
                    />
                  ))
                )}
              </Card>
            </div>
          )
        })}
      </div>

      {/* 인박스 서랍 — 개수 배지 없음 */}
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

      {planning && <WeeklyPlanner onClose={() => setPlanning(false)} />}

      <QuickAdd
        open={addDay !== null}
        onClose={() => setAddDay(null)}
        defaultDate={addDay}
      />
    </div>
  )
}

function WeekTaskItem({
  task,
  days,
  onDragStart,
}: {
  task: Task
  days: string[]
  onDragStart: () => void
}) {
  const goals = useStore((s) => s.yearlyGoals)
  const toggleDone = useStore((s) => s.toggleDone)
  const setDate = useStore((s) => s.setDate)
  const [moving, setMoving] = useState(false)
  const dot = goalColor(task.yearlyGoalId, goals)

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="border-b border-line py-1 last:border-b-0"
    >
      <div className="flex items-center gap-1">
        <Checkbox
          checked={task.done}
          onToggle={() => toggleDone(task.id)}
          ariaLabel={`${task.title} 완료`}
        />
        <button
          type="button"
          onClick={() => setMoving((m) => !m)}
          className="flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left"
        >
          <span
            className={`min-w-0 flex-1 truncate text-sm ${
              task.done ? 'text-ink-soft line-through' : ''
            }`}
          >
            {task.title}
          </span>
          <GoalDot color={dot} />
        </button>
      </div>
      {moving && (
        <div className="animate-fade-up flex flex-wrap gap-1.5 pb-2 pl-11">
          {days.map((d, i) => (
            <button
              key={d}
              type="button"
              onClick={() => {
                setDate(task.id, d)
                setMoving(false)
              }}
              className="rounded-full border px-2.5 py-1 text-xs"
              style={{
                borderColor: task.date === d ? 'var(--ink)' : 'var(--line)',
                color: task.date === d ? 'var(--ink)' : 'var(--ink-soft)',
              }}
            >
              {DOW[i]}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setDate(task.id, null)
              setMoving(false)
            }}
            className="rounded-full border border-line px-2.5 py-1 text-xs text-ink-soft"
          >
            인박스
          </button>
        </div>
      )}
    </div>
  )
}
