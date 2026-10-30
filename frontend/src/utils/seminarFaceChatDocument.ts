/**
 * Face-to-face notes archived under 面聊文档.
 * Live saves keep the transcript; a summary is written above it once drafted.
 */
import { beijingWallClock } from '@/utils/beijingClock'

export const SEMINAR_FACE_CHAT_KIND = 'face_chat'

export function isSeminarFaceChatFile(file: { kind?: string }): boolean {
  return file.kind === SEMINAR_FACE_CHAT_KIND
}

export function faceChatFilename(now: Date, stem: string): string {
  const wall = beijingWallClock(now)
  const safe = stem.replace(/[\\/:*?"<>|]/g, '').trim() || '面聊记录'
  return `${safe}-${wall.year}${wall.month}${wall.day}-${wall.hour}${wall.minute}.md`
}

export function composeFaceChatDocument(input: {
  transcript: string
  summary: string
  summaryHeading: string
  notesHeading: string
}): string {
  const notes = input.transcript.trim()
  const summary = input.summary.trim()
  if (!summary) {
    return notes
  }
  return [`# ${input.summaryHeading}`, '', summary, '', `# ${input.notesHeading}`, '', notes].join(
    '\n'
  )
}
