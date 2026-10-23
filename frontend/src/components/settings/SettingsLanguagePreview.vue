<script setup lang="ts">
/**
 * Live sample of the mind-map toolbar and a short branch.
 * Both show the interface language, plus a smaller second line when bilingual is on.
 * With bilingual off, the nodes stay one line in the AI language.
 */
import { type Component, computed, watch } from 'vue'

import { Trash2, Undo2 } from '@lucide/vue'

import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { hasLazyLocaleBundle, loadLocaleMessages, localeCatalogRevision } from '@/i18n'
import {
  PROMPT_LANGUAGE_OPTIONS,
  htmlLangForUiCode,
  isRtlUiLocale,
  isUiLocale,
} from '@/i18n/locales'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import type { Language } from '@/stores/ui'
import { MULTISCRIPT_SANS_STACK } from '@/utils/diagramNodeFontStack'

const previewFontFamily = MULTISCRIPT_SANS_STACK

const props = defineProps<{
  uiLocale: Language
  presenterLocale: Language
  bilingual: boolean
  contentLocale: string
}>()

const TOOLS: { id: string; icon: Component; key: string }[] = [
  { id: 'undo', icon: Undo2, key: 'canvas.toolbar.undo' },
  { id: 'delete', icon: Trash2, key: 'canvas.toolbar.deleteNode' },
]

const NODE_KEYS = {
  topic: 'diagram.defaults.centralTopic',
  branchA: 'diagram.defaults.topicA',
  branchB: 'diagram.defaults.topicB',
} as const

/** Prompt registry `zh-hant` is the Traditional Chinese UI bundle. */
function uiCodeFor(code: string): Language | null {
  if (code === 'zh-hant') {
    return 'zh-tw'
  }
  if (isUiLocale(code) && (code === 'en' || hasLazyLocaleBundle(code))) {
    return code
  }
  return null
}

function translated(key: string, locale: string): string | null {
  void localeCatalogRevision.value
  const ui = uiCodeFor(locale)
  if (ui === null) {
    return null
  }
  return translateForUiLocale(key, ui)
}

const toolbarDir = computed(() => (isRtlUiLocale(props.uiLocale) ? 'rtl' : 'ltr'))

const presenterDir = computed(() => (isRtlUiLocale(props.presenterLocale) ? 'rtl' : 'ltr'))

const tools = computed(() =>
  TOOLS.map((tool) => {
    const primary = translated(tool.key, props.uiLocale) ?? tool.key
    const other =
      props.bilingual && props.presenterLocale !== props.uiLocale
        ? translated(tool.key, props.presenterLocale)
        : null
    return {
      id: tool.id,
      icon: tool.icon,
      primary,
      secondary: other !== null && other !== primary ? other : '',
    }
  })
)

const contentUi = computed(() => uiCodeFor(props.contentLocale))

const contentDir = computed(() => {
  const ui = contentUi.value
  if (ui !== null && isRtlUiLocale(ui)) {
    return 'rtl'
  }
  return 'ltr'
})

const contentLang = computed(() => {
  const ui = contentUi.value
  return ui !== null ? htmlLangForUiCode(ui) : props.contentLocale
})

function registryField(field: 'label' | 'englishName' | 'code'): string {
  const row = PROMPT_LANGUAGE_OPTIONS.find((option) => option.code === props.contentLocale)
  if (!row) {
    return props.contentLocale
  }
  return row[field]
}

function nodeText(key: string, fallback: 'label' | 'englishName' | 'code'): string {
  return translated(key, props.contentLocale) ?? registryField(fallback)
}

function dualLine(
  key: string,
  fallback: 'label' | 'englishName' | 'code'
): { primary: string; secondary: string } {
  const primary = props.bilingual
    ? (translated(key, props.uiLocale) ?? nodeText(key, fallback))
    : nodeText(key, fallback)
  const other =
    props.bilingual && props.presenterLocale !== props.uiLocale
      ? translated(key, props.presenterLocale)
      : null
  return {
    primary,
    secondary: other !== null && other !== primary ? other : '',
  }
}

const topicLine = computed(() => dualLine(NODE_KEYS.topic, 'label'))
const branchALine = computed(() => dualLine(NODE_KEYS.branchA, 'englishName'))
const branchBLine = computed(() => dualLine(NODE_KEYS.branchB, 'code'))

watch(
  () => [props.uiLocale, props.presenterLocale, props.contentLocale] as const,
  (codes) => {
    const seen = new Set<string>()
    for (const code of codes) {
      if (seen.has(code)) {
        continue
      }
      seen.add(code)
      const ui = uiCodeFor(code)
      if (ui !== null) {
        void loadLocaleMessages(ui)
      }
      void ensureFontsForLanguageCode(code)
    }
  },
  { immediate: true }
)
</script>

