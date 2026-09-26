<script setup lang="ts">
/**
 * Mobile organization management — create a school, then open its chart card.
 */
import { useRouter } from 'vue-router'

import { Building2, ChevronRight, Home, Loader2, Plus } from '@lucide/vue'

import AdminTrendChartModal from '@/components/admin/AdminTrendChartModal.vue'
import { useLanguage } from '@/composables'
import { useMobileOrgManagement } from '@/composables/mobile/useMobileOrgManagement'

const router = useRouter()
const { t } = useLanguage()
const {
  orgName,
  isSubmitting,
  isLoading,
  organizations,
  openingId,
  diagramVisible,
  diagramSchool,
  schoolDialogMode,
  diagramReadOnly,
  submitCreate,
  openSchool,
  refreshOpenedSchool,
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
      <h1 class="flex-1 text-center text-base font-semibold text-gray-800 truncate px-2">
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
          class="org-card w-full text-left bg-white rounded-2xl border border-gray-200 p-4 active:bg-gray-50 flex items-center gap-3 disabled:opacity-60"
          :disabled="openingId != null"
          @click="openSchool(org.id)"
        >
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
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>
      </div>
    </div>

    <AdminTrendChartModal
      v-model:visible="diagramVisible"
      type="org"
      :school-dialog-mode="schoolDialogMode"
      :org-name="diagramSchool?.name"
      :org-id="diagramSchool?.id"
      :org-invitation-code="diagramSchool?.invitationCode"
      :org-display-name="diagramSchool?.display_name"
      :org-is-active="diagramSchool?.is_active"
      :org-user-count="diagramSchool?.user_count ?? 0"
      :org-expires-at="diagramSchool?.expires_at"
      :org-school-tier="diagramSchool?.school_tier"
      :org-extra-member-seats="diagramSchool?.extra_member_seats ?? 0"
      :org-teaching-design-template-key="diagramSchool?.teaching_design_template_key"
      :org-custom-llm-api-type="diagramSchool?.custom_llm_api_type"
      :org-custom-llm-base-url="diagramSchool?.custom_llm_base_url"
      :org-custom-llm-api-key-masked="diagramSchool?.custom_llm_api_key_masked"
      :org-custom-llm-model="diagramSchool?.custom_llm_model"
      :org-dify-api-base-url="diagramSchool?.dify_api_base_url"
      :org-dify-api-key-masked="diagramSchool?.dify_api_key_masked"
      :org-dify-api-base-url2="diagramSchool?.dify_api_base_url_2"
      :org-dify-api-key2-masked="diagramSchool?.dify_api_key_2_masked"
      :org-dify-active-server="diagramSchool?.dify_active_server"
      :org-dify-failover-enabled="diagramSchool?.dify_failover_enabled"
      :org-dify-timeout-seconds="diagramSchool?.dify_timeout_seconds"
      :org-dingtalk-ai-card-streaming-max-chars="
        diagramSchool?.dingtalk_ai_card_streaming_max_chars
      "
      :org-show-chain-of-thought="diagramSchool?.show_chain_of_thought"
      :org-mindmate-agent-name="diagramSchool?.mindmate_agent_name"
      :org-mindmate-agent-avatar-url="diagramSchool?.mindmate_agent_avatar_url"
      :initial-school-tab="diagramSchool?.initial_tab"
      :initial-trend-period="diagramSchool?.initial_trend_period"
      :read-only="diagramReadOnly"
      @refresh="refreshOpenedSchool"
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
}

.org-card:active {
  transform: scale(0.99);
}
</style>
