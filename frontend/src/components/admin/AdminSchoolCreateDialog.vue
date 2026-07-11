<script setup lang="ts">
/**
 * Create organization dialog — Swiss minimal (stone palette, borderless inputs).
 */
import { computed, ref, watch } from 'vue'

import { Close } from '@element-plus/icons-vue'

import { Copy, Loader2, RefreshCw } from '@lucide/vue'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useCreateAdminOrganization } from '@/composables/queries'
import {
  generateInvitationCode,
  isValidInvitationCode,
  normalizeInvitationCodeInput,
  resolveSchoolCodeFromName,
} from '@/utils/invitationCode'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'created', payload: { invitation_code?: string; name?: string }): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()
const createOrganization = useCreateAdminOrganization()

const isVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isSubmitting = ref(false)
const form = ref({
  name: '',
  invitation_code: '',
  expires_at: '',
})

function defaultExpiresAtDate(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() + 1)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function resetForm() {
  form.value = {
    name: '',
    invitation_code: generateInvitationCode(),
    expires_at: defaultExpiresAtDate(),
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
  const orgName = form.value.name.trim() || t('admin.organizationName')
  const text = t('admin.schoolInviteCopyPayload', {
    orgName,
    siteUrl: publicSiteUrl.value,
    code,
  })
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function submitCreate() {
  const name = form.value.name.trim()
  if (!name) {
    notify.error(t('admin.organizationNameRequired'))
    return
  }

  const code = resolveSchoolCodeFromName(name)
  const inviteRaw = normalizeInvitationCodeInput(form.value.invitation_code)
  if (inviteRaw && !isValidInvitationCode(inviteRaw)) {
    notify.error(t('admin.invitationCodeFormatHint'))
    return
  }

  const expiresDate = form.value.expires_at.trim()
  if (!expiresDate) {
    notify.error(t('admin.validityPeriodRequired'))
    return
  }

  isSubmitting.value = true
  try {
    const payload: Record<string, string> = {
      name,
      code,
      expires_at: `${expiresDate}T23:59:59+08:00`,
    }
    if (inviteRaw) {
      payload.invitation_code = inviteRaw.toUpperCase()
    }
    const data = (await createOrganization.mutateAsync(payload)) as { invitation_code?: string }
    notify.success(t('notification.saved'))
    isVisible.value = false
    emit('created', { invitation_code: data.invitation_code, name })
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.organizationCreateFailed')
    notify.error(message)
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
                {{ t('admin.createOrganization') }}
              </h2>
            </div>

            <form
              class="p-8 space-y-5"
              @submit.prevent="submitCreate"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="create-org-name"
                >
                  {{ t('admin.organizationName') }}
                  <span class="text-stone-400">*</span>
                </label>
                <input
                  id="create-org-name"
                  v-model="form.name"
                  type="text"
                  name="create-org-name"
                  :placeholder="t('admin.organizationNamePlaceholder')"
                  autocomplete="organization"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="create-org-invitation"
                >
                  {{ t('admin.invitationCode') }}
                </label>
                <div class="flex gap-2">
                  <input
                    id="create-org-invitation"
                    v-model="form.invitation_code"
                    type="text"
                    name="create-org-invitation"
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

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="create-org-expires"
                >
                  {{ t('admin.validityPeriod') }}
                  <span class="text-stone-400">*</span>
                </label>
                <input
                  id="create-org-expires"
                  v-model="form.expires_at"
                  type="date"
                  name="create-org-expires"
                  class="admin-school-create-date w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-sm text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
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
                  {{ t('admin.createOrganization') }}
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

/*
 * Native date controls often paint larger than text inputs at the same CSS size.
 * Lock to text-sm (0.875rem) so visual weight matches the name / invite fields.
 */
.admin-school-create-date {
  -webkit-appearance: none;
  appearance: none;
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: normal;
  color: #1c1917;
}

.admin-school-create-date::-webkit-datetime-edit,
.admin-school-create-date::-webkit-datetime-edit-fields-wrapper,
.admin-school-create-date::-webkit-datetime-edit-text,
.admin-school-create-date::-webkit-datetime-edit-month-field,
.admin-school-create-date::-webkit-datetime-edit-day-field,
.admin-school-create-date::-webkit-datetime-edit-year-field {
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: normal;
  color: inherit;
}

.admin-school-create-date::-webkit-calendar-picker-indicator {
  opacity: 0.55;
  cursor: pointer;
}
</style>
