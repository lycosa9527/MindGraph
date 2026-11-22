/**
 * Playback window and chapter segments for the clip-teaching timeline.
 */

export interface TimelineChapter {
  id: string
  title: string
  startMs: number
}

export interface TimelineSegment {
  id: string
  title: string
  startMs: number
  endMs: number
  leftPercent: number
  widthPercent: number
}

export function playbackBounds(
  trimStartMs: number,
  trimEndMs: number | null,
  durationMs: number
): { startMs: number; endMs: number } {
  const duration = Number.isFinite(durationMs) && durationMs > 0 ? durationMs : 0
  const start = Math.max(0, trimStartMs)
  const rawEnd = trimEndMs == null ? duration : trimEndMs
  const end = duration > 0 ? Math.min(Math.max(rawEnd, start), duration) : Math.max(rawEnd, start)
  return { startMs: Math.min(start, end), endMs: end }
}

export function chapterSegments(
  chapters: TimelineChapter[],
  startMs: number,
  endMs: number
): TimelineSegment[] {
  const span = Math.max(endMs - startMs, 1)
  const inside = chapters
    .filter((chapter) => chapter.startMs >= startMs && chapter.startMs < endMs)
    .sort((left, right) => left.startMs - right.startMs)
  const rows: Array<Pick<TimelineSegment, 'id' | 'title' | 'startMs' | 'endMs'>> = []
  if (inside.length === 0 || inside[0].startMs > startMs) {
    rows.push({
      id: 'lead',
      title: '',
      startMs,
      endMs: inside.length === 0 ? endMs : inside[0].startMs,
    })
  }
  inside.forEach((chapter, index) => {
    const next = inside[index + 1]
    rows.push({
      id: chapter.id,
      title: chapter.title,
      startMs: chapter.startMs,
      endMs: next ? next.startMs : endMs,
    })
  })
  return rows.map((row) => ({
    ...row,
    leftPercent: ((row.startMs - startMs) / span) * 100,
    widthPercent: Math.max(((row.endMs - row.startMs) / span) * 100, 0),
  }))
}

export function seekMsForRatio(ratio: number, startMs: number, endMs: number): number {
  const clamped = Math.min(1, Math.max(0, ratio))
  return Math.round(startMs + clamped * Math.max(endMs - startMs, 0))
}

export function clampPlayhead(
  currentMs: number,
  startMs: number,
  endMs: number,
  ready: boolean
): { seekMs: number | null; pause: boolean } {
  if (!ready || endMs <= startMs) {
    return { seekMs: null, pause: false }
  }
  if (currentMs < startMs) {
    return { seekMs: startMs, pause: false }
  }
  if (currentMs >= endMs) {
    return { seekMs: null, pause: true }
  }
  return { seekMs: null, pause: false }
}

export function formatClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}
