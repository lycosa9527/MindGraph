<script setup lang="ts">
/**
 * ZhiHui prompt composer — size / smart-rewrite / reference attach + submit.
 */
import { computed, ref } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { ArrowUp, Check, ChevronDown, ImagePlus, Loader2, Maximize2, Paperclip, X } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'

import {
  ZHIHUI_IMAGE_SIZES,
  imageSizeById,
  type ZhihuiMode,
} from './zhihuiModes'
import {
  ZHIHUI_MAX_REFERENCE_BYTES,
  ZHIHUI_MAX_REFERENCE_IMAGES,
  isAllowedReferenceMime,
  readFileAsDataUrl,
  type ZhihuiReferenceImage,
} from './zhihuiReferences'

/** ElDropdown command cannot be empty string — map auto size. */
const SIZE_AUTO_COMMAND = '__auto__'

const props = defineProps<{
  mode: ZhihuiMode
  isGenerating: boolean
  modeAvailable: boolean
  showWelcome: boolean
}>()

const prompt = defineModel<string>('prompt', { default: '' })
const sizeId = defineModel<string>('sizeId', { default: '' })
const smartRewrite = defineModel<boolean>('smartRewrite', { default: true })
const references = defineModel<ZhihuiReferenceImage[]>('references', { default: () => [] })

