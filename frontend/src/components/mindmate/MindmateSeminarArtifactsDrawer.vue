<script setup lang="ts">
/**
 * Seminar artifact sidebar: documents, diagrams, and files produced in the seminar.
 * Shared-folder uploads that were never sent in the chat stay under Resources.
 */
import { computed, ref } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElMessageBox } from 'element-plus'

import { ChevronDown, ExternalLink, FileText, MoreHorizontal, Quote, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  bumpSeminarFolderReload,
  citeSeminarFile,
  closeSeminarDoc,
  dropSeminarServerArtifact,
  openSeminarDoc,
  seminarDiagramDocId,
  seminarFileDocId,
  seminarServerArtifacts,
  seminarSpectator,
  upsertSeminarServerArtifact,
} from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import {
  collabDiagramSaveFailureKey,
  saveCollabDiagramToLibrary,
} from '@/utils/mindmateSeminarDiagramLibrary'
import {
  type SeminarDocumentArtifact,
  collectSeminarDiagramArtifacts,
  collectSeminarDocumentArtifacts,
} from '@/utils/mindmateSeminarArtifacts'
import {
  type SeminarBackgroundFile,
  deleteSeminarBackgroundFile,
  pinSeminarBackgroundFile,
  renameSeminarBackgroundFile,
  seminarFolderErrorKey,
} from '@/utils/mindmateSeminarFolder'

