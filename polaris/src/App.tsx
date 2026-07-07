import { useEffect, useState } from 'react'
import { useStore } from './store'
import { useReminders } from './lib/reminders'
import { todayKey } from './lib/dates'
import { TabBar, type Tab } from './components/TabBar'
import { QuickAdd } from './components/QuickAdd'
import { Onboarding } from './screens/Onboarding'
import { Today } from './screens/Today'
import { Week } from './screens/Week'
import { Plan } from './screens/Plan'
import { Constellation } from './screens/Constellation'
import { Review } from './screens/Review'

export default function App() {
  const onboarded = useStore((s) => s.onboarded)
  const runMaintenance = useStore((s) => s.runMaintenance)
  const settings = useStore((s) => s.settings)
  const [tab, setTab] = useState<Tab>('today')
  const [quickOpen, setQuickOpen] = useState(false)

  // 앱 진입 시 자정 유지보수 (반복 태스크 소멸/생성)
  useEffect(() => {
    runMaintenance()
  }, [runMaintenance])

  // 사용자가 켠 알림만 스케줄 (§1.6 #7)
  useReminders(settings)

  if (!onboarded) return <Onboarding />

  return (
    <div className="min-h-full md:pl-[104px]">
      <main key={tab} className="animate-fade-up min-h-full">
        {tab === 'today' && <Today />}
        {tab === 'week' && <Week />}
        {tab === 'plan' && <Plan />}
        {tab === 'constellation' && <Constellation />}
        {tab === 'review' && <Review />}
      </main>

      {/* 어느 화면에서나 '오늘'로 바로 추가 (긴급한 일 즉시 캡처) */}
      {tab !== 'today' && (
        <button
          type="button"
          onClick={() => setQuickOpen(true)}
          aria-label="빠른 추가"
          className="fixed bottom-[74px] right-5 z-40 grid h-14 w-14 place-items-center rounded-full text-white shadow-card"
          style={{ background: 'var(--dawn)', fontSize: 26, lineHeight: 1 }}
        >
          +
        </button>
      )}
      <QuickAdd
        open={quickOpen}
        onClose={() => setQuickOpen(false)}
        defaultDate={todayKey()}
      />

      <TabBar active={tab} onChange={setTab} />
    </div>
  )
}
