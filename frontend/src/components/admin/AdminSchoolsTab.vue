<script setup lang="ts">
/**
 * Admin Schools Tab - List and create organizations (Swiss panel)
 * Click school row to open chart + token cards modal
 */
import { onMounted, ref } from 'vue'

import { Edit, Loading } from '@element-plus/icons-vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import {
  resolveSchoolMindmateAgentName,
  resolveSchoolMindmateAvatarUrl,
} from '@/composables/mindmate/useMindMateBranding'
import '@/styles/admin-schools-swiss.css'
import { apiRequest } from '@/utils/apiClient'

import AdminSchoolCreateDialog from './AdminSchoolCreateDialog.vue'
import AdminSchoolShareDialog from './AdminSchoolShareDialog.vue'
import AdminTrendChartModal from './AdminTrendChartModal.vue'

const { t } = useLanguage()
const notify = useNotifications()

const isLoading = ref(true)
const schools = ref<Record<string, unknown>[]>([])
const createModalVisible = ref(false)
const shareModalVisible = ref(false)
const shareInvitationCode = ref('')
const trendModalVisible = ref(false)
const trendOrg = ref<{
  name: string
  id?: number
  display_name?: string
  is_active?: boolean
  user_count?: number
  expires_at?: string | null
  dify_api_base_url?: string | null
  dify_api_key_masked?: string | null
  dify_timeout_seconds?: number
  dingtalk_ai_card_streaming_max_chars?: number
  show_chain_of_thought?: boolean
  mindmate_agent_name?: string | null
  mindmate_agent_avatar_url?: string | null
  initial_tab?: 'usage' | 'general'
} | null>(null)

function agentDisplayName(row: Record<string, unknown>): string {
  const customName = resolveSchoolMindmateAgentName(
    row.mindmate_agent_name as string | null | undefined
  )
  return customName ?? (t('sidebar.mindMate') as string)
}

function agentAvatarSrc(row: Record<string, unknown>): string {
  return (
    resolveSchoolMindmateAvatarUrl(row.mindmate_agent_avatar_url as string | null | undefined) ??
    mindmateAvatarMd
  )
}

function onAgentAvatarError(event: Event) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== mindmateAvatarMd) {
    img.src = mindmateAvatarMd
  }
}

function hasPrivateDify(row: Record<string, unknown>): boolean {
  return Boolean(row.dify_api_key_masked)
}

function orgShowChainOfThought(row: Record<string, unknown>): boolean {
  return Boolean(
    row.show_chain_of_thought_oto ||
      row.show_chain_of_thought_internal_group ||
      row.show_chain_of_thought_cross_org_group
  )
}

function openTrendModal(row: Record<string, unknown>, initialTab: 'usage' | 'general' = 'general') {
  trendOrg.value = {
    name: String(row.name ?? ''),
    id: row.id as number | undefined,
    display_name: row.display_name as string | undefined,
    is_active: row.is_active as boolean | undefined,
    user_count: (row.user_count as number) ?? 0,
    expires_at: row.expires_at as string | null | undefined,
    dify_api_base_url: row.dify_api_base_url as string | null | undefined,
    dify_api_key_masked: row.dify_api_key_masked as string | null | undefined,
    dify_timeout_seconds: (row.dify_timeout_seconds as number | undefined) ?? 300,
    dingtalk_ai_card_streaming_max_chars:
      (row.dingtalk_ai_card_streaming_max_chars as number | undefined) ?? 6500,
    show_chain_of_thought: orgShowChainOfThought(row),
    mindmate_agent_name: row.mindmate_agent_name as string | null | undefined,
    mindmate_agent_avatar_url: row.mindmate_agent_avatar_url as string | null | undefined,
    initial_tab: initialTab,
  }
  trendModalVisible.value = true
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function syncTrendOrgFromSchools() {
  const trendId = trendOrg.value?.id
  const currentTrend = trendOrg.value
  if (trendId == null || !currentTrend) {
    return
  }
  const updated = schools.value.find((s: Record<string, unknown>) => s.id === trendId)
  if (updated) {
    trendOrg.value = {
      ...currentTrend,
      name: String(updated.name ?? currentTrend.name),
      display_name: updated.display_name as string | undefined,
      is_active: updated.is_active as boolean | undefined,
      user_count: (updated.user_count as number) ?? 0,
      expires_at: updated.expires_at as string | null | undefined,
      dify_api_base_url: updated.dify_api_base_url as string | null | undefined,
      dify_api_key_masked: updated.dify_api_key_masked as string | null | undefined,
      dify_timeout_seconds: (updated.dify_timeout_seconds as number | undefined) ?? 300,
      dingtalk_ai_card_streaming_max_chars:
        (updated.dingtalk_ai_card_streaming_max_chars as number | undefined) ?? 6500,
      show_chain_of_thought: orgShowChainOfThought(updated),
      mindmate_agent_name: updated.mindmate_agent_name as string | null | undefined,
      mindmate_agent_avatar_url: updated.mindmate_agent_avatar_url as string | null | undefined,
      initial_tab: currentTrend.initial_tab,
    }
  }
}

async function loadSchools(options?: { silent?: boolean }) {
  const silent = options?.silent === true
  if (!silent) {
    isLoading.value = true
  }
  try {
    const res = await apiRequest('/api/auth/admin/organizations')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.schoolsLoadError'))
      return
    }
    schools.value = await res.json()
    syncTrendOrgFromSchools()
  } catch {
    notify.error(t('admin.schoolsLoadError'))
  } finally {
    if (!silent) {
      isLoading.value = false
    }
  }
}

