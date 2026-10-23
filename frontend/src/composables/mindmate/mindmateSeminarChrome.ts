/**
 * Shared seminar chrome: roster pin + right task pane (members / files / artifacts)
 * + Doubao-style document split viewer.
 */
import { type Ref, computed, ref } from 'vue'

import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { pinSeminarRoster } from '@/composables/mindmate/useMindmateSeminarFaces'
import type { SeminarFace } from '@/utils/mindmateSeminarFaces'
import type { SeminarBackgroundFile } from '@/utils/mindmateSeminarFolder'

export type SeminarTaskPaneTab = 'members' | 'files' | 'artifacts' | 'highlights'

export type SeminarDocKind = 'file' | 'diagram'

export interface SeminarDocTab {
  id: string
  kind: SeminarDocKind
  title: string
  /** Background file id when kind === 'file'. */
  fileId?: string
  contentType?: string
  filename?: string
  /** Diagram preview fields when kind === 'diagram'. */
  previewId?: string
  imagePath?: string
  /** Shared canvas diagram shelved from the conversation. */
  diagramId?: string
}

export const seminarTaskPaneTab = ref<SeminarTaskPaneTab | null>(null)
export const seminarRosterVersion = ref(0)
/** Bump after brief resource upload so the folder pane refetches. */
export const seminarFolderReloadToken = ref(0)
/** Live collab transcript for artifact panels mounted outside CollabRoom. */
export const seminarLiveMessages: Ref<MindmateCollabMessage[]> = ref([])
/** Word files archived from MindMate replies. Shared by the artifacts pane. */
export const seminarServerArtifacts: Ref<SeminarBackgroundFile[]> = ref([])
/** True after the current room's artifact list has loaded. */
export const seminarArtifactsReady = ref(false)

/** Open document tabs in the middle split pane (Doubao-style). */
export const seminarDocTabs = ref<SeminarDocTab[]>([])
export const seminarDocActiveId = ref<string | null>(null)
const DOC_WIDTH_STORAGE_KEY = 'mindmate.seminar.docPaneWidthPx'

