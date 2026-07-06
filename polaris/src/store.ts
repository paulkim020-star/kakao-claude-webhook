import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  DailyReview,
  Milestone5,
  MonthlyGoal,
  Task,
  Vision10,
  YearlyGoal,
} from './types'
import { todayKey, weekdayIndex } from './lib/dates'

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36)

export const MAX_YEARLY_GOALS = 5 // §4.4 하드 리밋
export const MAX_CORE = 3 // §4.2 핵심 3
export const MAX_MILESTONES = 4 // §3

export interface NewTask {
  title: string
  date: string | null
  yearlyGoalId?: string | null
  importance?: 1 | 2 | 3
  duration?: 15 | 30 | 60 | 240
  recurring?: Task['recurring']
}

interface State {
  onboarded: boolean
  vision: Vision10 | null
  milestones: Milestone5[]
  yearlyGoals: YearlyGoal[]
  monthlyGoals: MonthlyGoal[]
  tasks: Task[]
  reviews: DailyReview[]
  lastMaintenance: string | null
  lastRitual: string | null
  startedAt: string | null // 온보딩 완료일 (3일차/7일차 초대 계산용)
  weeklyFocus: Record<string, string[]> // mondayKey → 연간 목표 id들
  settings: Settings
  invitesDismissed: InvitesDismissed

  // 온보딩
  completeOnboarding: () => void
  resetAll: () => void

  // 태스크
  addTask: (t: NewTask) => string
  removeTask: (id: string) => void // "놓아주기"
  toggleDone: (id: string) => void
  cycleImportance: (id: string) => void
  setDuration: (id: string, d: Task['duration']) => void
  setGoal: (id: string, goalId: string | null) => void
  setDate: (id: string, date: string | null) => void
  setRecurring: (id: string, rec: Task['recurring']) => void
  toggleCore: (id: string) => boolean // false = 이미 3개
  carryToToday: (id: string) => void // "가져오기"
  splitTask: (id: string, titles: string[]) => void

  // 목표
  addYearlyGoal: (
    g: Omit<YearlyGoal, 'id' | 'progress' | 'createdAt'>,
  ) => string | null
  updateYearlyGoal: (id: string, patch: Partial<YearlyGoal>) => void
  removeYearlyGoal: (id: string) => void
  addMonthlyGoal: (g: Omit<MonthlyGoal, 'id' | 'done'>) => void
  toggleMonthly: (id: string) => void

  // 비전 / 이정표
  saveVision: (narrative: string, keywords: string[]) => void
  addMilestone: (m: Omit<Milestone5, 'id'>) => boolean
  removeMilestone: (id: string) => void

  // 주간 초점
  toggleWeeklyFocus: (mondayKey: string, goalId: string) => void

  // 회고
  saveReview: (r: DailyReview) => void

  // 설정 / 데이터
  updateSettings: (patch: Partial<Settings>) => void
  dismissInvite: (key: keyof InvitesDismissed, value?: string) => void
  exportData: () => string
  importData: (json: string) => boolean

  // 유지보수
  runMaintenance: () => void
  markRitualSeen: () => void
}

export interface Settings {
  // §1.6 #7 알림 최소주의: 기본 0개. 하루 최대 2회(아침·저녁)만.
  morningReminder: boolean
  morningTime: string // "08:00"
  eveningReminder: boolean
  eveningTime: string // "22:00"
}

interface InvitesDismissed {
  milestone: boolean
  vision: boolean
  visionRefresh: string | null // 마지막으로 미룬 날짜
}

const DEFAULT_SETTINGS: Settings = {
  morningReminder: false,
  morningTime: '08:00',
  eveningReminder: false,
  eveningTime: '22:00',
}

function recomputeProgress(
  goals: YearlyGoal[],
  monthly: MonthlyGoal[],
): YearlyGoal[] {
  return goals.map((g) => {
    const rel = monthly.filter((m) => m.yearlyGoalId === g.id)
    if (rel.length === 0) return { ...g, progress: 0 }
    const done = rel.filter((m) => m.done).length
    return { ...g, progress: Math.round((done / rel.length) * 100) }
  })
}

