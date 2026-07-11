<script setup lang="ts">
/**
 * School-tier subscription pitch and consultation form.
 */
import { onMounted, reactive, ref, watch } from 'vue'

import { Building2, Headphones, Server, Settings, UserRound } from '@lucide/vue'

import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import {
  SCHOOL_CONSULT_LIMITS,
  schoolConsultValidationMessageKey,
  validateSchoolConsultForm,
} from '@/utils/schoolConsultValidation'

const { t } = useLanguage()
const authStore = useAuthStore()

const submitting = ref(false)

const form = reactive({
  name: '',
  phone: '',
  organization: '',
  note: '',
})

const SCHOOL_FEATURES = [
  {
    icon: UserRound,
    titleKey: 'thinkingCoins.school.feature.accountManager',
    descKey: 'thinkingCoins.school.feature.accountManagerDesc',
  },
  {
    icon: Server,
    titleKey: 'thinkingCoins.school.feature.privateDeploy',
    descKey: 'thinkingCoins.school.feature.privateDeployDesc',
  },
  {
    icon: Settings,
    titleKey: 'thinkingCoins.school.feature.customization',
    descKey: 'thinkingCoins.school.feature.customizationDesc',
  },
  {
    icon: Headphones,
    titleKey: 'thinkingCoins.school.feature.opsSupport',
    descKey: 'thinkingCoins.school.feature.opsSupportDesc',
  },
] as const

function profilePrefill(): { name: string; phone: string; organization: string } {
  const user = authStore.user
  const username = (user?.username || '').trim()
  const phone = (user?.phone || '').trim()
  const organization = (user?.schoolName || '').trim()
  // Skip name when username is just a phone (common for SMS-only accounts).
  const looksLikePhone =
    /^\d{7,15}$/.test(username) || (phone !== '' && username === phone)
  const name = looksLikePhone ? '' : username
  return {
    name: name.slice(0, SCHOOL_CONSULT_LIMITS.name),
    phone: phone.slice(0, SCHOOL_CONSULT_LIMITS.phone),
    organization: organization.slice(0, SCHOOL_CONSULT_LIMITS.organization),
  }
}

function applyProfilePrefill(options?: { onlyEmpty?: boolean }): void {
  const onlyEmpty = options?.onlyEmpty === true
  const prefill = profilePrefill()
  if (!onlyEmpty || !form.name.trim()) {
    form.name = prefill.name
  }
  if (!onlyEmpty || !form.phone.trim()) {
    form.phone = prefill.phone
  }
  if (!onlyEmpty || !form.organization.trim()) {
    form.organization = prefill.organization
  }
}

function resetForm(): void {
  applyProfilePrefill()
  form.note = ''
}

onMounted(() => {
  applyProfilePrefill()
})

// Fill blanks if /me arrives after mount; never overwrite user edits.
watch(
  () =>
    [
      authStore.user?.username,
      authStore.user?.phone,
      authStore.user?.schoolName,
    ] as const,
  () => {
    applyProfilePrefill({ onlyEmpty: true })
  }
)

