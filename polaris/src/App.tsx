import { useEffect, useState } from 'react'
import { useStore } from './store'
import { TabBar, type Tab } from './components/TabBar'
import { Onboarding } from './screens/Onboarding'
import { Today } from './screens/Today'
import { Week } from './screens/Week'
import { Plan } from './screens/Plan'
import { Constellation } from './screens/Constellation'
import { Review } from './screens/Review'

export default function App() {
  const onboarded = useStore((s) => s.onboarded)
  const runMaintenance = useStore((s) => s.runMaintenance)
  const [tab, setTab] = useState<Tab>('today')

  // 앱 진입 시 자정 유지보수 (반복 태스크 소멸/생성)
  useEffect(() => {
    runMaintenance()
  }, [runMaintenance])

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
      <TabBar active={tab} onChange={setTab} />
    </div>
  )
}
