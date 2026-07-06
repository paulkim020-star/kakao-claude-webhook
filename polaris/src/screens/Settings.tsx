import { useRef, useState } from 'react'
import { useStore } from '../store'
import {
  notificationsSupported,
  requestNotificationPermission,
} from '../lib/reminders'
import { Card } from '../components/Card'

// 프로필/설정 — 알림(최소주의), 데이터 내보내기·가져오기, 초기화.
export function Settings({ onClose }: { onClose: () => void }) {
  const settings = useStore((s) => s.settings)
  const update = useStore((s) => s.updateSettings)
  const exportData = useStore((s) => s.exportData)
  const importData = useStore((s) => s.importData)
  const resetAll = useStore((s) => s.resetAll)
  const goals = useStore((s) => s.yearlyGoals)
  const tasks = useStore((s) => s.tasks)

  const fileRef = useRef<HTMLInputElement>(null)
  const [msg, setMsg] = useState('')
  const [confirmReset, setConfirmReset] = useState(false)

  const toggleReminder = async (
    key: 'morningReminder' | 'eveningReminder',
    value: boolean,
  ) => {
    if (value) {
      const ok = await requestNotificationPermission()
      if (!ok) {
        setMsg('브라우저 알림 권한이 필요해요.')
        return
      }
    }
    update({ [key]: value })
  }

  const doExport = () => {
    const json = exportData()
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `polaris-backup.json`
    a.click()
    URL.revokeObjectURL(url)
    setMsg('내보냈어요.')
  }

  const doImport = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const ok = importData(String(reader.result))
      setMsg(ok ? '가져왔어요.' : '파일을 읽지 못했어요.')
    }
    reader.readAsText(file)
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: 'var(--paper)' }}>
      <div className="mx-auto max-w-[440px] px-5 py-8">
        <button type="button" onClick={onClose} className="mb-4 text-sm text-ink-soft">
          ← 닫기
        </button>
        <h1 className="font-display text-2xl">프로필</h1>
        <p className="mt-1 text-sm text-ink-soft">
          목표 {goals.length}개 · 태스크 {tasks.length}개
        </p>

        {/* 알림 */}
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-medium">알림</h2>
          <Card className="divide-y divide-line">
            {!notificationsSupported() && (
              <p className="p-4 text-sm text-ink-soft">
                이 브라우저는 알림을 지원하지 않아요.
              </p>
            )}
            <ReminderRow
              label="아침 리추얼"
              on={settings.morningReminder}
              time={settings.morningTime}
              onToggle={(v) => toggleReminder('morningReminder', v)}
              onTime={(t) => update({ morningTime: t })}
            />
            <ReminderRow
              label="저녁 회고"
              on={settings.eveningReminder}
              time={settings.eveningTime}
              onToggle={(v) => toggleReminder('eveningReminder', v)}
              onTime={(t) => update({ eveningTime: t })}
            />
          </Card>
          <p className="mt-2 px-1 text-xs text-ink-soft">
            기본 알림은 0개예요. 하루 최대 2회만, 마케팅성 알림은 없어요.
            앱이 열려 있을 때 도착합니다.
          </p>
        </section>

        {/* 데이터 */}
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-medium">데이터</h2>
          <Card className="divide-y divide-line">
            <button
              type="button"
              onClick={doExport}
              className="flex w-full items-center justify-between p-4 text-left text-sm"
            >
              내보내기 <span className="text-ink-soft">JSON 백업 저장</span>
            </button>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex w-full items-center justify-between p-4 text-left text-sm"
            >
              가져오기 <span className="text-ink-soft">백업 불러오기</span>
            </button>
          </Card>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) doImport(f)
              e.target.value = ''
            }}
          />
        </section>

        {/* 초기화 */}
        <section className="mt-6">
          {confirmReset ? (
            <Card className="p-4">
              <p className="text-sm">모든 별과 기록이 사라져요. 정말 초기화할까요?</p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    resetAll()
                    onClose()
                  }}
                  className="h-10 flex-1 rounded-full text-sm font-medium text-white"
                  style={{ background: 'var(--area-relation)' }}
                >
                  초기화
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmReset(false)}
                  className="h-10 rounded-full border border-line px-4 text-sm text-ink-soft"
                >
                  취소
                </button>
              </div>
            </Card>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmReset(true)}
              className="w-full py-3 text-center text-sm text-ink-soft"
            >
              모든 데이터 초기화
            </button>
          )}
        </section>

        {msg && (
          <p className="mt-4 text-center text-sm" style={{ color: 'var(--dawn)' }}>
            {msg}
          </p>
        )}
      </div>
    </div>
  )
}

function ReminderRow({
  label,
  on,
  time,
  onToggle,
  onTime,
}: {
  label: string
  on: boolean
  time: string
  onToggle: (v: boolean) => void
  onTime: (t: string) => void
}) {
  return (
    <div className="flex items-center justify-between p-4">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-3">
        {on && (
          <input
            type="time"
            value={time}
            onChange={(e) => onTime(e.target.value)}
            className="font-num rounded-lg border border-line bg-transparent px-2 py-1 text-sm outline-none"
          />
        )}
        <Toggle on={on} onChange={onToggle} />
      </div>
    </div>
  )
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className="relative h-6 w-11 rounded-full transition-colors"
      style={{ background: on ? 'var(--dawn)' : 'var(--line)' }}
    >
      <span
        className="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform"
        style={{ left: 2, transform: on ? 'translateX(20px)' : 'translateX(0)' }}
      />
    </button>
  )
}
