import { useEffect, useMemo, useRef, useState } from 'react'
import { useStore } from '../store'
import { parseQuickAdd, todayKey, displayDate } from '../lib/dates'
import { areaColor } from '../lib/meta'
import { Stars } from './Stars'
import { DurationPicker } from './TimeChip'
import type { Task } from '../types'

// §4.2 빠른 추가: 텍스트 → 별 → 시간 칩 → 목표 점(선택). 3초 목표.
// 날짜를 정하지 않으면 인박스로. (§3 규칙 2)
export function QuickAdd({
  open,
  onClose,
  defaultDate,
}: {
  open: boolean
  onClose: () => void
  defaultDate: string | null
}) {
  const goals = useStore((s) => s.yearlyGoals)
  const addTask = useStore((s) => s.addTask)

  const [raw, setRaw] = useState('')
  const [importance, setImportance] = useState<1 | 2 | 3>(1)
  const [duration, setDuration] = useState<Task['duration']>(30)
  const [goalId, setGoalId] = useState<string | null>(null)
  // 파싱으로 잡힌 날짜를 사용자가 지운 경우를 추적
  const [dateOverride, setDateOverride] = useState<string | null | undefined>(
    undefined,
  )
  const inputRef = useRef<HTMLInputElement>(null)

  const parsed = useMemo(() => parseQuickAdd(raw, todayKey()), [raw])
  const effectiveDate =
    dateOverride !== undefined ? dateOverride : parsed.date ?? defaultDate

  useEffect(() => {
    if (open) {
      setRaw('')
      setImportance(1)
      setDuration(30)
      setGoalId(null)
      setDateOverride(undefined)
      setTimeout(() => inputRef.current?.focus(), 60)
    }
  }, [open])

  if (!open) return null

  const submit = () => {
    const title = parsed.title.trim()
    if (!title) return
    addTask({ title, date: effectiveDate, importance, duration, yearlyGoalId: goalId })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end" role="dialog" aria-modal="true">
      <div
        className="absolute inset-0"
        style={{ background: 'rgba(28,39,51,.28)' }}
        onClick={onClose}
      />
      <div
        className="animate-fade-up relative w-full rounded-t-[20px] bg-paper-raised px-5 pb-6 pt-4"
        style={{ boxShadow: '0 -2px 16px rgba(28,39,51,.10)' }}
      >
        <div
          className="mx-auto mb-4 h-1 w-9 rounded-full"
          style={{ background: 'var(--line)' }}
        />

        <input
          ref={inputRef}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="한 줄이면 충분합니다"
          className="w-full bg-transparent text-lg outline-none placeholder:text-ink-soft"
        />

        {/* 파싱 결과 칩 — 항상 표시, 한 탭에 수정(제거) 가능 (§4.2 불만 #5) */}
        <div className="mt-3 flex min-h-[28px] flex-wrap items-center gap-2">
          {effectiveDate ? (
            <button
              type="button"
              onClick={() => setDateOverride(null)}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink-soft"
            >
              {effectiveDate === todayKey()
                ? '오늘'
                : displayDate(effectiveDate)}{' '}
              ✕
            </button>
          ) : (
            <span className="text-xs text-ink-soft">
              날짜 없음 · 인박스에 보관돼요
            </span>
          )}
        </div>

        {/* 별 · 시간 칩 */}
        <div className="mt-4 flex items-center justify-between">
          <Stars
            importance={importance}
            onClick={() => setImportance(((importance % 3) + 1) as 1 | 2 | 3)}
          />
          <DurationPicker value={duration} onChange={setDuration} />
        </div>

        {/* 목표 색 점(선택) */}
        {goals.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 text-xs text-ink-soft">
              어떤 목표에 빛을 보탤까요?
            </div>
            <div className="flex flex-wrap gap-2">
              <GoalPick
                active={goalId === null}
                color={null}
                label="없음"
                onClick={() => setGoalId(null)}
              />
              {goals.map((g) => (
                <GoalPick
                  key={g.id}
                  active={goalId === g.id}
                  color={areaColor(g.area)}
                  label={g.title}
                  onClick={() => setGoalId(g.id)}
                />
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={submit}
          disabled={!parsed.title.trim()}
          className="mt-5 h-12 w-full rounded-full text-base font-medium transition-opacity disabled:opacity-30"
          style={{ background: 'var(--dawn)', color: '#fff' }}
        >
          추가
        </button>
      </div>
    </div>
  )
}

function GoalPick({
  active,
  color,
  label,
  onClick,
}: {
  active: boolean
  color: string | null
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm"
      style={{
        borderColor: active ? 'var(--ink)' : 'var(--line)',
        color: active ? 'var(--ink)' : 'var(--ink-soft)',
      }}
    >
      <span
        className="inline-block rounded-full"
        style={{
          width: 8,
          height: 8,
          background: color ?? 'transparent',
          border: color ? 'none' : '1px solid var(--line)',
        }}
      />
      <span className="max-w-[120px] truncate">{label}</span>
    </button>
  )
}
