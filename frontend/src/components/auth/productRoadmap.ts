export type RoadmapColumn = 'now' | 'next' | 'later' | 'shipped'

export interface RoadmapItem {
  column: RoadmapColumn
  title: string
  summary: string
  owner: string
  area: string
  target: string
}

export const ROADMAP_COLUMNS: RoadmapColumn[] = ['now', 'next', 'later', 'shipped']

export function blankRoadmapItem(): RoadmapItem {
  return {
    column: 'now',
    title: '',
    summary: '',
    owner: '',
    area: '',
    target: '',
  }
}

const TARGET_PATTERN = /^20\d{2}年(?:[1-9]|1[0-2])月$/

function targetOrder(value: string): number {
  const match = /^(\d{4})年(\d{1,2})月$/.exec(value)
  if (!match) return 0
  return Number(match[1]) * 12 + Number(match[2])
}

export function roadmapTargetOptions(selected = '', anchor = new Date()): string[] {
  const start = new Date(anchor.getFullYear(), anchor.getMonth() - 3, 1)
  const options: string[] = []
  for (let offset = 0; offset < 18; offset += 1) {
    const date = new Date(start.getFullYear(), start.getMonth() + offset, 1)
    options.push(`${date.getFullYear()}年${date.getMonth() + 1}月`)
  }
  if (TARGET_PATTERN.test(selected) && !options.includes(selected)) {
    options.push(selected)
    options.sort((left, right) => targetOrder(left) - targetOrder(right))
  }
  return options
}

export function ownerMark(name: string): string {
  const trimmed = name.trim()
  return trimmed ? trimmed.slice(0, 1).toUpperCase() : ''
}

export function ownerHue(name: string): number {
  let hash = 0
  for (const char of name.trim()) {
    hash = (hash * 31 + char.charCodeAt(0)) % 360
  }
  return hash
}

export function cloneRoadmapItems(items: RoadmapItem[]): RoadmapItem[] {
  return items.map((item) => ({ ...item }))
}
