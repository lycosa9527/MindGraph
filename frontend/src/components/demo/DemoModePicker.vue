<script setup lang="ts">
/**
 * Two-column demo builder: library on the left, saved playlist on the right.
 */
import { computed, ref, watch } from 'vue'

import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Pencil,
  Presentation,
  Search,
} from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import DemoCaptionEditor from '@/components/demo/DemoCaptionEditor.vue'
import DemoStoneSelect from '@/components/demo/DemoStoneSelect.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { type DemoCaptionDraft, seedDemoCaption } from '@/composables/demo/demoCaptionDefaults'
import { type DemoListRecord, upsertDemoList } from '@/composables/demo/demoLists'
import {
  type LibraryDemoDocument,
  loadLibraryDemo,
  saveLibraryDemo,
} from '@/composables/demo/libraryDemoApi'
import { useDemoListThumbnails } from '@/composables/demo/useDemoListThumbnails'
import { type DemoDeckSlide, useLibraryDemo } from '@/composables/demo/useLibraryDemo'
import { getDiagramTypeDisplayName } from '@/composables/editor/useDiagramLabels'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const { t, currentLanguage } = useLanguage()
const savedDiagrams = useSavedDiagramsStore()
const { pickerOpen, closePicker, startDeck, claimFullscreen, releaseFullscreen } = useLibraryDemo()
const { thumbnails, renderingId, listThumb, publish, cancel } = useDemoListThumbnails()

const searchQuery = ref('')
const demoIds = ref<string[]>([])
const libraryFocusId = ref<string | null>(null)
const demoFocusId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const editorOpen = ref(false)
const drafts = ref<Record<string, DemoCaptionDraft>>({})
const lists = ref<DemoListRecord[]>([])
const activeListId = ref('')
const listName = ref('')
const nameMissing = ref(false)
const savedFlash = ref(false)
const saveFailed = ref(false)
const ready = ref(false)
const loadToken = ref(0)
let saveChain = Promise.resolve()

const libraryRows = computed(() => {
  const taken = new Set(demoIds.value)
  const query = searchQuery.value.trim().toLowerCase()
  return savedDiagrams.diagrams.filter((diagram) => {
    if (taken.has(diagram.id)) return false
    if (!query) return true
    return diagram.title.toLowerCase().includes(query)
  })
})

const demoRows = computed(() =>
  demoIds.value
    .map((id) => savedDiagrams.diagrams.find((diagram) => diagram.id === id))
    .filter((diagram): diagram is SavedDiagram => diagram !== undefined)
)

const editingDiagram = computed(
  () => savedDiagrams.diagrams.find((diagram) => diagram.id === editingId.value) ?? null
)

const editingDraft = computed(() => {
  const id = editingId.value
  if (!id) return null
  return drafts.value[id] ?? null
})

const listOptions = computed(() => [
  { value: '', label: t('sidebar.demo.listNew'), labelKey: 'sidebar.demo.listNew' },
  ...lists.value.map((list) => ({ value: list.id, label: list.name })),
])

watch(pickerOpen, (open) => {
  if (!open) {
    cancel()
    if (ready.value) saveList(false)
    ready.value = false
    return
  }
  const token = loadToken.value + 1
  loadToken.value = token
  ready.value = false
  searchQuery.value = ''
  libraryFocusId.value = null
  demoFocusId.value = null
  editingId.value = null
  editorOpen.value = false
  nameMissing.value = false
  savedFlash.value = false
  thumbnails.value = {}
  saveFailed.value = false
  void loadDeck(token)
  void savedDiagrams.fetchDiagrams(1, 50, { force: true })
})

async function loadDeck(token: number): Promise<void> {
  try {
    const document = await loadLibraryDemo()
    if (token !== loadToken.value || !pickerOpen.value) return
    drafts.value = document.captions
    thumbnails.value = document.thumbnails
    lists.value = document.lists
    applyList(document.lists.find((list) => list.id === document.lastId) ?? null)
    ready.value = true
  } catch {
    if (token !== loadToken.value || !pickerOpen.value) return
    saveFailed.value = true
  }
}

