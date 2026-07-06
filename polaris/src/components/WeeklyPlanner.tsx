import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { addDays, todayKey, weekdayIndex } from '../lib/dates'
import { areaColor } from '../lib/meta'

const DOW = ['월', '화', '수', '목', '금', '토', '일']

// §4.3 주간 계획 가이드: ① 인박스 살펴보기 → ② 미완료 정리 → ③ 초점 → ④ 요일 배분.
export function WeeklyPlanner({ onClose }: { onClose: () => void }) {
  const tasks = useStore((s) => s.tasks)
  const goals = useStore((s) => s.yearlyGoals)
  const weeklyFocus = useStore((s) => s.weeklyFocus)
  const setDate = useStore((s) => s.setDate)
  const carry = useStore((s) => s.carryToToday)
  const remove = useStore((s) => s.removeTask)
  const toggleFocus = useStore((s) => s.toggleWeeklyFocus)

  const [step, setStep] = useState(0)

  const today = todayKey()
  const nextMonday = useMemo(
    () => addDays(today, -((weekdayIndex(today) + 6) % 7) + 7),
    [today],
  )
  const nextWeekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(nextMonday, i)),
    [nextMonday],
  )

  const inbox = tasks.filter((t) => t.date === null && !t.done)
  const leftovers = tasks.filter(
    (t) => !t.done && t.recurring === 'none' && t.date !== null && t.date < today,
  )
  const focus = weeklyFocus[nextMonday] ?? []

  const steps = ['인박스 살펴보기', '미완료 정리', '이번 주의 초점', '다음 주 채우기']

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: 'var(--paper)' }}>
      <div className="mx-auto max-w-[440px] px-5 py-8">
        <button type="button" onClick={onClose} className="mb-4 text-sm text-ink-soft">
          ← 닫기
        </button>

        {/* 진행 점 */}
        <div className="mb-6 flex items-center gap-2">
          {steps.map((_, i) => (
            <div
              key={i}
              className="h-1 flex-1 rounded-full"
              style={{ background: i <= step ? 'var(--dawn)' : 'var(--line)' }}
            />
          ))}
        </div>

        <h1 className="font-display text-xl">{steps[step]}</h1>

        {/* ① 인박스 */}
        {step === 0 && (
          <div className="mt-4">
            <p className="text-sm text-ink-soft">
              언젠가 적어둔 것 중 다음 주로 올릴 것을 골라보세요.
            </p>
            {inbox.length === 0 ? (
              <p className="mt-6 text-sm text-ink-soft">인박스가 비어 있어요.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {inbox.map((t) => (
                  <div key={t.id} className="rounded-card border border-line p-3">
                    <p className="mb-2 text-sm">{t.title}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {nextWeekDays.map((d, i) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setDate(t.id, d)}
                          className="rounded-full border border-line px-2.5 py-1 text-xs text-ink-soft"
                        >
                          {DOW[i]}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ② 미완료 정리 */}
        {step === 1 && (
          <div className="mt-4">
            <p className="text-sm text-ink-soft">
              지난 주에 남은 일들이에요. 가져올까요, 놓아줄까요?
            </p>
            {leftovers.length === 0 ? (
              <p className="mt-6 text-sm text-ink-soft">깔끔해요. 남은 일이 없어요.</p>
            ) : (
              <div className="mt-4 space-y-2">
                {leftovers.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center gap-2 rounded-card border border-line p-3"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm">{t.title}</span>
                    <button
                      type="button"
                      onClick={() => carry(t.id)}
                      className="rounded-full px-3 py-1 text-xs font-medium text-white"
                      style={{ background: 'var(--dawn)' }}
                    >
                      가져오기
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(t.id)}
                      className="rounded-full border border-line px-3 py-1 text-xs text-ink-soft"
                    >
                      놓아주기
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ③ 초점 */}
        {step === 2 && (
          <div className="mt-4">
            <p className="text-sm text-ink-soft">
              다음 주에 진전시킬 목표를 1~2개만 골라요.
            </p>
            {goals.length === 0 ? (
              <p className="mt-6 text-sm text-ink-soft">
                아직 연간 목표가 없어요. 계획 탭에서 하나 세워보세요.
              </p>
            ) : (
              <div className="mt-4 flex flex-wrap gap-2">
                {goals.map((g) => {
                  const on = focus.includes(g.id)
                  return (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => toggleFocus(nextMonday, g.id)}
                      className="flex items-center gap-1.5 rounded-full border px-3 py-2 text-sm"
                      style={{
                        borderColor: on ? areaColor(g.area) : 'var(--line)',
                        color: on ? 'var(--ink)' : 'var(--ink-soft)',
                      }}
                    >
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ background: areaColor(g.area) }}
                      />
                      {g.title}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ④ 마무리 */}
        {step === 3 && (
          <div className="mt-4">
            <p className="text-sm text-ink-soft">
              다음 주 준비가 됐어요. 요일별 배분은 주간 화면에서 옮기며 마저 할 수 있어요.
            </p>
            <div className="mt-6 space-y-1.5">
              {nextWeekDays.map((d, i) => {
                const c = tasks.filter((t) => t.date === d).length
                return (
                  <div key={d} className="flex items-center gap-3 text-sm">
                    <span className="w-8 text-ink-soft">{DOW[i]}</span>
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-line">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, c * 25)}%`,
                          background: 'var(--dawn)',
                        }}
                      />
                    </div>
                    <span className="font-num w-5 text-right text-xs text-ink-soft">
                      {c}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* 내비 */}
        <div className="mt-8 flex gap-2">
          {step > 0 && (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="h-11 rounded-full border border-line px-5 text-sm text-ink-soft"
            >
              이전
            </button>
          )}
          <button
            type="button"
            onClick={() => (step < 3 ? setStep((s) => s + 1) : onClose())}
            className="h-11 flex-1 rounded-full text-sm font-medium text-white"
            style={{ background: 'var(--dawn)' }}
          >
            {step < 3 ? '다음' : '마쳤어요'}
          </button>
        </div>
      </div>
    </div>
  )
}
