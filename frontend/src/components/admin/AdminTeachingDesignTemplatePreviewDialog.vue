<script setup lang="ts">
/**
 * Showcase-style Word preview when clicking a template name.
 */
import { computed } from 'vue'

import { FileText } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import ShowcaseTeachingDocPreview from '@/components/showcase/ShowcaseTeachingDocPreview.vue'
import { useLanguage } from '@/composables'
import {
  teachingDesignTemplateDownloadUrl,
  teachingDesignTemplatePreviewUrl,
  type TeachingDesignTemplateRow,
} from '@/composables/admin/teachingDesignTemplateApi'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  row: TeachingDesignTemplateRow | null
}>()

const { t } = useLanguage()

const title = computed(() => {
  const name = props.row?.name.trim()
  if (name) {
    return name
  }
  if (props.row?.source === 'bundled') {
    return t('admin.teachingDesignTemplate.optionBundled')
  }
  return props.row?.filename || t('admin.teachingDesignTemplate.previewTitle')
})

const attachmentUrl = computed(() =>
  props.row ? teachingDesignTemplateDownloadUrl(props.row.id) : null
)

const previewUrl = computed(() =>
  props.row ? teachingDesignTemplatePreviewUrl(props.row.id) : null
)
</script>

<template>
  <SwissGlassCard
    v-model="visible"
    :ribbon="t('admin.teachingDesignTemplate.previewRibbon')"
    ribbon-key="admin.teachingDesignTemplate.previewRibbon"
    :title="t('admin.teachingDesignTemplate.previewTitle')"
    title-key="admin.teachingDesignTemplate.previewTitle"
    :line1="t('admin.teachingDesignTemplate.previewHint')"
    line1-key="admin.teachingDesignTemplate.previewHint"
    :line2="title"
    :icon="FileText"
    card-class="swiss-glass-card--xl admin-teaching-design-preview-card"
  >
    <div
      v-if="row"
      class="admin-teaching-design-preview-body"
    >
      <ShowcaseTeachingDocPreview
        :attachment-url="attachmentUrl"
        :preview-url="previewUrl"
        :fallback-text="t('admin.teachingDesignTemplate.previewFail')"
      />
    </div>
  </SwissGlassCard>
</template>

<style scoped>
.admin-teaching-design-preview-body {
  display: flex;
  flex-direction: column;
  min-height: min(62vh, 640px);
  height: min(62vh, 640px);
  margin: 0 -6px;
  overflow: hidden;
  border-radius: 0.75rem;
  background: #fff;
}

.admin-teaching-design-preview-body :deep(.showcase-doc-reader) {
  flex: 1 1 auto;
  min-height: 0;
}
</style>
