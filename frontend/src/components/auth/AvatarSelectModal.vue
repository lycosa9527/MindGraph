<script setup lang="ts">
/**
 * AvatarSelectModal - Modal for selecting user avatar from emoji collection
 *
 * Design: Swiss Design (Modern Minimalism)
 * Uses Element Plus el-scrollbar for infinite scroll
 */
import { computed, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const notify = useNotifications()

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
  '🐈‍⬛',
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

const currentAvatar = computed(() => {
  const avatar = authStore.user?.avatar || '🐈‍⬛'
  // Handle legacy avatar_01 format
  if (avatar.startsWith('avatar_')) {
    return '🐈‍⬛'
  }
  return avatar
})

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
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeModal"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />

        <!-- Modal -->
        <div class="relative w-full max-w-md">
          <!-- Card -->
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
            <!-- Header -->
            <div
              class="px-8 pt-8 pb-4 text-center border-b border-stone-100 flex-shrink-0 relative"
            >
              <el-button
                :icon="Close"
                circle
                text
                class="close-btn"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">选择头像</h2>
            </div>

            <!-- Content with scrollbar -->
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
                    class="w-full aspect-square rounded-lg border-2 transition-all duration-200 flex items-center justify-center text-4xl hover:scale-105"
                    :class="
                      selectedEmoji === emoji
                        ? 'border-stone-900 bg-stone-50 ring-2 ring-stone-900 ring-offset-2'
                        : 'border-stone-200 hover:border-stone-400 bg-white'
                    "
                    @click="selectAvatar(emoji)"
                  >
                    <span class="block">{{ emoji }}</span>
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
                  <div class="text-xs text-stone-400">
                    已显示全部 {{ allAvatars.length }} 个头像
                  </div>
                </div>
              </div>
            </el-scrollbar>

            <!-- Footer -->
            <div
              class="px-8 pb-8 flex items-center justify-end gap-3 flex-shrink-0 border-t border-stone-100 pt-6"
            >
              <el-button @click="closeModal"> 取消 </el-button>
              <el-button
                type="primary"
                :loading="isSaving"
                class="save-btn"
                @click="saveAvatar"
              >
                保存
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95);
}

/* Close button positioning and styling */
.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}

/* Footer buttons - Swiss Design style */
:deep(.el-button) {
  font-weight: 500;
}

:deep(.el-button--default) {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
}

:deep(.el-button--primary) {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-active-bg-color: #0c0a09;
  --el-button-active-border-color: #0c0a09;
}

/* Save button - wider */
.save-btn {
  min-width: 100px;
}

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
