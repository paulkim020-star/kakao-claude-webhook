import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { addDays, todayKey, weekdayIndex } from '../lib/dates'
import { areaColor, formatMinutes } from '../lib/meta'
import { Card } from '../components/Card'
import type { DailyReview } from '../types'

const MOODS = ['😔', '🙁', '😐', '🙂', '😊']

export function Review() {
  const tasks = useStore((s) => s.tasks)
  const goals = useStore((s) => s.yearlyGoals)
  const reviews = useStore((s) => s.reviews)
  const saveReview = useStore((s) => s.saveReview)
  const today = todayKey()

  const existing = reviews.find((r) => r.date === today)
  const [mood, setMood] = useState<DailyReview['mood']>(existing?.mood ?? 3)
  const [note, setNote] = useState(existing?.note ?? '')
  const [saved, setSaved] = useState(false)

  const todays = tasks.filter((t) => t.date === today)
  const doneToday = todays.filter((t) => t.done)

  // 이번 주 범위
  const monday = addDays(today, -((weekdayIndex(today) + 6) % 7))
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(monday, i)),
    [monday],
  )
  const weekTasks = tasks.filter((t) => t.date && weekDays.includes(t.date))
  const weekDone = weekTasks.filter((t) => t.done)

  // 3개 지표 (순서 고정: 목표 연결 비율 → 계획 대비 실행 → 완료 수)
  const linkedRatio = weekDone.length
    ? Math.round(
        (weekDone.filter((t) => t.yearlyGoalId).length / weekDone.length) * 100,
      )
    : 0
  const plannedMin = weekTasks.reduce((s, t) => s + t.duration, 0)
  const doneMin = weekDone.reduce((s, t) => s + t.duration, 0)

  // 목표별 완료 분포 (도넛)
  const dist = useMemo(() => {
    const byArea = new Map<string, number>()
    for (const t of weekDone) {
      const g = goals.find((x) => x.id === t.yearlyGoalId)
      const key = g ? g.area : 'life-routine'
      byArea.set(key, (byArea.get(key) ?? 0) + 1)
    }
    return [...byArea.entries()].map(([key, count]) => ({
      key,
      count,
      color: key === 'life-routine' ? 'var(--line)' : areaColor(key as never),
    }))
  }, [weekDone, goals])

  const save = () => {
    saveReview({
      date: today,
      mood,
      note: note.trim(),
      carriedOver: [],
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 1600)
  }

  return (
    <div className="mx-auto max-w-[440px] px-5 pb-28 pt-3">
      <header className="mb-4">
        <h1 className="font-display text-2xl">회고</h1>
      </header>

      {/* 저녁 회고 */}
      <Card className="mb-6 p-5">
        <p className="font-display text-lg">
          오늘 {doneToday.length}개의 빛을 보탰어요.
        </p>
        <p className="mt-1 text-sm text-ink-soft">
          {doneToday.length === 0
            ? '적게 한 날도 기록할 가치가 있어요.'
            : '오늘의 몫을 돌아봐요.'}
        </p>

        <div className="mt-4 flex justify-between">
          {MOODS.map((m, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setMood((i + 1) as DailyReview['mood'])}
              className="grid h-11 w-11 place-items-center rounded-full text-2xl transition-transform"
              style={{
                transform: mood === i + 1 ? 'scale(1.15)' : 'scale(1)',
                opacity: mood === i + 1 ? 1 : 0.4,
              }}
            >
              {m}
            </button>
          ))}
        </div>

        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="한 줄 회고"
          className="mt-4 w-full rounded-card border border-line bg-transparent px-4 py-3 text-base outline-none"
        />
        <button
          type="button"
          onClick={save}
          className="mt-3 h-11 w-full rounded-full text-sm font-medium text-white"
          style={{ background: 'var(--dawn)' }}
        >
          {saved ? '기록했어요' : '오늘을 기록하기'}
        </button>
      </Card>

      {/* 주간 회고 — 지표 3개, 대시보드화 금지 */}
      <p className="mb-2 text-sm text-ink-soft">이번 주</p>
      <div className="grid grid-cols-3 gap-3">
        <Metric label="목표 연결" value={`${linkedRatio}%`} />
        <Metric
          label="계획 대비 실행"
          value={
            plannedMin ? `${Math.round((doneMin / plannedMin) * 100)}%` : '—'
          }
          sub={`${formatMinutes(doneMin)}`}
        />
        <Metric label="완료" value={`${weekDone.length}`} />
      </div>

      {/* 완료 분포 도넛 */}
      <Card className="mt-4 p-5">
        <p className="mb-3 text-sm text-ink-soft">완료한 일의 방향</p>
        {weekDone.length === 0 ? (
          <p className="text-sm text-ink-soft">
            이번 주는 아직 조용해요. 한 걸음이면 시작돼요.
          </p>
        ) : (
          <Donut segments={dist} total={weekDone.length} />
        )}
      </Card>
    </div>
  )
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <Card className="p-3 text-center">
      <div className="font-num text-xl text-ink">{value}</div>
      {sub && <div className="font-num text-[10px] text-ink-soft">{sub}</div>}
      <div className="mt-1 text-xs text-ink-soft">{label}</div>
    </Card>
  )
}

function Donut({
  segments,
  total,
}: {
  segments: { key: string; count: number; color: string }[]
  total: number
}) {
  const size = 120
  const stroke = 14
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  let acc = 0

  return (
    <div className="flex items-center gap-5">
      <svg width={size} height={size} className="-rotate-90 shrink-0">
        {segments.map((s) => {
          const frac = s.count / total
          const dash = c * frac
          const el = (
            <circle
              key={s.key}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-acc}
            />
          )
          acc += dash
          return el
        })}
      </svg>
      <div className="space-y-1">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-2 text-sm">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: s.color }}
            />
            <span className="text-ink-soft">
              {s.key === 'life-routine' ? '일상 유지' : areaLabel(s.key)}
            </span>
            <span className="font-num text-xs text-ink-soft">{s.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function areaLabel(area: string): string {
  const map: Record<string, string> = {
    career: '일',
    health: '건강',
    relation: '관계',
    money: '재정',
    growth: '성장',
    life: '삶',
  }
  return map[area] ?? area
}