function openCreateModal() {
  createModalVisible.value = true
}

function openShareModalWithCode(code: string) {
  shareInvitationCode.value = code
  shareModalVisible.value = true
}

function onSchoolCreated(payload: { invitation_code?: string }) {
  void loadSchools()
  if (payload.invitation_code) {
    openShareModalWithCode(payload.invitation_code)
  }
}

onMounted(loadSchools)

defineExpose({
  openCreateModal,
})
</script>

<template>
  <div class="admin-schools-tab">
    <el-card
      shadow="never"
      class="admin-schools-card"
    >
      <div
        v-if="isLoading"
        class="flex justify-center py-12"
      >
        <el-icon
          class="is-loading"
          :size="32"
        >
          <Loading />
        </el-icon>
      </div>

      <el-table
        v-else
        :data="schools"
        row-key="id"
        class="admin-schools-table w-full"
        :empty-text="t('admin.noData')"
        stripe
        size="small"
      >
        <el-table-column
          prop="name"
          :label="t('admin.organizationName')"
          min-width="120"
          show-overflow-tooltip
          class-name="admin-schools-col-text"
        />
        <el-table-column
          :label="t('admin.orgPrivateDify')"
          min-width="96"
          align="center"
        >
          <template #default="{ row }">
            <span
              class="admin-schools-private"
              :class="
                hasPrivateDify(row)
                  ? 'admin-schools-private--yes'
                  : 'admin-schools-private--no'
              "
            >
              {{
                hasPrivateDify(row)
                  ? t('admin.orgPrivateDifyYes')
                  : t('admin.orgPrivateDifyNo')
              }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="mindmate_agent_name"
          :label="t('admin.schoolMindmateAgentName')"
          min-width="112"
          show-overflow-tooltip
          class-name="admin-schools-col-text"
        >
          <template #default="{ row }">
            <span class="text-stone-700">{{ agentDisplayName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.orgAgentAvatar')"
          min-width="64"
          align="center"
        >
          <template #default="{ row }">
            <img
              :src="agentAvatarSrc(row)"
              :alt="agentDisplayName(row)"
              class="admin-schools-agent-avatar"
              width="32"
              height="32"
              @error="onAgentAvatarError"
            />
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.tokensUsed')"
          min-width="96"
          align="right"
        >
          <template #default="{ row }">
            <button
              type="button"
              class="admin-schools-link tabular-nums"
              @click="openTrendModal(row, 'usage')"
            >
              {{ formatNumber((row.token_stats?.total_tokens as number) ?? 0) }}
            </button>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.status')"
          min-width="80"
          align="center"
        >
          <template #default="{ row }">
            <span
              class="admin-schools-status"
              :class="row.is_active ? 'admin-schools-status--on' : 'admin-schools-status--off'"
            >
              {{ row.is_active ? t('admin.enabled') : t('admin.disabled') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="user_count"
          :label="t('admin.usersCount')"
          min-width="72"
          align="right"
        >
          <template #default="{ row }">
            <span class="tabular-nums text-stone-700">{{ row.user_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="manager_count"
          :label="t('admin.managerCount')"
          min-width="80"
          align="right"
        >
          <template #default="{ row }">
            <span class="tabular-nums text-stone-700">{{ row.manager_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.actions')"
          min-width="96"
          fixed="right"
          align="center"
        >
          <template #default="{ row }">
            <el-button
              type="primary"
              plain
              size="small"
              class="admin-swiss-pill-btn admin-swiss-pill-btn--edit"
              @click="openTrendModal(row)"
            >
              <el-icon class="mr-0.5"><Edit /></el-icon>
              {{ t('common.edit') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <AdminSchoolCreateDialog
      v-model="createModalVisible"
      @created="onSchoolCreated"
    />

    <AdminSchoolShareDialog
      v-model="shareModalVisible"
      :invitation-code="shareInvitationCode"
    />

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="org"
      :org-name="trendOrg?.name"
      :org-id="trendOrg?.id"
      :org-display-name="trendOrg?.display_name"
      :org-is-active="trendOrg?.is_active"
      :org-user-count="trendOrg?.user_count ?? 0"
      :org-expires-at="trendOrg?.expires_at"
      :org-dify-api-base-url="trendOrg?.dify_api_base_url"
      :org-dify-api-key-masked="trendOrg?.dify_api_key_masked"
      :org-dify-timeout-seconds="trendOrg?.dify_timeout_seconds"
      :org-dingtalk-ai-card-streaming-max-chars="trendOrg?.dingtalk_ai_card_streaming_max_chars"
      :org-show-chain-of-thought="trendOrg?.show_chain_of_thought"
      :org-mindmate-agent-name="trendOrg?.mindmate_agent_name"
      :org-mindmate-agent-avatar-url="trendOrg?.mindmate_agent_avatar_url"
      :initial-school-tab="trendOrg?.initial_tab"
      @refresh="() => loadSchools({ silent: true })"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
