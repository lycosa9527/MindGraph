<script setup lang="ts">
/**
 * Admin — MindBot: per-organization DingTalk HTTP robot + Dify.
 */
import { computed, onMounted, ref } from 'vue'

import AdminMindBotConfigDialog from '@/components/admin/AdminMindBotConfigDialog.vue'
import type {
  MindbotConfigRow,
  OrgOption,
} from '@/components/admin/mindbotConfigTypes'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import {
  MINDBOT_BOT_CAP,
  useAdminMindBotConfig,
} from '@/composables/admin/useAdminMindBotConfig'
import { useLanguage, useNotifications } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAdminOrganizations, useMoveAdminMindbotConfig } from '@/composables/queries'
import { useAuthStore } from '@/stores/auth'
import { maskSensitiveDisplay } from '@/utils/sensitiveMask'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { featureMindbot } = useFeatureFlags()
const { on: onAdminEvent } = useAdminEventBus('AdminMindBotTab')

const mindbot = useAdminMindBotConfig()
const {
  loading,
  saving,
  rotating,
  configs,
  dialogMode,
  formOrgId,
  editingConfigId,
  dingtalkSecretReplaceMode,
  difyApiKeyReplaceMode,
  form,
  editingRow,
  canLoadUsage,
  buildCallbackUrlByToken,
  resetForm,
  fillForm,
  loadConfigs,
  saveConfig,
  rotateCallbackUrl,
  deleteConfig,
  copyUrl,
  startReplaceDingtalkSecret,
  startReplaceDifyApiKey,
} = mindbot

const moveConfigMutation = useMoveAdminMindbotConfig()
const orgsQuery = useAdminOrganizations({
  enabled: computed(() => authStore.isAdmin),
})

const BOT_CAP = MINDBOT_BOT_CAP
const schools = computed(() => (orgsQuery.data.value ?? []) as OrgOption[])

const isAdmin = computed(() => authStore.isAdmin)
const isManager = computed(() => authStore.isManager)
const managerOrgId = computed(() => {
  const raw = authStore.user?.schoolId
  if (raw == null || raw === '') {
    return NaN
  }
  const n = Number(raw)
  return Number.isFinite(n) ? n : NaN
})

const dialogVisible = ref(false)
const moveDialogVisible = ref(false)
const moveSourceRow = ref<MindbotConfigRow | null>(null)
const moveTargetOrgId = ref<number | null>(null)
const moveSubmitting = ref(false)

function orgLabel(org: OrgOption): string {
  const display = org.display_name?.trim()
  if (display) {
    return display
  }
  return org.name
}

function orgNameById(organizationId: number): string {
  const o = schools.value.find((x) => x.id === organizationId)
  return o ? orgLabel(o) : String(organizationId)
}

/** Organizations that can receive this bot (under per-school cap, excluding source). */
function getValidMoveTargets(sourceOrgId: number): OrgOption[] {
  const counts = new Map<number, number>()
  for (const c of configs.value) {
    counts.set(c.organization_id, (counts.get(c.organization_id) ?? 0) + 1)
  }
  return schools.value.filter((o) => {
    if (o.id === sourceOrgId) {
      return false
    }
    return (counts.get(o.id) ?? 0) < BOT_CAP
  })
}

function canMoveBot(row: MindbotConfigRow): boolean {
  return getValidMoveTargets(row.organization_id).length > 0
}

const moveTargetOptions = computed(() => {
  const r = moveSourceRow.value
  if (r == null) {
    return []
  }
  return getValidMoveTargets(r.organization_id)
})

function openMoveDialog(row: MindbotConfigRow): void {
  moveSourceRow.value = row
  const opts = getValidMoveTargets(row.organization_id)
  moveTargetOrgId.value = opts[0]?.id ?? null
  moveDialogVisible.value = true
}

function onMoveDialogClosed(): void {
  moveSourceRow.value = null
  moveTargetOrgId.value = null
}

async function confirmMoveBot(): Promise<void> {
  const row = moveSourceRow.value
  const oid = moveTargetOrgId.value
  if (row == null || oid == null) {
    notify.error(t('admin.mindbot.moveError'))
    return
  }
  moveSubmitting.value = true
  try {
    await moveConfigMutation.mutateAsync({
      configId: row.id,
      body: { organization_id: oid },
    })
    notify.success(t('admin.mindbot.moveSuccess'))
    moveDialogVisible.value = false
    await loadConfigs(true)
  } catch {
    notify.error(t('admin.mindbot.moveError'))
  } finally {
    moveSubmitting.value = false
  }
}

