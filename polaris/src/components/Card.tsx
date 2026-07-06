import type { ReactNode } from 'react'

// §6.4 카드: --paper-raised, radius 14px, 유일한 그림자.
export function Card({
  children,
  className = '',
  onClick,
}: {
  children: ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-card bg-paper-raised shadow-card ${className}`}
    >
      {children}
    </div>
  )
}

// §6.4 목표 점: 8px 원, 태스크 우측 끝.
export function GoalDot({ color }: { color: string | null }) {
  if (!color) return <span style={{ width: 8, height: 8 }} aria-hidden />
  return (
    <span
      className="inline-block rounded-full"
      style={{ width: 8, height: 8, background: color }}
      aria-label="연결된 목표"
    />
  )
}
