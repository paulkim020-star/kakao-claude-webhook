import { useState } from 'react'
import { useStore } from '../store'
import { todayKey } from '../lib/dates'
import { AREAS } from '../lib/meta'
import type { Area } from '../types'

// §4.1 역방향 온보딩 — 총 60초 이내. 5년/10년은 나중에 초대.
export function Onboarding() {
  const addTask = useStore((s) => s.addTask)
  const addYearlyGoal = useStore((s) => s.addYearlyGoal)
  const setGoal = useStore((s) => s.setGoal)
  const complete = useStore((s) => s.completeOnboarding)

  const [step, setStep] = useState(0)
  const [items, setItems] = useState(['', '', ''])
  const [area, setArea] = useState<Area>('growth')
  const [goalTitle, setGoalTitle] = useState('')

  const filled = items.map((x) => x.trim()).filter(Boolean)

  const finish = (connect: boolean) => {
    const ids = filled.map((title) => addTask({ title, date: todayKey() }))
    if (connect && goalTitle.trim()) {
      const gid = addYearlyGoal({
        title: goalTitle.trim(),
        milestoneId: null,
        area,
        measure: '',
      })
      if (gid && ids[0]) setGoal(ids[0], gid)
    }
    complete()
  }

  return (
    <div className="mx-auto flex min-h-full max-w-[440px] flex-col justify-center px-6 py-10">
      {step === 0 && (
        <div className="animate-fade-up text-center">
          <div
            className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-full"
            style={{ background: 'var(--dawn-soft)' }}
          >
            <span style={{ color: 'var(--dawn)', fontSize: 28 }}>✦</span>
          </div>
          <h1 className="font-display text-2xl">POLARIS</h1>
          <p className="font-display mt-4 text-lg leading-relaxed text-ink-soft">
            오늘부터 시작해요.
            <br />큰 그림은 나중에 그려도 됩니다.
          </p>
          <button
            type="button"
            onClick={() => setStep(1)}
            className="mt-10 h-12 w-full rounded-full text-base font-medium text-white"
            style={{ background: 'var(--dawn)' }}
          >
            시작하기
          </button>
        </div>
      )}

      {step === 1 && (
        <div className="animate-fade-up">
          <h2 className="font-display text-xl">오늘 할 일 3가지만 적어볼까요?</h2>
          <p className="mt-2 text-sm text-ink-soft">
            떠오르는 대로. 나중에 얼마든지 바꿀 수 있어요.
          </p>
          <div className="mt-6 space-y-3">
            {items.map((v, i) => (
              <input
                key={i}
                value={v}
                onChange={(e) =>
                  setItems((arr) =>
                    arr.map((x, j) => (j === i ? e.target.value : x)),
                  )
                }
                placeholder={`할 일 ${i + 1}`}
                className="w-full rounded-card border border-line bg-paper-raised px-4 py-3 text-base outline-none"
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => setStep(2)}
            className="mt-8 h-12 w-full rounded-full text-base font-medium text-white"
            style={{ background: 'var(--dawn)' }}
          >
            다음
          </button>
          <button
            type="button"
            onClick={() => finish(false)}
            className="mt-3 w-full py-2 text-sm text-ink-soft"
          >
            건너뛰기
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="animate-fade-up">
          {filled.length > 0 ? (
            <>
              <h2 className="font-display text-xl">
                「{filled[0]}」
              </h2>
              <p className="font-display mt-2 text-lg text-ink-soft">
                이 일은 더 큰 무언가로 이어지나요?
              </p>

              <div className="mt-6">
                <input
                  value={goalTitle}
                  onChange={(e) => setGoalTitle(e.target.value)}
                  placeholder="예: 출간 작가가 되기"
                  className="w-full rounded-card border border-line bg-paper-raised px-4 py-3 text-base outline-none"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {AREAS.map((a) => (
                    <button
                      key={a.key}
                      type="button"
                      onClick={() => setArea(a.key)}
                      className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm"
                      style={{
                        borderColor:
                          area === a.key ? 'var(--ink)' : 'var(--line)',
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
              </div>

              <button
                type="button"
                onClick={() => finish(true)}
                disabled={!goalTitle.trim()}
                className="mt-8 h-12 w-full rounded-full text-base font-medium text-white disabled:opacity-30"
                style={{ background: 'var(--dawn)' }}
              >
                예, 연결할게요
              </button>
              <button
                type="button"
                onClick={() => finish(false)}
                className="mt-3 w-full py-2 text-sm text-ink-soft"
              >
                아니오, 그냥 시작할게요
              </button>
            </>
          ) : (
            <>
              <h2 className="font-display text-xl">좋아요, 오늘부터예요.</h2>
              <p className="mt-2 text-sm text-ink-soft">
                할 일은 언제든 추가할 수 있어요.
              </p>
              <button
                type="button"
                onClick={() => finish(false)}
                className="mt-8 h-12 w-full rounded-full text-base font-medium text-white"
                style={{ background: 'var(--dawn)' }}
              >
                시작하기
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
