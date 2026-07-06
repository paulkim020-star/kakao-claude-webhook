import { useEffect } from 'react'
import type { Settings } from '../store'

// §1.6 #7 알림 최소주의: 사용자가 켠 것만, 하루 최대 2회(아침 리추얼·저녁 회고).
// 브라우저가 열려 있을 때 로컬 알림을 띄운다(서버/푸시 없음 — 이 한계는 설정 화면에 명시).

export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!notificationsSupported()) return false
  if (Notification.permission === 'granted') return true
  if (Notification.permission === 'denied') return false
  const res = await Notification.requestPermission()
  return res === 'granted'
}

function msUntil(time: string): number {
  const [h, m] = time.split(':').map(Number)
  const now = new Date()
  const target = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    h,
    m,
    0,
    0,
  )
  return target.getTime() - now.getTime()
}

function fire(title: string, body: string) {
  if (!notificationsSupported() || Notification.permission !== 'granted') return
  new Notification(title, { body, tag: title, silent: false })
}

// 설정이 바뀔 때마다 오늘 남은 시각에 대해 타이머를 다시 건다.
export function useReminders(settings: Settings) {
  useEffect(() => {
    if (!notificationsSupported() || Notification.permission !== 'granted') return

    const timers: number[] = []
    const plan: { on: boolean; time: string; title: string; body: string }[] = [
      {
        on: settings.morningReminder,
        time: settings.morningTime,
        title: '아침 리추얼',
        body: '오늘의 빛을 어디로 향할까요?',
      },
      {
        on: settings.eveningReminder,
        time: settings.eveningTime,
        title: '저녁 회고',
        body: '오늘을 잠시 돌아볼 시간이에요.',
      },
    ]

    for (const p of plan) {
      if (!p.on) continue
      const delay = msUntil(p.time)
      if (delay > 0) {
        timers.push(window.setTimeout(() => fire(p.title, p.body), delay))
      }
    }

    return () => timers.forEach((t) => window.clearTimeout(t))
  }, [
    settings.morningReminder,
    settings.morningTime,
    settings.eveningReminder,
    settings.eveningTime,
  ])
}