<template>
  <div
    class="language-settings-preview"
    aria-hidden="true"
  >
    <div
      class="language-settings-preview__toolbar"
      :dir="toolbarDir"
      :lang="uiLocale"
    >
      <div
        v-for="tool in tools"
        :key="tool.id"
        class="language-settings-preview__tool"
      >
        <component
          :is="tool.icon"
          class="language-settings-preview__icon"
        />
        <span class="language-settings-preview__copy">
          <span class="language-settings-preview__primary">{{ tool.primary }}</span>
          <span
            v-if="tool.secondary"
            class="language-settings-preview__secondary"
            :dir="presenterDir"
            >{{ tool.secondary }}</span
          >
        </span>
      </div>
    </div>
    <div
      class="language-settings-preview__canvas"
      :dir="bilingual ? toolbarDir : contentDir"
      :lang="bilingual ? uiLocale : contentLang"
    >
      <div class="language-settings-preview__map">
        <div class="language-settings-preview__topic">
          <span class="language-settings-preview__primary">{{ topicLine.primary }}</span>
          <span
            v-if="topicLine.secondary"
            class="language-settings-preview__secondary"
            :dir="presenterDir"
            >{{ topicLine.secondary }}</span
          >
        </div>
        <div class="language-settings-preview__branches">
          <div class="language-settings-preview__row">
            <div class="language-settings-preview__branch">
              <span class="language-settings-preview__primary">{{ branchALine.primary }}</span>
              <span
                v-if="branchALine.secondary"
                class="language-settings-preview__secondary"
                :dir="presenterDir"
                >{{ branchALine.secondary }}</span
              >
            </div>
          </div>
          <div class="language-settings-preview__row">
            <div class="language-settings-preview__branch">
              <span class="language-settings-preview__primary">{{ branchBLine.primary }}</span>
              <span
                v-if="branchBLine.secondary"
                class="language-settings-preview__secondary"
                :dir="presenterDir"
                >{{ branchBLine.secondary }}</span
              >
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.language-settings-preview {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 1px solid var(--lang-settings-border);
  border-radius: 8px;
  background: var(--lang-settings-inset, #fafaf9);
  overflow: hidden;
  font-family: v-bind(previewFontFamily);
}

.language-settings-preview__toolbar {
  display: flex;
  flex-wrap: nowrap;
  justify-content: center;
  gap: 1.25rem;
  padding: 0.45rem;
  background: var(--lang-settings-surface, #ffffff);
  border-bottom: 1px solid var(--lang-settings-border);
}

.language-settings-preview__tool {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  gap: 0.2rem;
  padding: 0.1rem 0.15rem;
  border-radius: 4px;
  color: var(--lang-settings-body, #44403c);
}

.language-settings-preview__icon {
  width: 0.75rem;
  height: 0.75rem;
  margin-top: 0.05rem;
  flex-shrink: 0;
}

.language-settings-preview__copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.15;
}

.language-settings-preview__primary {
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}

.language-settings-preview__secondary {
  font-size: 0.625rem;
  font-weight: 400;
  line-height: 1.15;
  opacity: 0.7;
  white-space: nowrap;
}

.language-settings-preview__toolbar .language-settings-preview__primary {
  font-size: 0.6875rem;
}

.language-settings-preview__toolbar .language-settings-preview__secondary {
  font-size: 0.5625rem;
}

.language-settings-preview__canvas {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 0.85rem 0.55rem;
}

.language-settings-preview__map {
  --preview-link: 0.9rem;
  display: flex;
  align-items: center;
  width: max-content;
  max-width: 100%;
  gap: var(--preview-link);
}

.language-settings-preview__topic,
.language-settings-preview__branch {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.4rem 0.55rem;
  border-radius: 999px;
  text-align: center;
}

.language-settings-preview__topic {
  position: relative;
  flex: 0 1 auto;
  background: var(--lang-settings-ink, #1c1917);
  color: var(--lang-settings-surface, #ffffff);
}

.language-settings-preview__topic::after {
  content: '';
  position: absolute;
  inset-inline-end: calc(var(--preview-link) * -1);
  top: 50%;
  width: var(--preview-link);
  height: 1px;
  background: var(--lang-settings-subtle, #a8a29e);
  transform: translateY(-50%);
}

.language-settings-preview__branches {
  --preview-arm: 0.7rem;
  --preview-branch-gap: 1rem;
  display: flex;
  flex: 0 1 auto;
  flex-direction: column;
  gap: var(--preview-branch-gap);
  min-width: 0;
}

.language-settings-preview__row {
  position: relative;
  display: flex;
  align-items: center;
  padding-inline-start: var(--preview-arm);
}

.language-settings-preview__row::before {
  content: '';
  position: absolute;
  inset-inline-start: 0;
  width: 1px;
  background: var(--lang-settings-subtle, #a8a29e);
}

.language-settings-preview__row:first-child::before {
  top: 50%;
  bottom: calc(var(--preview-branch-gap) * -0.5);
}

.language-settings-preview__row:last-child::before {
  top: calc(var(--preview-branch-gap) * -0.5);
  bottom: 50%;
}

.language-settings-preview__row::after {
  content: '';
  position: absolute;
  inset-inline-start: 0;
  top: 50%;
  width: var(--preview-arm);
  height: 1px;
  background: var(--lang-settings-subtle, #a8a29e);
  transform: translateY(-50%);
}

.language-settings-preview__branch {
  flex: 0 1 auto;
  background: var(--lang-settings-surface, #ffffff);
  color: var(--lang-settings-ink, #1c1917);
  border: 1px solid var(--lang-settings-border-strong, #d6d3d1);
  font-weight: 500;
}
</style>
