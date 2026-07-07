import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { todayKey, displayDate } from '../lib/dates'
import { dailyLine, formatMinutes, priorityScore } from '../lib/meta'
import { Card } from '../components/Card'
import { ProgressRing } from '../components/ProgressRing'
import { TaskRow } from '../components/TaskRow'
import { QuickAdd } from '../components/QuickAdd'
import { MorningRitual } from '../components/MorningRitual'
import { CarryThriceCard } from '../components/CarryThriceCard'
import { InviteCards } from '../components/InviteCards'
import { Settings } from './Settings'
import { MilestoneEditor } from '../components/MilestoneEditor'
import { VisionEditor } from '../components/VisionEditor'

export function Today() {
  const tasks = useStore((s) => s.tasks)
  const [addOpen, setAddOpen] = useState(false)
  const [showAux, setShowAux] = useState(true) // 추가한 일이 묻히지 않게 기본 펼침
  const [modal, setModal] = useState<null | 'settings' | 'milestone' | 'vision'>(
    null,
  )
  const today = todayKey()

  const todays = useMemo(
    () =>
      tasks
        .filter((t) => t.date === today)
        .sort((a, b) => priorityScore(b, today) - priorityScore(a, today)),
    [tasks, today],
  )
  const core = todays.filter((t) => t.isCore)
  const aux = todays.filter((t) => !t.isCore)

  const plannedMin = todays
    .filter((t) => !t.done)
    .reduce((sum, t) => sum + t.duration, 0)
  const doneCount = todays.filter((t) => t.done).length
  const pct = todays.length ? (doneCount / todays.length) * 100 : 0

  // 3회 이월 규칙 대상 (오늘로 온 태스크 중)
  const thrice = todays.find((t) => t.carryCount >= 3 && !t.done)

  return (
    <div className="mx-auto max-w-[440px] px-5 pb-28 pt-3">
      {/* 헤더 */}
      <header className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl">{displayDate(today)}</h1>
          <p className="font-display mt-1 text-lg text-ink-soft">
            {dailyLine(today)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ProgressRing value={pct} size={40} showLabel />
          <button
            type="button"
            onClick={() => setModal('settings')}
            aria-label="프로필"
            className="grid h-10 w-10 place-items-center rounded-full border border-line text-ink-soft"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.6" />
              <path
                d="M5 19.5c0-3.3 3.1-5 7-5s7 1.7 7 5"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </header>

      <InviteCards
        onDrawMilestone={() => setModal('milestone')}
        onDrawVision={() => setModal('vision')}
      />
      <MorningRitual />
      {thrice && <CarryThriceCard task={thrice} />}

      {todays.length === 0 ? (
        <Card className="animate-fade-up mt-6 p-8 text-center">
          <p className="font-display text-lg text-ink">오늘은 아직 백지예요.</p>
          <p className="mt-1 text-sm text-ink-soft">한 줄이면 충분합니다.</p>
        </Card>
      ) : (
        <>
          {/* 오늘의 핵심 3 */}
          <section className="mb-6">
            <div className="mb-2 flex items-center gap-2">
              <span style={{ color: 'var(--dawn)' }}>◆</span>
              <h2 className="text-sm font-medium">오늘의 핵심 3</h2>
              <span className="font-num text-xs text-ink-soft">
                {core.length}/3
              </span>
            </div>
            {core.length === 0 ? (
              <Card className="p-4 text-sm text-ink-soft">
                태스크를 눌러 오늘 가장 중요한 3개를 골라보세요.
              </Card>
            ) : (
              <Card className="px-4 py-1">
                {core.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </Card>
            )}
          </section>

          {/* 보조 태스크 (접힘 기본) */}
          {aux.length > 0 && (
            <section className="mb-6">
              <button
                type="button"
                onClick={() => setShowAux((v) => !v)}
                className="mb-2 flex items-center gap-2 text-sm text-ink-soft"
              >
                <span>{showAux ? '▽' : '▷'}</span>
                보조 태스크 ({aux.length})
              </button>
              {showAux && (
                <Card className="animate-fade-up px-4 py-1">
                  {aux.map((t) => (
                    <TaskRow key={t.id} task={t} />
                  ))}
                </Card>
              )}
            </section>
          )}

        </>
      )}

      {/* 하단 고정: 오늘 계획된 시간 합계(상시 표시) + 빠른 추가 플로팅 */}
      <div className="fixed inset-x-0 bottom-[60px] z-30 flex flex-col items-center gap-2 px-5 md:left-[104px]">
        {todays.length > 0 && (
          <div className="text-center text-sm text-ink-soft">
            {plannedMin > 0 ? (
              <>
                오늘 계획된 시간{' '}
                <span className="font-num text-ink">
                  {formatMinutes(plannedMin)}
                </span>
              </>
            ) : (
              '오늘의 몫을 다 했어요. 나머지는 내일의 나에게.'
            )}
          </div>
        )}
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="rounded-full px-6 py-3 text-sm font-medium text-white shadow-card"
          style={{ background: 'var(--dawn)' }}
        >
          + 빠른 추가
        </button>
      </div>

      <QuickAdd open={addOpen} onClose={() => setAddOpen(false)} defaultDate={today} />

      {modal === 'settings' && <Settings onClose={() => setModal(null)} />}
      {modal === 'milestone' && <MilestoneEditor onClose={() => setModal(null)} />}
      {modal === 'vision' && <VisionEditor onClose={() => setModal(null)} />}
    </div>
  )
}
