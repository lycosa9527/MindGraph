<script setup lang="ts">
/**
 * Full-screen caption editor for one library-demo slide.
 * Font, size, emphasis, and lists are written into sanitized HTML.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { Bold, Italic, List, ListOrdered, Underline } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import DemoStoneSelect from '@/components/demo/DemoStoneSelect.vue'
import { useLanguage } from '@/composables'
import {
  DEMO_FONT_COLORS,
  DEMO_FONT_FACES,
  DEMO_FONT_SIZES,
  type DemoCaptionDraft,
  type DemoFontColor,
  type DemoFontFace,
  type DemoFontSize,
  demoCaptionHtml,
  demoFontColor,
  demoFontFamily,
  isDemoFontSize,
  sanitizeDemoCaptionHtml,
} from '@/composables/demo/demoCaptionDefaults'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  draft: DemoCaptionDraft | null
  diagramTitle: string
}>()

const emit = defineEmits<{ save: [draft: DemoCaptionDraft] }>()

const { t } = useLanguage()
const surface = ref<HTMLElement | null>(null)
const face = ref<DemoFontFace>('sans')
const size = ref<DemoFontSize>(18)
const color = ref<DemoFontColor>('ink')

const faceLabel: Record<DemoFontFace, string> = {
  sans: 'sidebar.demo.fontSans',
  sc: 'sidebar.demo.fontSc',
  tc: 'sidebar.demo.fontTc',
  serif: 'sidebar.demo.fontSerif',
  song: 'sidebar.demo.fontSong',
  kai: 'sidebar.demo.fontKai',
  mono: 'sidebar.demo.fontMono',
}

const faceOptions = computed(() =>
  DEMO_FONT_FACES.map((item) => ({
    value: item,
    label: t(faceLabel[item]),
    labelKey: faceLabel[item],
    fontFamily: demoFontFamily(item),
  }))
)

const sizeOptions = computed(() =>
  DEMO_FONT_SIZES.map((item) => ({ value: String(item), label: String(item) }))
)

const colorLabel: Record<DemoFontColor, string> = {
  ink: 'sidebar.demo.colorInk',
  stone: 'sidebar.demo.colorStone',
  brown: 'sidebar.demo.colorBrown',
  red: 'sidebar.demo.colorRed',
  blue: 'sidebar.demo.colorBlue',
  green: 'sidebar.demo.colorGreen',
}

const colorOptions = computed(() =>
  DEMO_FONT_COLORS.map((item) => ({
    value: item,
    label: t(colorLabel[item]),
    labelKey: colorLabel[item],
    swatch: demoFontColor(item),
  }))
)

watch(visible, (open) => {
  if (!open || !props.draft) return
  face.value = props.draft.fontFace
  size.value = props.draft.fontSize
  color.value = props.draft.fontColor
  void nextTick(() => {
    void nextTick(() => {
      const node = surface.value
      if (!node || !props.draft) return
      node.innerHTML = demoCaptionHtml(props.draft)
      node.focus()
    })
  })
})

function keepSelection(event: MouseEvent): void {
  event.preventDefault()
}

function focusSurface(): void {
  surface.value?.focus()
}

function runCommand(command: string): void {
  focusSurface()
  document.execCommand('styleWithCSS', false, 'true')
  document.execCommand(command)
}

function wrapSelection(style: Partial<CSSStyleDeclaration>): void {
  const selection = window.getSelection()
  const node = surface.value
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed || !node) return
  if (!node.contains(selection.anchorNode)) return
  const range = selection.getRangeAt(0)
  const span = document.createElement('span')
  Object.assign(span.style, style)
  try {
    range.surroundContents(span)
  } catch {
    span.appendChild(range.extractContents())
    range.insertNode(span)
  }
  selection.removeAllRanges()
}

function setFace(next: DemoFontFace): void {
  face.value = next
  focusSurface()
  wrapSelection({ fontFamily: demoFontFamily(next) })
}

function setSize(next: DemoFontSize): void {
  size.value = next
  focusSurface()
  wrapSelection({ fontSize: `${next}px` })
}

function onFacePick(value: string): void {
  if (!(DEMO_FONT_FACES as readonly string[]).includes(value)) return
  setFace(value as DemoFontFace)
}

function onSizePick(value: string): void {
  const next = Number(value)
  if (!isDemoFontSize(next)) return
  setSize(next)
}

function setColor(next: DemoFontColor): void {
  color.value = next
  focusSurface()
  wrapSelection({ color: demoFontColor(next) })
}

function onColorPick(value: string): void {
  if (!(DEMO_FONT_COLORS as readonly string[]).includes(value)) return
  setColor(value as DemoFontColor)
}

function save(): void {
  const source = props.draft
  const node = surface.value
  if (!source || !node) return
  const html = sanitizeDemoCaptionHtml(node.innerHTML)
  const text = node.innerText.replace(/\u00a0/g, ' ').trim()
  emit('save', {
    text: text || source.text,
    html,
    fontSize: size.value,
    fontFace: face.value,
    fontColor: color.value,
  })
  visible.value = false
}
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    width="min(680px, 92vw)"
    top="8vh"
    :ribbon="t('sidebar.demo.edit')"
    ribbon-key="sidebar.demo.edit"
    :title="diagramTitle || t('sidebar.demo.edit')"
    :line1="t('sidebar.demo.editorLine')"
    line1-key="sidebar.demo.editorLine"
    dialog-class="demo-caption-editor"
  >
    <div
      class="demo-editor"
      :style="{
        fontFamily: demoFontFamily(face),
        fontSize: `${size}px`,
        color: demoFontColor(color),
      }"
    >
      <div class="demo-editor__bar">
        <label class="demo-editor__font">
          <I18nText k="sidebar.demo.font" />
          <DemoStoneSelect
            compact
            preserve-selection
            :model-value="face"
            :options="faceOptions"
            :placeholder="t(faceLabel[face])"
            :menu-label="t('sidebar.demo.font')"
            @update:model-value="onFacePick"
          />
        </label>
        <label class="demo-editor__font">
          <I18nText k="sidebar.demo.fontSize" />
          <DemoStoneSelect
            narrow
            preserve-selection
            :model-value="String(size)"
            :options="sizeOptions"
            :placeholder="String(size)"
            :menu-label="t('sidebar.demo.fontSize')"
            @update:model-value="onSizePick"
          />
        </label>
        <label class="demo-editor__font">
          <I18nText k="sidebar.demo.fontColor" />
          <DemoStoneSelect
            mid
            preserve-selection
            :model-value="color"
            :options="colorOptions"
            :placeholder="t(colorLabel[color])"
            :menu-label="t('sidebar.demo.fontColor')"
            @update:model-value="onColorPick"
          />
        </label>
        <div class="demo-editor__tools">
          <button
            type="button"
            class="demo-editor__icon"
            :aria-label="t('sidebar.demo.bold')"
            @mousedown="keepSelection"
            @click="runCommand('bold')"
          >
            <Bold class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="demo-editor__icon"
            :aria-label="t('sidebar.demo.italic')"
            @mousedown="keepSelection"
            @click="runCommand('italic')"
          >
            <Italic class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="demo-editor__icon"
            :aria-label="t('sidebar.demo.underline')"
            @mousedown="keepSelection"
            @click="runCommand('underline')"
          >
            <Underline class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="demo-editor__icon"
            :aria-label="t('sidebar.demo.bullets')"
            @mousedown="keepSelection"
            @click="runCommand('insertUnorderedList')"
          >
            <List class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="demo-editor__icon"
            :aria-label="t('sidebar.demo.numbered')"
            @mousedown="keepSelection"
            @click="runCommand('insertOrderedList')"
          >
            <ListOrdered class="h-4 w-4" />
          </button>
        </div>
      </div>
      <div
        ref="surface"
        class="demo-editor__surface"
        contenteditable="true"
        role="textbox"
        aria-multiline="true"
      />
    </div>
    <template #footer>
      <button
        type="button"
        class="demo-editor__done"
        @click="save"
      >
        <I18nText k="sidebar.demo.done" />
      </button>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.demo-editor__bar {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
  overflow: visible;
}

.demo-editor__font {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: #57534e;
  white-space: nowrap;
}

.demo-editor__tools {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
}

.demo-editor__icon {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: #fff;
  color: #1c1917;
  cursor: pointer;
}

.demo-editor__surface:focus {
  border-color: #1c1917;
  box-shadow: inset 0 0 0 1px #1c1917;
}

.demo-editor__icon:hover {
  border-color: #1c1917;
}

.demo-editor__surface {
  position: relative;
  z-index: 1;
  min-height: 16rem;
  max-height: min(52vh, 28rem);
  overflow: auto;
  padding: 1rem 1.1rem;
  border: 1px solid #e7e5e4;
  border-radius: 1rem;
  background: #fff;
  color: inherit;
  line-height: 1.65;
  outline: none;
}

.demo-editor__icon:focus-visible,
.demo-editor__done:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px #1c1917;
}

.demo-editor__surface :deep(ul),
.demo-editor__surface :deep(ol) {
  margin: 0.35rem 0 0.35rem 1.25rem;
  padding: 0;
}

.demo-editor__done {
  border: 0;
  border-radius: 999px;
  padding: 0.55rem 1.1rem;
  background: #1c1917;
  color: #fafaf9;
  cursor: pointer;
}
</style>
