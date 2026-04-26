<script setup lang="ts">
/**
 * Admin dialog: list / create / delete integration API keys
 * (X-API-Key for /api/generate_dingtalk and other public API routes).
 */
import { ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { DocumentCopy, Plus } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import '@/styles/admin-mindbot-swiss-api-keys.css'
import '@/styles/admin-mindbot-swiss-dialog-chrome.css'
import '@/styles/admin-mindbot-swiss-messagebox.css'
import { apiRequest } from '@/utils/apiClient'

const modelValue = defineModel<boolean>({ default: false })

const { t } = useLanguage()
const notify = useNotifications()

interface TokenStats {
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

interface AdminApiKeyRow {
  id: number
  key: string
  name: string
  description: string | null
  quota_limit: number | null
  usage_count: number
  is_active: boolean
  created_at: string | null
  last_used_at: string | null
  expires_at: string | null
  token_stats: TokenStats
}

const listLoading = ref(false)
const rows = ref<AdminApiKeyRow[]>([])

const createOpen = ref(false)
const createSubmitting = ref(false)
const createName = ref('')
const createDescription = ref('')
const createQuota = ref<string>('')
const createExpiresDays = ref<string>('')

const newKeyPlaintext = ref<string | null>(null)
const newKeyDialogOpen = ref(false)

function resetCreateForm(): void {
  createName.value = ''
  createDescription.value = ''
  createQuota.value = ''
  createExpiresDays.value = ''
}

async function loadList(): Promise<void> {
  listLoading.value = true
  try {
    const res = await apiRequest('/api/auth/admin/api_keys')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data as { detail?: string }).detail || t('admin.apiKeysLoadError'))
      return
    }
    rows.value = (await res.json()) as AdminApiKeyRow[]
  } catch {
    notify.error(t('admin.apiKeysLoadError'))
  } finally {
    listLoading.value = false
  }
}

watch(modelValue, (v) => {
  if (v) {
    void loadList()
  }
})

function parseOptionalInt(s: string): number | null {
  const trimmed = s.trim()
  if (!trimmed) return null
  const n = parseInt(trimmed, 10)
  return Number.isNaN(n) ? null : n
}

function openCreate(): void {
  resetCreateForm()
  newKeyPlaintext.value = null
  createOpen.value = true
}

async function submitCreate(): Promise<void> {
  const name = createName.value.trim()
  if (!name) {
    notify.error(t('admin.apiKeysNameRequired'))
    return
  }
  createSubmitting.value = true
  try {
    const body: Record<string, unknown> = {
      name,
      description: createDescription.value.trim() || '',
    }
    const q = parseOptionalInt(createQuota.value)
    if (q !== null) body.quota_limit = q
    const d = parseOptionalInt(createExpiresDays.value)
    if (d !== null) body.expires_days = d

    const res = await apiRequest('/api/auth/admin/api_keys', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      notify.error((data as { detail?: string }).detail || t('admin.apiKeysLoadError'))
      return
    }
    newKeyPlaintext.value = (data as { key?: string }).key ?? null
    createOpen.value = false
    resetCreateForm()
    await loadList()
    if (newKeyPlaintext.value) {
      newKeyDialogOpen.value = true
    } else {
      notify.success(t('admin.apiKeysCreateSuccess'))
    }
  } catch {
    notify.error(t('admin.apiKeysLoadError'))
  } finally {
    createSubmitting.value = false
  }
}