function shouldRecurOn(rec: Task['recurring'], dateKey: string): boolean {
  const dow = weekdayIndex(dateKey)
  switch (rec) {
    case 'daily':
      return true
    case 'weekdays':
      return dow >= 1 && dow <= 5
    case 'weekly':
      return true // 단순화: 같은 주기로 매주 (요일은 원본 유지 대신 이월일 기준)
    default:
      return false
  }
}

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      onboarded: false,
      vision: null,
      milestones: [],
      yearlyGoals: [],
      monthlyGoals: [],
      tasks: [],
      reviews: [],
      lastMaintenance: null,
      lastRitual: null,
      startedAt: null,
      weeklyFocus: {},
      settings: DEFAULT_SETTINGS,
      invitesDismissed: { milestone: false, vision: false, visionRefresh: null },

      completeOnboarding: () =>
        set((s) => ({ onboarded: true, startedAt: s.startedAt ?? todayKey() })),
      resetAll: () =>
        set({
          onboarded: false,
          vision: null,
          milestones: [],
          yearlyGoals: [],
          monthlyGoals: [],
          tasks: [],
          reviews: [],
          lastMaintenance: null,
          lastRitual: null,
          startedAt: null,
          weeklyFocus: {},
          settings: DEFAULT_SETTINGS,
          invitesDismissed: {
            milestone: false,
            vision: false,
            visionRefresh: null,
          },
        }),

      addTask: (t) => {
        const id = uid()
        const task: Task = {
          id,
          title: t.title,
          date: t.date,
          yearlyGoalId: t.yearlyGoalId ?? null,
          importance: t.importance ?? 1,
          duration: t.duration ?? 30,
          isCore: false,
          recurring: t.recurring ?? 'none',
          carryCount: 0,
          done: false,
          completedAt: null,
        }
        set((s) => ({ tasks: [...s.tasks, task] }))
        return id
      },

      removeTask: (id) =>
        set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),

      toggleDone: (id) =>
        set((s) => ({
          tasks: s.tasks.map((t) =>
            t.id === id
              ? {
                  ...t,
                  done: !t.done,
                  completedAt: !t.done ? new Date().toISOString() : null,
                }
              : t,
          ),
        })),

      cycleImportance: (id) =>
        set((s) => ({
          tasks: s.tasks.map((t) =>
            t.id === id
              ? { ...t, importance: (((t.importance % 3) + 1) as 1 | 2 | 3) }
              : t,
          ),
        })),

      setDuration: (id, d) =>
        set((s) => ({
          tasks: s.tasks.map((t) => (t.id === id ? { ...t, duration: d } : t)),
        })),

      setGoal: (id, goalId) =>
        set((s) => ({
          tasks: s.tasks.map((t) =>
            t.id === id ? { ...t, yearlyGoalId: goalId } : t,
          ),
        })),

      setDate: (id, date) =>
        set((s) => ({
          tasks: s.tasks.map((t) => (t.id === id ? { ...t, date } : t)),
        })),

      setRecurring: (id, rec) =>
        set((s) => ({
          tasks: s.tasks.map((t) => (t.id === id ? { ...t, recurring: rec } : t)),
        })),

      toggleCore: (id) => {
        const s = get()
        const t = s.tasks.find((x) => x.id === id)
        if (!t) return false
        if (!t.isCore) {
          const coreCount = s.tasks.filter(
            (x) => x.isCore && x.date === t.date,
          ).length
          if (coreCount >= MAX_CORE) return false
        }
        set((st) => ({
          tasks: st.tasks.map((x) =>
            x.id === id ? { ...x, isCore: !x.isCore } : x,
          ),
        }))
        return true
      },

      carryToToday: (id) =>
        set((s) => ({
          tasks: s.tasks.map((t) =>
            t.id === id
              ? { ...t, date: todayKey(), carryCount: t.carryCount + 1 }
              : t,
          ),
        })),

      splitTask: (id, titles) =>
        set((s) => {
          const src = s.tasks.find((t) => t.id === id)
          if (!src) return {}
          const parts: Task[] = titles
            .filter((x) => x.trim())
            .map((title) => ({
              ...src,
              id: uid(),
              title: title.trim(),
              carryCount: 0,
              done: false,
              completedAt: null,
              isCore: false,
            }))
          return { tasks: [...s.tasks.filter((t) => t.id !== id), ...parts] }
        }),

      addYearlyGoal: (g) => {
        const s = get()
        if (s.yearlyGoals.length >= MAX_YEARLY_GOALS) return null
        const id = uid()
        set({
          yearlyGoals: [
            ...s.yearlyGoals,
            { ...g, id, progress: 0, createdAt: todayKey() },
          ],
        })
        return id
      },

      updateYearlyGoal: (id, patch) =>
        set((s) => ({
          yearlyGoals: s.yearlyGoals.map((g) =>
            g.id === id ? { ...g, ...patch } : g,
          ),
        })),

      removeYearlyGoal: (id) =>
        set((s) => ({
          yearlyGoals: s.yearlyGoals.filter((g) => g.id !== id),
          monthlyGoals: s.monthlyGoals.filter((m) => m.yearlyGoalId !== id),
          tasks: s.tasks.map((t) =>
            t.yearlyGoalId === id ? { ...t, yearlyGoalId: null } : t,
          ),
        })),

      addMonthlyGoal: (g) =>
        set((s) => {
          const monthly = [...s.monthlyGoals, { ...g, id: uid(), done: false }]
          return {
            monthlyGoals: monthly,
            yearlyGoals: recomputeProgress(s.yearlyGoals, monthly),
          }
        }),

      toggleMonthly: (id) =>
        set((s) => {
          const monthly = s.monthlyGoals.map((m) =>
            m.id === id ? { ...m, done: !m.done } : m,
          )
          return {
            monthlyGoals: monthly,
            yearlyGoals: recomputeProgress(s.yearlyGoals, monthly),
          }
        }),

      saveVision: (narrative, keywords) =>
        set((s) => {
          const now = new Date().toISOString()
          if (!s.vision) {
            return {
              vision: {
                id: uid(),
                narrative,
                keywords: keywords.slice(0, 5),
                updatedAt: now,
                revisions: [{ date: now, narrative }],
              },
            }
          }
          return {
            vision: {
              ...s.vision,
              narrative,
              keywords: keywords.slice(0, 5),
              updatedAt: now,
              revisions: [
                ...s.vision.revisions,
                { date: now, narrative },
              ],
            },
          }
        }),

      addMilestone: (m) => {
        const s = get()
        if (s.milestones.length >= MAX_MILESTONES) return false
        set({ milestones: [...s.milestones, { ...m, id: uid() }] })
        return true
      },

      removeMilestone: (id) =>
        set((s) => ({
          milestones: s.milestones.filter((m) => m.id !== id),
          yearlyGoals: s.yearlyGoals.map((g) =>
            g.milestoneId === id ? { ...g, milestoneId: null } : g,
          ),
        })),

      toggleWeeklyFocus: (mondayKey, goalId) =>
        set((s) => {
          const cur = s.weeklyFocus[mondayKey] ?? []
          const next = cur.includes(goalId)
            ? cur.filter((x) => x !== goalId)
            : [...cur, goalId]
          return { weeklyFocus: { ...s.weeklyFocus, [mondayKey]: next } }
        }),

      saveReview: (r) =>
        set((s) => ({
          reviews: [...s.reviews.filter((x) => x.date !== r.date), r],
        })),

      updateSettings: (patch) =>
        set((s) => ({ settings: { ...s.settings, ...patch } })),

      dismissInvite: (key, value) =>
        set((s) => {
          if (key === 'visionRefresh') {
            return {
              invitesDismissed: {
                ...s.invitesDismissed,
                visionRefresh: value ?? todayKey(),
              },
            }
          }
          return {
            invitesDismissed: { ...s.invitesDismissed, [key]: true },
          }
        }),

      exportData: () => {
        const s = get()
        const payload = {
          version: 2,
          exportedAt: new Date().toISOString(),
          data: {
            vision: s.vision,
            milestones: s.milestones,
            yearlyGoals: s.yearlyGoals,
            monthlyGoals: s.monthlyGoals,
            tasks: s.tasks,
            reviews: s.reviews,
            weeklyFocus: s.weeklyFocus,
            settings: s.settings,
            startedAt: s.startedAt,
          },
        }
        return JSON.stringify(payload, null, 2)
      },

      importData: (json) => {
        try {
          const parsed = JSON.parse(json)
          const d = parsed?.data ?? parsed
          if (!d || typeof d !== 'object') return false
          set((s) => ({
            vision: d.vision ?? null,
            milestones: d.milestones ?? [],
            yearlyGoals: d.yearlyGoals ?? [],
            monthlyGoals: d.monthlyGoals ?? [],
            tasks: d.tasks ?? [],
            reviews: d.reviews ?? [],
            weeklyFocus: d.weeklyFocus ?? {},
            settings: { ...DEFAULT_SETTINGS, ...(d.settings ?? {}) },
            startedAt: d.startedAt ?? s.startedAt,
            onboarded: true,
          }))
          return true
        } catch {
          return false
        }
      },

      markRitualSeen: () => set({ lastRitual: todayKey() }),

      // §3 규칙 1: recurring 태스크는 미완료 시 자정에 조용히 소멸, 다음 회차만 생성.
      runMaintenance: () => {
        const s = get()
        const today = todayKey()
        if (s.lastMaintenance === today) return

        let tasks = [...s.tasks]

        // 반복 태스크: 과거 날짜의 회차를 정리하고 오늘 회차를 생성
        const recurringPast = tasks.filter(
          (t) => t.recurring !== 'none' && t.date && t.date < today,
        )
        for (const t of recurringPast) {
          // 오늘 같은 반복이 이미 있으면 중복 생성 금지
          const existsToday = tasks.some(
            (x) =>
              x.date === today &&
              x.recurring === t.recurring &&
              x.title === t.title,
          )
          if (!existsToday && shouldRecurOn(t.recurring, today)) {
            tasks.push({
              ...t,
              id: uid(),
              date: today,
              done: false,
              completedAt: null,
              isCore: false,
              carryCount: 0,
            })
          }
          if (t.done) {
            // 완료 회차는 기록으로 남기되 다시 반복하지 않도록 고정
            tasks = tasks.map((x) =>
              x.id === t.id ? { ...x, recurring: 'none' } : x,
            )
          } else {
            // 미완료 회차는 조용히 소멸 (이월 카드에 올리지 않는다)
            tasks = tasks.filter((x) => x.id !== t.id)
          }
        }

        set({ tasks, lastMaintenance: today })
      },
    }),
    {
      name: 'polaris-v1',
      version: 2,
    },
  ),
)
