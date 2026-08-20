<script setup lang="ts">
/**
 * Mobile organization management — create a school and share invite code / link.
 */
import { useRouter } from 'vue-router'

import { Building2, Home, Loader2, Plus } from '@lucide/vue'

import MobileOrgInviteShare from '@/components/mobile/MobileOrgInviteShare.vue'
import { useLanguage } from '@/composables'
import { useMobileOrgManagement } from '@/composables/mobile/useMobileOrgManagement'

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

function goHome() {
  router.push('/m')
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
      <h1 class="flex-1 text-center text-base font-semibold text-gray-800 truncate">
        {{ t('mobile.orgsTitle') }}
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
            {{ t('admin.createOrganization') }}
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
            class="w-full h-11 rounded-xl bg-indigo-600 text-white text-sm font-medium flex items-center justify-center gap-2 active:bg-indigo-700 disabled:opacity-50"
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
            {{ t('admin.createOrganization') }}
          </button>
        </form>

        <div class="text-sm font-semibold text-gray-500">
          {{ t('mobile.orgsListTitle') }}
        </div>

        <div
          v-if="isLoading && organizations.length === 0"
          class="text-sm text-gray-400 text-center py-8"
        >
          {{ t('common.loading') }}
        </div>

        <div
          v-else-if="organizations.length === 0"
          class="text-sm text-gray-400 text-center py-8"
        >
          {{ t('mobile.orgsEmpty') }}
        </div>

        <button
          v-for="org in organizations"
          :key="org.id"
          type="button"
          class="org-card w-full text-left bg-white rounded-2xl border border-gray-200 p-4 active:bg-gray-50"
          @click="toggleExpanded(org.id)"
        >
          <div class="flex items-start gap-3">
            <div
              class="flex items-center justify-center w-10 h-10 rounded-xl bg-amber-50 text-amber-600 shrink-0"
            >
              <Building2 :size="20" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold text-gray-900 truncate">
                {{ org.name }}
              </div>
              <div class="text-xs text-gray-500 mt-0.5">
                {{ t('mobile.orgsMemberCount', { count: org.userCount }) }}
              </div>
            </div>
          </div>

          <div
            v-if="expandedId === org.id && org.invitationCode"
            class="mt-3 pt-3 border-t border-gray-100"
            @click.stop
          >
            <MobileOrgInviteShare
              :invitation-code="org.invitationCode"
              :invite-link="org.inviteLink"
              @copy="copyText"
            />
          </div>
        </button>
      </div>
    </div>
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
}

.org-card:active {
  transform: scale(0.99);
}
</style>
