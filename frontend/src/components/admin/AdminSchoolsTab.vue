<script setup lang="ts">
/**
 * Admin Schools Tab - List and create organizations
 * Click school row to open chart + token cards modal
 */
import { onMounted, ref } from 'vue'

import { DocumentCopy, Loading, Plus, Share } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

import AdminTrendChartModal from './AdminTrendChartModal.vue'

const { t } = useLanguage()
const notify = useNotifications()

const isLoading = ref(true)
const schools = ref<Record<string, unknown>[]>([])
const createModalVisible = ref(false)
const createForm = ref({ code: '', name: '' })
const shareModalVisible = ref(false)
const shareInvitationCode = ref('')
const trendModalVisible = ref(false)
const trendOrg = ref<{
  name: string
  id?: number
  invitation_code?: string
  display_name?: string
} | null>(null)

function openTrendModal(row: Record<string, unknown>) {
  trendOrg.value = {
    name: String(row.name ?? ''),
    id: row.id as number | undefined,
    invitation_code: row.invitation_code as string | undefined,
    display_name: row.display_name as string | undefined,
  }
  trendModalVisible.value = true
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

async function loadSchools() {
  isLoading.value = true
  try {
    const res = await apiRequest('/api/auth/admin/organizations')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to load schools')
      return
    }
    schools.value = await res.json()
    if (trendOrg.value?.id) {
      const updated = schools.value.find(
        (s: Record<string, unknown>) => s.id === trendOrg.value!.id
      )
      if (updated) {
        trendOrg.value = {
          ...trendOrg.value,
          name: String(updated.name ?? trendOrg.value.name),
          display_name: updated.display_name as string | undefined,
        }
      }
    }
  } catch {
    notify.error('Failed to load schools')
  } finally {
    isLoading.value = false
  }
}

function openCreateModal() {
  createForm.value = { code: '', name: '' }
  createModalVisible.value = true
}

function openShareModal(code: string) {
  shareInvitationCode.value = code
  shareModalVisible.value = true
}

function shareMessageText(): string {
  return t('admin.shareInviteMessage').replace('{code}', shareInvitationCode.value)
}

async function copyShareMessage() {
  try {
    await navigator.clipboard.writeText(shareMessageText())
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function createSchool() {
  if (!createForm.value.code.trim() || !createForm.value.name.trim()) {
    notify.error('Code and name are required')
    return
  }
  try {
    const res = await apiRequest('/api/auth/admin/organizations', {
      method: 'POST',
      body: JSON.stringify(createForm.value),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to create school')
      return
    }
    notify.success(t('notification.saved'))
    createModalVisible.value = false
    loadSchools()
  } catch {
    notify.error('Failed to create school')
  }
}

onMounted(loadSchools)
</script>

<template>
  <div class="admin-schools-tab pt-4">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('admin.schools') }}</span>
          <el-button
            type="primary"
            size="small"
            @click="openCreateModal"
          >
            <el-icon class="mr-1"><Plus /></el-icon>
            {{ t('admin.createSchool') }}
          </el-button>
        </div>
      </template>

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
        stripe
        size="small"
      >
        <el-table-column
          prop="name"
          :label="t('admin.schoolName')"
          min-width="180"
        >
          <template #default="{ row }">
            <span
              class="cursor-pointer hover:text-primary-500 hover:underline"
              @click="openTrendModal(row)"
            >
              {{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="invitation_code"
          :label="t('admin.invitationCode')"
          width="160"
        >
          <template #default="{ row }">
            <span class="inline-flex items-center gap-1">
              {{ row.invitation_code }}
              <el-tooltip :content="t('admin.shareInviteTitle')" placement="top">
                <el-button
                  link
                  type="primary"
                  size="small"
                  class="p-0 min-w-0"
                  @click="openShareModal(String(row.invitation_code ?? ''))"
                >
                  <el-icon><Share /></el-icon>
                </el-button>
              </el-tooltip>
            </span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.tokensUsed')"
          width="120"
        >
          <template #default="{ row }">
            <span
              class="cursor-pointer hover:text-primary-500"
              @click="openTrendModal(row)"
            >
              {{ formatNumber((row.token_stats?.total_tokens as number) ?? 0) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.status')"
          width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.is_active ? 'success' : 'danger'"
              size="small"
            >
              {{ row.is_active ? t('admin.enabled') : t('admin.disabled') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="user_count"
          :label="t('admin.usersCount')"
          width="100"
        >
          <template #default="{ row }">
            {{ row.user_count ?? 0 }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="shareModalVisible"
      :title="t('admin.shareInviteTitle')"
      width="520px"
      destroy-on-close
    >
      <div class="whitespace-pre-wrap rounded bg-gray-100 p-4 text-sm text-gray-800">
        {{ shareMessageText() }}
      </div>
      <template #footer>
        <el-button @click="shareModalVisible = false">{{ t('common.close') }}</el-button>
        <el-button type="primary" @click="copyShareMessage">
          <el-icon class="mr-1"><DocumentCopy /></el-icon>
          {{ t('admin.copyShareMessage') }}
        </el-button>
      </template>
    </el-dialog>

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="org"
      :org-name="trendOrg?.name"
      :org-id="trendOrg?.id"
      :org-invitation-code="trendOrg?.invitation_code"
      :org-display-name="trendOrg?.display_name"
      @refresh="loadSchools"
    />

    <el-dialog
      v-model="createModalVisible"
      :title="t('admin.createSchool')"
      width="440px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item :label="t('admin.schoolName')" required>
          <el-input
            v-model="createForm.name"
            placeholder="Beijing High School"
          />
        </el-form-item>
        <el-form-item :label="t('admin.invitationCode')" required>
          <el-input
            v-model="createForm.code"
            placeholder="BJSCHOOL"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createModalVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          @click="createSchool"
        >
          {{ t('admin.createSchool') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
