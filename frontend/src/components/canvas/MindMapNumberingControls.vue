<script setup lang="ts">
/**
 * 编号 启用/隐藏 + Swiss el-selects (same chrome as language settings).
 */
import { computed, onUnmounted } from 'vue'

import { ElOption, ElSelect } from 'element-plus'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'
import {
  MIND_MAP_NUMBERING_GLYPH_PRESETS,
  MIND_MAP_NUMBERING_NESTED_PRESETS,
  type MindMapNumberingGlyphStyle,
  type MindMapNumberingNestedStyle,
  isMindMapBranchNumberingEnabled,
  resolveMindMapBranchNumberingNested,
  resolveMindMapBranchNumberingPrefix,
} from '@/utils/mindMapBranchNumbering'

const emit = defineEmits<{
  overlayLock: [locked: boolean]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()

type NumberingVisibility = 'enable' | 'hide'

const SWISS_SELECT_POPPER = 'mm-numbering-swiss-select-popper'

let unlockTimer = 0

onUnmounted(() => {
  if (unlockTimer !== 0) {
    window.clearTimeout(unlockTimer)
  }
})

function ensureDiagram(): boolean {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return false
  }
  return true
}

const numberingVisibility = computed<NumberingVisibility>({
  get: () => (isMindMapBranchNumberingEnabled(diagramStore.data) ? 'enable' : 'hide'),
  set: (value) => {
    if (!ensureDiagram()) return
    diagramStore.setMindMapBranchNumbering(value === 'enable')
  },
})

const numberingVisibilityOptions = computed(() => [
  { label: t('canvas.toolbar.mindMapAppearanceNumberingEnable'), value: 'enable' as const },
  { label: t('canvas.toolbar.mindMapAppearanceNumberingHide'), value: 'hide' as const },
])

const prefixStyle = computed<MindMapNumberingGlyphStyle>({
  get: () =>
    resolveMindMapBranchNumberingPrefix(diagramStore.data?._mindmap_branch_numbering_prefix),
  set: (style) => {
    if (!ensureDiagram()) return
    diagramStore.setMindMapBranchNumberingPrefix(style)
  },
})

const nestedStyle = computed<MindMapNumberingNestedStyle>({
  get: () =>
    resolveMindMapBranchNumberingNested(diagramStore.data?._mindmap_branch_numbering_nested),
  set: (style) => {
    if (!ensureDiagram()) return
    diagramStore.setMindMapBranchNumberingNested(style)
  },
})

function handleSelectVisible(open: boolean): void {
  emit('overlayLock', true)
  if (unlockTimer !== 0) {
    window.clearTimeout(unlockTimer)
    unlockTimer = 0
  }
  if (!open) {
    unlockTimer = window.setTimeout(() => {
      unlockTimer = 0
      emit('overlayLock', false)
    }, 0)
  }
}
</script>

<template>
  <div class="mm-numbering">
    <div class="mm-appearance-row mm-numbering__toggle">
      <span class="mm-appearance-row__label">
        {{ t('canvas.toolbar.mindMapAppearanceNumbering') }}
      </span>
      <AdminSwissSegmented
        v-model="numberingVisibility"
        fit
        :options="numberingVisibilityOptions"
        :aria-label="t('canvas.toolbar.mindMapAppearanceNumbering')"
      />
    </div>

    <div class="mm-numbering__styles">
      <section class="mm-numbering-field">
        <div class="mm-numbering-kicker">
          {{ t('canvas.toolbar.mindMapAppearanceNumberingPrefix') }}
        </div>
        <ElSelect
          v-model="prefixStyle"
          class="mm-numbering-swiss-select"
          :fit-input-width="true"
          :popper-class="SWISS_SELECT_POPPER"
          :aria-label="t('canvas.toolbar.mindMapAppearanceNumberingPrefix')"
          @visible-change="handleSelectVisible"
        >
          <ElOption
            v-for="preset in MIND_MAP_NUMBERING_GLYPH_PRESETS"
            :key="preset.id"
            :label="preset.samples"
            :value="preset.id"
            @click="prefixStyle = preset.id"
          />
        </ElSelect>
      </section>

      <section class="mm-numbering-field">
        <div class="mm-numbering-kicker">
          {{ t('canvas.toolbar.mindMapAppearanceNumberingNested') }}
        </div>
        <ElSelect
          v-model="nestedStyle"
          class="mm-numbering-swiss-select"
          :fit-input-width="true"
          :popper-class="SWISS_SELECT_POPPER"
          :aria-label="t('canvas.toolbar.mindMapAppearanceNumberingNested')"
          @visible-change="handleSelectVisible"
        >
          <ElOption
            v-for="preset in MIND_MAP_NUMBERING_NESTED_PRESETS"
            :key="preset.id"
            :label="preset.samples"
            :value="preset.id"
            @click="nestedStyle = preset.id"
          />
        </ElSelect>
      </section>
    </div>
  </div>
</template>

