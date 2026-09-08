<script setup lang="ts">
/**
 * 编号 启用/隐藏 + sample chips (no nested select inside the flyout).
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElTooltip } from 'element-plus'

import { ChevronDown, ListOrdered } from '@lucide/vue'

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

const props = withDefaults(
  defineProps<{
    /** toolbar = one ribbon button that opens this panel */
    variant?: 'embedded' | 'button'
    compact?: boolean
  }>(),
  { variant: 'embedded', compact: false }
)

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()

type NumberingVisibility = 'enable' | 'hide'

const numberingLabel = computed(() => t('canvas.toolbar.mindMapAppearanceNumbering'))
const isButton = computed(() => props.variant === 'button')
const dropdownOpen = ref(false)

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

const numberingEnabled = computed(() => numberingVisibility.value === 'enable')

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

function handleDropdownVisible(visible: boolean): void {
  dropdownOpen.value = visible
  emit('overlayLock', visible)
}
</script>

<template>
  <ElTooltip
    v-if="isButton"
    :content="numberingLabel"
    placement="bottom"
  >
    <span class="inline-flex shrink-0">
      <ElDropdown
        :visible="dropdownOpen"
        :hide-on-click="false"
        trigger="click"
        placement="bottom"
        popper-class="mm-toolbar-popper mm-toolbar-popper--numbering"
        @update:visible="handleDropdownVisible"
      >
        <button
          type="button"
          class="mm-btn"
          :aria-label="numberingLabel"
        >
          <ListOrdered class="w-4 h-4 shrink-0" />
          <span
            v-if="!compact"
            class="mm-btn__label"
            >{{ numberingLabel }}</span
          >
          <ChevronDown
            :size="12"
            class="mm-btn__chevron"
          />
        </button>
        <template #dropdown>
          <div class="mm-numbering mm-numbering--flyout">
            <AdminSwissSegmented
              v-model="numberingVisibility"
              equal
              :options="numberingVisibilityOptions"
              :aria-label="numberingLabel"
            />

            <div
              class="mm-numbering__styles"
              :class="{ 'is-disabled': !numberingEnabled }"
            >
              <section class="mm-numbering-field">
                <div class="mm-numbering-kicker">
                  {{ t('canvas.toolbar.mindMapAppearanceNumberingPrefix') }}
                </div>
                <div
                  class="mm-numbering-chips"
                  role="listbox"
                  :aria-label="t('canvas.toolbar.mindMapAppearanceNumberingPrefix')"
                >
                  <button
                    v-for="preset in MIND_MAP_NUMBERING_GLYPH_PRESETS"
                    :key="preset.id"
                    type="button"
                    class="mm-numbering-chip"
                    role="option"
                    :aria-selected="prefixStyle === preset.id"
                    :class="{ 'is-active': prefixStyle === preset.id }"
                    :disabled="!numberingEnabled"
                    @click="prefixStyle = preset.id"
                  >
                    {{ preset.samples }}
                  </button>
                </div>
              </section>

              <section class="mm-numbering-field">
                <div class="mm-numbering-kicker">
                  {{ t('canvas.toolbar.mindMapAppearanceNumberingNested') }}
                </div>
                <div
                  class="mm-numbering-chips"
                  role="listbox"
                  :aria-label="t('canvas.toolbar.mindMapAppearanceNumberingNested')"
                >
                  <button
                    v-for="preset in MIND_MAP_NUMBERING_NESTED_PRESETS"
                    :key="preset.id"
                    type="button"
                    class="mm-numbering-chip"
                    role="option"
                    :aria-selected="nestedStyle === preset.id"
                    :class="{ 'is-active': nestedStyle === preset.id }"
                    :disabled="!numberingEnabled"
                    @click="nestedStyle = preset.id"
                  >
                    {{ preset.samples }}
                  </button>
                </div>
              </section>
            </div>
          </div>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
  <div
    v-else
    class="mm-numbering"
  >
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

    <div
      class="mm-numbering__styles"
      :class="{ 'is-disabled': !numberingEnabled }"
    >
      <section class="mm-numbering-field">
        <div class="mm-numbering-kicker">
          {{ t('canvas.toolbar.mindMapAppearanceNumberingPrefix') }}
        </div>
        <div class="mm-numbering-chips">
          <button
            v-for="preset in MIND_MAP_NUMBERING_GLYPH_PRESETS"
            :key="preset.id"
            type="button"
            class="mm-numbering-chip"
            :class="{ 'is-active': prefixStyle === preset.id }"
            :disabled="!numberingEnabled"
            @click="prefixStyle = preset.id"
          >
            {{ preset.samples }}
          </button>
        </div>
      </section>

      <section class="mm-numbering-field">
        <div class="mm-numbering-kicker">
          {{ t('canvas.toolbar.mindMapAppearanceNumberingNested') }}
        </div>
        <div class="mm-numbering-chips">
          <button
            v-for="preset in MIND_MAP_NUMBERING_NESTED_PRESETS"
            :key="preset.id"
            type="button"
            class="mm-numbering-chip"
            :class="{ 'is-active': nestedStyle === preset.id }"
            :disabled="!numberingEnabled"
            @click="nestedStyle = preset.id"
          >
            {{ preset.samples }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.mm-numbering {
  --mm-numbering-ink: #1c1917;
  --mm-numbering-muted: #78716c;
  --mm-numbering-border: #e7e5e4;
  --mm-numbering-border-strong: #d6d3d1;
  --mm-numbering-surface: #ffffff;
  --mm-numbering-hover: #f5f5f4;
  --mm-numbering-active: #eff6ff;
  --mm-numbering-active-ink: #1d4ed8;
  --mm-numbering-active-border: #93c5fd;

  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--mm-numbering-border);
}

