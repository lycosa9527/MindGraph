<script setup lang="ts">
/**
 * Kitty Agent — floating panel (mobile): transcript, mic, text, camera.
 */
import { Camera, Loader2, Mic, MicOff, SendHorizontal, WifiOff, X } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'

const props = withDefaults(
  defineProps<{
    open: boolean
    state: KittyAgentState
    lines: string[]
    micDenied?: boolean
    cameraDenied?: boolean
  }>(),
  {
    micDenied: false,
    cameraDenied: false,
  }
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  connect: []
  disconnect: []
  'toggle-mic': []
  'send-text': [text: string]
  'pick-image': [file: File]
  retry: []
}>()

const draft = ref('')

const busy = computed(
  () => props.state === 'connecting' || (props.open && props.state === 'idle' && !connectedLike.value)
)

const connectedLike = computed(() =>
  ['active', 'listening', 'speaking'].includes(props.state)
)

watch(
  () => props.open,
  (v) => {
    if (!v) draft.value = ''
  }
)

function close(): void {
  emit('update:open', false)
}

function onSubmitText(): void {
  const t = draft.value.trim()
  if (!t) return
  emit('send-text', t)
  draft.value = ''
}

function onFileChange(ev: Event): void {
  if (!connectedLike.value) return
  const input = ev.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) {
    emit('pick-image', f)
  }
  input.value = ''
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="kitty-panel-overlay fixed inset-0 z-[80] flex flex-col justify-end bg-black/25"
      @click.self="close"
    >
      <div
        class="kitty-panel bg-white rounded-t-2xl shadow-xl max-h-[70vh] flex flex-col border-t border-gray-200"
        role="dialog"
        aria-label="Kitty Agent"
        @click.stop
      >
        <div class="flex items-center justify-between px-3 py-2 border-b border-gray-100">
          <div class="font-semibold text-gray-900">Kitty 智能体</div>
          <button
            type="button"
            class="p-2 rounded-full hover:bg-gray-100 text-gray-600"
            aria-label="Close"
            @click="close"
          >
            <X :size="20" />
          </button>
        </div>
        <div class="px-3 py-2 text-xs text-gray-500 flex flex-wrap gap-2">
          <span v-if="micDenied">麦克风不可用</span>
          <span v-if="cameraDenied">相机不可用</span>
          <span v-if="state === 'error'">连接异常，可点击重试</span>
        </div>
        <div class="flex-1 min-h-[120px] max-h-[36vh] overflow-y-auto px-3 py-2 text-sm space-y-1 text-gray-800">
          <p
            v-if="!lines.length"
            class="text-gray-400"
          >
            连接后可语音或输入文字控制图示；也可拍摄纸张内容。
          </p>
          <p
            v-for="(line, i) in lines"
            v-else
            :key="i"
            class="whitespace-pre-wrap"
          >
            {{ line }}
          </p>
        </div>
        <div class="px-3 py-3 border-t border-gray-100 flex flex-col gap-2 safe-area-pb">
          <div
            v-if="!connectedLike"
            class="flex gap-2"
          >
            <button
              type="button"
              class="flex-1 py-2.5 rounded-xl bg-gray-900 text-white text-sm font-medium disabled:opacity-50"
              :disabled="busy"
              @click="emit('connect')"
            >
              <span v-if="state === 'connecting'">连接中…</span>
              <span v-else>连接 Kitty</span>
            </button>
            <button
              v-if="state === 'error'"
              type="button"
              class="px-3 py-2.5 rounded-xl border border-gray-300 text-sm"
              @click="emit('retry')"
            >
              重试
            </button>
          </div>
          <div class="flex items-center justify-center gap-3 flex-wrap">
            <button
              type="button"
              class="p-3 rounded-full bg-gray-100 text-gray-800 disabled:opacity-40 shrink-0"
              :disabled="!connectedLike || micDenied"
              :title="
                !connectedLike
                  ? '请先连接 Kitty'
                  : state === 'listening'
                    ? '停止麦克风'
                    : '开始麦克风'
              "
              @click="emit('toggle-mic')"
            >
              <MicOff
                v-if="state === 'listening'"
                :size="22"
              />
              <Mic
                v-else
                :size="22"
              />
            </button>
            <label
              class="p-3 rounded-full bg-gray-100 text-gray-800 shrink-0"
              :class="
                !connectedLike || cameraDenied
                  ? 'pointer-events-none opacity-40 cursor-default'
                  : 'cursor-pointer active:bg-gray-200'
              "
              :title="!connectedLike ? '请先连接 Kitty' : '拍照或相册'"
            >
              <Camera :size="22" />
              <input
                type="file"
                accept="image/*"
                capture="environment"
                class="hidden"
                :disabled="!connectedLike || cameraDenied"
                @change="onFileChange"
              >
            </label>
            <button
              v-if="connectedLike"
              type="button"
              class="p-3 rounded-full bg-gray-100 text-gray-800 shrink-0"
              title="断开"
              @click="emit('disconnect')"
            >
              <WifiOff :size="22" />
            </button>
            <div
              v-else
              class="w-[46px] h-[46px] shrink-0"
              aria-hidden="true"
            />
          </div>
          <div
            v-if="connectedLike"
            class="flex gap-2 items-center"
          >
            <input
              v-model="draft"
              type="text"
              class="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm"
              placeholder="输入指令…"
              @keydown.enter.prevent="onSubmitText"
            >
            <button
              type="button"
              class="p-3 rounded-xl bg-gray-900 text-white disabled:opacity-40 shrink-0"
              :disabled="!draft.trim()"
              @click="onSubmitText"
            >
              <SendHorizontal :size="20" />
            </button>
          </div>
          <div
            v-if="state === 'connecting'"
            class="flex items-center justify-center gap-2 text-gray-500 text-sm py-1"
          >
            <Loader2
              :size="18"
              class="animate-spin"
            />
            连接中…
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.safe-area-pb {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}
</style>