/** Schools that have not yet reached the per-school bot cap. */
const orgsUnderLimit = computed(() => {
  const counts = new Map<number, number>()
  for (const c of configs.value) {
    counts.set(c.organization_id, (counts.get(c.organization_id) ?? 0) + 1)
  }
  return schools.value.filter((o) => (counts.get(o.id) ?? 0) < BOT_CAP)
})

const managerSchoolDisplayName = computed(() => {
  const fromProfile = authStore.user?.schoolName?.trim()
  if (fromProfile) {
    return fromProfile
  }
  if (Number.isFinite(managerOrgId.value)) {
    return orgNameById(managerOrgId.value)
  }
  return '—'
})

/** School name for the MindBot dialog header (钉钉机器人【name】). */
const mindbotDialogSchoolDisplayName = computed(() => {
  const oid = formOrgId.value
  if (oid == null) {
    return ''
  }
  const match = schools.value.find((x) => x.id === oid)
  if (match) {
    return orgLabel(match)
  }
  if (!isAdmin.value) {
    const m = managerSchoolDisplayName.value.trim()
    if (m && m !== '—') {
      return m
    }
  }
  return String(oid)
})

function openCreate(): void {
  dialogMode.value = 'create'
  resetForm()
  if (orgsUnderLimit.value.length) {
    formOrgId.value = orgsUnderLimit.value[0].id
  }
  dialogVisible.value = true
}

function openEdit(row: MindbotConfigRow): void {
  dialogMode.value = 'edit'
  fillForm(row)
  dialogVisible.value = true
}

function openManagerMindbotDialog(): void {
  if (!Number.isFinite(managerOrgId.value)) {
    return
  }
  const row = configs.value.find((c) => c.organization_id === managerOrgId.value)
  if (row) {
    dialogMode.value = 'edit'
    fillForm(row)
  } else {
    dialogMode.value = 'create'
    resetForm()
    formOrgId.value = managerOrgId.value
  }
  dialogVisible.value = true
}

async function save(): Promise<void> {
  await saveConfig()
}

async function removeRow(row: MindbotConfigRow): Promise<void> {
  await deleteConfig(row)
}

onMounted(() => {
  void loadConfigs(true)
})

onAdminEvent('admin:refresh_requested', ({ domain }) => {
  if (domain === 'mindbot' || domain === 'all') {
    void loadConfigs(true)
  }
})

const isAddBotDisabled = computed(() => loading.value || orgsUnderLimit.value.length === 0)

defineExpose({
  openCreate,
  openManagerMindbot: openManagerMindbotDialog,
  isAddSchoolDisabled: isAddBotDisabled,
})
</script>