async function submitConsultation(): Promise<void> {
  if (submitting.value) {
    return
  }

  const validated = validateSchoolConsultForm({
    name: form.name,
    phone: form.phone,
    organization: form.organization,
    note: form.note,
  })
  if (!validated.ok) {
    notify.warning(t(schoolConsultValidationMessageKey(validated.error)))
    return
  }

  submitting.value = true
  try {
    const { name, phone, organization, note } = validated.values
    const response = await apiRequest('/api/auth/thinking-coins/school-consultation', {
      method: 'POST',
      body: JSON.stringify({
        name,
        phone,
        organization,
        note,
      }),
    })
    if (response.ok) {
      notify.success(t('thinkingCoins.school.submitSuccess'))
      resetForm()
      return
    }
    if (response.status === 422) {
      notify.warning(t('thinkingCoins.school.validationInvalid'))
      return
    }
    if (response.status === 429) {
      notify.error(t('thinkingCoins.school.submitRateLimit'))
      return
    }
    if (response.status === 503) {
      notify.error(t('thinkingCoins.school.submitNotConfigured'))
      return
    }
    notify.error(t('thinkingCoins.school.submitFailed'))
  } catch {
    notify.error(t('thinkingCoins.school.submitFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="tc-school-panel space-y-5">
    <div class="flex items-start gap-3">
      <div
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-stone-200 bg-stone-50"
      >
        <Building2 class="h-5 w-5 text-stone-600" />
      </div>
      <div class="min-w-0">
        <h3 class="text-base font-semibold text-stone-900">
          {{ t('thinkingCoins.school.headline') }}
        </h3>
        <p class="mt-1.5 text-sm leading-relaxed text-stone-500">
          {{ t('thinkingCoins.school.description') }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div
        v-for="feature in SCHOOL_FEATURES"
        :key="feature.titleKey"
        class="rounded-xl border border-stone-100 bg-stone-50/80 px-4 py-3.5"
      >
        <div class="flex items-start gap-2.5">
          <component
            :is="feature.icon"
            class="mt-0.5 h-4 w-4 shrink-0 text-stone-500"
          />
          <div class="min-w-0">
            <div class="text-sm font-semibold text-stone-800">
              {{ t(feature.titleKey) }}
            </div>
            <div class="mt-0.5 text-xs text-stone-500">
              {{ t(feature.descKey) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <form
      class="rounded-2xl border border-stone-200 bg-stone-50/60 p-4 sm:p-5"
      @submit.prevent="submitConsultation"
    >
      <h4 class="text-sm font-semibold text-stone-800">
        {{ t('thinkingCoins.school.consultTitle') }}
      </h4>

      <div class="mt-4 space-y-3">
        <input
          v-model="form.name"
          type="text"
          required
          autocomplete="name"
          :maxlength="SCHOOL_CONSULT_LIMITS.name"
          class="tc-school-input"
          :placeholder="t('thinkingCoins.school.fieldName')"
        >
        <input
          v-model="form.phone"
          type="tel"
          inputmode="tel"
          required
          autocomplete="tel"
          :maxlength="SCHOOL_CONSULT_LIMITS.phone"
          class="tc-school-input"
          :placeholder="t('thinkingCoins.school.fieldPhone')"
        >
        <input
          v-model="form.organization"
          type="text"
          required
          autocomplete="organization"
          :maxlength="SCHOOL_CONSULT_LIMITS.organization"
          class="tc-school-input"
          :placeholder="t('thinkingCoins.school.fieldOrg')"
        >
        <textarea
          v-model="form.note"
          rows="3"
          :maxlength="SCHOOL_CONSULT_LIMITS.note"
          class="tc-school-input tc-school-textarea"
          :placeholder="t('thinkingCoins.school.fieldNote')"
        />
      </div>

      <button
        type="submit"
        class="tc-school-submit mt-4"
        :disabled="submitting"
      >
        {{ t('thinkingCoins.school.submit') }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.tc-school-input {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid #e7e5e4;
  background: #ffffff;
  padding: 0.625rem 0.875rem;
  font-size: 0.875rem;
  color: #1c1917;
  outline: none;
  transition:
    border-color 0.12s ease,
    box-shadow 0.12s ease;
}

.tc-school-input::placeholder {
  color: #a8a29e;
}

.tc-school-input:focus {
  border-color: #d6d3d1;
  box-shadow: 0 0 0 3px rgba(28, 25, 23, 0.06);
}

.tc-school-textarea {
  resize: vertical;
  min-height: 5.5rem;
}

.tc-school-submit {
  border: none;
  border-radius: 0.5rem;
  padding: 0.4375rem 0.875rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1.25;
  color: #ffffff;
  background: #1c1917;
  cursor: pointer;
  transition:
    background 0.12s ease,
    opacity 0.12s ease;
}

.tc-school-submit:hover:not(:disabled) {
  background: #292524;
}

.tc-school-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
