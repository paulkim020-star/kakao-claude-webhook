import { useState } from 'react'
import { useStore } from '../store'
import { Checkbox } from './Checkbox'
import { Stars } from './Stars'
import { DurationPicker } from './TimeChip'
import { GoalDot } from './Card'
import { areaColor, durationLabel, goalColor } from '../lib/meta'
import { addDays } from '../lib/dates'
import type { Task } from '../types'

export function TaskRow({ task }: { task: Task }) {
  const goals = useStore((s) => s.yearlyGoals)
  const toggleDone = useStore((s) => s.toggleDone)
  const cycleImportance = useStore((s) => s.cycleImportance)
  const setDuration = useStore((s) => s.setDuration)
  const setGoal = useStore((s) => s.setGoal)
  const setDate = useStore((s) => s.setDate)
  const toggleCore = useStore((s) => s.toggleCore)
  const removeTask = useStore((s) => s.removeTask)

  const [open, setOpen] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  const dot = goalColor(task.yearlyGoalId, goals)

  const promote = () => {
    const ok = toggleCore(task.id)
    if (!ok) setNote('핵심은 3개까지예요. 하나와 바꿀까요?')
    else setNote(null)
  }

  return (
    <div className="border-b border-line last:border-b-0">
      <div className="flex items-center gap-1 py-1.5">
        <Checkbox
          checked={task.done}
          onToggle={() => toggleDone(task.id)}
          ariaLabel={`${task.title} 완료`}
        />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-center gap-2 py-2 text-left"
        >
          <Stars importance={task.importance} isCore={task.isCore} />
          <span
            className={`min-w-0 flex-1 truncate text-base ${
              task.done ? 'text-ink-soft line-through' : 'text-ink'
            }`}
          >
            {task.title}
          </span>
          <span className="font-num text-xs text-ink-soft">
            {durationLabel(task.duration)}
          </span>
          <GoalDot color={dot} />
        </button>
      </div>

      {open && (
        <div className="animate-fade-up pb-3 pl-11 pr-1">
          <div className="mb-3 flex items-center justify-between">
            <button
              type="button"
              onClick={promote}
              className="rounded-full border px-3 py-1.5 text-sm"
              style={{
                borderColor: task.isCore ? 'var(--dawn)' : 'var(--line)',
                color: task.isCore ? 'var(--dawn)' : 'var(--ink-soft)',
              }}
            >
              {task.isCore ? '핵심 3 ✓' : '핵심 3으로'}
            </button>
            <div className="flex items-center gap-3">
              <Stars
                importance={task.importance}
                isCore={task.isCore}
                onClick={() => cycleImportance(task.id)}
              />
            </div>
          </div>

          {note && (
            <div className="mb-3 text-xs" style={{ color: 'var(--dawn)' }}>
              {note}
            </div>
          )}

          <DurationPicker
            value={task.duration}
            onChange={(d) => setDuration(task.id, d)}
          />

          {goals.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <GoalChip
                active={task.yearlyGoalId === null}
                color={null}
                label="목표 없음"
                onClick={() => setGoal(task.id, null)}
              />
              {goals.map((g) => (
                <GoalChip
                  key={g.id}
                  active={task.yearlyGoalId === g.id}
                  color={areaColor(g.area)}
                  label={g.title}
                  onClick={() => setGoal(task.id, g.id)}
                />
              ))}
            </div>
          )}

          <div className="mt-3 flex gap-4 text-sm text-ink-soft">
            <button
              type="button"
              onClick={() => setDate(task.id, addDays(task.date ?? '', 1))}
              disabled={!task.date}
              className="disabled:opacity-30"
            >
              내일로 옮기기
            </button>
            <button type="button" onClick={() => setDate(task.id, null)}>
              인박스로
            </button>
            <button type="button" onClick={() => removeTask(task.id)}>
              놓아주기
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function GoalChip({
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
      className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
      style={{
        borderColor: active ? 'var(--ink)' : 'var(--line)',
        color: active ? 'var(--ink)' : 'var(--ink-soft)',
      }}
    >
      <span
        className="inline-block rounded-full"
        style={{
          width: 7,
          height: 7,
          background: color ?? 'transparent',
          border: color ? 'none' : '1px solid var(--line)',
        }}
      />
      <span className="max-w-[110px] truncate">{label}</span>
    </button>
  )
}
