<script setup lang="ts">
/**
 * AvatarSelectModal - Emoji picker, plus a photo crop that uploads to COS.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Smile } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAuthStore } from '@/stores/auth'
import {
  photoAvatarsEnabled,
  resolveUserAvatarEmoji,
  userAvatarImageSrc,
} from '@/utils/userAvatarEmoji'

import AvatarCropModal from './AvatarCropModal.vue'
import { AVATAR_EMOJI_CATALOG } from './avatarEmojiCatalog'

const MAX_IMAGE_BYTES = 4 * 1024 * 1024

const notify = useNotifications()
const allowPhotoAvatar = photoAvatarsEnabled()
const { t } = useLanguage()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const allAvatars = AVATAR_EMOJI_CATALOG

const DISPLAY_COUNT = 50
const isLoadingMore = ref(false)
const isSaving = ref(false)
const displayedCount = ref(DISPLAY_COUNT)
const selectedEmoji = ref('')
const scrollbarRef = ref()
const fileInputRef = ref<HTMLInputElement | null>(null)
const cropOpen = ref(false)
const cropSrc = ref('')

const displayedAvatars = computed(() => allAvatars.slice(0, displayedCount.value))

const hasMore = computed(() => displayedCount.value < allAvatars.length)

watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      const stored = authStore.user?.avatar
      selectedEmoji.value = userAvatarImageSrc(stored) ? '' : resolveUserAvatarEmoji(stored)
      displayedCount.value = DISPLAY_COUNT
    }
  }
)

function closeModal() {
  isVisible.value = false
}

function selectAvatar(emoji: string) {
  selectedEmoji.value = emoji
}

function handleScroll() {
  if (isLoadingMore.value || !hasMore.value || !scrollbarRef.value) return

  const wrap = scrollbarRef.value.wrapRef
  if (!wrap) return

  const { scrollTop, scrollHeight, clientHeight } = wrap
  const threshold = 100
  if (scrollTop + clientHeight >= scrollHeight - threshold) {
    loadMore()
  }
}

function loadMore() {
  if (isLoadingMore.value || !hasMore.value) return
  isLoadingMore.value = true
  setTimeout(() => {
    displayedCount.value = Math.min(displayedCount.value + DISPLAY_COUNT, allAvatars.length)
    isLoadingMore.value = false
  }, 300)
}

function revokeCrop() {
  if (cropSrc.value) {
    URL.revokeObjectURL(cropSrc.value)
    cropSrc.value = ''
  }
}

function openCustomize() {
  fileInputRef.value?.click()
}

function onCustomizeFile(event: Event) {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) {
    return
  }
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  if (file.type && !file.type.startsWith('image/')) {
    notify.errorKey('auth.avatarImageInvalid')
    return
  }
  if (file.size > MAX_IMAGE_BYTES) {
    notify.errorKey('auth.avatarImageTooLarge')
    return
  }
  revokeCrop()
  cropSrc.value = URL.createObjectURL(file)
  cropOpen.value = true
}

function onCropInvalid() {
  cropOpen.value = false
  revokeCrop()
  notify.errorKey('auth.avatarImageInvalid')
}

async function uploadCroppedAvatar(blob: Blob) {
  isSaving.value = true
  try {
    const body = new FormData()
    body.append('file', blob, 'avatar.png')
    const response = await fetch('/api/auth/avatar/image', {
      method: 'POST',
      credentials: 'same-origin',
      body,
    })
    if (!response.ok) {
      if (response.status === 413) {
        notify.errorKey('auth.avatarImageTooLarge')
      } else if (response.status === 400) {
        notify.errorKey('auth.avatarImageInvalid')
      } else {
        notify.errorKey('auth.avatarUploadFailed')
      }
      return
    }
    notify.successKey('auth.avatarUploadSuccess')
    cropOpen.value = false
    revokeCrop()
    await authStore.checkAuth()
    emit('success')
    closeModal()
  } catch (error) {
    console.error('Failed to upload avatar:', error)
    notify.errorKey('auth.avatarUploadFailed')
  } finally {
    isSaving.value = false
  }
}

async function saveAvatar() {
  if (!selectedEmoji.value) {
    notify.warning('请选择头像')
    return
  }

  isSaving.value = true

  try {
    const response = await fetch('/api/auth/avatar', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ avatar: selectedEmoji.value }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success(data.message || '头像更新成功')
      await authStore.checkAuth()
      emit('success')
      closeModal()
    } else {
      notify.error(data.detail || data.message || '更新头像失败')
    }
  } catch (error) {
    console.error('Failed to update avatar:', error)
    notify.error('网络错误，更新头像失败')
  } finally {
    isSaving.value = false
  }
}

onBeforeUnmount(revokeCrop)
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.avatar.ribbon')"
    ribbon-key="swissGlass.hero.avatar.ribbon"
    :title="t('swissGlass.hero.avatar.title')"
    title-key="swissGlass.hero.avatar.title"
    :line1="t('swissGlass.hero.avatar.line1')"
    line1-key="swissGlass.hero.avatar.line1"
    :icon="Smile"
    @close="closeModal"
  >
    <el-scrollbar
      ref="scrollbarRef"
      height="400px"
      class="flex-1"
      @scroll="handleScroll"
    >
      <div class="p-8">
        <div class="grid grid-cols-5 gap-4">
          <button
            v-for="emoji in displayedAvatars"
            :key="emoji"
            class="w-full aspect-square rounded-lg border-2 transition-all duration-200 flex items-center justify-center text-4xl hover:scale-105 mg-user-avatar-emoji"
            :class="
              selectedEmoji === emoji
                ? 'border-stone-900 bg-stone-50 ring-2 ring-stone-900 ring-offset-2'
                : 'border-stone-200 hover:border-stone-400 bg-white'
            "
            @click="selectAvatar(emoji)"
          >
            <span class="block mg-user-avatar-emoji">{{ emoji }}</span>
          </button>
        </div>

        <div
          v-if="isLoadingMore"
          class="flex justify-center items-center py-4"
        >
          <div class="text-sm text-stone-500">加载中...</div>
        </div>

        <div
          v-if="!hasMore && displayedAvatars.length > 0"
          class="flex justify-center items-center py-4"
        >
          <div class="text-xs text-stone-400">已显示全部 {{ allAvatars.length }} 个头像</div>
        </div>
      </div>
    </el-scrollbar>

    <template #footer>
      <div class="swiss-glass-footer avatar-select-footer">
        <button
          v-if="allowPhotoAvatar"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          :disabled="isSaving"
          @click="openCustomize"
        >
          <I18nText k="auth.avatarCustomize" />
        </button>
        <div class="avatar-select-footer__actions">
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
            @click="closeModal"
          >
            <I18nText k="common.cancel" />
          </button>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
            :disabled="isSaving"
            @click="saveAvatar"
          >
            <I18nText k="common.save" />
          </button>
        </div>
      </div>
    </template>
  </SwissGlassCard>

  <input
    ref="fileInputRef"
    type="file"
    class="avatar-file-input"
    accept="image/png,image/jpeg,image/webp,image/gif"
    @change="onCustomizeFile"
  />
  <AvatarCropModal
    v-if="cropSrc"
    v-model="cropOpen"
    :src="cropSrc"
    :saving="isSaving"
    @confirm="uploadCroppedAvatar"
    @invalid="onCropInvalid"
  />
</template>

<style scoped>
.avatar-select-footer {
  justify-content: space-between;
  width: 100%;
}

.avatar-select-footer__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.avatar-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

:deep(.el-scrollbar__bar) {
  right: 2px;
  bottom: 2px;
}

:deep(.el-scrollbar__thumb) {
  background-color: rgba(120, 113, 108, 0.3);
  border-radius: 4px;
}

:deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(120, 113, 108, 0.5);
}

:deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}
</style>
