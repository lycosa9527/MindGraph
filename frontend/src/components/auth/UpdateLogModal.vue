<script setup lang="ts">
/**
 * Modal showing the latest changelog entries from the server (CHANGELOG.md).
 * Geek / terminal-inspired presentation.
 */
import { computed, ref, watch } from 'vue'

import { ElDialog, ElScrollbar } from 'element-plus'

import MarkdownIt from 'markdown-it'

import { useLanguage } from '@/composables'
import { sanitizeMarkdownItHtml } from '@/composables/core/markdownKatexSanitize'
import { apiGet } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

interface ChangelogEntry {
  title: string
  body: string
}

const loading = ref(false)
const loadError = ref<string | null>(null)
const entries = ref<ChangelogEntry[]>([])

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
})

function renderMd(source: string): string {
  if (!source.trim()) return ''
  return sanitizeMarkdownItHtml(md.render(source))
}

async function fetchChangelog(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const res = await apiGet('/api/changelog/recent?limit=5')
    if (!res.ok) {
      loadError.value = t('auth.updateLogLoadError')
      entries.value = []
      return
    }
    const data = (await res.json()) as { entries?: ChangelogEntry[] }
    entries.value = Array.isArray(data.entries) ? data.entries : []
    if (entries.value.length === 0) {
      loadError.value = t('auth.updateLogEmpty')
    }
  } catch {
    loadError.value = t('auth.updateLogLoadError')
    entries.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      void fetchChangelog()
    }
  }
)
</script>

<template>
  <ElDialog
    v-model="isVisible"
    width="min(580px, 94vw)"
    append-to-body
    destroy-on-close
    class="update-log-dialog"
    modal-class="ulog-modal-backdrop"
    :show-close="true"
    align-center
    @closed="loadError = null"
  >
    <template #header>
      <div class="ulog-header">
        <span class="ulog-header__glyph">◇</span>
        <span class="ulog-header__title">{{ t('auth.updateLogModalTitle') }}</span>
        <span
          class="ulog-header__divider"
          aria-hidden="true"
          >·</span>
        <span class="ulog-header__note">{{ t('auth.updateLogMaintainerNote') }}</span>
      </div>
    </template>

    <div class="ulog-body-wrap">
      <div
        class="ulog-scanlines"
        aria-hidden="true"
      />

      <div
        v-if="loading"
        class="ulog-loading"
      >
        <span class="ulog-loading__prompt">&gt;</span>
        <span class="ulog-loading__text">{{ t('common.loading') }}</span>
        <span class="ulog-loading__cursor" />
      </div>
      <p
        v-else-if="loadError"
        class="ulog-error"
      >
        <span class="ulog-error__mark">[!]</span>
        {{ loadError }}
      </p>
      <ElScrollbar
        v-else
        class="ulog-scrollbar"
        max-height="58vh"
      >
        <div class="ulog-scroll-inner">
          <article
            v-for="(entry, idx) in entries"
            :key="idx"
            class="ulog-entry"
          >
            <div class="ulog-entry__bar">
              <span class="ulog-entry__idx">{{ String(idx + 1).padStart(2, '0') }}</span>
              <h3 class="ulog-entry__title">
                {{ entry.title }}
              </h3>
            </div>
            <div
              class="ulog-md"
              v-html="renderMd(entry.body)"
            />
          </article>
        </div>
      </ElScrollbar>
    </div>
  </ElDialog>
</template>

<style scoped>
.ulog-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.5rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    'Cascadia Code',
    'SFMono-Regular',
    Consolas,
    monospace;
}

.ulog-header__glyph {
  color: #22d3ee;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.55);
  font-size: 1rem;
  flex-shrink: 0;
}

.ulog-header__title {
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #e2e8f0;
  text-shadow:
    0 0 1px rgba(226, 232, 240, 0.8),
    0 0 18px rgba(167, 139, 250, 0.35);
}

.ulog-header__divider {
  color: rgba(148, 163, 184, 0.55);
  font-weight: 700;
  user-select: none;
}

.ulog-header__note {
  flex: 1 1 10rem;
  min-width: 0;
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.35;
  text-transform: none;
  color: #f9a8d4;
  text-shadow:
    0 0 10px rgba(249, 168, 212, 0.35),
    0 0 18px rgba(167, 139, 250, 0.2);
}

.ulog-body-wrap {
  position: relative;
  margin: 0;
  padding: 0;
  min-height: 120px;
}

.ulog-scanlines {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: 2;
  border-radius: 2px;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.12) 2px,
    rgba(0, 0, 0, 0.12) 3px
  );
  opacity: 0.35;
}

.ulog-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2.5rem 1rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    'Cascadia Code',
    Consolas,
    monospace;
  font-size: 0.875rem;
  color: #4ade80;
  text-shadow: 0 0 10px rgba(74, 222, 128, 0.45);
}

.ulog-loading__prompt {
  color: #22d3ee;
  font-weight: 700;
}

.ulog-loading__cursor {
  display: inline-block;
  width: 0.55rem;
  height: 1em;
  margin-left: 2px;
  background: #4ade80;
  animation: ulog-blink 0.9s step-end infinite;
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.8);
}

@keyframes ulog-blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

