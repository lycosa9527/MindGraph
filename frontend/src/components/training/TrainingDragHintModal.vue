<script setup lang="ts">
import { ref, watch } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import { closeTrainingDragHint, trainingDragHint } from '@/composables/training/trainingDragKnock'

const emit = defineEmits<{
  save: [payload: { nodeId: string; text: string }]
}>()

const { t } = useLanguage()
const draft = ref('')

watch(
  trainingDragHint,
  (row) => {
    draft.value = row?.text ?? ''
  },
  { immediate: true }
)

function close(): void {
  closeTrainingDragHint()
}

function confirm(): void {
  const row = trainingDragHint.value
  if (row?.editable) emit('save', { nodeId: row.nodeId, text: draft.value })
  close()
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="trainingDragHint"
      class="drag-hint"
      role="dialog"
      aria-modal="true"
      :aria-label="t('canvas.floatingToolbar.explain')"
      @click.self="close"
    >
      <div class="drag-hint__card">
        <p class="drag-hint__title">
          <I18nText k="canvas.floatingToolbar.explain" />
        </p>
        <textarea
          v-if="trainingDragHint.editable"
          v-model="draft"
          class="drag-hint__field"
          rows="5"
          :placeholder="t('training.builder.interactHintBody')"
        />
        <p
          v-else
          class="drag-hint__text"
        >
          <template v-if="trainingDragHint.text">{{ trainingDragHint.text }}</template
          ><I18nText
            v-else
            k="training.builder.interactHintRetry"
          />
        </p>
        <button
          type="button"
          class="drag-hint__ok"
          @click="confirm"
        >
          <I18nText :k="trainingDragHint.editable ? 'common.ok' : 'common.close'" />
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.drag-hint {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  background: rgb(28 25 23 / 0.35);
  pointer-events: auto;
}
.drag-hint__card {
  display: flex;
  width: min(22rem, calc(100vw - 2rem));
  flex-direction: column;
  gap: 0.7rem;
  border-radius: 12px;
  background: #fff;
  padding: 1rem 1rem 0.85rem;
  box-shadow: 0 18px 40px rgb(28 25 23 / 0.18);
}
.drag-hint__title {
  margin: 0;
  color: #1f2937;
  font-size: 14px;
  font-weight: 700;
}
.drag-hint__field,
.drag-hint__text {
  margin: 0;
  color: #374151;
  font-size: 13px;
  line-height: 1.5;
}
.drag-hint__field {
  box-sizing: border-box;
  width: 100%;
  resize: vertical;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  padding: 0.5rem 0.55rem;
}
.drag-hint__ok {
  align-self: flex-end;
  border: 0;
  border-radius: 6px;
  background: #4f46e5;
  padding: 0.4rem 0.85rem;
  color: #fff;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}
</style>