<template>
  <div
    v-if="!featureMindbot"
    class="text-sm text-gray-600 dark:text-gray-400"
  >
    {{ t('admin.feature.mindbotHint') }}
  </div>
  <div
    v-else
    v-loading="loading"
    class="admin-mindbot-tab pt-4 max-w-4xl"
  >
    <template v-if="isAdmin">
      <el-card
        shadow="never"
        class="border border-gray-200 dark:border-gray-700"
      >
        <template #header>
          <div class="min-w-0 space-y-1">
            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
              {{ t('admin.mindbot.title') }}
            </span>
            <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-normal">
              {{ t('admin.mindbot.introHttpOnly') }}
            </p>
          </div>
        </template>

        <div
          v-if="!loading && configs.length === 0"
          class="rounded-md border border-dashed border-gray-200 dark:border-gray-600 py-14 px-4 text-center"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ t('admin.mindbot.emptyState') }}
          </p>
        </div>
        <el-table
          v-else-if="configs.length > 0"
          :data="configs"
          stripe
          size="small"
          class="w-full"
        >
          <el-table-column
            prop="organization_id"
            :label="t('admin.mindbot.colOrg')"
            min-width="140"
          >
            <template #default="{ row }">
              <span class="text-gray-900 dark:text-gray-100">{{
                orgNameById(row.organization_id)
              }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="bot_label"
            :label="t('admin.mindbot.colBotLabel')"
            min-width="120"
          >
            <template #default="{ row }">
              <span class="text-gray-700 dark:text-gray-300">{{ row.bot_label || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="dingtalk_robot_code"
            :label="t('admin.mindbot.colRobot')"
            min-width="130"
          >
            <template #default="{ row }">
              <code class="text-xs font-mono text-gray-800 dark:text-gray-200">{{
                maskSensitiveDisplay(row.dingtalk_robot_code)
              }}</code>
            </template>
          </el-table-column>
          <el-table-column
            prop="is_enabled"
            :label="t('admin.mindbot.colEnabled')"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.is_enabled ? 'success' : 'info'"
                size="small"
                effect="plain"
              >
                {{ row.is_enabled ? t('admin.enabled') : t('admin.disabled') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.library.colActions')"
            width="300"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="flex flex-wrap items-center gap-2">
                <el-button
                  type="primary"
                  size="small"
                  plain
                  class="mindbot-pill mindbot-pill--table-edit"
                  @click="openEdit(row)"
                >
                  {{ t('admin.mindbot.edit') }}
                </el-button>
                <el-tooltip
                  :disabled="canMoveBot(row)"
                  :content="t('admin.mindbot.moveNoTargets')"
                  placement="top"
                >
                  <span class="inline-block">
                    <el-button
                      type="warning"
                      size="small"
                      plain
                      class="mindbot-pill mindbot-pill--table-move"
                      :disabled="!canMoveBot(row)"
                      @click="openMoveDialog(row)"
                    >
                      {{ t('admin.mindbot.move') }}
                    </el-button>
                  </span>
                </el-tooltip>
                <el-button
                  type="danger"
                  size="small"
                  plain
                  class="mindbot-pill mindbot-pill--table-delete"
                  @click="removeRow(row)"
                >
                  {{ t('admin.mindbot.delete') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <template v-else-if="isManager">
      <el-card
        shadow="never"
        class="border border-gray-200 dark:border-gray-700"
      >
        <template #header>
          <div class="min-w-0 space-y-1">
            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
              {{ t('admin.mindbot.title') }}
            </span>
            <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-normal">
              {{ t('admin.mindbot.managerReadOnlyIntro') }}
            </p>
          </div>
        </template>
        <el-alert
          v-if="!Number.isFinite(managerOrgId)"
          type="warning"
          :closable="false"
          :title="t('admin.mindbot.managerNoOrg')"
          class="!items-start"
        />
        <template v-else>
          <div
            v-if="!loading && configs.length === 0"
            class="rounded-md border border-dashed border-gray-200 dark:border-gray-600 py-14 px-4 text-center"
          >
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('admin.mindbot.managerNoConfig') }}
            </p>
          </div>
          <el-table
            v-else-if="configs.length > 0"
            :data="configs"
            stripe
            size="small"
            class="w-full"
          >
            <el-table-column
              prop="bot_label"
              :label="t('admin.mindbot.colBotLabel')"
              min-width="120"
            >
              <template #default="{ row }">
                <span class="text-gray-700 dark:text-gray-300">{{ row.bot_label || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column
              prop="dingtalk_robot_code"
              :label="t('admin.mindbot.colRobot')"
              min-width="130"
            >
              <template #default="{ row }">
                <code class="text-xs font-mono text-gray-800 dark:text-gray-200">{{
                  maskSensitiveDisplay(row.dingtalk_robot_code)
                }}</code>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.mindbot.schoolCallbackUrl')"
              min-width="260"
            >
              <template #default="{ row }">
                <div class="flex items-center gap-2 min-w-0">
                  <code class="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                    {{ buildCallbackUrlByToken(row.public_callback_token) }}
                  </code>
                  <el-button
                    size="small"
                    plain
                    class="mindbot-pill shrink-0"
                    @click="copyUrl(buildCallbackUrlByToken(row.public_callback_token))"
                  >
                    {{ t('admin.mindbot.copyUrl') }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              prop="is_enabled"
              :label="t('admin.mindbot.colEnabled')"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.is_enabled ? 'success' : 'info'"
                  size="small"
                  effect="plain"
                >
                  {{ row.is_enabled ? t('admin.enabled') : t('admin.disabled') }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </el-card>
    </template>

    <el-dialog
      v-model="moveDialogVisible"
      class="mindbot-settings-dialog mindbot-swiss-dialog mindbot-move-dialog"
      width="min(480px, 94vw)"
      destroy-on-close
      append-to-body
      align-center
      modal-class="mindbot-swiss-backdrop"
      :show-close="true"
      @closed="onMoveDialogClosed"
    >
      <template #header>
        <div class="mindbot-swiss-header mindbot-config-header">
          <span class="mindbot-swiss-header__glyph">◇</span>
          <span class="mindbot-swiss-header__title">{{ t('admin.mindbot.move') }}</span>
          <span
            class="mindbot-swiss-header__divider"
            aria-hidden="true"
            >·</span
          >
          <span class="mindbot-swiss-header__note">{{ t('admin.mindbot.moveTitle') }}</span>
        </div>
      </template>
      <div class="mindbot-config-body">
        <div
          class="mindbot-config-scanlines"
          aria-hidden="true"
        />
        <div class="mindbot-swiss-form-wrap">
          <p class="mindbot-swiss-hint text-xs mb-4 leading-relaxed">
            {{ t('admin.mindbot.moveIntro') }}
          </p>
          <div class="flex flex-col gap-2">
            <span
              class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--mindbot-swiss-muted)]"
              >{{ t('admin.mindbot.moveTarget') }}</span
            >
            <el-select
              v-model="moveTargetOrgId"
              class="mindbot-swiss-select w-full"
              filterable
              :placeholder="t('admin.mindbot.orgSelect')"
            >
              <el-option
                v-for="o in moveTargetOptions"
                :key="o.id"
                :label="orgLabel(o)"
                :value="o.id"
              />
            </el-select>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="mindbot-dialog-footer flex w-full justify-end gap-2">
          <el-button
            class="mindbot-pill mindbot-pill--footer-cancel"
            @click="moveDialogVisible = false"
          >
            {{ t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            class="mindbot-pill mindbot-pill--footer-save"
            :loading="moveSubmitting"
            :disabled="moveTargetOrgId == null || moveTargetOptions.length === 0"
            @click="confirmMoveBot"
          >
            {{ t('admin.mindbot.move') }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <AdminMindBotConfigDialog
      v-if="isAdmin"
      v-model="dialogVisible"
      v-model:form="form"
      v-model:form-org-id="formOrgId"
      :mode="dialogMode"
      :editing-org-row="editingRow"
      :orgs-without-config="orgsUnderLimit"
      :is-admin="isAdmin"
      :feature-mindbot="featureMindbot"
      :saving="saving"
      :rotating="rotating"
      :dingtalk-secret-replace-mode="dingtalkSecretReplaceMode"
      :dify-api-key-replace-mode="difyApiKeyReplaceMode"
      :manager-school-display-name="managerSchoolDisplayName"
      :school-display-name="mindbotDialogSchoolDisplayName"
      :can-load-usage="canLoadUsage"
      :build-callback-url="buildCallbackUrlByToken"
      @save="save"
      @closed="resetForm"
      @rotate-callback="rotateCallbackUrl"
      @copy-url="copyUrl"
      @replace-dingtalk-secret="startReplaceDingtalkSecret"
      @replace-dify-api-key="startReplaceDifyApiKey"
    />
  </div>
</template>

<style scoped>
.mindbot-pill.el-button {
  border-radius: 9999px;
  font-weight: 500;
  padding-left: 1rem;
  padding-right: 1rem;
}

.mindbot-pill--header.el-button--primary {
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.06);
  --el-button-bg-color: rgb(241 245 249);
  --el-button-border-color: rgb(226 232 240);
  --el-button-text-color: rgb(71 85 105);
  --el-button-hover-bg-color: rgb(226 232 240);
  --el-button-hover-border-color: rgb(203 213 225);
  --el-button-hover-text-color: rgb(51 65 85);
}

html.dark .mindbot-pill--header.el-button--primary {
  --el-button-bg-color: rgb(51 65 85 / 0.55);
  --el-button-border-color: rgb(71 85 105 / 0.7);
  --el-button-text-color: rgb(226 232 240);
  --el-button-hover-bg-color: rgb(71 85 105 / 0.65);
  --el-button-hover-border-color: rgb(100 116 139 / 0.5);
  --el-button-hover-text-color: rgb(248 250 252);
}

.mindbot-pill--table-edit.el-button--primary.is-plain {
  --el-button-bg-color: rgb(248 250 252);
  --el-button-border-color: rgb(226 232 240);
  --el-button-text-color: rgb(100 116 139);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-edit.el-button--primary.is-plain {
  --el-button-bg-color: rgb(30 41 59 / 0.35);
  --el-button-border-color: rgb(51 65 85 / 0.5);
  --el-button-text-color: rgb(203 213 225);
}

.mindbot-pill--table-move.el-button--warning.is-plain {
  --el-button-bg-color: rgb(255 251 235);
  --el-button-border-color: rgb(254 240 199);
  --el-button-text-color: rgb(180 83 9);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-move.el-button--warning.is-plain {
  --el-button-bg-color: rgb(66 32 6 / 0.35);
  --el-button-border-color: rgb(180 83 9 / 0.35);
  --el-button-text-color: rgb(253 230 138);
}

.mindbot-pill--table-delete.el-button--danger.is-plain {
  --el-button-bg-color: rgb(255 251 251);
  --el-button-border-color: rgb(254 228 228);
  --el-button-text-color: rgb(185 100 100);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-delete.el-button--danger.is-plain {
  --el-button-bg-color: rgb(69 10 10 / 0.28);
  --el-button-border-color: rgb(127 29 29 / 0.35);
  --el-button-text-color: rgb(254 202 202 / 0.9);
}
</style>