async function confirmDelete(row: AdminApiKeyRow): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('admin.apiKeysDeleteConfirm', { name: row.name }),
      t('common.warning'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--delete',
        modalClass: 'mindbot-swiss-backdrop',
        cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
        showClose: true,
      }
    )
  } catch {
    return
  }
  const res = await apiRequest(`/api/auth/admin/api_keys/${row.id}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    notify.error((data as { detail?: string }).detail || t('admin.apiKeysLoadError'))
    return
  }
  await loadList()
  notify.success(t('admin.apiKeysDeleteSuccess'))
}

async function copyToClipboard(value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    notify.success(t('admin.mindbot.copied'))
  } catch {
    notify.error(t('common.error'))
  }
}

function formatKeyPreview(k: string): string {
  if (k.length <= 18) return k
  return `${k.slice(0, 10)}…${k.slice(-6)}`
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString()
}

function onNewKeyDialogClosed(): void {
  newKeyPlaintext.value = null
}

function cancelCreate(): void {
  createOpen.value = false
}
</script>

<template>
  <el-dialog
    v-model="modelValue"
    class="mindbot-settings-dialog mindbot-swiss-dialog api-keys-main-dialog"
    width="min(920px, 92vw)"
    align-center
    destroy-on-close
    append-to-body
    :show-close="true"
    modal-class="mindbot-swiss-backdrop"
  >
    <template #header>
      <div class="mindbot-swiss-header mindbot-config-header">
        <span class="mindbot-swiss-header__glyph">◇</span>
        <span class="mindbot-swiss-header__title">{{ t('admin.dingtalkApiKeysDialogTitle') }}</span>
        <span
          class="mindbot-swiss-header__divider"
          aria-hidden="true"
          >·</span
        >
        <span class="mindbot-swiss-header__note">{{ t('admin.dingtalkApiKeysDialogNote') }}</span>
      </div>
    </template>

    <div class="mindbot-config-body">
      <div
        class="mindbot-config-scanlines"
        aria-hidden="true"
      />
      <div class="mindbot-swiss-form-wrap">
        <div class="api-keys-hint-inset">
          <div class="api-keys-section-kicker">
            {{ t('admin.dingtalkGenerationCard') }}
          </div>
          <p class="mindbot-swiss-hint api-keys-hint-bumper">
            {{ t('admin.dingtalkApiKeysDialogIntro') }}
          </p>
        </div>

        <div class="api-keys-tool-row">
          <span
            class="text-[0.65rem] font-semibold uppercase tracking-[0.1em] text-[var(--mindbot-swiss-muted)]"
            >{{ t('admin.apiKeys') }}</span
          >
          <el-button
            type="primary"
            :icon="Plus"
            class="api-keys-pill"
            @click="openCreate"
          >
            {{ t('admin.createApiKey') }}
          </el-button>
        </div>

        <div
          v-loading="listLoading"
          class="api-keys-data-panel api-keys-floating-load"
        >
          <el-table
            :data="rows"
            class="api-keys-table w-full"
            :empty-text="t('admin.noData')"
            stripe
          >
            <el-table-column
              prop="name"
              :label="t('admin.name')"
              min-width="120"
              show-overflow-tooltip
            />
            <el-table-column
              :label="t('admin.apiKey')"
              min-width="200"
            >
              <template #default="{ row }">
                <div class="api-keys-key-cell flex items-start gap-1 flex-wrap">
                  <code class="api-keys-mono min-w-0 flex-1">{{ formatKeyPreview(row.key) }}</code>
                  <el-button
                    text
                    type="primary"
                    size="small"
                    :icon="DocumentCopy"
                    :aria-label="t('admin.apiKeyCopy')"
                    @click="copyToClipboard(row.key)"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.apiKeysTableStats')"
              width="115"
              align="right"
            >
              <template #default="{ row }">
                {{ formatNumber(row.token_stats?.total_tokens ?? 0) }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.apiKeysRequestCount')"
              width="100"
              align="right"
            >
              <template #default="{ row }">
                {{ (row.usage_count ?? 0).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.apiKeysTableQuota')"
              width="95"
              align="right"
            >
              <template #default="{ row }">
                {{
                  row.quota_limit != null
                    ? (row.quota_limit as number).toLocaleString()
                    : t('admin.apiKeysUnlimited')
                }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.apiKeysStatus')"
              width="100"
              align="center"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.is_active ? 'success' : 'info'"
                  size="small"
                  class="api-keys-tag"
                  effect="dark"
                >
                  {{ row.is_active ? t('admin.enabled') : t('admin.disabled') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              fixed="right"
              :label="t('admin.actions')"
              width="100"
              align="right"
            >
              <template #default="{ row }">
                <div class="api-keys-row-actions">
                  <el-button
                    type="danger"
                    link
                    @click="confirmDelete(row)"
                  >
                    {{ t('admin.delete') }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <!-- Create -->
    <el-dialog
      v-model="createOpen"
      class="mindbot-settings-dialog mindbot-swiss-dialog mindbot-api-key-nested"
      width="min(480px, 94vw)"
      align-center
      append-to-body
      destroy-on-close
      :show-close="true"
      modal-class="mindbot-swiss-backdrop"
      @close="resetCreateForm"
    >
      <template #header>
        <div class="mindbot-swiss-header mindbot-config-header">
          <span class="mindbot-swiss-header__glyph">◇</span>
          <span class="mindbot-swiss-header__title">{{ t('admin.createApiKey') }}</span>
        </div>
      </template>
      <div class="mindbot-config-body">
        <div
          class="mindbot-config-scanlines"
          aria-hidden="true"
        />
        <div class="mindbot-swiss-form-wrap">
          <el-form
            label-position="top"
            class="api-keys-nested-form"
            @submit.prevent="submitCreate"
          >
            <el-form-item
              :label="t('admin.name')"
              required
            >
              <el-input
                v-model="createName"
                clearable
              />
            </el-form-item>
            <el-form-item :label="t('admin.description')">
              <el-input
                v-model="createDescription"
                type="textarea"
                :rows="2"
              />
            </el-form-item>
            <el-form-item :label="t('admin.apiKeysTableQuota')">
              <el-input
                v-model="createQuota"
                :placeholder="t('admin.apiKeysQuotaPlaceholder')"
                clearable
              />
            </el-form-item>
            <el-form-item :label="t('admin.apiKeysExpiresDays')">
              <el-input
                v-model="createExpiresDays"
                :placeholder="t('admin.apiKeysExpiresDaysHint')"
                clearable
              />
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <div class="mindbot-dialog-footer w-full">
          <div class="api-keys-nested-footer">
            <el-button
              class="mindbot-pill mindbot-pill--footer-cancel"
              @click="cancelCreate"
            >
              {{ t('common.cancel') }}
            </el-button>
            <el-button
              type="primary"
              class="mindbot-pill mindbot-pill--footer-save"
              :loading="createSubmitting"
              @click="submitCreate"
            >
              {{ t('admin.createApiKey') }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- New key one-shot -->
    <el-dialog
      v-model="newKeyDialogOpen"
      class="mindbot-settings-dialog mindbot-swiss-dialog mindbot-api-key-nested--wide"
      width="min(520px, 94vw)"
      align-center
      append-to-body
      destroy-on-close
      :show-close="true"
      modal-class="mindbot-swiss-backdrop"
      @closed="onNewKeyDialogClosed"
    >
      <template #header>
        <div class="mindbot-swiss-header mindbot-config-header">
          <span class="mindbot-swiss-header__glyph">◇</span>
          <span class="mindbot-swiss-header__title">{{
            t('admin.apiKeysCreatedSecretTitle')
          }}</span>
        </div>
      </template>
      <div class="mindbot-config-body">
        <div
          class="mindbot-config-scanlines"
          aria-hidden="true"
        />
        <div class="mindbot-swiss-form-wrap">
          <div class="api-keys-hint-inset api-keys-hint-inset--banner">
            <p class="mindbot-swiss-hint text-xs leading-relaxed m-0">
              {{ t('admin.apiKeysCreatedSecretBody') }}
            </p>
          </div>
          <el-input
            v-if="newKeyPlaintext"
            :model-value="newKeyPlaintext"
            type="textarea"
            readonly
            :rows="3"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <div class="mindbot-dialog-footer w-full">
          <div class="api-keys-nested-footer">
            <el-button
              v-if="newKeyPlaintext"
              class="mindbot-pill mindbot-pill--copy"
              :icon="DocumentCopy"
              type="primary"
              plain
              @click="() => newKeyPlaintext && void copyToClipboard(newKeyPlaintext)"
            >
              {{ t('admin.apiKeyCopy') }}
            </el-button>
            <el-button
              type="primary"
              class="mindbot-pill mindbot-pill--footer-save"
              @click="newKeyDialogOpen = false"
            >
              {{ t('common.close') }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </el-dialog>
</template>
