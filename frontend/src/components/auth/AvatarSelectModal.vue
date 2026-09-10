<script setup lang="ts">
/**
 * AvatarSelectModal - Modal for selecting user avatar from emoji collection
 *
 * Design: Swiss Design (Modern Minimalism)
 * Uses Element Plus el-scrollbar for infinite scroll
 */
import { computed, ref, watch } from 'vue'

import { Smile } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { DEFAULT_USER_AVATAR_EMOJI, resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

const notify = useNotifications()
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

// Curated emoji avatars collection (200+ interesting emojis - no signs/symbols)
const allAvatars = [
  // Smileys & Faces
  DEFAULT_USER_AVATAR_EMOJI,
  '😀',
  '😃',
  '😄',
  '😁',
  '😊',
  '😉',
  '😍',
  '🤩',
  '😎',
  '🤗',
  '🙂',
  '😇',
  '🤔',
  '😋',
  '😌',
  '😏',
  '😴',
  '🤤',
  '😪',
  '😵',
  '🤐',
  '🤨',
  '🧐',
  '🤓',
  '🥳',
  '😮',
  '😯',
  '😲',
  '😱',
  '😭',
  '😓',
  '😤',
  '😠',
  '😡',
  '🤬',
  '🤯',
  '😳',
  '🥺',
  '😞',
  '😟',
  '🙁',
  '☹️',
  '😣',
  '😖',
  '😫',
  '😩',
  '🥱',
  '😑',
  '😶',
  '😐',
  '🤢',
  '🤮',
  '🤧',
  '😷',
  '🤒',
  '🤕',
  '🤑',
  '🤠',
  '😈',
  '👿',
  '👹',
  '👺',
  '🤡',
  '💩',
  '👻',
  '💀',
  '☠️',
  '👽',
  '👾',
  '🤖',
  '🎃',
  '😺',
  '😸',
  '😹',
  '😻',
  '😼',
  '😽',
  '🙀',
  '😿',
  '😾',
  // People & Gestures
  '👋',
  '🤚',
  '🖐️',
  '✋',
  '🖖',
  '👌',
  '🤏',
  '✌️',
  '🤞',
  '🤟',
  '🤘',
  '🤙',
  '👈',
  '👉',
  '👆',
  '🖕',
  '👇',
  '☝️',
  '👍',
  '👎',
  '✊',
  '👊',
  '🤛',
  '🤜',
  '👏',
  '🙌',
  '👐',
  '🤲',
  '🤝',
  '🙏',
  '✍️',
  '💪',
  '🦾',
  '🦿',
  '🦵',
  '🦶',
  '👂',
  '🦻',
  '👃',
  '🧠',
  '🫀',
  '🫁',
  '🦷',
  '🦴',
  '👀',
  '👁️',
  '👅',
  '👄',
  '💋',
  '👶',
  '👧',
  '🧒',
  '👦',
  '👩',
  '🧑',
  '👨',
  '👩‍🦱',
  '👨‍🦱',
  '👩‍🦰',
  '👨‍🦰',
  '👱‍♀️',
  '👱',
  '👩‍🦳',
  '👨‍🦳',
  '👩‍🦲',
  '👨‍🦲',
  '🧔',
  '👵',
  '🧓',
  '👴',
  // Animals & Nature
  '🦁',
  '🐯',
  '🐅',
  '🐆',
  '🐴',
  '🦄',
  '🦓',
  '🦌',
  '🦬',
  '🐮',
  '🐂',
  '🐃',
  '🐄',
  '🐷',
  '🐖',
  '🐗',
  '🐽',
  '🐏',
  '🐑',
  '🐐',
  '🐪',
  '🐫',
  '🦙',
  '🦒',
  '🐘',
  '🦣',
  '🦏',
  '🦛',
  '🐭',
  '🐁',
  '🐀',
  '🐹',
  '🐰',
  '🐇',
  '🐿️',
  '🦫',
  '🦔',
  '🦇',
  '🐻',
  '🐻‍❄️',
  '🐨',
  '🐼',
  '🦥',
  '🦦',
  '🦨',
  '🦘',
  '🦡',
  '🐾',
  '🦃',
  '🐔',
  '🐓',
  '🐣',
  '🐤',
  '🐥',
  '🐦',
  '🐧',
  '🕊️',
  '🦅',
  '🦆',
  '🦢',
  '🦉',
  '🦤',
  '🪶',
  '🦩',
  '🦚',
  '🦜',
  '🐸',
  '🐊',
  '🐢',
  '🦎',
  '🐍',
  '🐲',
  '🐉',
  '🦕',
  '🦖',
  '🐳',
  '🐋',
  '🐬',
  '🦭',
  '🐟',
  '🐠',
  '🐡',
  '🦈',
  '🐙',
  '🐚',
  '🐌',
  '🦋',
  '🐛',
  '🐜',
  '🐝',
  '🪲',
  '🐞',
  '🦗',
  '🪳',
  '🕷️',
  '🕸️',
  '🦂',
  '🦟',
  '🪰',
  '🪱',
  '🦠',
  '💐',
  '🌸',
  '💮',
  '🪷',
  '🏵️',
  '🌹',
  '🥀',
  '🌺',
  '🌻',
  '🌼',
  '🌷',
  '🪻',
  '🌱',
  '🪴',
  '🌲',
  '🌳',
  '🌴',
  '🌵',
  '🌶️',
  '🫑',
  '🌾',
  '🌿',
  '☘️',
  '🍀',
  '🍁',
  '🍂',
  '🍃',
  '🪹',
  '🪺',
  // Food & Drink
  '🍇',
  '🍈',
  '🍉',
  '🍊',
  '🍋',
  '🍌',
  '🍍',
  '🥭',
  '🍎',
  '🍏',
  '🍐',
  '🍑',
  '🍒',
  '🍓',
  '🫐',
  '🥝',
  '🍅',
  '🫒',
  '🥥',
  '🥑',
  '🍆',
  '🥔',
  '🥕',
  '🌽',
  '🥒',
  '🥬',
  '🥦',
  '🧄',
  '🧅',
  '🍄',
  '🥜',
  '🫘',
  '🌰',
  '🍞',
  '🥐',
  '🥖',
  '🫓',
  '🥨',
  '🥯',
  '🥞',
  '🧇',
  '🧈',
  '🍳',
  '🥚',
  '🧀',
  '🥓',
  '🥩',
  '🍗',
  '🍖',
  '🦴',
  '🌭',
  '🍔',
  '🍟',
  '🍕',
  '🥪',
  '🥙',
  '🧆',
  '🌮',
  '🌯',
  '🫔',
  '🥗',
  '🥘',
  '🫕',
  '🥫',
  '🍝',
  '🍜',
  '🍲',
  '🍛',
  '🍣',
  '🍱',
  '🥟',
  '🦪',
  '🍤',
  '🍙',
  '🍚',
  '🍘',
  '🍥',
  '🥠',
  '🥡',
  '🍢',
  '🍡',
  '🍧',
  '🍨',
  '🍦',
  '🥧',
  '🧁',
  '🍰',
  '🎂',
  '🍮',
  '🍭',
  '🍬',
  '🍫',
  '🍿',
  '🍩',
  '🍪',
  '🍯',
  '🥛',
  '🍼',
  '🫖',
  '☕️',
  '🍵',
  '🧃',
  '🥤',
  '🧋',
  '🍶',
  '🍺',
  '🍻',
  '🥂',
  '🍷',
  '🥃',
  '🍸',
  '🍹',
  '🧉',
  '🍾',
  '🧊',
  // Travel & Places
  '🗺️',
  '🧭',
  '🏔️',
  '⛰️',
  '🌋',
  '🗻',
  '🏕️',
  '🏖️',
  '🏜️',
  '🏝️',
  '🏞️',
  '🏟️',
  '🏛️',
  '🏗️',
  '🧱',
  '🪨',
  '🪵',
  '🛖',
  '🏘️',
  '🏚️',
  '🏠',
  '🏡',
  '🏢',
  '🏣',
  '🏤',
  '🏥',
  '🏦',
  '🏨',
  '🏩',
  '🏪',
  '🏫',
  '🏬',
  '🏭',
  '🏯',
  '🏰',
  '💒',
  '🗼',
  '🗽',
  '⛪',
  '🕌',
  '🛕',
  '🕍',
  '⛩️',
  '🕋',
  '⛲',
  '⛺',
  '🌁',
  '🌃',
  '🏙️',
  '🌄',
  '🌅',
  '🌆',
  '🌇',
  '🌉',
  '♨️',
  '🎠',
  '🎡',
  '🎢',
  '💈',
  '🎪',
  '🚂',
  '🚃',
  '🚄',
  '🚅',
  '🚆',
  '🚇',
  '🚈',
  '🚉',
  '🚊',
  '🚝',
  '🚞',
  '🚋',
  '🚌',
  '🚍',
  '🚎',
  '🚐',
  '🚑',
  '🚒',
  '🚓',
  '🚔',
  '🚕',
  '🚖',
  '🚗',
  '🚘',
  '🚙',
  '🚚',
  '🚛',
  '🚜',
  '🏎️',
  '🏍️',
  '🛵',
  '🦽',
  '🦼',
  '🛴',
  '🚲',
  '🛺',
  '🛸',
  '🚁',
  '✈️',
  '🛩️',
  '🛫',
  '🛬',
  '🪂',
  '💺',
  '🚀',
  '🚠',
  '🚡',
  '🛰️',
  '🚢',
  '⛵',
  '🛶',
  '🛥️',
  '🛳️',
  '⛴️',
  '🚤',
  '🛟',
  // Activities & Objects
  '🎯',
  '🎮',
  '🎰',
  '🎲',
  '🃏',
  '🀄',
  '🎴',
  '🎭',
  '🖼️',
  '🎨',
  '🧩',
  '🏸',
  '🎬',
  '🎤',
  '🎧',
  '🎼',
  '🎹',
  '🥁',
  '🪘',
  '🎷',
  '🎺',
  '🪗',
  '🎸',
  '🪕',
  '🎻',
  '🎳',
  '🧸',
  '🪅',
  '🪩',
  '🪆',
  '🎁',
  '🎀',
  '🎊',
  '🎉',
  '🎈',
  '🎂',
  '🎃',
  '🎄',
  '🎆',
  '🎇',
  '🧨',
  '✨',
  '🎊',
  '🎉',
  '🎈',
]

const DISPLAY_COUNT = 50 // Number of avatars to show initially and load per scroll
const isLoadingMore = ref(false) // Loading state for scrolling
const isSaving = ref(false) // Loading state for saving avatar
const displayedCount = ref(DISPLAY_COUNT)
const selectedEmoji = ref<string>('')
const scrollbarRef = ref()

const displayedAvatars = computed(() => allAvatars.slice(0, displayedCount.value))

const currentAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

const hasMore = computed(() => displayedCount.value < allAvatars.length)

watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      selectedEmoji.value = currentAvatar.value
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

  // Load more when user scrolls to within 100px of the bottom
  const threshold = 100
  if (scrollTop + clientHeight >= scrollHeight - threshold) {
    loadMore()
  }
}

