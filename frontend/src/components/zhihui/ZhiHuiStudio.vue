<script setup lang="ts">
/**
 * ZhiHui studio body — welcome landing or MindMate-style conversation + composer.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Check, ChevronDown } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  type ZhihuiConversationItem,
  useZhihuiHistoryStore,
} from '@/stores/zhihuiHistory'
import { apiPost } from '@/utils/apiClient'

import ZhiHuiComposer from './ZhiHuiComposer.vue'
import ZhiHuiLandingGallery from './ZhiHuiLandingGallery.vue'
import ZhiHuiMessages, { type ZhihuiSessionTurn } from './ZhiHuiMessages.vue'
import {
  DEFAULT_IMAGE_SIZE_ID,
  ZHIHUI_MODELS,
  defaultModelId,
  type ZhihuiMode,
} from './zhihuiModes'
import type { ZhihuiReferenceImage } from './zhihuiReferences'

const emit = defineEmits<{
  generated: []
}>()

const mode = defineModel<ZhihuiMode>('mode', { default: 'image' })

const { t, currentLanguage } = useLanguage()
const notify = useNotifications()
const historyStore = useZhihuiHistoryStore()

const modelId = ref(defaultModelId(mode.value))
const sizeId = ref(DEFAULT_IMAGE_SIZE_ID)
const prompt = ref('')
const smartRewrite = ref(true)
const references = ref<ZhihuiReferenceImage[]>([])
const isGenerating = ref(false)
/** Bumped on unmount / new submit so late responses cannot selectItem after leave. */
const generateEpoch = ref(0)
const modelMenuOpen = ref(false)
const modelMenuRef = ref<HTMLElement | null>(null)
const turns = ref<ZhihuiSessionTurn[]>([])

const showWelcome = computed(() => turns.value.length === 0)

const modelsForMode = computed(() => ZHIHUI_MODELS[mode.value])

const selectedModel = computed(
  () => modelsForMode.value.find((m) => m.id === modelId.value) ?? modelsForMode.value[0]
)

const modeAvailable = computed(() => Boolean(selectedModel.value?.available))

const welcomePrefix = computed(() => String(t(`zhihui.welcome.${mode.value}`)))

const composerHint = computed(() => String(t(`zhihui.composerHint.${mode.value}`)))

watch(mode, (next) => {
  modelId.value = defaultModelId(next)
  modelMenuOpen.value = false
})

function turnFromConversation(item: ZhihuiConversationItem): ZhihuiSessionTurn[] {
  const gens = item.generations ?? []
  if (gens.length === 0) {
    const cover = item.cover_image_url
    if (!cover) return []
    return [
      {
        localId: item.id,
        prompt: item.title || '',
        status: 'done',
        imageUrl: cover,
        error: null,
        historyId: item.id,
        referencePreviews: [],
      },
    ]
  }
  return gens.map((gen) => ({
    localId: gen.id,
    prompt: gen.slide_title || gen.prompt || item.title || '',
    status: 'done' as const,
    imageUrl: gen.image_url,
    error: null,
    historyId: item.id,
    referencePreviews: [],
  }))
}

watch(
  () => historyStore.currentId,
  async (id) => {
    // Landing / history select always wins over an in-flight generate UI.
    if (!id) {
      isGenerating.value = false
      turns.value = []
      return
    }
    if (isGenerating.value) {
      // Keep doodle wait only while the new selection is still this in-flight turn.
      const active = turns.value.find((turn) => turn.status === 'waiting')
      if (active?.historyId && active.historyId !== id) {
        isGenerating.value = false
      } else if (!active?.historyId) {
        // Local generate not yet bound to a conversation id — allow switch away.
        isGenerating.value = false
      } else {
        return
      }
    }
    const detail = await historyStore.loadConversation(id).catch(() => null)
    if (historyStore.currentId !== id) return
    const item = detail ?? historyStore.currentItem
    if (!item) {
      return
    }
    // Page owns studio mode; image studio only hydrates image conversations.
    if (item.mode !== 'image') {
      turns.value = []
      return
    }
    turns.value = turnFromConversation(item)
  },
  { immediate: true }
)

function toggleModelMenu(): void {
  modelMenuOpen.value = !modelMenuOpen.value
}

function selectModel(id: string): void {
  if (!modelsForMode.value.some((m) => m.id === id && m.available)) {
    return
  }
  modelId.value = id
  modelMenuOpen.value = false
}

function onDocumentPointerDown(event: MouseEvent): void {
  const target = event.target
  if (!(target instanceof Node)) {
    return
  }
  if (modelMenuRef.value && !modelMenuRef.value.contains(target)) {
    modelMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  generateEpoch.value += 1
  document.removeEventListener('mousedown', onDocumentPointerDown)
})

function parseMarkdownImageUrl(text: string): string | null {
  const match = text.match(/!\[[^\]]*]\((https?:\/\/[^)\s]+)\)/)
  return match?.[1] ?? null
}

