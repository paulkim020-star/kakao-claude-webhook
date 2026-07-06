// 날짜 유틸 (로컬 타임존 기준, 문자열 YYYY-MM-DD 키)

export function toKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayKey(): string {
  return toKey(new Date())
}

function parse(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(key: string, n: number): string {
  const dt = parse(key)
  dt.setDate(dt.getDate() + n)
  return toKey(dt)
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

export function displayDate(key: string): string {
  const dt = parse(key)
  return `${dt.getMonth() + 1}월 ${dt.getDate()}일 ${WEEKDAYS[dt.getDay()]}요일`
}

export function weekdayIndex(key: string): number {
  return parse(key).getDay()
}

// 최소 자연어 파싱 (§4.2): "내일 / 모레 / 다음주 X요일" 수준만.
// 파싱 결과는 항상 칩으로 표시해 한 탭에 수정 가능 (불만 #5 대응).
const WEEKDAY_WORDS: Record<string, number> = {
  일: 0, 월: 1, 화: 2, 수: 3, 목: 4, 금: 5, 토: 6,
}

export function parseQuickAdd(
  raw: string,
  base: string,
): { title: string; date: string | null } {
  let title = raw.trim()
  let date: string | null = null

  const strip = (re: RegExp) => {
    title = title.replace(re, ' ').replace(/\s+/g, ' ').trim()
  }

  const nextWeek = /다음\s?주\s?([일월화수목금토])요일/.exec(title)
  if (/(^|\s)오늘(\s|$)/.test(title)) {
    date = base
    strip(/(^|\s)오늘(\s|$)/)
  } else if (/(^|\s)내일(\s|$)/.test(title)) {
    date = addDays(base, 1)
    strip(/(^|\s)내일(\s|$)/)
  } else if (/(^|\s)모레(\s|$)/.test(title)) {
    date = addDays(base, 2)
    strip(/(^|\s)모레(\s|$)/)
  } else if (nextWeek) {
    const target = WEEKDAY_WORDS[nextWeek[1]]
    const baseDow = weekdayIndex(base)
    // 이번 주 월요일 → 다음 주 월요일 → 목표 요일 오프셋(월=0)
    const backToMonday = (baseDow + 6) % 7
    const mondayNextWeek = addDays(base, -backToMonday + 7)
    date = addDays(mondayNextWeek, (target + 6) % 7)
    strip(/다음\s?주\s?([일월화수목금토])요일/)
  }

  return { title, date }
}
