<script setup lang="ts">
/**
 * `/auth` contact modal — same school consultation form as Thinking Coins school tab.
 */
import { reactive, ref, watch } from 'vue'

import { MessageCircle } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import {
  SCHOOL_CONSULT_LIMITS,
  schoolConsultValidationMessageKey,
  validateSchoolConsultForm,
} from '@/utils/schoolConsultValidation'

const visible = defineModel<boolean>({ required: true })

const { t } = useLanguage()
const authStore = useAuthStore()
const submitting = ref(false)

const form = reactive({
  name: '',
  phone: '',
  organization: '',
  note: '',
})

function profilePrefill(): { name: string; phone: string; organization: string } {
  const user = authStore.user
  const username = (user?.username || '').trim()
  const phone = (user?.phone || '').trim()
  const organization = (user?.schoolName || '').trim()
  const looksLikePhone =
    /^\d{7,15}$/.test(username) || (phone !== '' && username === phone)
  const name = looksLikePhone ? '' : username
  return {
    name: name.slice(0, SCHOOL_CONSULT_LIMITS.name),
    phone: phone.slice(0, SCHOOL_CONSULT_LIMITS.phone),
    organization: organization.slice(0, SCHOOL_CONSULT_LIMITS.organization),
  }
}

function applyProfilePrefill(): void {
  const prefill = profilePrefill()
  form.name = prefill.name
  form.phone = prefill.phone
  form.organization = prefill.organization
  form.note = ''
}

watch(visible, (open) => {
  if (open) {
    applyProfilePrefill()
  }
})

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
      applyProfilePrefill()
      visible.value = false
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
  <SwissGlassCard
    v-model="visible"
    :ribbon="t('auth.landing.navContact')"
    :title="t('thinkingCoins.school.consultTitle')"
    :line1="t('thinkingCoins.school.description')"
    :icon="MessageCircle"
    show-close
  >
    <form
      class="auth-contact-form space-y-3 p-5"
      @submit.prevent="submitConsultation"
    >
      <input
        v-model="form.name"
        type="text"
        required
        autocomplete="name"
        :maxlength="SCHOOL_CONSULT_LIMITS.name"
        class="auth-contact-form__input"
        :placeholder="t('thinkingCoins.school.fieldName')"
      />
      <input
        v-model="form.phone"
        type="tel"
        inputmode="tel"
        required
        autocomplete="tel"
        :maxlength="SCHOOL_CONSULT_LIMITS.phone"
        class="auth-contact-form__input"
        :placeholder="t('thinkingCoins.school.fieldPhone')"
      />
      <input
        v-model="form.organization"
        type="text"
        required
        autocomplete="organization"
        :maxlength="SCHOOL_CONSULT_LIMITS.organization"
        class="auth-contact-form__input"
        :placeholder="t('thinkingCoins.school.fieldOrg')"
      />
      <textarea
        v-model="form.note"
        rows="3"
        :maxlength="SCHOOL_CONSULT_LIMITS.note"
        class="auth-contact-form__input auth-contact-form__textarea"
        :placeholder="t('thinkingCoins.school.fieldNote')"
      />
      <button
        type="submit"
        class="auth-contact-form__submit"
        :disabled="submitting"
      >
        {{ t('thinkingCoins.school.submit') }}
      </button>
    </form>
  </SwissGlassCard>
</template>

<style scoped>
.auth-contact-form__input {
  width: 100%;
  border-radius: 0.85rem;
  border: 0;
  background: #eef2ff;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
  color: #0f172a;
  outline: none;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.auth-contact-form__input::placeholder {
  color: #94a3b8;
}

.auth-contact-form__input:focus {
  background: #fff;
  box-shadow: 0 0 0 3px rgb(99 102 241 / 0.16);
}

.auth-contact-form__textarea {
  resize: vertical;
  min-height: 5.5rem;
}

.auth-contact-form__submit {
  width: 100%;
  margin-top: 0.35rem;
  border: 0;
  border-radius: 0.75rem;
  padding: 0.85rem 1rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(90deg, #3b82f6 0%, #7c5cbf 100%);
  box-shadow: 0 10px 24px rgb(99 102 241 / 0.28);
  cursor: pointer;
  transition: filter 0.15s ease;
}

.auth-contact-form__submit:hover:not(:disabled) {
  filter: brightness(1.05);
}

.auth-contact-form__submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
