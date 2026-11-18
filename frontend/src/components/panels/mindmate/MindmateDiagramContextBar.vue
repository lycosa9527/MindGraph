<script setup lang="ts">
/**
 * Include/exclude current diagram in MindMate prompts.
 */
import { computed } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'

const includeDiagram = defineModel<boolean>({ default: true })

const { t } = useLanguage()

const diagramChoice = computed({
  get: () => (includeDiagram.value ? 'include' : 'exclude'),
  set: (value: string) => {
    includeDiagram.value = value === 'include'
  },
})

const diagramOptions = computed(() => [
  { labelKey: 'mindmate.diagramContext.off', value: 'exclude' },
  { labelKey: 'mindmate.diagramContext.on', value: 'include' },
])
</script>

<template>
  <div class="mm-diagram-context">
    <span class="mm-diagram-context__label">
      <I18nText
        k="mindmate.diagramContext.label"
        dense
        primary-only
      />
    </span>
    <AdminSwissSegmented
      v-model="diagramChoice"
      equal
      class="mm-diagram-context__seg"
      :options="diagramOptions"
      :aria-label="t('mindmate.diagramContext.label')"
    />
  </div>
</template>

<style scoped>
.mm-diagram-context {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 0 16px 4px;
}

.mm-diagram-context__label {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--swiss-ink, #1c1917);
  white-space: nowrap;
}

.mm-diagram-context__seg :deep(.admin-swiss-segment) {
  min-height: 26px;
  min-width: 3.75rem;
  padding: 0.1rem 0.5rem;
  font-size: 12px;
  justify-content: center;
}

.mm-diagram-context__seg :deep(.admin-swiss-segment.is-active) {
  background: var(--swiss-geek-violet-ui, #7c3aed);
  color: #fff;
}

:global(html.dark) .mm-diagram-context__label {
  color: var(--swiss-ink, #f5f5f4);
}

:global(html.dark) .mm-diagram-context__seg :deep(.admin-swiss-segment.is-active) {
  background: var(--swiss-geek-violet, #a78bfa);
  color: #1c1917;
}
</style>
