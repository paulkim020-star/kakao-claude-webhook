export type Tab = 'today' | 'week' | 'plan' | 'constellation' | 'review'

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'today', label: '오늘', icon: '◇' },
  { key: 'week', label: '주간', icon: '▤' },
  { key: 'plan', label: '계획', icon: '◎' },
  { key: 'constellation', label: '별자리', icon: '✦' },
  { key: 'review', label: '회고', icon: '↩' },
]

export function TabBar({
  active,
  onChange,
}: {
  active: Tab
  onChange: (t: Tab) => void
}) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-paper-raised md:inset-y-0 md:left-0 md:right-auto md:w-[104px] md:flex-col md:justify-center md:gap-2 md:border-r md:border-t-0 md:pt-0"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {TABS.map((t) => {
        const on = active === t.key
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className="flex flex-1 flex-col items-center gap-1 py-2.5 md:flex-none md:py-3"
            style={{ color: on ? 'var(--dawn)' : 'var(--ink-soft)' }}
          >
            <span style={{ fontSize: 18, lineHeight: 1 }}>{t.icon}</span>
            <span style={{ fontSize: 11 }}>{t.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
