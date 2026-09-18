<script setup lang="ts">
/**
 * Rename / default / replace / delete one teaching-design Word template.
 */
import { computed, ref, watch } from 'vue'

import { Settings2 } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  type TeachingDesignTemplateRow,
  deleteTeachingDesignTemplate,
  downloadTeachingDesignTemplateFile,
  patchTeachingDesignTemplate,
  replaceTeachingDesignTemplateFile,
} from '@/composables/admin/teachingDesignTemplateApi'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  row: TeachingDesignTemplateRow | null
  canEdit: boolean
}>()

const emit = defineEmits<{
  saved: []
}>()

const { t } = useLanguage()
const notify = useNotifications()

const nameEdit = ref('')
const isDefaultEdit = ref(false)
const saving = ref(false)
const replacing = ref(false)
const deleting = ref(false)
const replaceInput = ref<HTMLInputElement | null>(null)

const displayName = computed(() => {
  const name = nameEdit.value.trim()
  if (name) {
    return name
  }
  if (props.row?.source === 'bundled') {
    return t('admin.teachingDesignTemplate.optionBundled')
  }
  return props.row?.filename || ''
})

watch(
  () => [visible.value, props.row] as const,
  ([open, row]) => {
    if (!open || !row) {
      return
    }
    nameEdit.value = row.name
    isDefaultEdit.value = row.is_default
  }
)

async function save(): Promise<void> {
  if (!props.row || !props.canEdit) {
    return
  }
  const nextName = nameEdit.value.trim()
  if (props.row.source === 'uploaded' && !nextName) {
    notify.error(t('admin.teachingDesignTemplate.nameRequired'))
    return
  }
  saving.value = true
  try {
    await patchTeachingDesignTemplate(props.row.id, {
      name: nextName,
      ...(isDefaultEdit.value ? { is_default: true } : {}),
    })
    notify.success(t('admin.teachingDesignTemplate.saveOk'))
    visible.value = false
    emit('saved')
  } catch {
    notify.error(t('admin.teachingDesignTemplate.saveFail'))
  } finally {
    saving.value = false
  }
}

async function onReplaceFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !props.row || !props.canEdit) {
    return
  }
  if (!file.name.toLowerCase().endsWith('.docx')) {
    notify.error(t('admin.teachingDesignTemplate.invalidType'))
    return
  }
  replacing.value = true
  try {
    await replaceTeachingDesignTemplateFile(props.row.id, file)
    notify.success(t('admin.teachingDesignTemplate.replaceOk'))
    emit('saved')
  } catch {
    notify.error(t('admin.teachingDesignTemplate.uploadFail'))
  } finally {
    replacing.value = false
  }
}

async function onDownload(): Promise<void> {
  if (!props.row) {
    return
  }
  try {
    await downloadTeachingDesignTemplateFile(props.row.id)
  } catch {
    notify.error(t('admin.teachingDesignTemplate.downloadFail'))
  }
}

async function onDelete(): Promise<void> {
  if (!props.row?.can_delete || !props.canEdit) {
    return
  }
  try {
    await swissGlassConfirm(
      t('admin.teachingDesignTemplate.deleteConfirm'),
      t('admin.teachingDesignTemplate.delete'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      }
    )
  } catch {
    return
  }
  deleting.value = true
  try {
    await deleteTeachingDesignTemplate(props.row.id)
    notify.success(t('admin.teachingDesignTemplate.deleteOk'))
    visible.value = false
    emit('saved')
  } catch {
    notify.error(t('admin.teachingDesignTemplate.deleteFail'))
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('swissGlass.hero.adminInline.ribbon')"
    ribbon-key="swissGlass.hero.adminInline.ribbon"
    :title="t('swissGlass.hero.adminInline.title')"
    title-key="swissGlass.hero.adminInline.title"
    :line1="t('swissGlass.hero.adminInline.line1')"
    line1-key="swissGlass.hero.adminInline.line1"
    :line2="t('admin.teachingDesignTemplate.editTitle')"
    line2-key="admin.teachingDesignTemplate.editTitle"
    :icon="Settings2"
    width="min(480px, 92vw)"
  >
    <div
      v-if="row"
      class="space-y-4 text-sm"
    >
      <label class="block">
        <span class="text-stone-600"><I18nText k="admin.teachingDesignTemplate.nameLabel" /></span>
        <el-input
          v-model="nameEdit"
          :placeholder="t('admin.teachingDesignTemplate.namePlaceholder')"
          :disabled="!canEdit"
          maxlength="80"
          class="mt-1"
        />
      </label>
      <label class="flex items-center justify-between gap-3">
        <span class="text-stone-600"><I18nText k="admin.teachingDesignTemplate.setDefault" /></span>
        <el-switch
          v-model="isDefaultEdit"
          :disabled="!canEdit || row.is_default"
        />
      </label>
      <p class="m-0 text-xs text-stone-500">
        {{ row.filename }}
      </p>
      <div class="flex flex-wrap gap-2">
        <el-button
          size="small"
          class="admin-swiss-btn"
          @click="onDownload"
        >
          <I18nText k="admin.teachingDesignTemplate.download" />
        </el-button>
        <el-button
          v-if="canEdit && row.source === 'uploaded'"
          size="small"
          class="admin-swiss-btn"
          :loading="replacing"
          @click="replaceInput?.click()"
        >
          <I18nText k="admin.teachingDesignTemplate.replaceFile" />
        </el-button>
        <el-button
          v-if="canEdit && row.can_delete"
          size="small"
          type="danger"
          plain
          :loading="deleting"
          @click="onDelete"
        >
          <I18nText k="admin.teachingDesignTemplate.delete" />
        </el-button>
      </div>
      <input
        ref="replaceInput"
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        class="hidden"
        @change="onReplaceFile"
      />
    </div>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="visible = false"
        >
          <I18nText k="common.cancel" />
        </button>
        <button
          v-if="canEdit"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="saving || !displayName"
          @click="save"
        >
          <I18nText k="admin.save" />
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
