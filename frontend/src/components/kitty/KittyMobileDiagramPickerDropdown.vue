<script setup lang="ts">
/**
 * Mobile Kitty: Swiss-style diagram picker anchored to the bottom-bar context card.
 */
import { computed, ref, watch } from 'vue'

import { ElPopover } from 'element-plus'

import { Check, Loader2, Plus, Pin, Search } from '@lucide/vue'

import KittyMobileDiagramContextCard from '@/components/kitty/KittyMobileDiagramContextCard.vue'
import { useLanguage } from '@/composables'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  modelValue: boolean
  selecting?: boolean
  currentDiagramId?: string | null
  primaryLine: string
  metaLine?: string | null
  sourceBadge?: string | null
  accessibleLabel: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'select', diagram: SavedDiagram): void
  (e: 'create-new'): void
}>()

const { t } = useLanguage()
const savedDiagramsStore = useSavedDiagramsStore()

const searchQuery = ref('')

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const diagrams = computed(() => savedDiagramsStore.diagrams)
const isLoading = computed(() => savedDiagramsStore.isLoading)

const filteredDiagrams = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) {
    return diagrams.value
  }
  return diagrams.value.filter((diagram) => {
    const title = diagram.title.toLowerCase()
    const type = diagram.diagram_type.toLowerCase()
    const typeLabel = typeLabelFor(diagram.diagram_type).toLowerCase()
    return title.includes(query) || type.includes(query) || typeLabel.includes(query)
  })
})

watch(open, (visible) => {
  if (!visible) {
    searchQuery.value = ''
    return
  }
  void savedDiagramsStore.fetchDiagrams()
})

function typeLabelFor(type: string): string {
  const key = `sidebar.diagramType.${type}`
  const val = t(key)
  return val !== key ? val : type
}

function handleSelect(diagram: SavedDiagram): void {
  if (props.selecting) {
    return
  }
  emit('select', diagram)
  open.value = false
}

function handleCreateNew(): void {
  if (props.selecting) {
    return
  }
  emit('create-new')
  open.value = false
}
</script>

<template>
  <ElPopover
    v-model:visible="open"
    trigger="click"
    placement="top"
    :offset="10"
    :show-arrow="false"
    :teleported="true"
    popper-class="kitty-mobile-diagram-picker-popper"
    :width="320"
    class="kitty-diagram-picker-anchor"
  >
    <template #reference>
      <KittyMobileDiagramContextCard
        :primary-line="primaryLine"
        :meta-line="metaLine"
        :source-badge="sourceBadge"
        :accessible-label="accessibleLabel"
        :expanded="open"
        :disabled="disabled"
      />
    </template>

    <div
      class="kitty-diagram-picker-panel"
      role="listbox"
      :aria-label="t('mobile.kittyDiagramPickerTitle', '选择导图')"
    >
      <div class="kitty-diagram-picker-panel__header">
        <span class="kitty-diagram-picker-panel__label">
          {{ t('mobile.kittyDiagramPickerTitle', '选择导图') }}
        </span>
      </div>

      <button
        type="button"
        class="kitty-diagram-picker-create"
        :disabled="selecting"
        @click="handleCreateNew"
      >
        <Plus
          :size="16"
          class="kitty-diagram-picker-create__icon"
          aria-hidden="true"
        />
        <span>{{ t('mobile.kittyCreateNewMindmap', '新建思维导图') }}</span>
      </button>

      <div
        v-if="diagrams.length > 0 || isLoading"
        class="kitty-diagram-picker-panel__search"
      >
        <Search
          :size="14"
          class="kitty-diagram-picker-panel__search-icon"
          aria-hidden="true"
        />
        <input
          v-model="searchQuery"
          type="search"
          class="kitty-diagram-picker-panel__search-input"
          :placeholder="t('mobile.kittyDiagramPickerSearch', '搜索导图…')"
          autocomplete="off"
          enterkeyhint="search"
        />
      </div>

      <div
        v-if="isLoading && diagrams.length === 0"
        class="kitty-diagram-picker-panel__state"
      >
        <Loader2
          :size="18"
          class="animate-spin text-stone-400"
        />
        <span>{{ t('mobile.kittyDiagramPickerLoading', '加载中…') }}</span>
      </div>

      <div
        v-else-if="diagrams.length === 0"
        class="kitty-diagram-picker-panel__state"
      >
        {{ t('mobile.kittyDiagramPickerEmpty', '暂无已保存的导图') }}
      </div>

      <div
        v-else-if="filteredDiagrams.length === 0"
        class="kitty-diagram-picker-panel__state"
      >
        {{ t('mobile.kittyDiagramPickerNoMatch', '没有匹配的导图') }}
      </div>

      <ul
        v-else
        class="kitty-diagram-picker-panel__list"
      >
        <li
          v-for="diagram in filteredDiagrams"
          :key="diagram.id"
        >
          <button
            type="button"
            class="kitty-diagram-picker-option"
            :class="{ 'kitty-diagram-picker-option--selected': diagram.id === currentDiagramId }"
            role="option"
            :aria-selected="diagram.id === currentDiagramId"
            :disabled="selecting"
            @click="handleSelect(diagram)"
          >
            <span class="kitty-diagram-picker-option__text">
              <span class="kitty-diagram-picker-option__title">
                <Pin
                  v-if="diagram.is_pinned"
                  :size="12"
                  class="kitty-diagram-picker-option__pin"
                  aria-hidden="true"
                />
                {{ diagram.title }}
              </span>
              <span class="kitty-diagram-picker-option__meta">
                {{ typeLabelFor(diagram.diagram_type) }}
              </span>
            </span>
            <Check
              v-if="diagram.id === currentDiagramId"
              :size="16"
              class="kitty-diagram-picker-option__check"
              aria-hidden="true"
            />
          </button>
        </li>
      </ul>

      <div
        v-if="selecting"
        class="kitty-diagram-picker-panel__overlay"
        aria-hidden="true"
      >
        <Loader2
          :size="22"
          class="animate-spin text-stone-500"
        />
      </div>
    </div>
  </ElPopover>
