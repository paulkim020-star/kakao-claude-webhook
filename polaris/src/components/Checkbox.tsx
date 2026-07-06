import { useState } from 'react'

// §6.4 체크박스: 22px 원형 외곽선 → 체크 시 --dawn 채움 + 빛 입자(§4.2 시그니처 모션)
export function Checkbox({
  checked,
  onToggle,
  ariaLabel,
}: {
  checked: boolean
  onToggle: () => void
  ariaLabel: string
}) {
  const [bursts, setBursts] = useState<number[]>([])

  const handle = () => {
    if (!checked) {
      // 완료의 순간에만 빛 입자를 피운다
      const seed = Date.now()
      setBursts((b) => [...b, seed])
      window.setTimeout(
        () => setBursts((b) => b.filter((x) => x !== seed)),
        650,
      )
    }
    onToggle()
  }

  return (
    <button
      type="button"
      onClick={handle}
      aria-label={ariaLabel}
      aria-pressed={checked}
      className="relative grid h-11 w-11 shrink-0 place-items-center"
    >
      <span
        className="grid place-items-center rounded-full border transition-all duration-fast ease-out-dawn"
        style={{
          width: 22,
          height: 22,
          borderColor: checked ? 'var(--dawn)' : 'var(--ink-soft)',
          background: checked ? 'var(--dawn)' : 'transparent',
        }}
      >
        {checked && (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M2.5 6.2 5 8.7 9.6 3.6"
              stroke="var(--paper-raised)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>

      {/* 빛 입자: 위로 떠올라 사라진다 */}
      {bursts.map((seed) =>
        [0, 1, 2, 3].map((i) => (
          <span
            key={`${seed}-${i}`}
            className="light-particle pointer-events-none absolute rounded-full"
            style={{
              width: 5 - (i % 2),
              height: 5 - (i % 2),
              left: 18 + ((i * 7) % 12) - 6,
              top: 18,
              background: 'var(--dawn)',
              animationDelay: `${i * 55}ms`,
            }}
          />
        )),
      )}
    </button>
  )
}
