<script setup lang="ts">
/**
 * Invite users tab — organization table with invitation codes.
 */
import { computed, onMounted, ref } from 'vue'

import { DocumentCopy, Loading } from '@element-plus/icons-vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import AdminPersonalTrialInviteCard from '@/components/admin/AdminPersonalTrialInviteCard.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import {
  resolveSchoolMindmateAgentName,
  resolveSchoolMindmateAvatarUrl,
} from '@/composables/mindmate/useMindMateBranding'
import '@/styles/admin-schools-swiss.css'
import { apiRequest } from '@/utils/apiClient'
import {
  buildPrivatizedColumnFilters,
  filterOrgByPrivatized,
  isOrgPrivatized,
} from '@/utils/orgPrivatization'

import AdminSchoolCreateDialog from './AdminSchoolCreateDialog.vue'
import AdminSchoolShareDialog from './AdminSchoolShareDialog.vue'

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()
const { can, canEditTab } = useAdminAccess()

const isLoading = ref(true)
const organizations = ref<Record<string, unknown>[]>([])
const createModalVisible = ref(false)
const shareModalVisible = ref(false)
const shareInvitationCode = ref('')

const showOrgInvites = computed(
  () => can('scope.org') || can('scope.global') || can('scope.invited_orgs')
)
const canEditInvites = computed(() => canEditTab('invites'))

const orgTableEmptyText = computed(() => {
  if (can('scope.invited_orgs')) {
    return t('admin.inviteOrgsEmpty')
  }
  return t('admin.noData')
})

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

const privatizedColumnFilters = computed(() =>
  buildPrivatizedColumnFilters(
    t('admin.orgPrivateDifyYes') as string,
    t('admin.orgPrivateDifyNo') as string
  )
)

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function invitationCodeFor(row: Record<string, unknown>): string {
  return String(row.invitation_code ?? '').trim()
}

async function loadOrganizations(): Promise<void> {
  isLoading.value = true
  try {
    const res = await apiRequest('/api/auth/admin/invites/organizations')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.schoolsLoadError'))
      return
    }
    organizations.value = await res.json()
  } catch {
    notify.error(t('admin.schoolsLoadError'))
  } finally {
    isLoading.value = false
  }
}

async function copyInvite(code: string): Promise<void> {
  if (!code) {
    return
  }
  const text = t('admin.schoolInviteCopyPayload', {
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

function openCreateModal(): void {
  createModalVisible.value = true
}

function openShareModalWithCode(code: string): void {
  shareInvitationCode.value = code
  shareModalVisible.value = true
}

function onSchoolCreated(payload: { invitation_code?: string }): void {
  void loadOrganizations()
  if (payload.invitation_code) {
    openShareModalWithCode(payload.invitation_code)
  }
}

onMounted(() => {
  if (showOrgInvites.value) {
    void loadOrganizations()
  }
})

defineExpose({
  openCreateModal,
})
</script>

<template>
  <div class="admin-schools-tab admin-invite-users-tab">
    <template v-if="showOrgInvites">
      <el-card shadow="never" class="admin-schools-card">
        <div v-if="isLoading" class="flex justify-center py-12">
          <el-icon class="is-loading" :size="32">
            <Loading />
          </el-icon>
        </div>

        <el-table
          v-else
          :data="organizations"
          row-key="id"
          class="admin-schools-table w-full"
          :empty-text="orgTableEmptyText"
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
            column-key="is_privatized"
            :label="t('admin.orgPrivateDify')"
            min-width="96"
            align="center"
            :filters="privatizedColumnFilters"
            :filter-method="filterOrgByPrivatized"
            filter-placement="bottom-end"
          >
            <template #default="{ row }">
              <span
                class="admin-schools-private"
                :class="
                  isOrgPrivatized(row)
                    ? 'admin-schools-private--yes'
                    : 'admin-schools-private--no'
                "
              >
                {{
                  isOrgPrivatized(row)
                    ? t('admin.orgPrivateDifyYes')
                    : t('admin.orgPrivateDifyNo')
                }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
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
              <span class="tabular-nums text-stone-700">
                {{ formatNumber((row.token_stats as { total_tokens?: number })?.total_tokens ?? 0) }}
              </span>
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
            :label="t('admin.invitationCode')"
            min-width="140"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono text-sm text-stone-800 truncate">
                  {{ invitationCodeFor(row) || '—' }}
                </span>
                <el-button
                  v-if="canEditInvites && invitationCodeFor(row)"
                  type="primary"
                  link
                  size="small"
                  :title="t('admin.copyShareMessage')"
                  @click="copyInvite(invitationCodeFor(row))"
                >
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      <AdminPersonalTrialInviteCard />
    </template>

    <template v-else-if="can('tab.invites.view')">
      <AdminPersonalTrialInviteCard />
    </template>

    <AdminSchoolCreateDialog
      v-model="createModalVisible"
      @created="onSchoolCreated"
    />

    <AdminSchoolShareDialog
      v-model="shareModalVisible"
      :invitation-code="shareInvitationCode"
    />
  </div>
</template>