const props = withDefaults(
  defineProps<{
    sessionId: string
    messages: MindmateSeminarMessage[]
    /** Hide chrome when mounted inside the seminar task pane. */
    embedded?: boolean
  }>(),
  {
    embedded: false,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const savingId = ref('')
const savedIds = ref<string[]>([])
const openSections = ref({ files: true, diagrams: true, transcripts: true })

const diagrams = computed(() => {
  const shelved = seminarServerArtifacts.value
    .filter((file) => file.diagramId)
    .map((file) => ({
      previewId: file.diagramId || file.id,
      label: file.filename,
      messageId: file.sourceMessageId,
      imagePath: '',
    }))
  const seen = new Set(shelved.map((item) => item.previewId))
  const fromChat = collectSeminarDiagramArtifacts(props.messages).filter(
    (item) => !seen.has(item.previewId)
  )
  return [...shelved, ...fromChat]
})
const documents = computed(() => {
  const archived = seminarServerArtifacts.value
    .filter((file) => !file.diagramId)
    .map((file) => ({
      id: `artifact:${file.id}`,
      title: file.filename,
      url: '',
      messageId: file.sourceMessageId,
      backgroundFileId: file.id,
    }))
  const seen = new Set(archived.map((doc) => doc.backgroundFileId))
  const fromChat = collectSeminarDocumentArtifacts(props.messages).filter((doc) => {
    return !doc.backgroundFileId || !seen.has(doc.backgroundFileId)
  })
  return [...archived, ...fromChat]
})

function diagramLabel(label: string): string {
  return label || t('mindmate.artifacts.diagramFallback')
}

function isSaved(previewId: string): boolean {
  return savedIds.value.includes(previewId)
}

function toggleSection(key: 'files' | 'diagrams' | 'transcripts'): void {
  openSections.value = { ...openSections.value, [key]: !openSections.value[key] }
}

function openDocument(doc: SeminarDocumentArtifact): void {
  if (doc.backgroundFileId) {
    openSeminarDoc({
      id: seminarFileDocId(doc.backgroundFileId),
      kind: 'file',
      title: doc.title,
      fileId: doc.backgroundFileId,
      filename: doc.title,
      contentType: '',
    })
    return
  }
  if (doc.url && typeof window !== 'undefined') {
    window.open(doc.url, '_blank', 'noopener,noreferrer')
  }
}

function artifactFile(doc: SeminarDocumentArtifact): SeminarBackgroundFile | null {
  if (!doc.backgroundFileId) {
    return null
  }
  return seminarServerArtifacts.value.find((file) => file.id === doc.backgroundFileId) || null
}

async function renameArtifact(file: SeminarBackgroundFile): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      t('mindmate.folder.renameHint'),
      t('mindmate.folder.rename'),
      {
        inputValue: file.filename,
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        inputValidator: (raw) => {
          const next = (raw || '').trim()
          if (!next) {
            return t('mindmate.folder.renameRequired')
          }
          return true
        },
      }
    )
    const saved = await renameSeminarBackgroundFile(props.sessionId, file.id, value.trim())
    upsertSeminarServerArtifact(saved)
    bumpSeminarFolderReload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function pinArtifact(file: SeminarBackgroundFile): Promise<void> {
  try {
    const saved = await pinSeminarBackgroundFile(props.sessionId, file.id, !file.pinned)
    upsertSeminarServerArtifact(saved)
    bumpSeminarFolderReload()
  } catch (error) {
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function deleteArtifact(file: SeminarBackgroundFile): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('mindmate.folder.deleteConfirm', { name: file.filename }),
      t('mindmate.folder.delete'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      }
    )
    await deleteSeminarBackgroundFile(props.sessionId, file.id)
    dropSeminarServerArtifact(file.id)
    closeSeminarDoc(seminarFileDocId(file.id))
    bumpSeminarFolderReload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function onArtifactCommand(command: string, doc: SeminarDocumentArtifact): Promise<void> {
  const file = artifactFile(doc)
  if (!file) {
    return
  }
  if (command === 'rename') {
    await renameArtifact(file)
    return
  }
  if (command === 'pin') {
    await pinArtifact(file)
    return
  }
  if (command === 'delete') {
    await deleteArtifact(file)
  }
}

function citeDocument(doc: SeminarDocumentArtifact): void {
  citeSeminarFile({
    fileId: doc.backgroundFileId || `doc:${doc.id}`,
    filename: doc.title,
    contentType: 'application/octet-stream',
    sizeBytes: 0,
  })
  notify.successKey('mindmate.docViewer.cited')
}

function openDiagram(previewId: string, label: string, imagePath: string): void {
  if (!imagePath) {
    openSeminarDoc({
      id: `canvas:${previewId}`,
      kind: 'diagram',
      title: diagramLabel(label),
      diagramId: previewId,
    })
    return
  }
  openSeminarDoc({
    id: seminarDiagramDocId(previewId),
    kind: 'diagram',
    title: diagramLabel(label),
    previewId,
    imagePath,
  })
}

function citeDiagram(label: string, imagePath: string): void {
  citeSeminarFile({
    fileId: `diagram:${imagePath}`,
    filename: diagramLabel(label),
    contentType: 'image/png',
    sizeBytes: 0,
  })
  notify.successKey('mindmate.docViewer.cited')
}

async function saveDiagram(previewId: string): Promise<void> {
  if (!props.sessionId || savingId.value) {
    return
  }
  savingId.value = previewId
  try {
    const result = await saveCollabDiagramToLibrary(props.sessionId, previewId)
    if (result.ok) {
      savedIds.value = [...savedIds.value, previewId]
      notify.successKey('mindmate.artifacts.saved')
      return
    }
    notify.errorKey(collabDiagramSaveFailureKey(result.reason))
  } finally {
    savingId.value = ''
  }
}
</script>

<template>
  <aside
    class="mm-artifact-side"
    :class="{ 'is-embedded': embedded }"
    :aria-label="t('mindmate.artifacts.title')"
  >
    <header
      v-if="!embedded"
      class="mm-artifact-side__header"
    >
      <h2 class="mm-artifact-side__title">
        <I18nText k="mindmate.artifacts.title" />
      </h2>
      <button
        type="button"
        class="mm-artifact-side__close"
        :aria-label="t('common.close')"
        @click="emit('close')"
      >
        <X
          :size="16"
          aria-hidden="true"
        />
      </button>
    </header>

    <section class="mm-artifact-side__section">
      <button
        type="button"
        class="mm-artifact-side__heading"
        :aria-expanded="openSections.files"
        @click="toggleSection('files')"
      >
        <I18nText
          k="mindmate.artifacts.files"
          dense
        />
        <ChevronDown
          :size="14"
          class="mm-artifact-side__chevron"
          :class="{ 'is-closed': !openSections.files }"
        />
      </button>
      <p
        v-if="openSections.files && documents.length === 0"
        class="mm-artifact-side__empty"
      >
        <I18nText k="mindmate.artifacts.emptyFiles" />
      </p>
      <ul
        v-else-if="openSections.files"
        class="mm-artifact-side__list"
      >
        <li
          v-for="doc in documents"
          :key="doc.id"
          class="mm-artifact-side__file-row"
        >
          <button
            type="button"
            class="mm-artifact-side__file"
            @click="openDocument(doc)"
          >
            <FileText
              :size="15"
              class="mm-artifact-side__file-icon"
              aria-hidden="true"
            />
            <span class="mm-artifact-side__file-meta">
              <span class="mm-artifact-side__name">{{ doc.title }}</span>
            </span>
            <ExternalLink
              v-if="doc.url"
              :size="13"
              class="mm-artifact-side__ext"
              aria-hidden="true"
            />
          </button>
          <button
            v-if="!seminarSpectator"
            type="button"
            class="mm-artifact-side__cite"
            :aria-label="t('mindmate.docViewer.cite')"
            :title="t('mindmate.docViewer.cite')"
            @click="citeDocument(doc)"
          >
            <Quote
              :size="15"
              aria-hidden="true"
            />
          </button>
          <ElDropdown
            v-if="artifactFile(doc) && !seminarSpectator"
            trigger="click"
            @command="(command: string) => onArtifactCommand(command, doc)"
          >
            <button
              type="button"
              class="mm-artifact-side__cite"
              :aria-label="t('mindmate.folder.more')"
              @click.stop
            >
              <MoreHorizontal
                :size="16"
                aria-hidden="true"
              />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem command="rename">
                  <I18nText k="mindmate.folder.rename" />
                </ElDropdownItem>
                <ElDropdownItem command="pin">
                  <I18nText
                    :k="artifactFile(doc)?.pinned ? 'mindmate.folder.unpin' : 'mindmate.folder.pin'"
                  />
                </ElDropdownItem>
                <ElDropdownItem
                  command="delete"
                  divided
                >
                  <I18nText k="mindmate.folder.delete" />
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </li>
      </ul>
    </section>

    <section class="mm-artifact-side__section">
      <button
        type="button"
        class="mm-artifact-side__heading"
        :aria-expanded="openSections.diagrams"
        @click="toggleSection('diagrams')"
      >
        <I18nText
          k="mindmate.artifacts.diagrams"
          dense
        />
        <ChevronDown
          :size="14"
          class="mm-artifact-side__chevron"
          :class="{ 'is-closed': !openSections.diagrams }"
        />
      </button>
      <p
        v-if="openSections.diagrams && diagrams.length === 0"
        class="mm-artifact-side__empty"
      >
        <I18nText k="mindmate.artifacts.emptyDiagrams" />
      </p>
      <ul
        v-else-if="openSections.diagrams"
        class="mm-artifact-side__list"
      >
        <li
          v-for="item in diagrams"
          :key="item.previewId"
          class="mm-artifact-side__row"
        >
          <button
            type="button"
            class="mm-artifact-side__open"
            @click="openDiagram(item.previewId, item.label, item.imagePath)"
          >
            <img
              v-if="item.imagePath"
              class="mm-artifact-side__thumb"
              :src="item.imagePath"
              :alt="diagramLabel(item.label)"
            />
            <span class="mm-artifact-side__name">{{ diagramLabel(item.label) }}</span>
          </button>
          <button
            v-if="!seminarSpectator"
            type="button"
            class="mm-artifact-side__cite"
            :aria-label="t('mindmate.docViewer.cite')"
            :title="t('mindmate.docViewer.cite')"
            @click="citeDiagram(item.label, item.imagePath)"
          >
            <Quote
              :size="15"
              aria-hidden="true"
            />
          </button>
          <ElButton
            size="small"
            text
            :disabled="isSaved(item.previewId) || savingId === item.previewId"
            @click="saveDiagram(item.previewId)"
          >
            <I18nText
              v-if="isSaved(item.previewId)"
              k="mindmate.artifacts.saved"
              dense
            />
            <I18nText
              v-else
              k="mindmate.artifacts.saveToLibrary"
              dense
            />
          </ElButton>
        </li>
      </ul>
    </section>

    <section class="mm-artifact-side__section">
      <button
        type="button"
        class="mm-artifact-side__heading"
        :aria-expanded="openSections.transcripts"
        @click="toggleSection('transcripts')"
      >
        <I18nText
          k="mindmate.artifacts.transcripts"
          dense
        />
        <ChevronDown
          :size="14"
          class="mm-artifact-side__chevron"
          :class="{ 'is-closed': !openSections.transcripts }"
        />
      </button>
      <p
        v-show="openSections.transcripts"
        class="mm-artifact-side__empty"
      >
        <I18nText k="mindmate.artifacts.emptyTranscripts" />
      </p>
    </section>
  </aside>
</template>

<style scoped>
.mm-artifact-side {
  display: flex;
  flex-direction: column;
  width: 300px;
  max-width: 38vw;
  min-width: 0;
  min-height: 0;
  height: 100%;
  border-left: 1px solid #e9e5ff;
  background: #fff;
  overflow: auto;
  box-shadow: -8px 0 24px rgba(109, 94, 252, 0.05);
}

.mm-artifact-side.is-embedded {
  width: 100%;
  max-width: none;
  border-left: none;
  box-shadow: none;
  background: transparent;
}

.mm-artifact-side__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #f3f0ff;
}

.mm-artifact-side__title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: #1c1917;
}