function loadMore() {
  if (isLoadingMore.value || !hasMore.value) return
  isLoadingMore.value = true

  // Simulate loading delay for smooth UX
  setTimeout(() => {
    displayedCount.value = Math.min(displayedCount.value + DISPLAY_COUNT, allAvatars.length)
    isLoadingMore.value = false
  }, 300)
}

async function saveAvatar() {
  if (!selectedEmoji.value) {
    notify.warning('请选择头像')
    return
  }

  isSaving.value = true

  try {
    // Use credentials (token in httpOnly cookie)
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
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.avatar.ribbon')"
    :title="t('swissGlass.hero.avatar.title')"
    :line1="t('swissGlass.hero.avatar.line1')"
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
        <!-- Avatar grid (5 columns) -->
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

        <!-- Loading indicator for scrolling -->
        <div
          v-if="isLoadingMore"
          class="flex justify-center items-center py-4"
        >
          <div class="text-sm text-stone-500">加载中...</div>
        </div>

        <!-- No more indicator -->
        <div
          v-if="!hasMore && displayedAvatars.length > 0"
          class="flex justify-center items-center py-4"
        >
          <div class="text-xs text-stone-400">已显示全部 {{ allAvatars.length }} 个头像</div>
        </div>
      </div>
    </el-scrollbar>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="closeModal"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="isSaving"
          @click="saveAvatar"
        >
          {{ t('common.save') }}
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>

<style scoped>
/* Scrollbar - Element Plus style with Swiss Design */
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
