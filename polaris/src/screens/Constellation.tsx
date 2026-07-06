import { useMemo, useState } from 'react'
import { useStore } from '../store'
import {
  areaColor,
  daysSinceActivity,
  recentCompletions,
} from '../lib/meta'
import { VisionEditor } from '../components/VisionEditor'

const W = 360
const H = 460

function spread(n: number, top: number, bottom: number, y: number) {
  // n개 점을 x축에 고르게 배치
  return Array.from({ length: n }, (_, i) => {
    const x = n === 1 ? W / 2 : top + ((bottom - top) * i) / (n - 1)
    return { x, y }
  })
}

export function Constellation() {
  const vision = useStore((s) => s.vision)
  const milestones = useStore((s) => s.milestones)
  const goals = useStore((s) => s.yearlyGoals)
  const tasks = useStore((s) => s.tasks)

  const [editing, setEditing] = useState(false)
  const [showVision, setShowVision] = useState(false)
  const [replay, setReplay] = useState(0)

  const visionPos = { x: W / 2, y: 64 }
  const msPos = useMemo(
    () => spread(Math.max(milestones.length, 0), 70, W - 70, 190),
    [milestones.length],
  )
  const goalPos = useMemo(
    () => spread(Math.max(goals.length, 0), 48, W - 48, 320),
    [goals.length],
  )

  const goalMeta = goals.map((g) => {
    const recent = recentCompletions(tasks, g.id, 30)
    const idle = daysSinceActivity(tasks, g.id)
    // 밝기 = 최근 활동량, 최소 0.32
    const brightness = Math.min(1, 0.32 + recent * 0.12)
    const fading = idle > 14 && recent === 0
    return { recent, idle, brightness, fading }
  })
  const fadingGoal = goals.find((_, i) => goalMeta[i].fading)

  return (
    <div
      className="relative min-h-screen"
      style={{ background: 'var(--night)', color: 'var(--starlight)' }}
    >
      <div className="mx-auto max-w-[440px] px-5 pb-28 pt-4">
        <header className="mb-2 flex items-center justify-between">
          <h1 className="font-display text-xl" style={{ color: 'var(--starlight)' }}>
            별자리
          </h1>
          <button
            type="button"
            onClick={() => setReplay((r) => r + 1)}
            className="text-xs"
            style={{ color: 'var(--starlight)', opacity: 0.6 }}
          >
            다시 보기
          </button>
        </header>

        <svg
          key={replay}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          style={{ overflow: 'visible' }}
        >
          {/* 연결선 */}
          {milestones.map((m, i) => (
            <line
              key={`vm-${m.id}`}
              className="link-pulse"
              x1={visionPos.x}
              y1={visionPos.y}
              x2={msPos[i].x}
              y2={msPos[i].y}
              stroke="var(--starlight)"
              strokeWidth="1"
              style={{ animationDelay: `${i * 220}ms` }}
            />
          ))}
          {goals.map((g, i) => {
            const mIdx = milestones.findIndex((m) => m.id === g.milestoneId)
            const from = mIdx >= 0 ? msPos[mIdx] : visionPos
            return (
              <line
                key={`mg-${g.id}`}
                className="link-pulse"
                x1={from.x}
                y1={from.y}
                x2={goalPos[i].x}
                y2={goalPos[i].y}
                stroke={areaColor(g.area)}
                strokeWidth="1"
                style={{ animationDelay: `${300 + i * 220}ms` }}
              />
            )
          })}

          {/* 최근 30일 완료된 연결 태스크 = 작은 빛점 */}
          {goals.map((g, i) =>
            Array.from({ length: Math.min(goalMeta[i].recent, 8) }, (_, k) => (
              <circle
                key={`pt-${g.id}-${k}`}
                cx={goalPos[i].x - 20 + ((k * 37) % 40)}
                cy={goalPos[i].y + 26 + ((k * 13) % 34)}
                r="1.4"
                fill="var(--starlight)"
                opacity={0.5}
              />
            )),
          )}

          {/* 북극성 (10년) */}
          <g
            style={{ cursor: 'pointer' }}
            onClick={() => (vision ? setShowVision(true) : setEditing(true))}
          >
            <circle
              className="star-glow"
              cx={visionPos.x}
              cy={visionPos.y}
              r="9"
              fill="var(--dawn)"
            />
            <circle cx={visionPos.x} cy={visionPos.y} r="4" fill="var(--starlight)" />
            <text
              x={visionPos.x}
              y={visionPos.y - 18}
              textAnchor="middle"
              className="font-display"
              fontSize="12"
              fill="var(--starlight)"
            >
              {vision?.keywords[0] ?? '북극성'}
            </text>
          </g>

          {/* 5년 이정표 */}
          {milestones.map((m, i) => (
            <g key={m.id}>
              <circle
                cx={msPos[i].x}
                cy={msPos[i].y}
                r="5"
                fill="var(--starlight)"
                opacity={0.85}
              />
              <text
                x={msPos[i].x}
                y={msPos[i].y - 12}
                textAnchor="middle"
                fontSize="10"
                fill="var(--starlight)"
                opacity={0.75}
              >
                {m.title}
              </text>
            </g>
          ))}

          {/* 연간 목표 별 (영역 색, 밝기 = 최근 활동) */}
          {goals.map((g, i) => (
            <g key={g.id}>
              <circle
                cx={goalPos[i].x}
                cy={goalPos[i].y}
                r="6"
                fill={areaColor(g.area)}
                opacity={goalMeta[i].brightness}
              />
              <text
                x={goalPos[i].x}
                y={goalPos[i].y + 22}
                textAnchor="middle"
                fontSize="10"
                fill="var(--starlight)"
                opacity={goalMeta[i].fading ? 0.4 : 0.8}
              >
                {g.title.length > 8 ? g.title.slice(0, 7) + '…' : g.title}
              </text>
            </g>
          ))}
        </svg>

        {/* 흐려지는 별 안내 (삭제 아님) */}
        {fadingGoal && (
          <p
            className="mt-4 text-center text-sm"
            style={{ color: 'var(--starlight)', opacity: 0.7 }}
          >
            「{fadingGoal.title}」 별이 흐려지고 있어요. 다시 밝힐까요, 놓아줄까요?
          </p>
        )}

        {goals.length === 0 && !vision && (
          <div className="mt-10 text-center">
            <p className="font-display text-lg" style={{ opacity: 0.85 }}>
              아직 별이 없어요.
            </p>
            <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
              오늘의 빛이 쌓이면 별자리가 그려집니다.
            </p>
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="mt-6 rounded-full px-5 py-2.5 text-sm font-medium"
              style={{ background: 'var(--dawn)', color: '#1c2733' }}
            >
              북극성 그리기
            </button>
          </div>
        )}
      </div>

      {/* 북극성 상세 + 수정 이력 */}
      {showVision && vision && (
        <div
          className="fixed inset-0 z-50 overflow-y-auto"
          style={{ background: 'var(--night)', color: 'var(--starlight)' }}
        >
          <div className="mx-auto max-w-[540px] px-6 py-8">
            <button
              type="button"
              onClick={() => setShowVision(false)}
              className="mb-4 text-sm"
              style={{ opacity: 0.7 }}
            >
              ← 닫기
            </button>
            <div className="mb-2 flex flex-wrap gap-2">
              {vision.keywords.map((k) => (
                <span
                  key={k}
                  className="font-display rounded-full px-3 py-1 text-sm"
                  style={{ background: 'var(--night-raised)' }}
                >
                  {k}
                </span>
              ))}
            </div>
            <p className="font-display whitespace-pre-wrap text-lg leading-relaxed">
              {vision.narrative}
            </p>
            <button
              type="button"
              onClick={() => {
                setShowVision(false)
                setEditing(true)
              }}
              className="mt-6 rounded-full px-4 py-2 text-sm"
              style={{ background: 'var(--night-raised)' }}
            >
              다시 쓰기
            </button>

            {vision.revisions.length > 1 && (
              <div className="mt-8">
                <p className="mb-3 text-sm" style={{ opacity: 0.6 }}>
                  북극성도 자랍니다
                </p>
                <div className="space-y-3">
                  {vision.revisions
                    .slice(0, -1)
                    .reverse()
                    .map((r, i) => (
                      <div
                        key={i}
                        className="rounded-card p-3 text-sm"
                        style={{ background: 'var(--night-raised)', opacity: 0.85 }}
                      >
                        <div className="mb-1 font-num text-xs" style={{ opacity: 0.6 }}>
                          {r.date.slice(0, 10)}
                        </div>
                        <p className="line-clamp-3 whitespace-pre-wrap">
                          {r.narrative}
                        </p>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {editing && <VisionEditor onClose={() => setEditing(false)} />}
    </div>
  )
}
