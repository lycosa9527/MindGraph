<script setup lang="ts">
/**
 * ExportToCommunityModal - Share diagram to community
 * Create: title, description, category; generates thumbnail from container
 * Edit: same form, optional thumbnail re-upload
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElButton, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus'

import { toPng } from 'html-to-image'

import {
  createCommunityPost,
  updateCommunityPost,
  type CommunityPost,
} from '@/utils/apiClient'
import { useLanguage, useNotifications } from '@/composables'

const categoryOptions = [
  '学习笔记',
  '教学设计',
  '读书感悟',
  '工作总结',
  '创意灵感',
  '知识整理',
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
const { isZh } = useLanguage()
const notify = useNotifications()

const title = ref('')
const description = ref('')
const category = ref<string>('')
const isSubmitting = ref(false)

const isEdit = computed(() => props.mode === 'edit')
const modalTitle = computed(() =>
  isZh.value ? (isEdit.value ? '编辑分享' : '分享到社区') : isEdit.value ? 'Edit Post' : 'Share to Community'
)
const submitLabel = computed(() =>
  isZh.value ? (isEdit.value ? '保存' : '发布') : isEdit.value ? 'Save' : 'Publish'
)

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

async function generateThumbnail(): Promise<Blob | null> {
  const container = props.getContainer()
  if (!container) {
    notify.warning(isZh.value ? '无法生成预览图' : 'Cannot generate preview')
    return null
  }
  try {
    const dataUrl = await toPng(container, {
      backgroundColor: '#ffffff',
      pixelRatio: 2,
      style: { transform: 'none' },
    })
    const res = await fetch(dataUrl)
    return await res.blob()
  } catch (e) {
    console.error('[ExportToCommunity] Thumbnail generation failed:', e)
    notify.error(isZh.value ? '预览图生成失败' : 'Failed to generate preview')
    return null
  }
}

async function submit() {
  if (!title.value.trim()) {
    notify.warning(isZh.value ? '请输入标题' : 'Please enter a title')
    return
  }

  let spec: Record<string, unknown> | null = null
  if (props.mode === 'edit' && props.initialPost) {
    spec = (props.initialPost as CommunityPost & { spec?: unknown }).spec as Record<string, unknown> | undefined
      ?? null
  } else {
    spec = props.getDiagramSpec()
  }

  if (!spec) {
    notify.warning(isZh.value ? '没有可分享的图示数据' : 'No diagram data to share')
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
      notify.success(isZh.value ? '已更新' : 'Updated')
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
      notify.success(isZh.value ? '已发布到社区' : 'Published to community')
      emit('success', result.post)
      close()
      router.push('/community')
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : (isZh.value ? '操作失败' : 'Operation failed')
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
      <el-form-item :label="isZh ? '标题' : 'Title'" required>
        <el-input
          v-model="title"
          :placeholder="isZh ? '给你的分享起个标题' : 'Give your post a title'"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
      <el-form-item :label="isZh ? '描述' : 'Description'">
        <el-input
          v-model="description"
          type="textarea"
          :rows="4"
          :placeholder="isZh ? '介绍一下你的作品...' : 'Describe your work...'"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item :label="isZh ? '分类' : 'Category'">
        <el-select
          v-model="category"
          :placeholder="isZh ? '选择分类' : 'Select category'"
          clearable
          class="w-full"
        >
          <el-option
            v-for="opt in categoryOptions"
            :key="opt"
            :label="opt"
            :value="opt"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="close">
          {{ isZh ? '取消' : 'Cancel' }}
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
