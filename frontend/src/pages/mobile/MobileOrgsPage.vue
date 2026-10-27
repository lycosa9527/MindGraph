<script setup lang="ts">
/**
 * Mobile organization management — create a school and share invite code / link.
 */
import { shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { Building2, Home, Loader2, Plus } from '@lucide/vue'

import MobileOrgBrandingSheet from '@/components/mobile/MobileOrgBrandingSheet.vue'
import MobileOrgInviteShare from '@/components/mobile/MobileOrgInviteShare.vue'
import { useLanguage } from '@/composables'
import {
  type MobileOrgRow,
  useMobileOrgManagement,
} from '@/composables/mobile/useMobileOrgManagement'
import { mobileOrgCardLabel } from '@/utils/mobileOrganizations'

const router = useRouter()
const { t } = useLanguage()
const {
  orgName,
  isSubmitting,
  isLoading,
  organizations,
  expandedId,
  submitCreate,
  toggleExpanded,
  copyText,
} = useMobileOrgManagement()

const brandingOrg = shallowRef<MobileOrgRow | null>(null)

function goHome() {
  router.push('/m')
}

function openBranding(org: MobileOrgRow): void {
  brandingOrg.value = org
}

function closeBranding(): void {
  brandingOrg.value = null
}
</script>

<template>
  <div class="mobile-orgs flex flex-col flex-1 min-h-0">
    <header
      class="mobile-orgs-header flex items-center h-12 px-3 bg-white border-b border-gray-200 shrink-0"
    >
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
        :aria-label="t('mobile.navHome', 'Home')"
        @click="goHome"
      >
        <Home
          :size="18"
          class="text-gray-500"
        />
      </button>
      <h1 class="flex-1 text-center text-base font-semibold text-gray-800 truncate px-2">
        <I18nText k="mobile.orgsTitle" />
      </h1>
      <div class="w-8 shrink-0" />
    </header>

    <div class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
      <div class="px-4 pt-4 pb-8 max-w-md mx-auto space-y-4">
        <form
          class="bg-white rounded-2xl border border-gray-200 p-4 space-y-3"
          @submit.prevent="submitCreate"
        >
          <label
            class="block text-sm font-semibold text-gray-800"
            for="mobile-org-name"
          >
            <I18nText k="admin.createOrganization" />
          </label>
          <input
            id="mobile-org-name"
            v-model="orgName"
            type="text"
            autocomplete="organization"
            class="w-full h-11 px-3 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            :placeholder="t('admin.organizationNamePlaceholder')"
          />
          <button
            type="submit"
            class="org-pill org-pill--primary"
            :disabled="isSubmitting || !orgName.trim()"
          >
            <Loader2
              v-if="isSubmitting"
              :size="16"
              class="animate-spin"
            />
            <Plus
              v-else
              :size="16"
            />
            <I18nText k="admin.createOrganization" />
          </button>
        </form>

        <div class="text-sm font-semibold text-gray-500">
          <I18nText k="mobile.orgsListTitle" />
        </div>

        <div
          v-if="isLoading && organizations.length === 0"
          class="text-sm text-gray-400 text-center py-8"
        >
          <I18nText k="common.loading" />
        </div>

        <div
          v-else-if="organizations.length === 0"
          class="text-sm text-gray-400 text-center py-8"
        >
          <I18nText k="mobile.orgsEmpty" />
        </div>

        <article
          v-for="org in organizations"
          :id="`mobile-org-${org.id}`"
          :key="org.id"
          class="org-card bg-white rounded-2xl border border-gray-200 p-4"
        >
          <button
            type="button"
            class="org-name"
            :aria-expanded="expandedId === org.id"
            @click="toggleExpanded(org.id)"
          >
            <div
              class="flex items-center justify-center w-10 h-10 rounded-xl bg-amber-50 text-amber-600 shrink-0"
            >
              <Building2 :size="20" />
            </div>
            <div class="min-w-0">
              <div class="text-sm font-semibold text-gray-900 truncate">
                {{ mobileOrgCardLabel(org) }}
              </div>
              <div class="text-xs text-gray-500 mt-0.5">
                <I18nText
                  k="mobile.orgsMemberCount"
                  :params="{ count: org.userCount }"
                />
              </div>
            </div>
          </button>

          <div
            v-if="expandedId === org.id"
            class="mt-3 pt-3 border-t border-gray-100"
          >
            <MobileOrgInviteShare
              :organization-name="mobileOrgCardLabel(org)"
              :invitation-code="org.invitationCode"
              :invite-link="org.inviteLink"
              @copy="copyText"
              @edit="openBranding(org)"
            />
          </div>
        </article>
      </div>
    </div>

    <MobileOrgBrandingSheet
      :org="brandingOrg"
      @close="closeBranding"
    />
  </div>
</template>

<style scoped>
.mobile-orgs-header {
  -webkit-user-select: none;
  user-select: none;
  z-index: 10;
  padding-top: env(safe-area-inset-top);
}

.org-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  scroll-margin-top: 4.5rem;
  scroll-margin-bottom: 1.5rem;
}

.org-name {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  padding: 8px 12px;
  border: 0;
  border-radius: 6px;
  background: #f3f4f6;
  text-align: left;
}

.org-name:active {
  background: #e5e7eb;
}

.org-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 44px;
  flex: 0 0 auto;
  width: fit-content;
  max-width: 100%;
  padding: 0 20px;
  border: 0;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
}

.org-pill:disabled {
  opacity: 0.5;
}

.org-pill--primary {
  background: #4f46e5;
  color: #fff;
}

.org-pill--primary:active:not(:disabled) {
  background: #4338ca;
}
</style>