.mm-numbering--flyout {
  margin-top: 0;
  padding: 12px;
  border-top: none;
}

.dark .mm-numbering {
  --mm-numbering-ink: #f9fafb;
  --mm-numbering-muted: #a8a29e;
  --mm-numbering-border: #374151;
  --mm-numbering-border-strong: #4b5563;
  --mm-numbering-surface: #1f2937;
  --mm-numbering-hover: #374151;
  --mm-numbering-active: rgb(37 99 235 / 0.22);
  --mm-numbering-active-ink: #93c5fd;
  --mm-numbering-active-border: #3b82f6;

  border-top-color: var(--mm-numbering-border);
}

.mm-numbering--flyout :deep(.admin-swiss-segmented) {
  width: 100%;
}

.mm-numbering__toggle {
  margin-bottom: 0;
}

.mm-numbering :deep(.mm-appearance-row__label) {
  width: 60px;
}

.mm-numbering__styles {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mm-numbering__styles.is-disabled {
  opacity: 0.45;
}

.mm-numbering-kicker {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--mm-numbering-muted);
  line-height: 1.2;
}

.mm-numbering-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mm-numbering-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid var(--mm-numbering-border-strong);
  border-radius: 6px;
  background: var(--mm-numbering-surface);
  color: var(--mm-numbering-ink);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.25;
  white-space: nowrap;
  transition:
    border-color 0.12s ease,
    background-color 0.12s ease,
    color 0.12s ease;
}

.mm-numbering-chip:hover:not(:disabled) {
  background: var(--mm-numbering-hover);
}

.mm-numbering-chip.is-active {
  border-color: var(--mm-numbering-active-border);
  background: var(--mm-numbering-active);
  color: var(--mm-numbering-active-ink);
  font-weight: 600;
}

.mm-numbering-chip:disabled {
  cursor: not-allowed;
}
</style>

<style>
.mm-toolbar-popper--numbering.el-popper {
  width: min(340px, calc(100vw - 24px)) !important;
}

.mm-toolbar-popper--numbering .mm-numbering--flyout {
  margin-top: 0;
  padding: 12px;
  border-top: none;
}
</style>
