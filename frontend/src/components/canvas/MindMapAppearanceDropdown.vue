<script setup lang="ts">
/**
 * Mind map appearance picker — table-style card: color dots + style preview grid.
 */
import { computed, ref, watch } from 'vue'

import { ElDropdown, ElTooltip } from 'element-plus'

import { Check, ChevronDown, Palette } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import MindMapDiagramStylePreview from '@/components/canvas/MindMapDiagramStylePreview.vue'
import {
  MIND_MAP_DIAGRAM_STYLES,
  resolveMindMapDiagramStyleId,
  type MindMapDiagramStyleId,
} from '@/config/mindMapDiagramStyles'
import {
  getMindMapCommonThemes,
  resolveMindMapThemeId,
  type MindMapThemeId,
} from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_THEME_ID } from '@/config/mindMapVibrantThemes'
import { useDiagramStore } from '@/stores'

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()

const dropdownOpen = ref(false)

const activeThemeId = ref<MindMapThemeId>(
  resolveMindMapThemeId(diagramStore.data?._mindmap_theme as string | undefined)
)
const activeDiagramStyleId = ref<MindMapDiagramStyleId>(
  resolveMindMapDiagramStyleId(diagramStore.data?._mindmap_diagram_style as string | undefined)
)

watch(
  () => diagramStore.data?._mindmap_theme,
  (themeId) => {
    activeThemeId.value = resolveMindMapThemeId(themeId as string | undefined)
  }
)

watch(
  () => diagramStore.data?._mindmap_diagram_style,
  (styleId) => {
    activeDiagramStyleId.value = resolveMindMapDiagramStyleId(styleId as string | undefined)
  }
)

const commonThemes = getMindMapCommonThemes()

const isRainbowActive = computed(() => activeThemeId.value === MIND_MAP_RAINBOW_THEME_ID)

const activeTheme = computed(
  () => commonThemes.find((theme) => theme.id === activeThemeId.value) ?? commonThemes[0]
)

function ensureDiagram(): boolean {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return false
  }
  return true
}

function applyAppearance(
  themeId: MindMapThemeId,
  diagramStyleId: MindMapDiagramStyleId
): void {
  if (!ensureDiagram()) return
  diagramStore.applyMindMapAppearance({ themeId, diagramStyleId })
  activeThemeId.value = themeId
  activeDiagramStyleId.value = diagramStyleId
}

function handlePickDiagramStyle(styleId: MindMapDiagramStyleId): void {
  applyAppearance(activeThemeId.value, styleId)
}

function handlePickTheme(themeId: MindMapThemeId): void {
  applyAppearance(themeId, activeDiagramStyleId.value)
}

function handlePickRainbow(): void {
  applyAppearance(MIND_MAP_RAINBOW_THEME_ID, activeDiagramStyleId.value)
}
</script>

<template>
  <ElTooltip
    :content="t('canvas.toolbar.mindMapAppearanceLabel')"
    placement="bottom"
    :disabled="!props.compact"
  >
    <span class="inline-flex shrink-0">
      <ElDropdown
        v-model:visible="dropdownOpen"
        trigger="click"
        placement="bottom"
        popper-class="mm-toolbar-popper mm-toolbar-popper--appearance"
      >
        <button
          type="button"
          class="mm-btn mm-btn--select"
          :class="{ 'mm-btn--appearance-compact': props.compact }"
          :aria-label="t('canvas.toolbar.mindMapAppearanceLabel')"
        >
          <Palette class="w-4 h-4 text-gray-500 shrink-0" />
          <span
            class="mm-btn__color-dot"
            :class="{ 'mm-btn__color-dot--rainbow': isRainbowActive }"
            :style="isRainbowActive ? undefined : { backgroundColor: activeTheme.topicBorderColor }"
            aria-hidden="true"
          />
          <span
            v-if="!props.compact"
            class="mm-btn__label"
          >{{ t('canvas.toolbar.mindMapAppearanceLabel') }}</span>
          <ChevronDown
            v-if="!props.compact"
            class="mm-btn__chevron"
          />
        </button>
        <template #dropdown>
      <div class="mm-appearance-card">
        <div class="mm-appearance-card__title">
          {{ t('canvas.toolbar.mindMapAppearanceLabel') }}
        </div>

        <div class="mm-appearance-row">
          <span class="mm-appearance-row__label">
            {{ t('canvas.toolbar.mindMapAppearanceThemeColor') }}
          </span>
          <div
            class="mm-appearance-colors"
            role="listbox"
            :aria-label="t('canvas.toolbar.mindMapAppearanceThemeColor')"
          >
            <button
              v-for="theme in commonThemes"
              :key="theme.id"
              type="button"
              class="mm-appearance-color-dot"
              :class="{ 'is-active': theme.id === activeThemeId }"
              :style="{ backgroundColor: theme.topicBorderColor }"
              :title="t(theme.nameKey)"
              :aria-label="t(theme.nameKey)"
              :aria-selected="theme.id === activeThemeId"
              role="option"
              @click="handlePickTheme(theme.id)"
            >
              <Check
                v-if="theme.id === activeThemeId"
                class="mm-appearance-color-dot__check"
                :stroke-width="3"
              />
            </button>
            <button
              type="button"
              class="mm-appearance-color-dot mm-appearance-color-dot--rainbow"
              :class="{ 'is-active': isRainbowActive }"
              :title="t('canvas.toolbar.mindMapThemeRainbow')"
              :aria-label="t('canvas.toolbar.mindMapThemeRainbow')"
              :aria-selected="isRainbowActive"
              role="option"
              @click="handlePickRainbow()"
            >
              <Check
                v-if="isRainbowActive"
                class="mm-appearance-color-dot__check"
                :stroke-width="3"
              />
            </button>
          </div>
        </div>

        <div class="mm-appearance-style-section">
          <div class="mm-appearance-section-label">
            {{ t('canvas.toolbar.mindMapAppearanceDiagramStyle') }}
          </div>
          <div
            class="mm-appearance-style-grid"
            role="listbox"
            :aria-label="t('canvas.toolbar.mindMapAppearanceDiagramStyle')"
          >
          <button
            v-for="style in MIND_MAP_DIAGRAM_STYLES"
            :key="style.id"
            type="button"
            class="mm-appearance-style-tile"
            :class="{ 'is-active': style.id === activeDiagramStyleId }"
            :title="t(style.nameKey)"
            :aria-label="t(style.nameKey)"
            :aria-selected="style.id === activeDiagramStyleId"
            role="option"
            @click="handlePickDiagramStyle(style.id)"
          >
            <MindMapDiagramStylePreview
              :preset="style"
              :active="style.id === activeDiagramStyleId"
            />
          </button>
        </div>
        </div>
      </div>
    </template>
      </ElDropdown>
    </span>
  </ElTooltip>
