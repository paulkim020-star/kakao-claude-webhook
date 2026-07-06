// §6.4 중요도: 별 ★ 1~3개, 탭 순환. 별 색은 --ink-soft, 핵심3에 오르면 --dawn.
export function Stars({
  importance,
  isCore,
  onClick,
}: {
  importance: 1 | 2 | 3
  isCore?: boolean
  onClick?: () => void
}) {
  const color = isCore ? 'var(--dawn)' : 'var(--ink-soft)'
  const content = (
    <span
      className="inline-flex select-none tracking-tight"
      style={{ color, fontSize: 13 }}
      aria-label={`중요도 ${importance}`}
    >
      {[1, 2, 3].map((n) => (
        <span key={n} style={{ opacity: n <= importance ? 1 : 0.22 }}>
          ★
        </span>
      ))}
    </span>
  )

  if (!onClick) return content
  return (
    <button
      type="button"
      onClick={onClick}
      className="grid h-11 place-items-center px-1"
      aria-label="중요도 변경"
    >
      {content}
    </button>
  )
}