function applyList(list: DemoListRecord | null): void {
  activeListId.value = list?.id ?? ''
  listName.value = list?.name ?? ''
  demoIds.value = list ? [...list.diagramIds] : []
  if (list) {
    drafts.value = { ...drafts.value, ...list.captions }
  }
  demoFocusId.value = null
  libraryFocusId.value = null
}

function persistDocument(force = false): void {
  if (!ready.value && !force) return
  const snapshot = JSON.parse(
    JSON.stringify({
      lists: lists.value,
      lastId: activeListId.value || null,
      captions: drafts.value,
      thumbnails: thumbnails.value,
    })
  ) as LibraryDemoDocument
  saveChain = saveChain
    .then(async () => {
      await saveLibraryDemo(snapshot)
      saveFailed.value = false
    })
    .catch(() => {
      saveFailed.value = true
    })
}

function ensureDraft(diagram: SavedDiagram): DemoCaptionDraft {
  const existing = drafts.value[diagram.id]
  if (existing) return existing
  const seeded = seedDemoCaption(
    diagram.diagram_type,
    diagram.title,
    (key, params) => t(key, params),
    undefined
  )
  drafts.value = { ...drafts.value, [diagram.id]: seeded }
  return seeded
}

function onPickListId(id: string): void {
  if (id === activeListId.value) return
  savedFlash.value = false
  saveList(false)
  const list = lists.value.find((item) => item.id === id) ?? null
  applyList(list)
}

function focusLibrary(diagram: SavedDiagram): void {
  libraryFocusId.value = diagram.id
  demoFocusId.value = null
}

function focusDemo(diagram: SavedDiagram): void {
  demoFocusId.value = diagram.id
  libraryFocusId.value = null
}

function moveIn(): void {
  const id = libraryFocusId.value
  if (!id || demoIds.value.includes(id)) return
  demoIds.value = [...demoIds.value, id]
  demoFocusId.value = id
  libraryFocusId.value = null
  savedFlash.value = false
}

function moveOut(): void {
  const id = demoFocusId.value
  if (!id) return
  demoIds.value = demoIds.value.filter((item) => item !== id)
  libraryFocusId.value = id
  demoFocusId.value = null
  savedFlash.value = false
}

function shiftDemo(delta: number): void {
  const id = demoFocusId.value
  if (!id) return
  const index = demoIds.value.indexOf(id)
  const next = index + delta
  if (index < 0 || next < 0 || next >= demoIds.value.length) return
  const copy = [...demoIds.value]
  const current = copy[index]
  const neighbor = copy[next]
  if (!current || !neighbor) return
  copy[index] = neighbor
  copy[next] = current
  demoIds.value = copy
  savedFlash.value = false
}

function openEditor(diagram: SavedDiagram): void {
  focusDemo(diagram)
  ensureDraft(diagram)
  editingId.value = diagram.id
  editorOpen.value = true
}

function onSaveCaption(next: DemoCaptionDraft): void {
  const id = editingId.value
  if (!id) return
  drafts.value = { ...drafts.value, [id]: next }
  const listId = activeListId.value
  if (listId) {
    lists.value = lists.value.map((list) =>
      list.id === listId ? { ...list, captions: { ...list.captions, [id]: next } } : list
    )
  }
  persistDocument()
}

function captionsForList(ids: string[]): Record<string, DemoCaptionDraft> {
  const captions: Record<string, DemoCaptionDraft> = {}
  for (const id of ids) {
    const diagram = savedDiagrams.diagrams.find((item) => item.id === id)
    if (diagram) {
      captions[id] = ensureDraft(diagram)
      continue
    }
    const existing = drafts.value[id]
    if (existing) captions[id] = existing
  }
  return captions
}

function saveList(requireName = true, announce = requireName): boolean {
  const name = listName.value.trim()
  if (!name) {
    if (requireName) nameMissing.value = true
    return false
  }
  nameMissing.value = false
  const diagramIds = [...demoIds.value]
  const list: DemoListRecord = {
    id: activeListId.value || crypto.randomUUID(),
    name,
    diagramIds,
    captions: captionsForList(diagramIds),
  }
  const stored = upsertDemoList({ lists: lists.value, lastId: list.id }, list)
  lists.value = stored.lists
  activeListId.value = list.id
  persistDocument()
  if (announce) savedFlash.value = true
  return true
}