.ulog-error {
  position: relative;
  z-index: 1;
  padding: 1.25rem 1rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    Consolas,
    monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #fb923c;
  text-shadow: 0 0 12px rgba(251, 146, 60, 0.35);
}

.ulog-error__mark {
  margin-right: 0.5rem;
  color: #f472b6;
  font-weight: 700;
}

.ulog-scrollbar {
  position: relative;
  z-index: 1;
}

.ulog-scroll-inner {
  padding: 0.25rem 0.5rem 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.ulog-entry {
  border: 1px solid rgba(34, 211, 238, 0.22);
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.65) 0%, rgba(8, 12, 22, 0.9) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 0 24px rgba(34, 211, 238, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.ulog-entry__bar {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-bottom: 1px solid rgba(167, 139, 250, 0.25);
  background: rgba(34, 211, 238, 0.06);
}

.ulog-entry__idx {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 2.25rem;
  padding: 0.35rem 0.4rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    Consolas,
    monospace;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #0f172a;
  background: linear-gradient(180deg, #22d3ee 0%, #06b6d4 100%);
  text-shadow: none;
}

.ulog-entry__title {
  flex: 1;
  margin: 0;
  padding: 0.5rem 0.65rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    Consolas,
    monospace;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #a5f3fc;
  text-shadow: 0 0 14px rgba(165, 243, 252, 0.35);
  line-height: 1.35;
}

.ulog-md {
  padding: 0.65rem 0.75rem 0.85rem;
  font-family:
    ui-monospace,
    'JetBrains Mono',
    'Cascadia Code',
    Consolas,
    monospace;
  font-size: 0.75rem;
  line-height: 1.55;
  letter-spacing: 0.02em;
  color: #cbd5e1;
}

.ulog-md :deep(h3) {
  font-size: 0.7rem;
  font-weight: 700;
  margin: 0.65rem 0 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #e879f9;
  text-shadow: 0 0 10px rgba(232, 121, 249, 0.35);
}

.ulog-md :deep(h3:first-child) {
  margin-top: 0;
}

.ulog-md :deep(ul) {
  margin: 0.25rem 0 0.5rem;
  padding-left: 1.1rem;
  list-style-type: square;
}

.ulog-md :deep(li) {
  margin: 0.25rem 0;
  color: #94a3b8;
}

.ulog-md :deep(li::marker) {
  color: #22d3ee;
}

.ulog-md :deep(strong) {
  color: #fde68a;
  font-weight: 700;
}

.ulog-md :deep(p) {
  margin: 0.35rem 0;
}

.ulog-md :deep(a) {
  color: #38bdf8;
  text-decoration: none;
  border-bottom: 1px solid rgba(56, 189, 248, 0.45);
  text-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
}

.ulog-md :deep(a:hover) {
  color: #7dd3fc;
  border-bottom-color: rgba(125, 211, 252, 0.8);
}

.ulog-md :deep(code) {
  font-size: 0.88em;
  font-family: inherit;
  background: rgba(34, 211, 238, 0.1);
  color: #5eead4;
  padding: 0.1em 0.35em;
  border-radius: 2px;
  border: 1px solid rgba(34, 211, 238, 0.25);
}
</style>

<style>
/* Element Plus dialog shell — unscoped so overlay/header/body pick up geek theme */
.update-log-dialog.el-dialog {
  --el-dialog-bg-color: transparent;
  --el-dialog-padding-primary: 0;
  background: linear-gradient(165deg, #0f172a 0%, #020617 45%, #0c1220 100%);
  border: 1px solid rgba(34, 211, 238, 0.35);
  border-radius: 3px;
  box-shadow:
    0 0 0 1px rgba(167, 139, 250, 0.12),
    0 0 40px rgba(34, 211, 238, 0.12),
    0 0 80px rgba(99, 102, 241, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.update-log-dialog .el-dialog__header {
  margin: 0;
  /* Extra right padding so custom header clears the absolute close button */
  padding: 0.85rem 2.85rem 0.65rem 1rem;
  position: relative;
  border-bottom: 1px solid rgba(34, 211, 238, 0.2);
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.08) 0%, transparent 55%);
}

.update-log-dialog .el-dialog__headerbtn {
  top: 0.65rem;
  right: 0.65rem;
  width: 2rem;
  height: 2rem;
}

.update-log-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #64748b;
  font-size: 1.1rem;
  transition:
    color 0.15s ease,
    filter 0.15s ease;
}

.update-log-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #f472b6;
  filter: drop-shadow(0 0 6px rgba(244, 114, 182, 0.6));
}

.update-log-dialog .el-dialog__body {
  padding: 0 0 1rem;
  color: #cbd5e1;
}

.update-log-dialog .el-scrollbar__bar.is-vertical {
  width: 6px;
}

.update-log-dialog .el-scrollbar__thumb {
  background: rgba(34, 211, 238, 0.35);
  border-radius: 2px;
}

.update-log-dialog .el-scrollbar__thumb:hover {
  background: rgba(232, 121, 249, 0.45);
}

/* Backdrop mask (modal-class on ElDialog overlay) */
.el-overlay.ulog-modal-backdrop {
  backdrop-filter: blur(4px);
}
</style>
