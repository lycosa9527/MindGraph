<script setup lang="ts">
/**
 * ExportToCommunityModal - Share diagram to community
 * Create: title, description, category; generates thumbnail from container
 * Edit: same form, optional thumbnail re-upload
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElOption, ElSelect } from 'element-plus'

import { toPng } from 'html-to-image'

import { useLanguage, useNotifications } from '@/composables'
import { type CommunityPost, createCommunityPost, updateCommunityPost } from '@/utils/apiClient'

/** Stored category values (Chinese) — API / existing posts use these strings */
const CATEGORY_CATALOG = [
  { value: '学习笔记', key: 'studyNotes' as const },
  { value: '教学设计', key: 'teachingDesign' as const },
  { value: '读书感悟', key: 'readingReflection' as const },
  { value: '工作总结', key: 'workSummary' as const },
  { value: '创意灵感', key: 'creative' as const },
  { value: '知识整理', key: 'knowledge' as const },
] as const

const props = withDefaults(
  defineProps<{
    visible: boolean
    mode: 'create' | 'edit'
    getContainer?: () => HTMLElement | null
    getDiagramSpec?: () => Record<string, unknown> | null
    getTitle?: () => string
    diagramType: string
    initialPost?: (CommunityPost & { spec?: unknown }) | null
  }>(),
  {
    getContainer: () => null,
    getDiagramSpec: () => null,
    getTitle: () => '',
  }
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success', post: CommunityPost): void
}>()

const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()

const title = ref('')
const description = ref('')
const category = ref<string>('')
const isSubmitting = ref(false)

const isEdit = computed(() => props.mode === 'edit')
const modalTitle = computed(() =>
  isEdit.value ? t('community.shareModal.titleEdit') : t('community.shareModal.titleCreate')
)
const submitLabel = computed(() =>
  isEdit.value ? t('community.shareModal.save') : t('community.shareModal.publish')
)

function categoryLabelKey(k: (typeof CATEGORY_CATALOG)[number]['key']): string {
  return `community.category.${k}`
}

watch(
  () => [props.visible, props.initialPost] as const,
  ([visible, post]) => {
    if (visible) {
      if (post) {
        title.value = post.title
        description.value = post.description || ''
        category.value = post.category || ''
      } else {
        title.value = props.getTitle?.() || ''
        description.value = ''
        category.value = ''
      }
    }
  }
)

function close() {
  emit('update:visible', false)
}

function dataUrlToBlob(dataUrl: string): Blob {
  const arr = dataUrl.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] ?? 'image/png'
  const bstr = atob(arr[1])
  const u8arr = new Uint8Array(bstr.length)
  for (let i = 0; i < bstr.length; i++) {
    u8arr[i] = bstr.charCodeAt(i)
  }
  return new Blob([u8arr], { type: mime })
}

async function generateThumbnail(): Promise<Blob | null> {
  const container = props.getContainer()
  if (!container) {
    notify.warning(t('community.shareModal.cannotPreview'))
    return null
  }
  try {
    const dataUrl = await toPng(container, {
      backgroundColor: '#ffffff',
      pixelRatio: 2,
      style: { transform: 'none' },
    })
    return dataUrlToBlob(dataUrl)
  } catch (e) {
    console.error('[ExportToCommunity] Thumbnail generation failed:', e)
    notify.error(t('community.shareModal.previewFailed'))
    return null
  }
}

async function submit() {
  if (!title.value.trim()) {
    notify.warning(t('community.shareModal.enterTitle'))
    return
  }

  let spec: Record<string, unknown> | null = null
  if (props.mode === 'edit' && props.initialPost) {
    spec =
      ((props.initialPost as CommunityPost & { spec?: unknown }).spec as
        | Record<string, unknown>
        | undefined) ?? null
  } else {
    spec = props.getDiagramSpec()
  }

  if (!spec) {
    notify.warning(t('community.shareModal.noDiagramData'))
    return
  }

  isSubmitting.value = true
  try {
    if (props.mode === 'edit' && props.initialPost) {
      const thumbnail = props.getContainer() ? await generateThumbnail() : null
      const result = await updateCommunityPost(props.initialPost.id, {
        title: title.value.trim(),
        description: description.value.trim(),
        category: category.value || null,
        diagram_type: props.diagramType,
        spec,
        thumbnail: thumbnail || undefined,
      })
      notify.success(t('community.shareModal.updated'))
      emit('success', result.post)
      close()
    } else {
      const thumbnail = await generateThumbnail()
      if (!thumbnail) return

      const result = await createCommunityPost({
        title: title.value.trim(),
        description: description.value.trim(),
        category: category.value || null,
        diagram_type: props.diagramType,
        spec,
        thumbnail,
      })
      notify.success(t('community.shareModal.published'))
      emit('success', result.post)
      close()
      router.push('/community')
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : t('community.shareModal.operationFailed')
    notify.error(msg)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="modalTitle"
    width="480px"
    :close-on-click-modal="false"
    class="export-to-community-modal"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form
      label-position="top"
      class="community-form"
    >
      <el-form-item
        :label="t('community.shareModal.titleLabel')"
        required
      >
        <el-input
          v-model="title"
          :placeholder="t('community.shareModal.titlePlaceholder')"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
      <el-form-item :label="t('community.shareModal.descriptionLabel')">
        <el-input
          v-model="description"
          type="textarea"
          :rows="4"
          :placeholder="t('community.shareModal.descriptionPlaceholder')"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item :label="t('community.shareModal.categoryLabel')">
        <el-select
          v-model="category"
          :placeholder="t('community.shareModal.categoryPlaceholder')"
          clearable
          class="w-full"
        >
          <el-option
            v-for="cat in CATEGORY_CATALOG"
            :key="cat.value"
            :label="t(categoryLabelKey(cat.key))"
            :value="cat.value"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="close">
          {{ t('community.shareModal.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="isSubmitting"
          @click="submit"
        >
          {{ submitLabel }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.community-form {
  padding: 8px 0;
}

.w-full {
  width: 100%;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