const emit = defineEmits<{
  submit: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const fileInputRef = ref<HTMLInputElement | null>(null)

const maxChars = 1000
const charCount = computed(() => prompt.value.length)

const promptPlaceholder = computed(() => String(t(`zhihui.promptPlaceholder.${props.mode}`)))

const selectedSize = computed(() => imageSizeById(sizeId.value))

const sizeButtonLabel = computed(() => {
  const opt = selectedSize.value
  if (!opt.id) {
    return String(t('zhihui.sizeButton'))
  }
  return `${String(t(`zhihui.size.${opt.labelKey}`))} · ${opt.pixels}`
})

const canAttachMore = computed(
  () => props.mode === 'image' && references.value.length < ZHIHUI_MAX_REFERENCE_IMAGES
)

function selectSize(command: string | number): void {
  const value = String(command)
  sizeId.value = value === SIZE_AUTO_COMMAND ? '' : value
}

function sizeCommand(id: string): string {
  return id || SIZE_AUTO_COMMAND
}

function openFilePicker(): void {
  if (props.isGenerating || !canAttachMore.value) {
    if (!canAttachMore.value && props.mode === 'image') {
      notify.warning(String(t('zhihui.referenceLimit')))
    }
    return
  }
  fileInputRef.value?.click()
}

async function onFilesSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement | null
  const files = input?.files ? Array.from(input.files) : []
  if (input) {
    input.value = ''
  }
  if (files.length === 0) {
    return
  }

  const room = ZHIHUI_MAX_REFERENCE_IMAGES - references.value.length
  if (room <= 0) {
    notify.warning(String(t('zhihui.referenceLimit')))
    return
  }

  const next = [...references.value]
  for (const file of files.slice(0, room)) {
    if (!isAllowedReferenceMime(file.type)) {
      notify.warning(String(t('zhihui.referenceInvalid')))
      continue
    }
    if (file.size > ZHIHUI_MAX_REFERENCE_BYTES) {
      notify.warning(String(t('zhihui.referenceTooLarge')))
      continue
    }
    try {
      const dataUrl = await readFileAsDataUrl(file)
      next.push({
        id: `ref-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        mime: file.type,
        dataUrl,
      })
    } catch {
      notify.warning(String(t('zhihui.referenceInvalid')))
    }
  }
  references.value = next
}

function removeReference(id: string): void {
  references.value = references.value.filter((row) => row.id !== id)
}
</script>

<template>
  <div class="zhihui-composer">
    <div
      v-if="mode !== 'image'"
      class="rounded-t-2xl border-b border-stone-100 px-5 pt-3.5 pb-3"
    >
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="flex h-16 w-16 flex-col items-center justify-center rounded-xl border border-dashed border-stone-300 bg-stone-50 text-stone-400"
          disabled
          :title="String(t('zhihui.refUploadSoon'))"
        >
          <ImagePlus :size="20" />
          <span class="mt-1 text-[10px]">0/1</span>
        </button>
        <p class="text-xs text-stone-400">
          {{ t('zhihui.refUploadSoon') }}
        </p>
      </div>
    </div>

    <textarea
      v-model="prompt"
      class="zhihui-composer__textarea w-full resize-none border-0 bg-transparent px-5 py-4 text-[15px] leading-relaxed text-stone-800 outline-none placeholder:text-stone-400"
      :class="{
        'rounded-t-2xl': mode === 'image',
        'zhihui-composer__textarea--welcome': showWelcome,
        'zhihui-composer__textarea--session': !showWelcome,
      }"
      :placeholder="promptPlaceholder"
      :maxlength="maxChars"
      :disabled="isGenerating"
      :rows="showWelcome ? 4 : 2"
      @keydown.meta.enter.prevent="emit('submit')"
      @keydown.ctrl.enter.prevent="emit('submit')"
    />

    <div
      v-if="mode === 'image' && references.length > 0"
      class="zhihui-composer__refs"
    >
      <div
        v-for="refItem in references"
        :key="refItem.id"
        class="zhihui-composer__ref"
      >
        <img
          :src="refItem.dataUrl"
          :alt="refItem.name"
          class="zhihui-composer__ref-img"
        />
        <button
          type="button"
          class="zhihui-composer__ref-remove"
          :disabled="isGenerating"
          :aria-label="String(t('zhihui.removeReference'))"
          :title="String(t('zhihui.removeReference'))"
          @click="removeReference(refItem.id)"
        >
          <X :size="12" />
        </button>
      </div>
    </div>

    <input
      ref="fileInputRef"
      type="file"
      class="hidden"
      accept="image/png,image/jpeg,image/jpg,image/webp"
      multiple
      :disabled="isGenerating || mode !== 'image'"
      @change="onFilesSelected"
    />

    <div
      class="flex flex-wrap items-center gap-2 rounded-b-2xl border-t border-stone-100 bg-stone-50/70 px-3 py-2.5 sm:gap-3 sm:px-4"
    >
      <div
        v-if="mode === 'image'"
        class="zhihui-size-switcher-root"
      >
        <ElDropdown
          trigger="click"
          placement="top-start"
          popper-class="zhihui-size-switcher-popper"
          :disabled="isGenerating"
          @command="selectSize"
        >
          <ElButton
            size="small"
            class="zhihui-size-switcher"
            :title="String(t('zhihui.sizeButton'))"
            :aria-label="String(t('zhihui.sizeButton'))"
          >
            <Maximize2 class="zhihui-size-switcher__icon h-3.5 w-3.5 shrink-0" />
            <span class="zhihui-size-switcher__label">{{ sizeButtonLabel }}</span>
            <ChevronDown class="zhihui-size-switcher__chevron h-3.5 w-3.5 shrink-0" />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu class="zhihui-size-switcher__menu">
              <ElDropdownItem
                v-for="opt in ZHIHUI_IMAGE_SIZES"
                :key="opt.id || 'auto'"
                :command="sizeCommand(opt.id)"
              >
                <span class="zhihui-size-switcher__row">
                  <span class="zhihui-size-switcher__name">
                    {{ t(`zhihui.size.${opt.labelKey}`) }}
                  </span>
                  <span class="zhihui-size-switcher__pixels">
                    {{ opt.pixels || t('zhihui.size.autoHint') }}
                  </span>
                  <Check
                    v-if="opt.id === sizeId"
                    class="zhihui-size-switcher__check h-4 w-4 shrink-0 opacity-70"
                    aria-hidden="true"
                  />
                </span>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>

      <label
        v-if="mode === 'image'"
        class="zhihui-composer__footer-label inline-flex cursor-pointer items-center gap-1.5 select-none"
      >
        <input
          v-model="smartRewrite"
          type="checkbox"
          class="rounded border-stone-300 text-amber-800 focus:ring-amber-700/30"
          :disabled="isGenerating"
        />
        {{ t('zhihui.smartRewrite') }}
      </label>
      <span
        v-else
        class="rounded-full bg-stone-200/70 px-2.5 py-1 text-[11px] font-medium text-stone-600"
      >
        {{ t('zhihui.modeComingSoon') }}
      </span>

      <div class="ml-auto flex items-center gap-2 sm:gap-3">
        <span class="zhihui-composer__char-count">
          {{ charCount }}/{{ maxChars }}
        </span>
        <button
          v-if="mode === 'image'"
          type="button"
          class="zhihui-composer__attach"
          :class="{ 'zhihui-composer__attach--active': references.length > 0 }"
          :disabled="isGenerating"
          :aria-label="String(t('zhihui.attachReference'))"
          :title="String(t('zhihui.attachReferenceHint'))"
          @click="openFilePicker"
        >
          <Paperclip :size="18" />
        </button>
        <button
          type="button"
          class="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-stone-900 text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="isGenerating || !prompt.trim() || !modeAvailable"
          :aria-label="String(t('zhihui.generate'))"
          @click="emit('submit')"
        >
          <Loader2
            v-if="isGenerating"
            :size="18"
            class="animate-spin"
          />
          <ArrowUp
            v-else
            :size="18"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.zhihui-composer {
  width: 100%;
  border: 1px solid rgb(231 229 228 / 0.9);
  border-radius: 1rem;
  background: #fff;
  box-shadow: 0 12px 40px -24px rgb(28 25 23 / 0.35);
}

.zhihui-composer__textarea {
  field-sizing: content;
  font-family: inherit;
}

.zhihui-composer__textarea--welcome {
  min-height: 7.5rem;
}

.zhihui-composer__textarea--session {
  min-height: 3.5rem;
}

.zhihui-composer__textarea:focus,
.zhihui-composer__textarea:focus-visible {
  outline: none;
  box-shadow: none;
}

.zhihui-composer__footer-label,
.zhihui-composer__char-count {
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #57534e;
}

.zhihui-composer__char-count {
  color: #a8a29e;
  font-variant-numeric: tabular-nums;
}

.zhihui-composer__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0 1rem 0.75rem;
}

.zhihui-composer__ref {
  position: relative;
  width: 3.5rem;
  height: 3.5rem;
  overflow: hidden;
  border: 1px solid #e7e5e4;
  border-radius: 0.65rem;
  background: #f5f5f4;
}

.zhihui-composer__ref-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.zhihui-composer__ref-remove {
  position: absolute;
  top: 0.2rem;
  right: 0.2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1.15rem;
  padding: 0;
  border: 0;
  border-radius: 9999px;
  background: rgb(28 25 23 / 0.72);
  color: #fafaf9;
  cursor: pointer;
}

.zhihui-composer__ref-remove:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.zhihui-composer__attach {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  padding: 0;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #fff;
  color: #57534e;
  cursor: pointer;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    color 0.12s ease;
}

.zhihui-composer__attach:hover:not(:disabled),
.zhihui-composer__attach:focus-visible:not(:disabled) {
  border-color: #d6d3d1;
  background: #f5f5f4;
  color: #1c1917;
  outline: none;
}

.zhihui-composer__attach--active {
  border-color: #d6d3d1;
  background: #f5f5f4;
  color: #1c1917;
}

.zhihui-composer__attach:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.zhihui-size-switcher.zhihui-size-switcher {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-family: inherit;
  font-weight: 500;
  border-radius: 9999px;
}

.zhihui-size-switcher__icon,
.zhihui-size-switcher__chevron {
  color: #57534e;
}

.zhihui-size-switcher__label {
  margin-left: 4px;
  margin-right: 2px;
  max-width: 9.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #1c1917;
}

.zhihui-size-switcher__row {
  position: relative;
  display: flex;
  box-sizing: border-box;
  width: 100%;
  min-height: 1.35em;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 24px 7px 10px;
  font-family: inherit;
}

.zhihui-size-switcher__name {
  flex-shrink: 0;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #44403c;
  text-align: left;
}

.zhihui-size-switcher__pixels {
  min-width: 0;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #a8a29e;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.zhihui-size-switcher__check {
  position: absolute;
  top: 50%;
  right: 4px;
  width: 1rem;
  height: 1rem;
  color: #57534e;
  transform: translateY(-50%);
}
</style>

<style>
.zhihui-size-switcher-popper.el-popper {
  width: min(220px, calc(100vw - 24px)) !important;
  max-width: min(220px, calc(100vw - 24px)) !important;
  box-sizing: border-box !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
  font-family: inherit !important;
}

.zhihui-size-switcher-popper .el-dropdown-menu {
  width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  font-family: inherit !important;
}

.zhihui-size-switcher-popper .el-dropdown-menu__item {
  box-sizing: border-box;
  width: 100%;
  padding: 0 !important;
  border-radius: 6px;
  font-family: inherit !important;
  transition:
    background 0.12s,
    color 0.12s;
}

.zhihui-size-switcher-popper .el-dropdown-menu__item:hover,
.zhihui-size-switcher-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.zhihui-size-switcher-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.zhihui-size-switcher-popper .zhihui-size-switcher__name {
  color: #44403c;
}

.zhihui-size-switcher-popper .el-dropdown-menu__item:hover .zhihui-size-switcher__name,
.zhihui-size-switcher-popper .el-dropdown-menu__item:focus .zhihui-size-switcher__name {
  color: #1c1917;
}
</style>