function onSaveList(): void {
  if (!saveList()) return
  void publish(demoRows.value, () => persistDocument(true))
}

function start(): void {
  const slides: DemoDeckSlide[] = []
  for (const id of demoIds.value) {
    const diagram = savedDiagrams.diagrams.find((item) => item.id === id)
    if (!diagram) continue
    slides.push({
      id: diagram.id,
      title: diagram.title,
      diagramType: diagram.diagram_type,
      thumbnail: listThumb(diagram.id, diagram.thumbnail),
      caption: ensureDraft(diagram),
    })
  }
  if (slides.length === 0) return
  claimFullscreen()
  if (listName.value.trim()) saveList()
  persistDocument()
  void savedDiagrams.prefetchDiagramSpecs(
    slides.map((slide) => slide.id),
    slides.length
  )
  const chosen = demoRows.value
  void publish(chosen, () => persistDocument(true)).then((finished) => {
    if (!finished) {
      releaseFullscreen()
      return
    }
    startDeck(
      slides.map((slide) => ({
        ...slide,
        thumbnail: listThumb(slide.id, slide.thumbnail),
      }))
    )
  })
}

function typeLabel(diagram: SavedDiagram): string {
  return getDiagramTypeDisplayName(diagram.diagram_type, currentLanguage.value)
}
</script>

