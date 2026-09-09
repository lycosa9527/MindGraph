<script setup lang="ts">
/**
 * Property card for an association line (shape, dash, width, color, arrows).
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { ChevronDown } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { FLOATING_TOOLBAR_COLORS } from '@/config/floatingToolbarColors'
import type { AssociationLineStyle } from '@/utils/mindMapAssociationLine'
import {
  associationArrowheadFromEnds,
  associationEndsFromArrowhead,
  associationLineStyleFromDash,
  associationStrokeColor,
  associationStrokeWidth,
  clampAssociationStrokeWidth,
} from '@/utils/mindMapAssociationLine'
import { MINDMAP_SUMMARY_LINE_STYLES } from '@/utils/mindMapSummary'

const LINE_DASH: Record<AssociationLineStyle, string | undefined> = {
  solid: undefined,
  dashed: '5 4',
  dotted: '1.5 3',
}

const ASSOC_COLORS = ['#64748b', ...FLOATING_TOOLBAR_COLORS.filter((c) => c !== '#64748b')]

const props = defineProps<{
  connectionId: string
  left: number
  top: number
}>()

const { t } = useLanguage()
const diagramStore = useDiagramSession()
const colorOpen = ref(false)

const conn = computed(() =>
  diagramStore.data?.connections?.find((item) => item.id === props.connectionId)
)

const lineStyle = computed(() => associationLineStyleFromDash(conn.value?.style?.strokeDasharray))
const strokeColor = computed(() => associationStrokeColor(conn.value?.style?.strokeColor))
const strokeWidth = computed(() => associationStrokeWidth(conn.value?.style?.strokeWidth))
const arrows = computed(() => associationEndsFromArrowhead(conn.value?.arrowheadDirection))

const toolbarStyle = computed(() => ({
  left: `${props.left}px`,
  top: `${props.top}px`,
}))

const lineLabel: Record<AssociationLineStyle, string> = {
  solid: 'canvas.floatingToolbar.summaryLineSolid',
  dashed: 'canvas.floatingToolbar.summaryLineDashed',
  dotted: 'canvas.floatingToolbar.summaryLineDotted',
}

function apply(patch: Parameters<typeof diagramStore.updateConnectionChrome>[1]): void {
  diagramStore.updateConnectionChrome(props.connectionId, patch)
}

function onLineStylePick(next: AssociationLineStyle): void {
  apply({ lineStyle: next })
}

function onColorPick(color: string): void {
  apply({ strokeColor: color })
  colorOpen.value = false
}

function onCustomColor(event: Event): void {
  onColorPick((event.target as HTMLInputElement).value)
}

function bumpWidth(delta: number): void {
  apply({ strokeWidth: clampAssociationStrokeWidth(strokeWidth.value + delta) })
}

function setStartArrow(on: boolean): void {
  apply({ arrowheadDirection: associationArrowheadFromEnds(on, arrows.value.end) })
}

function setEndArrow(on: boolean): void {
  apply({ arrowheadDirection: associationArrowheadFromEnds(arrows.value.start, on) })
}
</script>

<template>
  <Teleport to="body">
    <div
      class="mm-summary-toolbar"
      :style="toolbarStyle"
      role="dialog"
      :aria-label="t('canvas.floatingToolbar.assocStyle', 'Relationship line style')"
      @pointerdown.stop
      @mousedown.stop
      @click.stop
    >
      <div class="mm-summary-toolbar__row">
        <span class="mm-summary-toolbar__label">{{
          t('canvas.floatingToolbar.assocShape', '关联线形状')
        }}</span>
        <button
          type="button"
          class="mm-summary-toolbar__field"
          :title="t('canvas.floatingToolbar.assocShapeCurve', '曲线')"
        >
          <svg
            class="mm-summary-toolbar__shape"
            viewBox="0 0 28 12"
            aria-hidden="true"
          >
            <path
              d="M2 9 C8 1 20 1 26 9"
              fill="none"
              :stroke="strokeColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
          <ChevronDown class="mm-summary-toolbar__chevron" />
        </button>
      </div>

      <div class="mm-summary-toolbar__row">
        <div class="mm-summary-toolbar__triple">
          <ElDropdown
            trigger="click"
            placement="bottom-end"
            popper-class="mm-summary-toolbar-popper"
          >
            <button
              type="button"
              class="mm-summary-toolbar__field"
              :title="t(lineLabel[lineStyle])"
            >
              <svg
                class="mm-summary-toolbar__line"
                viewBox="0 0 28 10"
                aria-hidden="true"
              >
                <line
                  x1="2"
                  y1="5"
                  x2="26"
                  y2="5"
                  :stroke="strokeColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  :stroke-dasharray="LINE_DASH[lineStyle]"
                />
              </svg>
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  v-for="option in MINDMAP_SUMMARY_LINE_STYLES"
                  :key="option"
                  :class="{ 'is-active': lineStyle === option }"
                  @click="onLineStylePick(option)"
                >
                  <svg
                    class="mm-summary-toolbar__line"
                    viewBox="0 0 28 10"
                    aria-hidden="true"
                  >
                    <line
                      x1="2"
                      y1="5"
                      x2="26"
                      y2="5"
                      stroke="#334155"
                      stroke-width="2"
                      stroke-linecap="round"
                      :stroke-dasharray="LINE_DASH[option]"
                    />
                  </svg>
                  {{ t(lineLabel[option]) }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>

          <div
            class="mm-summary-toolbar__stepper"
            :title="t('canvas.floatingToolbar.summaryThickness')"
          >
            <span class="mm-summary-toolbar__px">{{ strokeWidth }}px</span>
            <div class="mm-summary-toolbar__stepper-btns">
              <button
                type="button"
                class="mm-summary-toolbar__step"
                :disabled="strokeWidth >= 8"
                @click="bumpWidth(1)"
              >
                ▲
              </button>
              <button
                type="button"
                class="mm-summary-toolbar__step"
                :disabled="strokeWidth <= 1"
                @click="bumpWidth(-1)"
              >
                ▼
              </button>
            </div>
          </div>

          <div class="mm-summary-toolbar__color-wrap">
            <button
              type="button"
              class="mm-summary-toolbar__field"
              :title="t('canvas.floatingToolbar.borderColor')"
              @click="colorOpen = !colorOpen"
            >
              <span
                class="mm-summary-toolbar__swatch"
                :style="{ backgroundColor: strokeColor }"
              />
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <div
              v-if="colorOpen"
              class="mm-summary-toolbar__palette"
            >
              <button
                v-for="color in ASSOC_COLORS"
                :key="color"
                type="button"
                class="mm-summary-toolbar__swatch-btn"
                :style="{ backgroundColor: color }"
                @click="onColorPick(color)"
              />
              <input
                type="color"
                class="mm-summary-toolbar__native"
                :value="strokeColor"
                @input="onCustomColor"
              >
            </div>
          </div>
        </div>
      </div>

      <div class="mm-summary-toolbar__row mm-summary-toolbar__row--arrows">
        <div class="mm-summary-toolbar__arrow">
          <span class="mm-summary-toolbar__label">{{
            t('canvas.floatingToolbar.assocStartArrow', '起始箭头')
          }}</span>
          <ElDropdown
            trigger="click"
            placement="bottom-end"
            popper-class="mm-summary-toolbar-popper"
          >
            <button
              type="button"
              class="mm-summary-toolbar__field"
            >
              <svg
                class="mm-summary-toolbar__arrow-icon"
                viewBox="0 0 28 10"
                aria-hidden="true"
              >
                <line
                  x1="4"
                  y1="5"
                  x2="24"
                  y2="5"
                  stroke="#334155"
                  stroke-width="1.6"
                />
                <path
                  v-if="arrows.start"
                  d="M4 5 L9 2 L9 8 Z"
                  fill="#334155"
                />
              </svg>
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  :class="{ 'is-active': !arrows.start }"
                  @click="setStartArrow(false)"
                >
                  {{ t('canvas.floatingToolbar.assocArrowNone', '无') }}
                </ElDropdownItem>
                <ElDropdownItem
                  :class="{ 'is-active': arrows.start }"
                  @click="setStartArrow(true)"
                >
                  {{ t('canvas.floatingToolbar.assocArrow', '箭头') }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </div>
        <div class="mm-summary-toolbar__arrow">
          <span class="mm-summary-toolbar__label">{{
            t('canvas.floatingToolbar.assocEndArrow', '结束箭头')
          }}</span>
          <ElDropdown
            trigger="click"
            placement="bottom-end"
            popper-class="mm-summary-toolbar-popper"
          >
            <button
              type="button"
              class="mm-summary-toolbar__field"
            >
              <svg
                class="mm-summary-toolbar__arrow-icon"
                viewBox="0 0 28 10"
                aria-hidden="true"
              >
                <line
                  x1="4"
                  y1="5"
                  x2="24"
                  y2="5"
                  stroke="#334155"
                  stroke-width="1.6"
                />
                <path
                  v-if="arrows.end"
                  d="M24 5 L19 2 L19 8 Z"
                  fill="#334155"
                />
              </svg>
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  :class="{ 'is-active': !arrows.end }"
                  @click="setEndArrow(false)"
                >
                  {{ t('canvas.floatingToolbar.assocArrowNone', '无') }}
                </ElDropdownItem>
                <ElDropdownItem
                  :class="{ 'is-active': arrows.end }"
                  @click="setEndArrow(true)"
                >
                  {{ t('canvas.floatingToolbar.assocArrow', '箭头') }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mm-summary-toolbar {
  position: fixed;
  z-index: 5010;
  min-width: 268px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #ececec;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mm-summary-toolbar__row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mm-summary-toolbar__row--arrows {
  align-items: stretch;
}

.mm-summary-toolbar__label {
  flex: 0 0 72px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.2;
}

.mm-summary-toolbar__triple,
.mm-summary-toolbar__arrow {
  flex: 1;
  display: flex;
  gap: 8px;
  min-width: 0;
  align-items: center;
}

.mm-summary-toolbar__arrow {
  flex-direction: column;
  gap: 4px;
}

.mm-summary-toolbar__arrow .mm-summary-toolbar__label {
  flex: none;
}

.mm-summary-toolbar__row :deep(.el-dropdown) {
  flex: 1;
  min-width: 0;
}

.mm-summary-toolbar__field,
.mm-summary-toolbar__stepper {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #d4d4d8;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
}

.mm-summary-toolbar__chevron {
  width: 14px;
  height: 14px;
  color: #94a3b8;
  flex-shrink: 0;
}

.mm-summary-toolbar__line,
.mm-summary-toolbar__shape,
.mm-summary-toolbar__arrow-icon {
  width: 28px;
  height: 12px;
}

.mm-summary-toolbar__swatch {
  display: block;
  width: 28px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.mm-summary-toolbar__color-wrap {
  position: relative;
  flex: 1;
}

.mm-summary-toolbar__palette {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  width: 168px;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}

.mm-summary-toolbar__swatch-btn {
  width: 20px;
  height: 20px;
  padding: 0;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
}

.mm-summary-toolbar__native {
  grid-column: 1 / -1;
  width: 100%;
  height: 26px;
  padding: 0;
  border: none;
  cursor: pointer;
}

.mm-summary-toolbar__px {
  font-size: 13px;
  color: #334155;
}

.mm-summary-toolbar__stepper-btns {
  display: flex;
  flex-direction: column;
  margin-right: -4px;
}

.mm-summary-toolbar__step {
  padding: 0 2px;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 8px;
  line-height: 1;
  cursor: pointer;
}

.mm-summary-toolbar__step:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>
