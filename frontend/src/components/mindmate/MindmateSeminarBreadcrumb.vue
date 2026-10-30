<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'

const props = withDefaults(
  defineProps<{
    visibility?: string
    sessionTitle?: string
    /** Toolbar on /mindmate full page (dark mode classes). */
    tone?: 'light' | 'toolbar'
    canRename?: boolean
    renaming?: boolean
  }>(),
  {
    visibility: 'organization',
    sessionTitle: '',
    tone: 'light',
    canRename: false,
    renaming: false,
  }
)

const emit = defineEmits<{
  (e: 'rename', title: string): void
}>()

const { t } = useLanguage()
const editing = ref(false)
const draft = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

const isPublicSeminar = computed(() => props.visibility === 'network')

const titleLabel = computed(() => {
  const name = props.sessionTitle.trim()
  return name || t('mindmate.collabPill')
})

const parentClass = computed(() =>
  props.tone === 'toolbar' ? 'text-gray-500 dark:text-gray-400' : 'text-stone-500'
)

const currentClass = computed(() =>
  props.tone === 'toolbar'
    ? 'font-semibold text-gray-900 dark:text-white'
    : 'font-semibold text-stone-900'
)

const sepClass = computed(() =>
  props.tone === 'toolbar' ? 'text-gray-400 dark:text-gray-500' : 'text-stone-400'
)

watch(
  () => props.sessionTitle,
  (value) => {
    if (!editing.value) {
      draft.value = value
    }
  }
)

async function beginEdit(): Promise<void> {
  if (!props.canRename || props.renaming) {
    return
  }
  draft.value = props.sessionTitle.trim()
  editing.value = true
  await nextTick()
  inputEl.value?.focus()
  inputEl.value?.select()
}

function cancelEdit(): void {
  editing.value = false
  draft.value = props.sessionTitle
}

function commitEdit(): void {
  const next = draft.value.trim()
  editing.value = false
  if (!next || next === props.sessionTitle.trim()) {
    draft.value = props.sessionTitle
    return
  }
  emit('rename', next)
}
</script>

<template>
  <nav
    aria-label="breadcrumb"
    class="mindmate-seminar-breadcrumb flex min-w-0 items-center gap-1 truncate"
  >
    <span
      class="truncate shrink-0"
      :class="parentClass"
    >
      <I18nText
        :k="isPublicSeminar ? 'mindmate.collabSeminarPublic' : 'mindmate.collabSeminarOrg'"
      />
    </span>
    <span
      class="shrink-0"
      :class="sepClass"
      aria-hidden="true"
    >
      /
    </span>
    <input
      v-if="editing"
      ref="inputEl"
      v-model="draft"
      type="text"
      class="mindmate-seminar-breadcrumb__input"
      maxlength="200"
      :placeholder="t('mindmate.home.renameSeminarPlaceholder')"
      :disabled="renaming"
      @keydown.enter.prevent="commitEdit"
      @keydown.esc.prevent="cancelEdit"
      @blur="commitEdit"
    />
    <button
      v-else-if="canRename"
      type="button"
      class="mindmate-seminar-breadcrumb__title truncate"
      :class="currentClass"
      :title="t('mindmate.home.renameSeminar')"
      @click="beginEdit"
    >
      {{ titleLabel }}
    </button>
    <span
      v-else
      class="truncate"
      :class="currentClass"
    >
      {{ titleLabel }}
    </span>
  </nav>
</template>

<style scoped>
.mindmate-seminar-breadcrumb {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
}

.mindmate-seminar-breadcrumb__title {
  max-width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: text;
  border-radius: 6px;
}

.mindmate-seminar-breadcrumb__title:hover {
  background: #f5f5f4;
}

.mindmate-seminar-breadcrumb__input {
  min-width: 0;
  flex: 1 1 auto;
  max-width: 100%;
  height: 30px;
  padding: 0 8px;
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  background: #fff;
  color: #1c1917;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  outline: none;
  box-shadow: 0 0 0 3px rgba(109, 94, 252, 0.12);
}
</style>