</template>

<style scoped>
.kitty-diagram-picker-anchor {
  display: block;
  width: 100%;
  min-width: 0;
  height: 100%;
}

.kitty-diagram-picker-anchor :deep(.el-tooltip__trigger),
.kitty-diagram-picker-anchor :deep(.el-popover__reference) {
  display: block;
  width: 100%;
  min-width: 0;
  height: 100%;
}

.kitty-diagram-picker-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kitty-diagram-picker-panel__header {
  padding: 2px 2px 8px;
}

.kitty-diagram-picker-panel__label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #78716c;
}

.kitty-diagram-picker-create {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  width: 100%;
  margin: 0 0 8px;
  padding: 0.55rem 0.65rem;
  border-radius: 0.65rem;
  border: 1px dashed rgba(120, 113, 108, 0.55);
  background: rgba(250, 250, 249, 0.95);
  color: #44403c;
  font-size: 0.8125rem;
  font-weight: 650;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.kitty-diagram-picker-create:active:not(:disabled) {
  background: #f5f5f4;
}

.kitty-diagram-picker-create:disabled {
  opacity: 0.55;
  cursor: default;
}

.kitty-diagram-picker-create__icon {
  flex-shrink: 0;
  color: #57534e;
}

.kitty-diagram-picker-panel__search {
  position: relative;
  margin-bottom: 6px;
}

.kitty-diagram-picker-panel__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #a8a29e;
  pointer-events: none;
}

.kitty-diagram-picker-panel__search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px 8px 30px;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  background: #fafaf9;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
}

.kitty-diagram-picker-panel__search-input:focus {
  outline: none;
  border-color: #d6d3d1;
  background: #ffffff;
  box-shadow: 0 0 0 2px rgba(120, 113, 108, 0.12);
}

.kitty-diagram-picker-panel__search-input::placeholder {
  color: #a8a29e;
  font-weight: 400;
}

.kitty-diagram-picker-panel__list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: min(52vh, 280px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.kitty-diagram-picker-panel__list::-webkit-scrollbar {
  width: 5px;
}

.kitty-diagram-picker-panel__list::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 99px;
}

.kitty-diagram-picker-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  margin: 1px 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.kitty-diagram-picker-option:active {
  background: #e7e5e4;
}

@media (hover: hover) {
  .kitty-diagram-picker-option:hover {
    background: #f5f5f4;
  }

  .kitty-diagram-picker-option--selected:hover {
    background: #ececea;
  }
}

.kitty-diagram-picker-option--selected {
  background: #f5f5f4;
}

.kitty-diagram-picker-option__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.kitty-diagram-picker-option__title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-diagram-picker-option__meta {
  font-size: 11px;
  font-weight: 500;
  color: #a8a29e;
  letter-spacing: 0.02em;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-diagram-picker-option__pin {
  flex-shrink: 0;
  color: #d97706;
}

.kitty-diagram-picker-option__check {
  flex-shrink: 0;
  color: #57534e;
}

.kitty-diagram-picker-panel__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #78716c;
  text-align: center;
}

.kitty-diagram-picker-panel__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.72);
  border-radius: 6px;
}
</style>

<!-- Teleported popper -->
<style>
.kitty-mobile-diagram-picker-popper.el-popper {
  box-sizing: border-box !important;
  width: min(320px, calc(100vw - 24px)) !important;
  max-width: min(320px, calc(100vw - 24px)) !important;
  padding: 8px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  background: #ffffff !important;
  overflow: hidden !important;
}

.dark .kitty-mobile-diagram-picker-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.dark .kitty-diagram-picker-panel__label {
  color: #9ca3af;
}

.dark .kitty-diagram-picker-create {
  border-color: rgba(156, 163, 175, 0.45);
  background: rgba(17, 24, 39, 0.92);
  color: #e5e7eb;
}

.dark .kitty-diagram-picker-create:active:not(:disabled) {
  background: rgba(55, 65, 81, 0.95);
}

.dark .kitty-diagram-picker-create__icon {
  color: #9ca3af;
}

.dark .kitty-diagram-picker-panel__search-input {
  border-color: #374151;
  background: #111827;
  color: #e5e7eb;
}

.dark .kitty-diagram-picker-panel__search-input:focus {
  border-color: #4b5563;
  background: #1f2937;
}

.dark .kitty-diagram-picker-option__title {
  color: #e5e7eb;
}

.dark .kitty-diagram-picker-option--selected {
  background: #374151;
}

.dark .kitty-diagram-picker-option:active {
  background: #4b5563;
}

.dark .kitty-diagram-picker-option__check {
  color: #d1d5db;
}

.dark .kitty-diagram-picker-panel__overlay {
  background: rgba(31, 41, 55, 0.72);
}
</style>
