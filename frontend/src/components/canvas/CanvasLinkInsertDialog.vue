<script setup lang="ts">
/**
 * Swiss stone dialog to attach an http(s) hyperlink to the selected mind-map node.
 * Header plus the small top-right menu; name is shown on the node, URL on the icon.
 */
import { ref, watch } from 'vue'

import { ElDialog } from 'element-plus'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import '@/components/canvas/aiGenerateGlass.css'
import { useLanguage } from '@/composables/core/useLanguage'
import { sanitizeMindMapHref } from '@/utils/mindMapAdornments'

const props = defineProps<{
  modelValue: boolean
  initialHref?: string
  initialName?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [href: string, name: string]
}>()

const { t } = useLanguage()
const name = ref('')
const href = ref('')
const error = ref('')

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      name.value = props.initialName ?? ''
      href.value = props.initialHref ?? ''
      error.value = ''
    }
  }
)

function close(): void {
  emit('update:modelValue', false)
}

function confirm(): void {
  const sanitized = sanitizeMindMapHref(href.value)
  if (!sanitized) {
    error.value = t('canvas.ribbon.linkInvalid')
    return
  }
  emit('confirm', sanitized, name.value.trim())
  close()
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    width="min(480px, 92vw)"
    top="12vh"
    append-to-body
    destroy-on-close
    :show-close="false"
    class="mm-link-insert mm-canvas-upper-dialog ai-gen-shell ai-gen-shell--link"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <AiGenerateGlassHero
        variant="link"
        @close="close"
      />
    </template>

    <div class="mm-link-stack">
      <label class="mm-link-field">
        <span class="mm-link-field__kicker">{{ t('canvas.ribbon.linkName') }}</span>
        <input
          v-model="name"
          type="text"
          class="mm-link-field__input"
          :placeholder="t('canvas.ribbon.linkName')"
          autocomplete="off"
          @keydown.enter.prevent="confirm"
        />
      </label>
      <label class="mm-link-field">
        <span class="mm-link-field__kicker">{{ t('canvas.ribbon.linkUrl') }}</span>
        <input
          v-model="href"
          type="url"
          inputmode="url"
          class="mm-link-field__input"
          :placeholder="t('canvas.ribbon.linkUrl')"
          autocomplete="url"
          @keydown.enter.prevent="confirm"
        />
      </label>
      <p
        v-if="error"
        class="mm-link-error"
      >
        {{ error }}
      </p>
    </div>

    <template #footer>
      <div class="mm-link-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="close"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="confirm"
        >
          {{ t('canvas.ribbon.linkConfirm') }}
        </button>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-link-stack {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.mm-link-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.mm-link-field__kicker {
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ai-muted, #6b7280);
}

.mm-link-field__input {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgb(231 229 228);
  background: rgb(255 255 255 / 0.78);
  padding: 0.65rem 0.8rem;
  font-size: 0.875rem;
  color: var(--ai-ink, #1f2937);
  outline: none;
}

.mm-link-field__input::placeholder {
  color: #a8a29e;
}

.mm-link-field__input:focus {
  border-color: #c7d2fe;
  box-shadow: 0 0 0 3px rgb(99 102 241 / 0.12);
}

.mm-link-error {
  margin: 0;
  color: #b91c1c;
  font-size: 12px;
}

.mm-link-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
}

.dark .mm-link-field__kicker {
  color: #94a3b8;
}

.dark .mm-link-field__input {
  border-color: rgb(255 255 255 / 0.16);
  background: rgb(15 23 42 / 0.45);
  color: #f8fafc;
}
</style>
