/**
 * Format seminar transcript lines for the share-message-record sheet.
 */
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import {
  type SeminarSummaryCardModel,
  parseSeminarBriefCard,
  parseSeminarSummaryCard,
  seminarBriefPlainText,
} from '@/utils/mindmateSeminarCards'
import {
  hasGeneratedDiagramImage,
  parseMindmateDiagramLibraryId,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'
import {
  isSeminarVoiceFilename,
  splitSeminarMessageFiles,
} from '@/utils/mindmateSeminarFolder'

export type SeminarShareLineKind =
  | 'text'
  | 'summary'
  | 'brief'
  | 'diagram'
  | 'image'
  | 'file'
  | 'voice'

export interface SeminarShareFormatted {
  kind: SeminarShareLineKind
  /** Shown above the bubble for card-like lines. */
  badge: string
  content: string
}

type Translate = UseLanguageTranslate

const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg'])

function isImageFilename(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return IMAGE_EXT.has(ext)
}

function looksLikeHashFilename(filename: string): boolean {
  const base = filename.replace(/\.[^.]+$/, '')
  return /^[a-f0-9]{16,}$/i.test(base)
}

function sectionBlock(title: string, rows: string[]): string {
  if (!rows.length) {
    return ''
  }
  return `${title}\n${rows.map((item) => `· ${item}`).join('\n')}`
}

function summaryShareText(model: SeminarSummaryCardModel, t: Translate): string {
  if (!model.structured) {
    return [model.scope, model.body].filter(Boolean).join('\n\n')
  }
  const speakers = model.speakers
    .map((row) => (row.role ? `${row.name}（${row.role}）` : row.name))
    .filter(Boolean)
  const goals = model.goals.map((row) => row.goal.trim()).filter(Boolean)
  const materials = model.materials.filter((item) => item && !item.includes('[object Object]'))
  return [
    model.topic.trim(),
    model.scope.trim(),
    model.timeRange
      ? `${t('mindmate.summary.covered')} ${model.timeRange}`
      : '',
    speakers.length ? `${t('mindmate.summary.speakers')} ${speakers.join('、')}` : '',
    model.observers.length
      ? `${t('mindmate.summary.observers')} ${model.observers.join('、')}`
      : '',
    sectionBlock(t('mindmate.summary.section.goals'), goals),
    sectionBlock(t('mindmate.summary.section.consensus'), model.consensus),
    sectionBlock(t('mindmate.summary.section.open'), model.open),
    sectionBlock(t('mindmate.summary.section.materials'), materials),
    sectionBlock(t('mindmate.summary.section.tasks'), model.tasks),
    sectionBlock(t('mindmate.summary.section.quotes'), model.quotes),
    model.body.trim(),
  ]
    .filter(Boolean)
    .join('\n\n')
}

function fileLabel(filename: string, t: Translate): string {
  if (isSeminarVoiceFilename(filename)) {
    return t('mindmate.shareSheet.voiceAttachment')
  }
  if (isImageFilename(filename)) {
    return looksLikeHashFilename(filename)
      ? t('mindmate.shareSheet.imageAttachment')
      : t('mindmate.shareSheet.imageNamed', { name: filename })
  }
  return t('mindmate.shareSheet.fileAttachment', { name: filename || t('mindmate.shareSheet.fileFallback') })
}

/** Turn a raw seminar message into share-sheet copy (no markers / JSON dumps). */
export function formatSeminarShareLine(content: string, t: Translate): SeminarShareFormatted {
  const raw = (content || '').trim()
  if (!raw) {
    return { kind: 'text', badge: '', content: '' }
  }

  const summary = parseSeminarSummaryCard(raw)
  if (summary) {
    return {
      kind: 'summary',
      badge: t('mindmate.summary.cardKicker'),
      content: summaryShareText(summary, t),
    }
  }

  const brief = parseSeminarBriefCard(raw)
  if (brief) {
    return {
      kind: 'brief',
      badge: t('mindmate.briefCard.kicker'),
      content: seminarBriefPlainText(brief),
    }
  }

  const diagramId = parseMindmateDiagramLibraryId(raw)
  if (diagramId || hasGeneratedDiagramImage(raw)) {
    const split = splitSeminarMessageFiles(raw)
    const caption = stripMindmateDiagramIdComments(split.text)
      .replace(/!\[[^\]]*]\([^)]+\)/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    return {
      kind: 'diagram',
      badge: t('mindmate.shareSheet.diagramAttachment'),
      content: caption || t('mindmate.artifacts.diagramFallback'),
    }
  }

  const split = splitSeminarMessageFiles(raw)
  const text = split.text
    .replace(/!\[[^\]]*]\([^)]+\)/g, '')
    .replace(/<!--\s*mg-diagram-id:[a-f0-9-]+\s*-->/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  const fileLines = split.files.map((file) => fileLabel(file.filename, t))
  const onlyFiles = !text && fileLines.length > 0
  const kind: SeminarShareLineKind = onlyFiles
    ? isSeminarVoiceFilename(split.files[0]?.filename || '')
      ? 'voice'
      : isImageFilename(split.files[0]?.filename || '')
        ? 'image'
        : 'file'
    : 'text'
  return {
    kind,
    badge: '',
    content: [text, ...fileLines].filter(Boolean).join('\n'),
  }
}
