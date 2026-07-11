<script setup lang="ts">
/**
 * Share invitation message dialog — Swiss minimal.
 */
import { computed } from 'vue'

import { Close } from '@element-plus/icons-vue'

import { Copy } from '@lucide/vue'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'

const props = defineProps<{
  modelValue: boolean
  invitationCode: string
  organizationName?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const isVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const resolvedOrgName = computed(
  () => props.organizationName?.trim() || (t('admin.organizationName') as string)
)

const shareMessageText = computed(() =>
  t('admin.shareInviteMessage', {
    orgName: resolvedOrgName.value,
    code: props.invitationCode,
    siteUrl: publicSiteUrl.value,
  })
)

const shortInviteText = computed(() =>
  t('admin.schoolInviteCopyPayload', {
    orgName: resolvedOrgName.value,
    code: props.invitationCode,
    siteUrl: publicSiteUrl.value,
  })
)

function closeModal() {
  isVisible.value = false
}

async function copyShareMessage() {
  try {
    await navigator.clipboard.writeText(shareMessageText.value)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function copyShortInvite() {
  try {
    await navigator.clipboard.writeText(shortInviteText.value)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="admin-school-modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div
          class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]"
          aria-hidden="true"
          @click="closeModal"
        />

        <div
          class="relative w-full max-w-lg"
          @click.stop
        >
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden">
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative">
              <el-button
                :icon="Close"
                circle
                text
                class="admin-school-modal__close"
                :aria-label="t('common.close')"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">
                {{ t('admin.shareInviteTitle') }}
              </h2>
            </div>

            <div class="p-8 space-y-5">
              <p
                class="whitespace-pre-wrap rounded-lg bg-stone-50 p-4 text-sm text-stone-700 leading-relaxed max-h-[min(50vh,320px)] overflow-y-auto"
              >
                {{ shareMessageText }}
              </p>

              <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-stone-600 bg-stone-100 hover:bg-stone-200 transition-colors"
                  @click="closeModal"
                >
                  {{ t('common.close') }}
                </button>
                <button
                  type="button"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 flex items-center justify-center gap-2 transition-colors"
                  @click="copyShortInvite"
                >
                  <Copy class="w-4 h-4" />
                  {{ t('admin.copyShortInvite') }}
                </button>
                <button
                  type="button"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-stone-900 hover:bg-stone-800 flex items-center justify-center gap-2 transition-colors"
                  @click="copyShareMessage"
                >
                  <Copy class="w-4 h-4" />
                  {{ t('admin.copyShareMessage') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.admin-school-modal-enter-active,
.admin-school-modal-leave-active {
  transition: opacity 0.2s ease;
}

.admin-school-modal-enter-active .relative,
.admin-school-modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.admin-school-modal-enter-from,
.admin-school-modal-leave-to {
  opacity: 0;
}

.admin-school-modal-enter-from .relative,
.admin-school-modal-leave-to .relative {
  transform: scale(0.97);
}

.admin-school-modal__close {
  position: absolute;
  top: 16px;
  inset-inline-end: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
