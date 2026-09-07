<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ElMessage } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { embedWorkshopLibraryDiagram } from '@/utils/workshopDiagramEmbed'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  insert: [markdown: string]
}>()

const { t } = useLanguage()
const savedStore = useSavedDiagramsStore()
const insertingId = ref<string | null>(null)

const diagrams = computed(() => savedStore.diagrams)
const isLoading = computed(() => savedStore.isLoading && diagrams.value.length === 0)

watch(
  () => props.visible,
  (open) => {
    if (!open) {
      insertingId.value = null
      return
    }
    void savedStore.fetchDiagrams(1, 50, { force: true })
  }
)

function diagramTypeLabel(type: string): string {
  const key = `sidebar.diagramType.${type}`
  const translated = t(key)
  return translated === key ? type : translated
}

async function pick(diagram: SavedDiagram): Promise<void> {
  if (insertingId.value) {
    return
  }
  insertingId.value = String(diagram.id)
  try {
    const markdown = await embedWorkshopLibraryDiagram({
      id: String(diagram.id),
      title: diagram.title || t('workshop.diagram'),
      thumbnail: diagram.thumbnail,
    })
    if (!markdown) {
      ElMessage.error(t('workshop.diagramInsertFailed'))
      return
    }
    emit('insert', markdown)
    emit('update:visible', false)
  } catch {
    ElMessage.error(t('workshop.diagramInsertFailed'))
  } finally {
    insertingId.value = null
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="t('workshop.diagramPickerTitle')"
    width="560px"
    append-to-body
    class="ws-diagram-picker"
    @update:model-value="emit('update:visible', $event)"
  >
    <p
      v-if="isLoading"
      class="ws-diagram-picker__hint"
    >
      {{ t('workshop.diagramInserting') }}
    </p>
    <p
      v-else-if="diagrams.length === 0"
      class="ws-diagram-picker__hint"
    >
      {{ t('workshop.diagramPickerEmpty') }}
    </p>
    <ul
      v-else
      class="ws-diagram-picker__list"
    >
      <li
        v-for="diagram in diagrams"
        :key="diagram.id"
      >
        <button
          type="button"
          class="ws-diagram-picker__row"
          :disabled="insertingId != null"
          @click="pick(diagram)"
        >
          <span class="ws-diagram-picker__meta">
            <span class="ws-diagram-picker__title">{{ diagram.title || t('workshop.diagram') }}</span>
            <span class="ws-diagram-picker__type">{{ diagramTypeLabel(diagram.diagram_type) }}</span>
          </span>
          <span
            v-if="insertingId === String(diagram.id)"
            class="ws-diagram-picker__busy"
          >
            {{ t('workshop.diagramInserting') }}
          </span>
        </button>
      </li>
    </ul>
  </el-dialog>
</template>

<style scoped>
.ws-diagram-picker__hint {
  margin: 0;
  font-size: 13px;
  color: hsl(0deg 0% 40%);
  line-height: 1.5;
}

.ws-diagram-picker__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid hsl(0deg 0% 0% / 8%);
  border-radius: 8px;
}

.ws-diagram-picker__list li + li {
  border-top: 1px solid hsl(0deg 0% 0% / 6%);
}

.ws-diagram-picker__row {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  position: relative;
}

.ws-diagram-picker__row:hover:not(:disabled) {
  background: hsl(228deg 56% 97%);
}

.ws-diagram-picker__row:disabled {
  cursor: default;
  opacity: 0.7;
}

.ws-diagram-picker__meta {
  min-width: 0;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.ws-diagram-picker__title {
  font-size: 13px;
  font-weight: 600;
  color: hsl(0deg 0% 18%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-diagram-picker__type {
  font-size: 11px;
  color: hsl(0deg 0% 48%);
}

.ws-diagram-picker__busy {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: hsl(0deg 0% 100% / 82%);
  font-size: 12px;
  font-weight: 600;
  color: hsl(228deg 40% 36%);
}
</style>