.mm-artifact-side__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.mm-artifact-side__close:hover {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-artifact-side__section {
  padding: 10px 16px 14px;
  border-top: 1px solid #f5f3ff;
}

.mm-artifact-side__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  margin: 0 0 8px;
  padding: 0;
  border: none;
  background: transparent;
  color: #57534e;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.02em;
  cursor: pointer;
}

.mm-artifact-side__chevron {
  transition: transform 0.15s ease;
}

.mm-artifact-side__chevron.is-closed {
  transform: rotate(-90deg);
}

.mm-artifact-side__empty {
  margin: 0;
  padding: 8px 0;
  color: #a8a29e;
  font-size: 12px;
  line-height: 1.4;
}

.mm-artifact-side__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mm-artifact-side__file-row,
.mm-artifact-side__row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.mm-artifact-side__file,
.mm-artifact-side__open {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: 10px;
  background: #fafaf9;
  color: #1c1917;
  text-align: left;
  cursor: pointer;
}

.mm-artifact-side__file:hover,
.mm-artifact-side__open:hover {
  background: #f5f3ff;
}

.mm-artifact-side__file-icon {
  flex-shrink: 0;
  color: #6d5efc;
}

.mm-artifact-side__file-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-artifact-side__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}

.mm-artifact-side__ext {
  flex-shrink: 0;
  color: #a8a29e;
}

.mm-artifact-side__thumb {
  flex-shrink: 0;
  width: 56px;
  height: 40px;
  object-fit: cover;
  object-position: left center;
  border-radius: 7px;
  background: #fff;
  border: 1px solid #e7e5e4;
}

.mm-artifact-side__cite {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.mm-artifact-side__cite:hover {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-artifact-side__more {
  flex-shrink: 0;
  height: 28px;
  padding: 0 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6d5efc;
  font-size: 12px;
  cursor: pointer;
}

.mm-artifact-side__more:hover {
  background: #f5f3ff;
}
</style>
