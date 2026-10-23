<script setup lang="ts">
/**
 * Auth field with a two-line empty hint on `/auth` (browser language, then Simplified Chinese).
 * Simplified and Traditional Chinese stay one line. Off that page the native placeholder stays one line.
 */
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { authPageSecondaryLocale } from '@/i18n/authPageBilingual'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import { useUIStore } from '@/stores/ui'

const props = withDefaults(
  defineProps<{
    id: string
    modelValue: string
    placeholderKey: string
    type?: string
    name?: string
    maxlength?: number | string
    autocomplete?: string
    inputmode?: 'text' | 'numeric' | 'tel' | 'email' | 'search' | 'none' | 'url' | 'decimal'
    inputClass?: string
    hintClass?: string
    required?: boolean
    disabled?: boolean
    reserveEnd?: boolean
    multiline?: boolean
    rows?: number
  }>(),
  {
    type: 'text',
    name: '',
    maxlength: undefined,
    autocomplete: undefined,
    inputmode: undefined,
    inputClass: '',
    hintClass: '',
    required: false,
    disabled: false,
    reserveEnd: false,
    multiline: false,
    rows: 3,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: []
}>()

const uiStore = useUIStore()
const bilingual = computed(
  () => uiStore.authPageBilingual && authPageSecondaryLocale(uiStore.language) !== null
)
const showHint = computed(() => bilingual.value && props.modelValue.length === 0)
const nativePlaceholder = computed(() => {
  if (bilingual.value) {
    return ''
  }
  return translateForUiLocale(props.placeholderKey, uiStore.language)
})

function onInput(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLTextAreaElement)) {
    return
  }
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div
    class="auth-dual-input"
    :class="{
      'auth-dual-input--pair': bilingual,
      'auth-dual-input--reserve-end': reserveEnd,
      'auth-dual-input--multiline': multiline,
    }"
  >
    <textarea
      v-if="multiline"
      :id="id"
      :value="modelValue"
      :name="name || undefined"
      :maxlength="maxlength"
      :autocomplete="autocomplete"
      :required="required"
      :disabled="disabled"
      :rows="rows"
      :placeholder="nativePlaceholder"
      class="auth-dual-input__control"
      :class="inputClass"
      @input="onInput"
      @blur="emit('blur')"
    />
    <input
      v-else
      :id="id"
      :value="modelValue"
      :type="type"
      :name="name || undefined"
      :maxlength="maxlength"
      :autocomplete="autocomplete"
      :inputmode="inputmode"
      :required="required"
      :disabled="disabled"
      :placeholder="nativePlaceholder"
      class="auth-dual-input__control"
      :class="inputClass"
      @input="onInput"
      @blur="emit('blur')"
    />
    <span
      v-if="showHint"
      class="auth-dual-input__hint"
      :class="hintClass"
      aria-hidden="true"
    >
      <I18nText
        :k="placeholderKey"
        dense
      />
    </span>
    <slot />
  </div>
</template>

<style scoped>
.auth-dual-input {
  position: relative;
}

.auth-dual-input__control {
  display: block;
  width: 100%;
  box-sizing: border-box;
}

.auth-dual-input--pair .auth-dual-input__control {
  min-height: 3.35rem;
}

.auth-dual-input--reserve-end .auth-dual-input__control {
  padding-right: 3rem;
}

.auth-dual-input__hint {
  position: absolute;
  left: 1rem;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: #a8a29e;
  font-size: 0.875rem;
  line-height: 1.15;
  overflow: hidden;
}

.auth-dual-input--reserve-end .auth-dual-input__hint {
  right: 3rem;
}

.auth-dual-input--multiline .auth-dual-input__hint {
  top: 0.75rem;
  transform: none;
}

.auth-dual-input--multiline.auth-dual-input--pair .auth-dual-input__control {
  min-height: 5.5rem;
}
</style>