</template>

<style scoped>
.mm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

.mm-btn__label {
  font-weight: 500;
}

.mm-btn--appearance-compact {
  width: auto;
  max-width: none;
  padding: 0 8px;
}

.mm-btn__color-dot {
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  border: 1px solid rgb(0 0 0 / 0.12);
  flex-shrink: 0;
}

.mm-btn__chevron {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: #9ca3af;
}
</style>

<style>
.mm-toolbar-popper--appearance.el-popper {
  width: min(292px, calc(100vw - 24px)) !important;
}

.mm-appearance-card {
  padding: 12px 14px 14px;
}

.mm-appearance-card__title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.2;
}

.dark .mm-appearance-card__title {
  color: #f3f4f6;
}

.mm-appearance-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.mm-appearance-row__label {
  flex-shrink: 0;
  width: 52px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.2;
}

.dark .mm-appearance-row__label {
  color: #9ca3af;
}

.mm-appearance-colors {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.mm-appearance-color-dot {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 9999px;
  cursor: pointer;
  transition:
    transform 0.12s ease,
    box-shadow 0.12s ease,
    border-color 0.12s ease;
  box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.08);
}

.mm-appearance-color-dot:hover {
  transform: scale(1.06);
}

.mm-appearance-color-dot.is-active {
  border-color: #fff;
  box-shadow:
    0 0 0 2px #3b82f6,
    inset 0 0 0 1px rgb(0 0 0 / 0.1);
}

.mm-appearance-color-dot__check {
  width: 12px;
  height: 12px;
  color: #fff;
  filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.35));
}

.mm-btn__color-dot--rainbow {
  background: conic-gradient(
    from 90deg,
    #fa8055,
    #ffad36,
    #b5c62a,
    #0098b9,
    #4a72d4,
    #7574bc,
    #ff7dc1,
    #fa8055
  );
  border-color: rgb(0 0 0 / 0.08);
}

.mm-appearance-section-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.2;
}

.dark .mm-appearance-section-label {
  color: #9ca3af;
}

.mm-appearance-style-section {
  margin-top: 2px;
}

.mm-appearance-color-dot--rainbow {
  background: conic-gradient(
    from 90deg,
    #fa8055,
    #ffad36,
    #b5c62a,
    #0098b9,
    #4a72d4,
    #7574bc,
    #ff7dc1,
    #fa8055
  );
}

.mm-appearance-color-dot--rainbow.is-active {
  box-shadow:
    0 0 0 2px #3b82f6,
    inset 0 0 0 1px rgb(0 0 0 / 0.1);
}

.mm-appearance-style-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.mm-appearance-style-tile {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 58px;
  padding: 4px 3px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition:
    border-color 0.12s ease,
    box-shadow 0.12s ease,
    background 0.12s ease;
}

.mm-appearance-style-tile:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.mm-appearance-style-tile.is-active {
  border-color: #3b82f6;
  box-shadow: inset 0 0 0 1px #3b82f6;
  background: #f8fbff;
}

.dark .mm-appearance-style-tile {
  border-color: #374151;
  background: #111827;
}

.dark .mm-appearance-style-tile:hover {
  border-color: #4b5563;
  background: #1f2937;
}

.dark .mm-appearance-style-tile.is-active {
  border-color: #60a5fa;
  box-shadow: inset 0 0 0 1px #60a5fa;
  background: #172554;
}
</style>
