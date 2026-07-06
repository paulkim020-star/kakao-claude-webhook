// §3 데이터 모델

export type Horizon =
  | 'vision10'
  | 'milestone5'
  | 'yearly'
  | 'monthly'
  | 'weekly'
  | 'daily'

export type Area =
  | 'career'
  | 'health'
  | 'relation'
  | 'money'
  | 'growth'
  | 'life'

export interface Vision10 {
  id: string
  narrative: string // 자유 서술 1~3문단: "10년 뒤 나는 어떤 사람인가"
  keywords: string[] // 최대 5개 키워드 (별자리에서 별 이름으로 표시)
  updatedAt: string
  revisions: { date: string; narrative: string }[] // "북극성도 자란다"
}

export interface Milestone5 {
  id: string
  title: string
  visionKeyword: string
  targetYear: number
}

export interface YearlyGoal {
  id: string
  title: string
  milestoneId: string | null
  area: Area
  measure: string // "무엇이 되면 달성인가" 한 줄
  progress: number // 0–100, 월간 목표 완료로 자동 계산
}

export interface MonthlyGoal {
  id: string
  yearlyGoalId: string
  title: string
  month: number // 1–12
  done: boolean
}

export interface Task {
  id: string
  title: string
  date: string | null // null = 인박스(미배정)
  yearlyGoalId: string | null // ★ 핵심 필드: 목표 연결. null이면 '일상 유지'
  importance: 1 | 2 | 3
  duration: 15 | 30 | 60 | 240 // 분 단위 4개 칩
  isCore: boolean // 오늘의 핵심 3 여부
  recurring: 'none' | 'daily' | 'weekdays' | 'weekly'
  carryCount: number // 이월 횟수 (3회 규칙)
  done: boolean
  completedAt: string | null
}

export interface DailyReview {
  date: string
  mood: 1 | 2 | 3 | 4 | 5
  note: string
  carriedOver: string[]
}
