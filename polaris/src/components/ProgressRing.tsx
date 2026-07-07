// §6.4 진행 링: 1.5px 스트로크, --dawn. 두껍게 만들지 말 것.
export function ProgressRing({
  value,
  size = 40,
  stroke = 1.5,
  showLabel = false,
}: {
  value: number // 0–100
  size?: number
  stroke?: number
  showLabel?: boolean
}) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const clamped = Math.max(0, Math.min(100, value))
  const offset = c * (1 - clamped / 100)

  return (
    <div
      className="relative grid place-items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--line)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--dawn)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset var(--dur-base) var(--ease-out)' }}
        />
      </svg>
      {showLabel && (
        <span
          className="absolute font-num"
          style={{ fontSize: size < 44 ? 10 : 12, color: 'var(--ink-soft)' }}
        >
          {Math.round(clamped)}
        </span>
      )}
    </div>
  )
}
