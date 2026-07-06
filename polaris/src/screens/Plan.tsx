import { useState } from 'react'
import { useStore, MAX_YEARLY_GOALS } from '../store'
import { AREAS, areaColor } from '../lib/meta'
import { Card } from '../components/Card'
import { ProgressRing } from '../components/ProgressRing'
import { Checkbox } from '../components/Checkbox'
import type { Area } from '../types'

export function Plan() {
  const [view, setView] = useState<'yearly' | 'monthly'>('yearly')
  return (
    <div className="mx-auto max-w-[440px] px-5 pb-28 pt-3">
      <header className="mb-4">
        <h1 className="font-display text-2xl">계획</h1>
      </header>

      <div className="mb-5 flex rounded-full border border-line p-1 text-sm">
        {(['yearly', 'monthly'] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className="flex-1 rounded-full py-1.5"
            style={{
              background: view === v ? 'var(--ink)' : 'transparent',
              color: view === v ? '#fff' : 'var(--ink-soft)',
            }}
          >
            {v === 'yearly' ? '연간' : '월간'}
          </button>
        ))}
      </div>

      {view === 'yearly' ? <YearlyView /> : <MonthlyView />}
    </div>
  )
}

function YearlyView() {
  const goals = useStore((s) => s.yearlyGoals)
  const monthly = useStore((s) => s.monthlyGoals)
  const addGoal = useStore((s) => s.addYearlyGoal)
  const removeGoal = useStore((s) => s.removeYearlyGoal)

  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [measure, setMeasure] = useState('')
  const [area, setArea] = useState<Area>('growth')

  const full = goals.length >= MAX_YEARLY_GOALS

  const save = () => {
    if (!title.trim()) return
    addGoal({ title: title.trim(), measure: measure.trim(), area, milestoneId: null })
    setTitle('')
    setMeasure('')
    setAdding(false)
  }

  return (
    <div className="space-y-3">
      {goals.map((g) => {
        const count = monthly.filter((m) => m.yearlyGoalId === g.id).length
        return (
          <Card key={g.id} className="animate-fade-up p-4">
            <div className="flex items-start gap-3">
              <span
                className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: areaColor(g.area) }}
              />
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-medium">{g.title}</h3>
                {g.measure && (
                  <p className="mt-0.5 text-sm text-ink-soft">{g.measure}</p>
                )}
                <p className="mt-1 font-num text-xs text-ink-soft">
                  월간 목표 {count}개
                </p>
              </div>
              <ProgressRing value={g.progress} size={40} showLabel />
            </div>
            <button
              type="button"
              onClick={() => removeGoal(g.id)}
              className="mt-2 text-xs text-ink-soft"
            >
              놓아주기
            </button>
          </Card>
        )
      })}

      {adding ? (
        <Card className="animate-fade-up space-y-3 p-4">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="올해의 목표"
            className="w-full rounded-lg border border-line bg-transparent px-3 py-2 text-base outline-none"
          />
          <input
            value={measure}
            onChange={(e) => setMeasure(e.target.value)}
            placeholder="무엇이 되면 달성인가 (한 줄)"
            className="w-full rounded-lg border border-line bg-transparent px-3 py-2 text-sm outline-none"
          />
          <div className="flex flex-wrap gap-2">
            {AREAS.map((a) => (
              <button
                key={a.key}
                type="button"
                onClick={() => setArea(a.key)}
                className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm"
                style={{
                  borderColor: area === a.key ? 'var(--ink)' : 'var(--line)',
                  color: area === a.key ? 'var(--ink)' : 'var(--ink-soft)',
                }}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: a.color }}
                />
                {a.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={save}
              className="h-10 flex-1 rounded-full text-sm font-medium text-white"
              style={{ background: 'var(--dawn)' }}
            >
              추가
            </button>
            <button
              type="button"
              onClick={() => setAdding(false)}
              className="h-10 rounded-full border border-line px-4 text-sm text-ink-soft"
            >
              취소
            </button>
          </div>
        </Card>
      ) : full ? (
        <p className="px-1 py-3 text-center text-sm text-ink-soft">
          목표가 많으면 전부 흐려져요. 올해는 5개까지.
        </p>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="w-full rounded-card border border-dashed border-line py-3 text-sm text-ink-soft"
        >
          + 올해의 목표 ({goals.length}/{MAX_YEARLY_GOALS})
        </button>
      )}
    </div>
  )
}

function MonthlyView() {
  const goals = useStore((s) => s.yearlyGoals)
  const monthly = useStore((s) => s.monthlyGoals)
  const addMonthly = useStore((s) => s.addMonthlyGoal)
  const toggle = useStore((s) => s.toggleMonthly)
  const month = new Date().getMonth() + 1

  const [drafts, setDrafts] = useState<Record<string, string>>({})

  if (goals.length === 0) {
    return (
      <p className="px-1 py-8 text-center text-sm text-ink-soft">
        먼저 연간 목표를 하나 세워보세요.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-soft">{month}월의 목표</p>
      {goals.map((g) => {
        const items = monthly.filter(
          (m) => m.yearlyGoalId === g.id && m.month === month,
        )
        const done = items.filter((m) => m.done).length
        const pct = items.length ? (done / items.length) * 100 : 0
        return (
          <Card key={g.id} className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: areaColor(g.area) }}
              />
              <h3 className="flex-1 text-base font-medium">{g.title}</h3>
            </div>
            <div className="mb-3 h-1 w-full overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full"
                style={{ width: `${pct}%`, background: 'var(--dawn)' }}
              />
            </div>
            {items.map((m) => (
              <div key={m.id} className="flex items-center gap-1 py-0.5">
                <Checkbox
                  checked={m.done}
                  onToggle={() => toggle(m.id)}
                  ariaLabel={`${m.title} 완료`}
                />
                <span
                  className={`text-sm ${
                    m.done ? 'text-ink-soft line-through' : ''
                  }`}
                >
                  {m.title}
                </span>
              </div>
            ))}
            <div className="mt-2 flex gap-2">
              <input
                value={drafts[g.id] ?? ''}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [g.id]: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (drafts[g.id] ?? '').trim()) {
                    addMonthly({
                      yearlyGoalId: g.id,
                      title: drafts[g.id].trim(),
                      month,
                    })
                    setDrafts((d) => ({ ...d, [g.id]: '' }))
                  }
                }}
                placeholder="이번 달 한 걸음"
                className="flex-1 rounded-lg border border-line bg-transparent px-3 py-1.5 text-sm outline-none"
              />
            </div>
          </Card>
        )
      })}
    </div>
  )
}
