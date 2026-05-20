<script setup lang="ts">
/**
 * Create school dialog — Swiss minimal (stone palette, borderless inputs).
 */
import { computed, ref, watch } from 'vue'

import { Close } from '@element-plus/icons-vue'
import { Copy, Loader2, RefreshCw } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import {
  generateInvitationCode,
  isValidInvitationCode,
  normalizeInvitationCodeInput,
  resolveSchoolCodeFromName,
} from '@/utils/invitationCode'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'created', payload: { invitation_code?: string }): void
}>()

const { t } = useLanguage()
const notify = useNotifications()

const isVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isSubmitting = ref(false)
const form = ref({
  name: '',
  invitation_code: '',
})

function resetForm() {
  form.value = {
    name: '',
    invitation_code: generateInvitationCode(),
  }
}

function closeModal() {
  isVisible.value = false
}

function regenerateInvitationCode() {
  form.value.invitation_code = generateInvitationCode()
}

function normalizeInvitationField() {
  form.value.invitation_code = normalizeInvitationCodeInput(form.value.invitation_code)
}

async function copyInvitationCode() {
  const code = normalizeInvitationCodeInput(form.value.invitation_code)
  if (!code) {
    return
  }
  try {
    await navigator.clipboard.writeText(code)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function submitCreate() {
  const name = form.value.name.trim()
  if (!name) {
    notify.error(t('admin.schoolNameRequired'))
    return
  }

  const code = resolveSchoolCodeFromName(name)
  const inviteRaw = normalizeInvitationCodeInput(form.value.invitation_code)
  if (inviteRaw && !isValidInvitationCode(inviteRaw)) {
    notify.error(t('admin.invitationCodeFormatHint'))
    return
  }

  isSubmitting.value = true
  try {
    const payload: Record<string, string> = { name, code }
    if (inviteRaw) {
      payload.invitation_code = inviteRaw.toUpperCase()
    }
    const res = await apiRequest('/api/auth/admin/organizations', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.schoolCreateFailed'))
      return
    }
    const data = (await res.json()) as { invitation_code?: string }
    notify.success(t('notification.saved'))
    isVisible.value = false
    emit('created', { invitation_code: data.invitation_code })
  } catch {
    notify.error(t('admin.schoolCreateFailed'))
  } finally {
    isSubmitting.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      resetForm()
    }
  }
)
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
          class="relative w-full max-w-md"
          @click.stop
        >
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden">
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative">
              <el-button
                :icon="Close"
                circle
                text
                class="admin-school-modal__close"
                :aria-label="t('common.cancel')"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">
                {{ t('admin.createSchool') }}
              </h2>
            </div>

            <form
              class="p-8 space-y-5"
              @submit.prevent="submitCreate"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="create-school-name"
                >
                  {{ t('admin.schoolName') }}
                  <span class="text-stone-400">*</span>
                </label>
                <input
                  id="create-school-name"
                  v-model="form.name"
                  type="text"
                  name="create-school-name"
                  :placeholder="t('admin.schoolNamePlaceholder')"
                  autocomplete="organization"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="create-school-invitation"
                >
                  {{ t('admin.invitationCode') }}
                </label>
                <div class="flex gap-2">
                  <input
                    id="create-school-invitation"
                    v-model="form.invitation_code"
                    type="text"
                    name="create-school-invitation"
                    autocomplete="off"
                    spellcheck="false"
                    class="min-w-0 flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all uppercase tracking-wider"
                    @blur="normalizeInvitationField"
                  />
                  <button
                    type="button"
                    class="shrink-0 px-3 py-3 rounded-lg bg-stone-100 text-stone-600 hover:bg-stone-200 hover:text-stone-800 transition-colors"
                    :title="t('admin.regenerateInvitationCode')"
                    :aria-label="t('admin.regenerateInvitationCode')"
                    @click="regenerateInvitationCode"
                  >
                    <RefreshCw class="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end pt-1">
                <button
                  type="button"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-stone-600 bg-stone-100 hover:bg-stone-200 transition-colors"
                  @click="closeModal"
                >
                  {{ t('common.cancel') }}
                </button>
                <button
                  type="button"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="!form.invitation_code.trim()"
                  @click="copyInvitationCode"
                >
                  <Copy class="w-4 h-4" />
                  {{ t('admin.copyInvitationCode') }}
                </button>
                <button
                  type="submit"
                  :disabled="isSubmitting"
                  class="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-stone-900 hover:bg-stone-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
                >
                  <Loader2
                    v-if="isSubmitting"
                    class="w-4 h-4 animate-spin"
                  />
                  {{ t('admin.createSchool') }}
                </button>
              </div>
            </form>
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
