<script setup lang="ts">
/**
 * ChatMessageToast — WeChat-style in-app message notification stack.
 *
 * Renders up to 5 toast cards in the bottom trailing corner (mirrors for RTL).
 * Each card shows sender avatar, name, context, and a message preview.
 * Cards slide in from the outer edge, auto-dismiss after 5 s, and stack vertically.
 * Clicking "View" navigates to the relevant conversation.
 *
 * Mounted globally in App.vue via <Teleport to="body">.
 */
import { useRouter } from 'vue-router'

import { X } from 'lucide-vue-next'

import {
  type ChatToastItem,
  dismissChatToast,
  useChatToastQueue,
} from '@/composables/core/chatToastQueue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const { t } = useLanguage()
const router = useRouter()
const store = useWorkshopChatStore()
const { toasts } = useChatToastQueue()

function navigate(toast: ChatToastItem): void {
  dismissChatToast(toast.id)
  const { partnerId, channelId, topicId } = toast.nav
  if (partnerId !== undefined) {
    store.selectDMPartner(partnerId)
    store.activeTab = 'dms'
  } else if (channelId !== undefined) {
    store.selectChannel(channelId)
    store.activeTab = 'channels'
    if (topicId !== undefined) {
      store.selectTopic(topicId)
    }
  }
  router.push('/workshop-chat')
}
</script>

<template>
  <Teleport to="body">
    <div
      aria-live="polite"
      class="fixed bottom-6 end-6 z-[9999] flex flex-col gap-2.5 items-end pointer-events-none"
    >
      <TransitionGroup name="chat-toast">
        <article
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto w-80 bg-white rounded-2xl shadow-2xl border border-stone-100 overflow-hidden"
          :class="
            toast.type === 'dm'
              ? 'border-s-[3px] border-s-blue-400'
              : 'border-s-[3px] border-s-amber-400'
          "
          role="alert"
        >
          <!-- Body -->
          <div class="flex items-start gap-3 px-4 pt-3.5 pb-2">
            <!-- Avatar -->
            <div
              class="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center text-lg shrink-0 select-none"
            >
              {{ toast.senderAvatar || '👤' }}
            </div>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="font-semibold text-stone-900 text-sm leading-tight truncate">
                    {{ toast.senderName }}
                  </p>
                  <p class="text-xs text-stone-400 mt-0.5 truncate">
                    {{ toast.context }}
                  </p>
                </div>
                <button
                  class="shrink-0 text-stone-300 hover:text-stone-500 transition-colors -mt-0.5"
                  :aria-label="t('workshop.dismiss')"
                  @click="dismissChatToast(toast.id)"
                >
                  <X :size="14" />
                </button>
              </div>

              <p class="mt-2 text-sm text-stone-600 leading-snug line-clamp-2 break-words">
                {{ toast.content }}
              </p>
            </div>
          </div>

          <!-- Footer: view button -->
          <div class="px-4 pb-3 flex justify-end">
            <button
              class="text-xs font-semibold tracking-wide transition-colors"
              :class="
                toast.type === 'dm'
                  ? 'text-blue-500 hover:text-blue-700'
                  : 'text-amber-500 hover:text-amber-700'
              "
              @click="navigate(toast)"
            >
              {{ t('workshop.view') }} →
            </button>
          </div>

          <!-- Auto-dismiss progress bar -->
          <div class="h-0.5 bg-stone-50">
            <div
              class="h-full toast-drain"
              :class="toast.type === 'dm' ? 'bg-blue-300' : 'bg-amber-300'"
            />
          </div>
        </article>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Slide-in / slide-out ─────────────────────────────────────── */
.chat-toast-enter-active {
  animation: toast-slide-in 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.chat-toast-leave-active {
  animation: toast-slide-out 0.2s ease-in forwards;
  /* keep the element in flow while it slides out so siblings don't jump */
  position: relative;
}

.chat-toast-move {
  transition: transform 0.25s ease;
}

@keyframes toast-slide-in {
  from {
    opacity: 0;
    transform: translateX(110%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-slide-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(110%);
  }
}

/* Mirror slide direction when document is RTL */
html[dir='rtl'] .chat-toast-enter-active {
  animation-name: toast-slide-in-rtl;
}

html[dir='rtl'] .chat-toast-leave-active {
  animation-name: toast-slide-out-rtl;
}

@keyframes toast-slide-in-rtl {
  from {
    opacity: 0;
    transform: translateX(-110%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-slide-out-rtl {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(-110%);
  }
}

/* ── Progress drain ───────────────────────────────────────────── */
.toast-drain {
  animation: toast-drain-progress 5s linear forwards;
}

@keyframes toast-drain-progress {
  from {
    width: 100%;
  }
  to {
    width: 0%;
  }
}
</style>