function parseGenerateErrorBody(body: string, status: number): string {
  const trimmed = body.trim()
  if (!trimmed) {
    return `HTTP ${status}`
  }
  const plain = trimmed.replace(/^Error:\s*/i, '').trim()
  if (plain && !plain.startsWith('{') && !plain.startsWith('[')) {
    return plain
  }
  try {
    const json = JSON.parse(trimmed) as {
      detail?: string | Array<{ msg?: string }>
      message?: string
    }
    if (typeof json.detail === 'string' && json.detail.trim()) {
      return json.detail.trim()
    }
    if (Array.isArray(json.detail) && json.detail.length > 0) {
      const first = json.detail[0]
      if (typeof first?.msg === 'string' && first.msg.trim()) {
        return first.msg.trim()
      }
    }
    if (typeof json.message === 'string' && json.message.trim()) {
      return json.message.trim()
    }
  } catch {
    // keep plain text fallback
  }
  return plain || `HTTP ${status}`
}

function patchTurn(localId: string, patch: Partial<ZhihuiSessionTurn>): void {
  const idx = turns.value.findIndex((row) => row.localId === localId)
  if (idx < 0) {
    return
  }
  turns.value[idx] = { ...turns.value[idx], ...patch }
}

async function submitGenerate(): Promise<void> {
  const trimmed = prompt.value.trim()
  if (!trimmed) {
    notify.warning(String(t('zhihui.promptRequired')))
    return
  }
  if (!modeAvailable.value) {
    notify.info(String(t('zhihui.modeComingSoon')))
    return
  }
  if (mode.value !== 'image') {
    notify.info(String(t('zhihui.modeComingSoon')))
    return
  }
  if (isGenerating.value) {
    return
  }

  const localId = `local-${Date.now()}`
  const attachedRefs = [...references.value]
  const referencePreviews = attachedRefs.map((row) => row.dataUrl)
  turns.value = [
    ...turns.value,
    {
      localId,
      prompt: trimmed,
      status: 'waiting',
      imageUrl: null,
      error: null,
      historyId: null,
      referencePreviews,
    },
  ]
  // Clear composer while waiting; restore on failure so the user can retry.
  prompt.value = ''
  references.value = []
  isGenerating.value = true
  const epoch = generateEpoch.value + 1
  generateEpoch.value = epoch

  try {
    const lang = currentLanguage.value === 'zh' || currentLanguage.value.startsWith('zh') ? 'zh' : 'en'
    const payload: Record<string, string | boolean | string[]> = {
      prompt: trimmed,
      language: lang,
      model: modelId.value,
      prompt_extend: smartRewrite.value,
    }
    if (sizeId.value) {
      payload.size = sizeId.value
    }
    if (attachedRefs.length > 0) {
      payload.reference_images = attachedRefs.map((row) => row.dataUrl)
    }
    const res = await apiPost('/api/generate-text-to-image', payload)
    const body = await res.text()
    if (!res.ok) {
      throw new Error(parseGenerateErrorBody(body, res.status))
    }
    const url = parseMarkdownImageUrl(body)
    if (!url) {
      throw new Error(String(t('zhihui.generateFailed')))
    }
    // Still refresh history if the user left mid-request; do not yank mode/selection.
    await historyStore.fetchHistory()
    if (epoch !== generateEpoch.value) {
      return
    }
    notify.success(String(t('zhihui.generateSuccess')))
    const newest = historyStore.sortedItems[0]
    patchTurn(localId, {
      status: 'done',
      imageUrl: url,
      historyId: newest?.id ?? null,
    })
    if (newest) {
      historyStore.selectItem(newest.id)
    }
    emit('generated')
  } catch (err) {
    if (epoch !== generateEpoch.value) {
      return
    }
    const message = err instanceof Error ? err.message : String(t('zhihui.generateFailed'))
    patchTurn(localId, {
      status: 'error',
      error: message,
    })
    prompt.value = trimmed
    references.value = attachedRefs
    notify.error(message)
  } finally {
    if (epoch === generateEpoch.value) {
      isGenerating.value = false
    }
  }
}
</script>

