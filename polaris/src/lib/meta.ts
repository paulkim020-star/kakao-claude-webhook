import type { Area, Task, YearlyGoal } from '../types'

// 삶의 영역 6색 (§3, §6.2)
export const AREAS: { key: Area; label: string; color: string }[] = [
  { key: 'career', label: '일', color: 'var(--area-career)' },
  { key: 'health', label: '건강', color: 'var(--area-health)' },
  { key: 'relation', label: '관계', color: 'var(--area-relation)' },
  { key: 'money', label: '재정', color: 'var(--area-money)' },
  { key: 'growth', label: '성장', color: 'var(--area-growth)' },
  { key: 'life', label: '삶', color: 'var(--area-life)' },
]

export function areaColor(area: Area): string {
  return AREAS.find((a) => a.key === area)?.color ?? 'var(--ink-soft)'
}

export function goalColor(
  goalId: string | null,
  goals: YearlyGoal[],
): string | null {
  if (!goalId) return null
  const g = goals.find((x) => x.id === goalId)
  return g ? areaColor(g.area) : null
}

// 우선순위 자동 계산 (§3) — 사용자에게 우선순위를 매기라고 요구하지 않는다.
export function priorityScore(t: Task, today: string): number {
  let score = t.importance * 10
  if (t.yearlyGoalId) score += 8 // 목표 연결 가산점
  if (t.date === today) score += 6 // 오늘 마감
  if (t.carryCount > 0) score += 4 // 이월 태스크
  if (t.duration >= 240) score -= 3 // 반나절짜리는 살짝 뒤로 (분해 유도)
  return score
}

// 시간 칩 (§6.4)
export const DURATIONS: { value: Task['duration']; label: string }[] = [
  { value: 15, label: '15m' },
  { value: 30, label: '30m' },
  { value: 60, label: '1h' },
  { value: 240, label: '½일' },
]

export function durationLabel(d: Task['duration']): string {
  return DURATIONS.find((x) => x.value === d)?.label ?? `${d}m`
}

export function formatMinutes(total: number): string {
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h && m) return `${h}h ${m}m`
  if (h) return `${h}h`
  return `${m}m`
}

// 데일리 문장 (§7) — 시적이되 짧게. 날짜로 결정적 선택(랜덤 아님).
const DAILY_LINES = [
  '작은 반복이 방향이 된다',
  '오늘의 빛이 어디로 향하나요',
  '한 걸음의 무게를 믿어요',
  '멀리 가려면 오늘에 머물러요',
  '방향이 속도보다 앞선다',
  '조용히, 그러나 매일',
  '오늘 보탠 빛은 사라지지 않아요',
]

// 별 밝기 = 최근 활동량 (§1.6 누적 빛 모델, §4.5). streak 아님.
export function recentCompletions(
  tasks: Task[],
  goalId: string,
  days: number,
): number {
  const cutoff = Date.now() - days * 86400000
  return tasks.filter(
    (t) =>
      t.yearlyGoalId === goalId &&
      t.done &&
      t.completedAt &&
      new Date(t.completedAt).getTime() >= cutoff,
  ).length
}

export function daysSinceActivity(tasks: Task[], goalId: string): number {
  const times = tasks
    .filter((t) => t.yearlyGoalId === goalId && t.done && t.completedAt)
    .map((t) => new Date(t.completedAt as string).getTime())
  if (times.length === 0) return Infinity
  return Math.floor((Date.now() - Math.max(...times)) / 86400000)
}

export function dailyLine(dateKey: string): string {
  const n = dateKey
    .split('-')
    .reduce((acc, part) => acc + Number(part), 0)
  return DAILY_LINES[n % DAILY_LINES.length]
}
