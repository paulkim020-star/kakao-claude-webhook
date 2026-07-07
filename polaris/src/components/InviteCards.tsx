import { useStore } from '../store'
import { daysBetween, todayKey } from '../lib/dates'
import { Card } from './Card'

// §4.1 3일차/7일차 부드러운 초대 + §4.6 분기 리마인드.
// 강제하지 않고, 죄책감 없이 미룰 수 있게.
export function InviteCards({
  onDrawMilestone,
  onDrawVision,
}: {
  onDrawMilestone: () => void
  onDrawVision: () => void
}) {
  const startedAt = useStore((s) => s.startedAt)
  const vision = useStore((s) => s.vision)
  const milestones = useStore((s) => s.milestones)
  const goals = useStore((s) => s.yearlyGoals)
  const dismissed = useStore((s) => s.invitesDismissed)
  const dismiss = useStore((s) => s.dismissInvite)

  const today = todayKey()
  const sinceStart = startedAt ? daysBetween(startedAt, today) : 0

  // 7일차: 북극성 초대 (아직 비전 없음)
  if (sinceStart >= 7 && !vision && !dismissed.vision) {
    return (
      <Invite
        title="이제 북극성을 그려볼 시간이에요."
        body="10년 뒤의 하루를 상상해서 편지처럼 써보세요."
        cta="북극성 그리기"
        onCta={onDrawVision}
        onLater={() => dismiss('vision')}
      />
    )
  }

  // 3일차: 5년 이정표 초대 (연간 목표는 있고 이정표는 없음)
  if (
    sinceStart >= 3 &&
    goals.length > 0 &&
    milestones.length === 0 &&
    !dismissed.milestone
  ) {
    return (
      <Invite
        title="연간 목표에 이름을 붙였네요."
        body="5년 뒤 이 목표는 어떤 모습일까요?"
        cta="5년 뒤 그려보기"
        onCta={onDrawMilestone}
        onLater={() => dismiss('milestone')}
      />
    )
  }

  // 분기 리마인드: 비전을 90일 넘게 안 봤을 때
  if (vision) {
    const sinceVision = daysBetween(vision.updatedAt.slice(0, 10), today)
    const snoozed = dismissed.visionRefresh === today
    if (sinceVision >= 90 && !snoozed) {
      return (
        <Invite
          title="북극성을 다시 볼 시간이에요."
          body="북극성도 자랍니다. 지금의 나로 다시 써볼까요?"
          cta="다시 쓰기"
          onCta={onDrawVision}
          onLater={() => dismiss('visionRefresh', today)}
        />
      )
    }
  }

  return null
}

function Invite({
  title,
  body,
  cta,
  onCta,
  onLater,
}: {
  title: string
  body: string
  cta: string
  onCta: () => void
  onLater: () => void
}) {
  return (
    <Card className="animate-fade-up mb-6 p-5">
      <p className="font-display text-lg">{title}</p>
      <p className="mt-1 text-sm text-ink-soft">{body}</p>
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={onCta}
          className="rounded-full px-4 py-2 text-sm font-medium text-white"
          style={{ background: 'var(--dawn)' }}
        >
          {cta}
        </button>
        <button
          type="button"
          onClick={onLater}
          className="text-sm text-ink-soft"
        >
          나중에
        </button>
      </div>
    </Card>
  )
}