<template>
  <div
    class="zhihui-studio"
    :class="{ 'zhihui-studio--welcome': showWelcome }"
  >
    <ZhiHuiMessages
      v-if="!showWelcome"
      :turns="turns"
    />

    <div
      v-else
      class="zhihui-studio__welcome"
    >
      <h2 class="zhihui-studio__welcome-title">
        <span>{{ welcomePrefix }}</span>
        <span
          ref="modelMenuRef"
          class="zhihui-model-switcher relative inline-flex"
        >
          <button
            type="button"
            class="zhihui-model-switcher__trigger"
            :aria-expanded="modelMenuOpen"
            :aria-haspopup="true"
            :title="selectedModel?.label"
            @click="toggleModelMenu"
          >
            <span class="zhihui-model-switcher__trigger-label">{{ selectedModel?.label }}</span>
            <ChevronDown class="zhihui-model-switcher__trigger-chevron" />
          </button>
          <div
            v-if="modelMenuOpen"
            class="zhihui-model-switcher__menu"
            role="menu"
          >
            <button
              v-for="opt in modelsForMode"
              :key="opt.id"
              type="button"
              role="menuitem"
              class="zhihui-model-switcher__item"
              :class="{
                'zhihui-model-switcher__item--active': opt.id === modelId,
                'zhihui-model-switcher__item--disabled': !opt.available,
              }"
              :disabled="!opt.available"
              @click="selectModel(opt.id)"
            >
              <span class="zhihui-model-switcher__row">
                <span class="zhihui-model-switcher__name">{{ opt.label }}</span>
                <span
                  v-if="!opt.available"
                  class="zhihui-model-switcher__soon"
                >
                  {{ t('zhihui.soon') }}
                </span>
                <Check
                  v-else-if="opt.id === modelId"
                  class="zhihui-model-switcher__check"
                  aria-hidden="true"
                />
              </span>
            </button>
          </div>
        </span>
        <span>{{ t('zhihui.welcomeSuffix') }}</span>
      </h2>
      <p class="zhihui-studio__welcome-hint">
        {{ composerHint }}
      </p>
    </div>

    <div class="zhihui-studio__composer-wrap">
      <ZhiHuiComposer
        v-model:prompt="prompt"
        v-model:size-id="sizeId"
        v-model:smart-rewrite="smartRewrite"
        v-model:references="references"
        :mode="mode"
        :is-generating="isGenerating"
        :mode-available="modeAvailable"
        :show-welcome="showWelcome"
        @submit="submitGenerate"
      />
    </div>

    <div
      v-if="showWelcome"
      class="zhihui-studio__gallery-wrap"
    >
      <ZhiHuiLandingGallery />
    </div>
  </div>
</template>

<style scoped>
.zhihui-studio {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.zhihui-studio--welcome {
  justify-content: flex-start;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 1.75rem 1rem 1.25rem;
}

@media (min-width: 640px) {
  .zhihui-studio--welcome {
    padding-top: 2.25rem;
  }
}

.zhihui-studio__welcome {
  width: 100%;
  max-width: 48rem;
  margin: 0 auto;
  text-align: center;
}

.zhihui-studio__welcome-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  column-gap: 0.25rem;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: #1c1917;
  line-height: 1.25;
}

@media (min-width: 640px) {
  .zhihui-studio__welcome-title {
    font-size: 1.875rem;
  }
}

.zhihui-studio__welcome-hint {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #78716c;
}

.zhihui-studio__composer-wrap {
  flex-shrink: 0;
  width: 100%;
  max-width: 48rem;
  margin: 0 auto;
  padding: 0.75rem 1rem 1.25rem;
}

.zhihui-studio--welcome .zhihui-studio__composer-wrap {
  margin-top: 1.25rem;
  padding-bottom: 0;
}

.zhihui-studio__gallery-wrap {
  flex: 0 0 auto;
  width: 100%;
  max-width: 64rem;
  margin: 0 auto;
  padding: 1.75rem 1rem 1.25rem;
}

.zhihui-model-switcher__trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  padding: 0.15rem 0.4rem;
  border: 0;
  border-radius: 0.35rem;
  background: transparent;
  color: #1c1917;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: background 0.12s ease;
}

@media (min-width: 640px) {
  .zhihui-model-switcher__trigger {
    font-size: 1.125rem;
  }
}

.zhihui-model-switcher__trigger:hover {
  background: #f5f5f4;
}

.zhihui-model-switcher__trigger-label {
  white-space: nowrap;
  line-height: 1;
}

.zhihui-model-switcher__trigger-chevron {
  width: 0.95rem;
  height: 0.95rem;
  flex-shrink: 0;
  color: #78716c;
  opacity: 0.85;
}

.zhihui-model-switcher__menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  z-index: 30;
  box-sizing: border-box;
  width: min(220px, calc(100vw - 24px));
  padding: 4px;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #ffffff;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05);
  transform: translateX(-50%);
}

.zhihui-model-switcher__item {
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}

.zhihui-model-switcher__item:hover:not(:disabled),
.zhihui-model-switcher__item:focus-visible:not(:disabled) {
  background: #f5f5f4;
}

.zhihui-model-switcher__item:active:not(:disabled) {
  background: #e7e5e4;
}

.zhihui-model-switcher__item--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.zhihui-model-switcher__row {
  position: relative;
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-height: 1.35em;
  padding: 7px 24px 7px 10px;
}

.zhihui-model-switcher__name {
  display: block;
  width: 100%;
  text-align: center;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #44403c;
}

.zhihui-model-switcher__item:hover:not(:disabled) .zhihui-model-switcher__name,
.zhihui-model-switcher__item--active .zhihui-model-switcher__name {
  color: #1c1917;
}

.zhihui-model-switcher__check,
.zhihui-model-switcher__soon {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
}

.zhihui-model-switcher__check {
  width: 1rem;
  height: 1rem;
  color: #57534e;
  opacity: 0.7;
}

.zhihui-model-switcher__soon {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #a8a29e;
  text-transform: uppercase;
}
</style>
