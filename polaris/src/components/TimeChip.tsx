import { DURATIONS } from '../lib/meta'
import type { Task } from '../types'

// §6.4 시간 칩: 모노 서체, 28px 높이 필 형태, 15m / 30m / 1h / ½일
export function TimeChip({
  value,
  active,
  onClick,
  label,
}: {
  value?: Task['duration']
  active?: boolean
  onClick?: () => void
  label?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border font-num transition-colors duration-fast ease-out-dawn"
      style={{
        height: 28,
        padding: '0 12px',
        fontSize: 12,
        borderColor: active ? 'var(--dawn)' : 'var(--line)',
        background: active ? 'var(--dawn-soft)' : 'transparent',
        color: active ? 'var(--ink)' : 'var(--ink-soft)',
      }}
    >
      {label ?? DURATIONS.find((d) => d.value === value)?.label}
    </button>
  )
}

export function DurationPicker({
  value,
  onChange,
}: {
  value: Task['duration']
  onChange: (d: Task['duration']) => void
}) {
  return (
    <div className="flex gap-1.5">
      {DURATIONS.map((d) => (
        <TimeChip
          key={d.value}
          value={d.value}
          active={value === d.value}
          onClick={() => onChange(d.value)}
        />
      ))}
    </div>
  )
}