<style scoped>
.mm-numbering {
  --mm-numbering-ink: #1c1917;
  --mm-numbering-muted: #78716c;
  --mm-numbering-subtle: #a8a29e;
  --mm-numbering-border: #e7e5e4;
  --mm-numbering-border-strong: #d6d3d1;
  --mm-numbering-surface: #ffffff;
  --mm-numbering-hover: #f5f5f4;

  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--mm-numbering-border);
}

.dark .mm-numbering {
  --mm-numbering-ink: #f9fafb;
  --mm-numbering-muted: #a8a29e;
  --mm-numbering-subtle: #78716c;
  --mm-numbering-border: #374151;
  --mm-numbering-border-strong: #4b5563;
  --mm-numbering-surface: #1f2937;
  --mm-numbering-hover: #374151;

  border-top-color: var(--mm-numbering-border);
}

.mm-numbering__toggle {
  margin-bottom: 0;
}

.mm-numbering :deep(.mm-appearance-row__label) {
  width: 60px;
}

.mm-numbering :deep(.admin-swiss-segmented) {
  flex: 0 0 auto;
}

.mm-numbering :deep(.admin-swiss-segment) {
  min-width: 0;
  min-height: 28px;
  padding: 0 8px;
  font-size: 12px;
}

.mm-numbering__styles {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mm-numbering-kicker {
  display: flex;
  align-items: baseline;
  margin-bottom: 6px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--mm-numbering-muted);
  line-height: 1.35;
}

.mm-numbering-kicker::before {
  content: '';
  display: inline-block;
  width: 0.35rem;
  height: 0.35rem;
  margin-inline-end: 0.35rem;
  background: var(--mm-numbering-subtle);
  border-radius: 1px;
  transform: translateY(-0.05rem);
}

.mm-numbering-swiss-select {
  width: 12rem;
  max-width: 100%;
}

.mm-numbering-swiss-select :deep(.el-select__wrapper) {
  min-height: 2.25rem;
  border-radius: 6px;
  border: 1px solid var(--mm-numbering-border-strong);
  background: var(--mm-numbering-surface);
  box-shadow: none;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--mm-numbering-ink);
  transition:
    border-color 0.12s ease,
    background-color 0.12s ease;
}

.mm-numbering-swiss-select :deep(.el-select__wrapper:hover) {
  border-color: var(--mm-numbering-subtle);
}

.mm-numbering-swiss-select :deep(.el-select__wrapper.is-focused) {
  border-color: var(--mm-numbering-muted);
  box-shadow: 0 0 0 1px var(--mm-numbering-border-strong);
}

.mm-numbering-swiss-select :deep(.el-select__caret) {
  color: var(--mm-numbering-muted);
}

.mm-numbering-swiss-select :deep(.el-select__placeholder),
.mm-numbering-swiss-select :deep(.el-select__selected-item) {
  color: var(--mm-numbering-ink);
}

.mm-numbering-swiss-select :deep(.el-select__placeholder) {
  color: var(--mm-numbering-muted);
}
</style>

<!-- Dropdown is teleported; target via popper-class (same Swiss panel as language). -->
<style>
.el-select__popper.mm-numbering-swiss-select-popper.el-popper {
  box-sizing: border-box !important;
  min-width: 0 !important;
  width: 12rem !important;
  max-width: min(12rem, calc(100vw - 32px)) !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  background: #ffffff !important;
  overflow: hidden !important;
}

.dark .el-select__popper.mm-numbering-swiss-select-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.el-select-dropdown.mm-numbering-swiss-select-popper {
  min-width: 0 !important;
  width: 100% !important;
  max-width: 100% !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.mm-numbering-swiss-select-popper .el-select-dropdown__list {
  padding: 0 !important;
  margin: 0 !important;
}

.mm-numbering-swiss-select-popper .el-select-dropdown__item {
  height: auto !important;
  min-height: 2rem;
  line-height: 1.25;
  padding: 0.3rem 8px !important;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.dark .mm-numbering-swiss-select-popper .el-select-dropdown__item {
  color: #d6d3d1;
}

.mm-numbering-swiss-select-popper .el-select-dropdown__item.is-hovering,
.mm-numbering-swiss-select-popper .el-select-dropdown__item:hover {
  background: #f5f5f4 !important;
  color: #1c1917 !important;
}

.dark .mm-numbering-swiss-select-popper .el-select-dropdown__item.is-hovering,
.dark .mm-numbering-swiss-select-popper .el-select-dropdown__item:hover {
  background: #374151 !important;
  color: #f9fafb !important;
}

.mm-numbering-swiss-select-popper .el-select-dropdown__item:active {
  background: #e7e5e4 !important;
}

.dark .mm-numbering-swiss-select-popper .el-select-dropdown__item:active {
  background: #4b5563 !important;
}

.mm-numbering-swiss-select-popper .el-select-dropdown__item.is-selected {
  font-weight: 600 !important;
  color: #1c1917 !important;
  background: #f5f5f4 !important;
}

.dark .mm-numbering-swiss-select-popper .el-select-dropdown__item.is-selected {
  color: #f9fafb !important;
  background: #374151 !important;
}
</style>