function readStoredDocPaneWidth(): number | null {
  try {
    const raw = localStorage.getItem(DOC_WIDTH_STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  } catch {
    return null
  }
}

const storedDocWidth = readStoredDocPaneWidth()

/** Viewer pane width in px; chat fills the rest. Remembered across sessions. */
export const seminarDocPaneWidthPx = ref(storedDocWidth ?? 640)
/** True after the user (or a prior session) has chosen a width. */
export const seminarDocPaneWidthPreferred = ref(storedDocWidth != null)
/** Document viewer covers the whole seminar shell. */
export const seminarDocFullscreen = ref(false)

export interface SeminarComposerCitation {
  fileId: string
  filename: string
  contentType: string
  sizeBytes: number
}

/** Files cited into the composer for the next send. */
export const seminarComposerCitations = ref<SeminarComposerCitation[]>([])

/** Files dropped on the composer. They ride the next message, not the shared folder. */
export interface SeminarComposerAttachment {
  key: string
  name: string
  file: File
}

export const seminarComposerAttachments = ref<SeminarComposerAttachment[]>([])

const DOC_PANE_MIN = 320
const DOC_PANE_MAX = 1400
/** Remember which drawer to restore after leaving reading mode. */
const seminarTaskPaneBeforeDoc = ref<SeminarTaskPaneTab | null>('files')

export const seminarMembersPaneOpen = computed(() => seminarTaskPaneTab.value === 'members')
export const seminarFolderOpen = computed(() => seminarTaskPaneTab.value === 'files')
export const seminarArtifactsOpen = computed(() => seminarTaskPaneTab.value === 'artifacts')
export const seminarHighlightsOpen = computed(() => seminarTaskPaneTab.value === 'highlights')
export const seminarTaskPaneOpen = computed(() => seminarTaskPaneTab.value != null)
export const seminarDocViewerOpen = computed(() => seminarDocTabs.value.length > 0)
export const seminarDocActiveTab = computed(
  () =>
    seminarDocTabs.value.find((tab) => tab.id === seminarDocActiveId.value) ??
    seminarDocTabs.value[0] ??
    null
)

export function toggleSeminarTaskPane(tab: SeminarTaskPaneTab): void {
  seminarTaskPaneTab.value = seminarTaskPaneTab.value === tab ? null : tab
}

export function openSeminarTaskPane(tab: SeminarTaskPaneTab): void {
  seminarTaskPaneTab.value = tab
}

export function bumpSeminarFolderReload(): void {
  seminarFolderReloadToken.value += 1
}

export function toggleSeminarMembersPane(): void {
  toggleSeminarTaskPane('members')
}

export function toggleSeminarFolder(): void {
  toggleSeminarTaskPane('files')
}

export function toggleSeminarArtifacts(): void {
  toggleSeminarTaskPane('artifacts')
}

export function toggleSeminarHighlights(): void {
  toggleSeminarTaskPane('highlights')
}

export function closeSeminarTaskDrawer(): void {
  seminarTaskPaneTab.value = null
}

export interface SeminarHighlight {
  id: string
  text: string
  authorName: string
  messageId: number | null
  createdAt: string
  createdByUserId?: number | null
  createdByName?: string
  messageAt?: string
}

let messageLocator: ((messageId: number) => void) | null = null

export function setSeminarMessageLocator(handler: ((messageId: number) => void) | null): void {
  messageLocator = handler
}

export function locateSeminarMessage(messageId: number): void {
  if (messageId > 0) {
    messageLocator?.(messageId)
  }
}

export interface SeminarHighlightNotice {
  id: string
  createdAt: string
  kind: 'set' | 'cancel' | 'shelf'
  ownMessage: boolean
  authorName: string
  title?: string
  destination?: 'resource' | 'artifact' | 'removed'
  shelf?: 'resource' | 'artifact'
}

/** Group highlights pinned from chat (local to this browser until a server API exists). */
export const seminarHighlights = ref<SeminarHighlight[]>([])
/** Set / cancel tips shown in the transcript (local to this browser). */
export const seminarHighlightNotices = ref<SeminarHighlightNotice[]>([])
/** True when the signed-in seat is 观摩学习: watch and share only. */
export const seminarSpectator = ref(false)
/** Right-click an avatar to drop @name into the seminar composer. */
export const seminarMentionRequest = ref<{ name: string; nonce: number } | null>(null)

export function requestSeminarMention(name: string): void {
  const trimmed = name.trim().replace(/^[@＠]+/u, '')
  if (!trimmed || seminarSpectator.value) {
    return
  }
  seminarMentionRequest.value = { name: trimmed, nonce: Date.now() }
}

function highlightsStorageKey(sessionId: string): string {
  return `mindmate.seminar.highlights.${sessionId}`
}

function highlightNoticesStorageKey(sessionId: string): string {
  return `mindmate.seminar.highlightNotices.${sessionId}`
}

export function loadSeminarHighlights(sessionId: string): void {
  if (!sessionId) {
    seminarHighlights.value = []
    seminarHighlightNotices.value = []
    return
  }
  try {
    const raw = localStorage.getItem(highlightsStorageKey(sessionId))
    const parsed = raw ? (JSON.parse(raw) as SeminarHighlight[]) : []
    seminarHighlights.value = Array.isArray(parsed) ? parsed : []
  } catch {
    seminarHighlights.value = []
  }
  try {
    const rawNotices = localStorage.getItem(highlightNoticesStorageKey(sessionId))
    const parsedNotices = rawNotices ? (JSON.parse(rawNotices) as SeminarHighlightNotice[]) : []
    seminarHighlightNotices.value = Array.isArray(parsedNotices) ? parsedNotices : []
  } catch {
    seminarHighlightNotices.value = []
  }
}

function persistSeminarHighlights(sessionId: string): void {
  if (!sessionId) {
    return
  }
  try {
    localStorage.setItem(highlightsStorageKey(sessionId), JSON.stringify(seminarHighlights.value))
  } catch {
    /* private mode / quota */
  }
}

export function addSeminarHighlight(
  sessionId: string,
  entry: Omit<SeminarHighlight, 'id' | 'createdAt'> & { id?: string; createdAt?: string }
): SeminarHighlight | null {
  const item: SeminarHighlight = {
    id: entry.id || `hl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text: entry.text.trim(),
    authorName: entry.authorName,
    messageId: entry.messageId,
    createdAt: entry.createdAt || new Date().toISOString(),
    createdByUserId: entry.createdByUserId ?? null,
    createdByName: entry.createdByName?.trim() || '',
    messageAt: entry.messageAt || '',
  }
  if (!item.text) {
    return null
  }
  const duplicate = seminarHighlights.value.some(
    (row) => row.text === item.text && row.messageId === item.messageId
  )
  if (duplicate) {
    return null
  }
  seminarHighlights.value = [item, ...seminarHighlights.value]
  persistSeminarHighlights(sessionId)
  return item
}

function persistHighlightNotices(sessionId: string): void {
  if (!sessionId) {
    return
  }
  try {
    localStorage.setItem(
      highlightNoticesStorageKey(sessionId),
      JSON.stringify(seminarHighlightNotices.value)
    )
  } catch {
    /* private mode / quota */
  }
}

export function pushSeminarHighlightNotice(
  sessionId: string,
  entry: Omit<SeminarHighlightNotice, 'id' | 'createdAt'>
): void {
  if (!sessionId) {
    return
  }
  const item: SeminarHighlightNotice = {
    id: `hn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: new Date().toISOString(),
    kind: entry.kind,
    ownMessage: entry.ownMessage,
    authorName: entry.authorName.trim(),
    title: entry.title?.trim() || '',
    destination: entry.destination,
    shelf: entry.shelf,
  }
  seminarHighlightNotices.value = [...seminarHighlightNotices.value, item]
  persistHighlightNotices(sessionId)
}

export function removeSeminarHighlight(sessionId: string, id: string): void {
  seminarHighlights.value = seminarHighlights.value.filter((row) => row.id !== id)
  persistSeminarHighlights(sessionId)
}

function enterReadingMode(): void {
  // Collapse the list drawer so chat + document can share the screen (Doubao-style).
  if (seminarTaskPaneTab.value != null) {
    seminarTaskPaneBeforeDoc.value = seminarTaskPaneTab.value
  }
  seminarTaskPaneTab.value = null
}

function leaveReadingMode(): void {
  if (seminarDocTabs.value.length > 0) {
    return
  }
  seminarTaskPaneTab.value = seminarTaskPaneBeforeDoc.value ?? 'files'
}

export function openSeminarDoc(tab: SeminarDocTab): void {
  const existing = seminarDocTabs.value.find((item) => item.id === tab.id)
  if (!existing) {
    seminarDocTabs.value = [...seminarDocTabs.value, tab]
  }
  seminarDocActiveId.value = tab.id
  enterReadingMode()
}

export function focusSeminarDoc(id: string): void {
  if (seminarDocTabs.value.some((tab) => tab.id === id)) {
    seminarDocActiveId.value = id
  }
}

export function closeSeminarDoc(id: string): void {
  const next = seminarDocTabs.value.filter((tab) => tab.id !== id)
  seminarDocTabs.value = next
  if (seminarDocActiveId.value === id) {
    seminarDocActiveId.value = next[next.length - 1]?.id ?? null
  }
  if (next.length === 0) {
    seminarDocFullscreen.value = false
  }
  leaveReadingMode()
}

export function closeAllSeminarDocs(restorePane = true): void {
  seminarDocTabs.value = []
  seminarDocActiveId.value = null
  seminarDocFullscreen.value = false
  if (restorePane) {
    leaveReadingMode()
  }
}

export function setSeminarDocFullscreen(open: boolean): void {
  seminarDocFullscreen.value = open && seminarDocTabs.value.length > 0
}

export function toggleSeminarDocFullscreen(): void {
  setSeminarDocFullscreen(!seminarDocFullscreen.value)
}

export function citeSeminarFile(citation: SeminarComposerCitation): void {
  if (seminarComposerCitations.value.some((item) => item.fileId === citation.fileId)) {
    return
  }
  seminarComposerCitations.value = [...seminarComposerCitations.value, citation]
}

export function removeSeminarCitation(fileId: string): void {
  seminarComposerCitations.value = seminarComposerCitations.value.filter(
    (item) => item.fileId !== fileId
  )
}

export function clearSeminarCitations(): void {
  seminarComposerCitations.value = []
}

export function takeSeminarCitations(): SeminarComposerCitation[] {
  const items = [...seminarComposerCitations.value]
  seminarComposerCitations.value = []
  return items
}

export function addSeminarComposerAttachments(files: File[]): void {
  const next = files
    .filter((file) => file.size > 0)
    .map((file) => ({
      key: `${file.name}:${file.size}:${file.lastModified}:${Math.random().toString(36).slice(2, 8)}`,
      name: file.name,
      file,
    }))
  if (next.length === 0) {
    return
  }
  seminarComposerAttachments.value = [...seminarComposerAttachments.value, ...next]
}

export function removeSeminarComposerAttachment(key: string): void {
  seminarComposerAttachments.value = seminarComposerAttachments.value.filter(
    (item) => item.key !== key
  )
}

export function takeSeminarComposerAttachments(): SeminarComposerAttachment[] {
  const items = [...seminarComposerAttachments.value]
  seminarComposerAttachments.value = []
  return items
}

export function clampSeminarDocPaneWidth(width: number): number {
  return Math.min(DOC_PANE_MAX, Math.max(DOC_PANE_MIN, Math.round(width)))
}

export function setSeminarDocPaneWidth(width: number, remember = true): void {
  const next = clampSeminarDocPaneWidth(width)
  seminarDocPaneWidthPx.value = next
  if (!remember) {
    return
  }
  seminarDocPaneWidthPreferred.value = true
  try {
    localStorage.setItem(DOC_WIDTH_STORAGE_KEY, String(next))
  } catch {
    /* private mode / quota — preference stays in-memory only */
  }
}

export function replaceSeminarServerArtifacts(rows: SeminarBackgroundFile[]): void {
  const extras = seminarServerArtifacts.value.filter(
    (row) => !rows.some((item) => item.id === row.id)
  )
  seminarServerArtifacts.value = [...extras, ...rows]
}

export function upsertSeminarServerArtifact(row: SeminarBackgroundFile): void {
  const rest = seminarServerArtifacts.value.filter((item) => item.id !== row.id)
  seminarServerArtifacts.value = [row, ...rest]
}

export function dropSeminarServerArtifact(fileId: string): void {
  seminarServerArtifacts.value = seminarServerArtifacts.value.filter((item) => item.id !== fileId)
}

export function clearSeminarServerArtifacts(): void {
  seminarServerArtifacts.value = []
  seminarArtifactsReady.value = false
}

export function closeSeminarChrome(): void {
  closeAllSeminarDocs(false)
  seminarTaskPaneTab.value = null
  clearSeminarCitations()
  clearSeminarServerArtifacts()
  seminarSpectator.value = false
  seminarMentionRequest.value = null
}

export function setSeminarLiveMessages(messages: MindmateCollabMessage[]): void {
  seminarLiveMessages.value = messages
}

export function applySeminarGroup(next: SeminarFace[]): void {
  if (next.length === 0) {
    return
  }
  pinSeminarRoster(next)
  seminarRosterVersion.value += 1
}

export function seminarFileDocId(fileId: string): string {
  return `file:${fileId}`
}

export function seminarDiagramDocId(previewId: string): string {
  return `diagram:${previewId}`
}