<template>
  <SwissGlassDialog
    v-model="pickerOpen"
    width="min(720px, 92vw)"
    top="6vh"
    :ribbon="t('sidebar.demo.ribbon')"
    ribbon-key="sidebar.demo.ribbon"
    :title="t('sidebar.demo.title')"
    title-key="sidebar.demo.title"
    :line1="t('sidebar.demo.line1')"
    line1-key="sidebar.demo.line1"
    :icon="Presentation"
    dialog-class="demo-picker-dialog"
    @close="closePicker"
  >
    <p
      v-if="!ready && !saveFailed"
      class="demo-picker__flash"
    >
      <I18nText k="sidebar.demo.loadingLists" />
    </p>
    <div
      class="demo-picker__bar"
      :class="{ 'is-busy': !ready }"
    >
      <DemoStoneSelect
        :model-value="activeListId"
        :options="listOptions"
        :placeholder="t('sidebar.demo.listNew')"
        :menu-label="t('sidebar.demo.listName')"
        @update:model-value="onPickListId"
      />
      <input
        v-model="listName"
        class="demo-picker__name"
        type="text"
        :placeholder="t('sidebar.demo.listName')"
        @input="nameMissing = false"
      />
      <button
        type="button"
        class="demo-picker__save"
        :class="{ 'is-rendering': renderingId }"
        @click="onSaveList"
      >
        <I18nText k="sidebar.demo.saveList" />
      </button>
      <span
        v-if="saveFailed"
        class="demo-picker__warn"
      >
        <I18nText k="sidebar.demo.saveFailed" />
      </span>
      <span
        v-else-if="savedFlash"
        class="demo-picker__flash"
      >
        <I18nText k="sidebar.demo.saved" />
      </span>
      <span
        v-else-if="nameMissing"
        class="demo-picker__warn"
      >
        <I18nText k="sidebar.demo.nameRequired" />
      </span>
    </div>

    <div
      class="demo-picker"
      :class="{ 'is-busy': !ready }"
    >
      <section class="demo-picker__col">
        <h3 class="demo-picker__heading">
          <I18nText k="sidebar.demo.library" />
        </h3>
        <div class="demo-picker__search">
          <Search class="demo-picker__search-icon" />
          <input
            v-model="searchQuery"
            type="search"
            :placeholder="t('sidebar.demo.search')"
          />
        </div>
        <p
          v-if="libraryRows.length === 0"
          class="demo-picker__empty"
        >
          <I18nText k="sidebar.demo.empty" />
        </p>
        <ul v-else>
          <li
            v-for="diagram in libraryRows"
            :key="diagram.id"
          >
            <button
              type="button"
              class="demo-picker__row"
              :class="{ 'is-hot': diagram.id === libraryFocusId }"
              @click="focusLibrary(diagram)"
            >
              <img
                v-if="listThumb(diagram.id, diagram.thumbnail)"
                :src="listThumb(diagram.id, diagram.thumbnail) ?? undefined"
                alt=""
                class="demo-picker__thumb"
              />
              <span
                v-else
                class="demo-picker__thumb"
              />
              <span class="demo-picker__meta">
                <span class="demo-picker__title">{{ diagram.title }}</span>
                <span class="demo-picker__type">{{ typeLabel(diagram) }}</span>
              </span>
            </button>
          </li>
        </ul>
      </section>

      <div class="demo-picker__shuttle">
        <button
          type="button"
          :disabled="!libraryFocusId"
          :aria-label="t('sidebar.demo.moveIn')"
          @click="moveIn"
        >
          <ChevronRight class="h-4 w-4" />
        </button>
        <button
          type="button"
          :disabled="!demoFocusId"
          :aria-label="t('sidebar.demo.moveOut')"
          @click="moveOut"
        >
          <ChevronLeft class="h-4 w-4" />
        </button>
        <button
          type="button"
          :disabled="!demoFocusId || demoIds.indexOf(demoFocusId) <= 0"
          :aria-label="t('sidebar.demo.moveUp')"
          @click="shiftDemo(-1)"
        >
          <ChevronUp class="h-4 w-4" />
        </button>
        <button
          type="button"
          :disabled="
            !demoFocusId ||
            demoIds.indexOf(demoFocusId) < 0 ||
            demoIds.indexOf(demoFocusId) >= demoIds.length - 1
          "
          :aria-label="t('sidebar.demo.moveDown')"
          @click="shiftDemo(1)"
        >
          <ChevronDown class="h-4 w-4" />
        </button>
      </div>

      <section class="demo-picker__col">
        <h3 class="demo-picker__heading">
          <I18nText k="sidebar.demo.deck" />
        </h3>
        <p
          v-if="demoRows.length === 0"
          class="demo-picker__empty"
        >
          <I18nText k="sidebar.demo.deckEmpty" />
        </p>
        <ul v-else>
          <li
            v-for="(diagram, index) in demoRows"
            :key="diagram.id"
          >
            <div
              class="demo-picker__row"
              :class="{
                'is-hot': diagram.id === demoFocusId,
                'is-rendering': renderingId === diagram.id,
              }"
            >
              <button
                type="button"
                class="demo-picker__main"
                @click="focusDemo(diagram)"
              >
                <span class="demo-picker__order">{{ index + 1 }}</span>
                <img
                  v-if="listThumb(diagram.id, diagram.thumbnail)"
                  :src="listThumb(diagram.id, diagram.thumbnail) ?? undefined"
                  alt=""
                  class="demo-picker__thumb"
                />
                <span
                  v-else
                  class="demo-picker__thumb"
                />
                <span class="demo-picker__meta">
                  <span class="demo-picker__title">{{ diagram.title }}</span>
                  <span class="demo-picker__type">{{ typeLabel(diagram) }}</span>
                </span>
              </button>
              <button
                type="button"
                class="demo-picker__edit"
                :aria-label="t('sidebar.demo.edit')"
                @click="openEditor(diagram)"
              >
                <Pencil class="h-4 w-4" />
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>
    <template #footer>
      <button
        type="button"
        class="demo-picker__start"
        :disabled="!ready || demoRows.length === 0"
        @click="start"
      >
        <I18nText k="sidebar.demo.start" />
        <span v-if="demoRows.length">
          <I18nText
            k="sidebar.demo.selected"
            :params="{ n: demoRows.length }"
          />
        </span>
      </button>
    </template>
  </SwissGlassDialog>
  <DemoCaptionEditor
    v-model="editorOpen"
    :draft="editingDraft"
    :diagram-title="editingDiagram?.title ?? ''"
    @save="onSaveCaption"
  />
</template>

<style scoped src="./demoPickerLayout.css"></style>
