/**
 * Load a previous Voice Notes diagram back into the transcript UI.
 */
import { voiceNotesMarkdownUrl } from '@/composables/voiceNotes/voiceNotesBind'
import { DOC_SUMMARY_API_BASE } from '@/config/docSummaryApi'
import { apiGet, apiRequestJson } from '@/utils/apiClient'
import { parseVoiceNotesMarkdown } from '@/utils/voiceNotesMarkdown'
import type { VoiceNotesTurn } from '@/utils/voiceNotesTranscript'

type DocSummaryPackage = {
  id: number
}

type ExtractedMarkdown = {
  markdown?: string
}

export type RestoredVoiceNotesConversation = {
  diagramId: string
  packageId: number
  turns: VoiceNotesTurn[]
  speakerNames: Record<number, string>
  speakerIds: number[]
  speakerRemaps: Record<number, number>
  speakerContextId: string
  savedAt: number | null
  elapsedMs: number
  hasTranscript: boolean
}

export async function loadVoiceNotesConversation(
  diagramId: string,
  title: string,
  defaultLabelTemplate: string,
  ingestSource?: string
): Promise<RestoredVoiceNotesConversation> {
  const pkg = await apiRequestJson<DocSummaryPackage>(`${DOC_SUMMARY_API_BASE}/session/start`, {
    method: 'POST',
    body: JSON.stringify({
      diagram_id: diagramId,
      diagram_title: title,
      create_if_missing: true,
    }),
  })
  const response = await apiGet(voiceNotesMarkdownUrl(pkg.id, ingestSource))
  let markdown = ''
  if (response.ok) {
    const payload = (await response.json()) as ExtractedMarkdown
    markdown = typeof payload.markdown === 'string' ? payload.markdown : ''
  } else if (response.status !== 404) {
    throw new Error(`Failed to load voice note transcript: ${response.status}`)
  }
  const parsed = parseVoiceNotesMarkdown(markdown, defaultLabelTemplate)
  return {
    diagramId,
    packageId: pkg.id,
    turns: parsed.turns,
    speakerNames: parsed.speakerNames,
    speakerIds: parsed.speakerIds,
    speakerRemaps: parsed.speakerRemaps,
    speakerContextId: parsed.speakerContextId,
    savedAt: parsed.savedAt,
    elapsedMs: parsed.elapsedMs,
    hasTranscript: parsed.turns.length > 0,
  }
}
