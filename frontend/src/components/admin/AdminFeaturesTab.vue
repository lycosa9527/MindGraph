<script setup lang="ts">
/**
 * Admin — toggle FEATURE_* flags (writes .env + runtime reload) and DB access rules.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage, useNotifications } from '@/composables'
import {
  useAdminConfigFeatures,
  useAdminOrganizations,
  useReloadAdminEnvRuntime,
  useUpdateAdminEnvSettings,
  useUpdateAdminFeatureOrgAccess,
  type AdminFeatureFlagsPayload,
} from '@/composables/queries'
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'
import { useAdminPanelStore } from '@/stores'
import { useFeatureFlagsStore } from '@/stores/featureFlags'

const { t } = useLanguage()
const notify = useNotifications()
const queryClient = useQueryClient()
const featureFlagsStore = useFeatureFlagsStore()
const adminPanel = useAdminPanelStore()
const { on: onAdminEvent } = useAdminEventBus('AdminFeaturesTab')

const configFeaturesQuery = useAdminConfigFeatures()
const organizationsQuery = useAdminOrganizations()
const updateFeatureAccessMutation = useUpdateAdminFeatureOrgAccess()
const updateEnvSettingsMutation = useUpdateAdminEnvSettings()
const reloadEnvRuntimeMutation = useReloadAdminEnvRuntime()

interface FeatureFlagsPayload extends AdminFeatureFlagsPayload {
  feature_rag_chunk_test: boolean
  feature_course: boolean
  feature_template: boolean
  feature_community: boolean
  feature_askonce: boolean
  feature_school_zone: boolean
  feature_debateverse: boolean
  feature_knowledge_space: boolean
  feature_library: boolean
  feature_gewe: boolean
  feature_smart_response: boolean
  feature_teacher_usage: boolean
  feature_workshop_chat: boolean
  feature_mindmate_collab: boolean
  feature_markets: boolean
  feature_mindbot: boolean
  feature_mindmate_export: boolean
  feature_kitty_agent: boolean
  feature_org_access?: Record<string, FeatureOrgAccessEntry>
}

type ApiKey = keyof Omit<FeatureFlagsPayload, 'feature_org_access'>

type RowDef = {
  apiKey: ApiKey
  envKey: string
  labelKey: string
  hintKey: string
}

const ROWS: RowDef[] = [
  {
    apiKey: 'feature_workshop_chat',
    envKey: 'FEATURE_WORKSHOP_CHAT',
    labelKey: 'admin.feature.workshopChat',
    hintKey: 'admin.feature.workshopChatHint',
  },
  {
    apiKey: 'feature_mindmate_collab',
    envKey: 'FEATURE_MINDMATE_COLLAB',
    labelKey: 'admin.feature.mindmateCollab',
    hintKey: 'admin.feature.mindmateCollabHint',
  },
  {
    apiKey: 'feature_library',
    envKey: 'FEATURE_LIBRARY',
    labelKey: 'admin.feature.library',
    hintKey: 'admin.feature.libraryHint',
  },
  {
    apiKey: 'feature_markets',
    envKey: 'FEATURE_MARKETS',
    labelKey: 'admin.feature.markets',
    hintKey: 'admin.feature.marketsHint',
  },
  {
    apiKey: 'feature_mindbot',
    envKey: 'FEATURE_MINDBOT',
    labelKey: 'admin.feature.mindbot',
    hintKey: 'admin.feature.mindbotHint',
  },
  {
    apiKey: 'feature_mindmate_export',
    envKey: 'FEATURE_MINDMATE_EXPORT',
    labelKey: 'admin.feature.mindmateExport',
    hintKey: 'admin.feature.mindmateExportHint',
  },
  {
    apiKey: 'feature_community',
    envKey: 'FEATURE_COMMUNITY',
    labelKey: 'admin.feature.community',
    hintKey: 'admin.feature.communityHint',
  },
  {
    apiKey: 'feature_knowledge_space',
    envKey: 'FEATURE_KNOWLEDGE_SPACE',
    labelKey: 'admin.feature.knowledgeSpace',
    hintKey: 'admin.feature.knowledgeSpaceHint',
  },
  {
    apiKey: 'feature_rag_chunk_test',
    envKey: 'FEATURE_RAG_CHUNK_TEST',
    labelKey: 'admin.feature.ragChunkTest',
    hintKey: 'admin.feature.ragChunkTestHint',
  },
  {
    apiKey: 'feature_gewe',
    envKey: 'FEATURE_GEWE',
    labelKey: 'admin.feature.gewe',
    hintKey: 'admin.feature.geweHint',
  },
  {
    apiKey: 'feature_debateverse',
    envKey: 'FEATURE_DEBATEVERSE',
    labelKey: 'admin.feature.debateverse',
    hintKey: 'admin.feature.debateverseHint',
  },
  {
    apiKey: 'feature_askonce',
    envKey: 'FEATURE_ASKONCE',
    labelKey: 'admin.feature.askonce',
    hintKey: 'admin.feature.askonceHint',
  },
  {
    apiKey: 'feature_school_zone',
    envKey: 'FEATURE_SCHOOL_ZONE',
    labelKey: 'admin.feature.schoolZone',
    hintKey: 'admin.feature.schoolZoneHint',
  },
  {
    apiKey: 'feature_course',
    envKey: 'FEATURE_COURSE',
    labelKey: 'admin.feature.course',
    hintKey: 'admin.feature.courseHint',
  },
  {
    apiKey: 'feature_template',
    envKey: 'FEATURE_TEMPLATE',
    labelKey: 'admin.feature.template',
    hintKey: 'admin.feature.templateHint',
  },
  {
    apiKey: 'feature_smart_response',
    envKey: 'FEATURE_SMART_RESPONSE',
    labelKey: 'admin.feature.smartResponse',
    hintKey: 'admin.feature.smartResponseHint',
  },
  {
    apiKey: 'feature_teacher_usage',
    envKey: 'FEATURE_TEACHER_USAGE',
    labelKey: 'admin.feature.teacherUsage',
    hintKey: 'admin.feature.teacherUsageHint',
  },
  {
    apiKey: 'feature_kitty_agent',
    envKey: 'FEATURE_KITTY_AGENT',
    labelKey: 'admin.feature.kittyAgent',
    hintKey: 'admin.feature.kittyAgentHint',
  },
]

interface OrgOption {
  id: number
  name: string
  display_name?: string | null
}

const loading = computed(
  () => configFeaturesQuery.isFetching.value || organizationsQuery.isFetching.value
)
const saving = ref(false)
const savingPermissions = ref(false)
const draft = ref<Partial<Record<ApiKey, boolean>>>({})
const accessDraft = ref<Record<ApiKey, FeatureOrgAccessEntry>>(
  {} as Record<ApiKey, FeatureOrgAccessEntry>
)
const orgOptions = computed(() => {
  const list = organizationsQuery.data.value
  return Array.isArray(list) ? (list as OrgOption[]) : []
})

const dialogVisible = ref(false)
const permissionDialogKey = ref<ApiKey | null>(null)
const userIdsText = ref('')

const dialogTitleKey = computed(() => {
  const key = permissionDialogKey.value
  if (!key) {
    return ''
  }
  return ROWS.find((r) => r.apiKey === key)?.labelKey ?? ''
})

function orgLabel(org: OrgOption): string {
  const display = org.display_name?.trim()
  if (display) {
    return display
  }
  return org.name
}

function formatHttpErrorDetail(err: unknown): string {
  if (!err || typeof err !== 'object' || !('detail' in err)) {
    return ''
  }
  const detail = (err as { detail: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join('; ')
  }
  return String(detail)
}

function initAccessDraft(raw: Record<string, FeatureOrgAccessEntry> | undefined): void {
  const next = {} as Record<ApiKey, FeatureOrgAccessEntry>
  for (const row of ROWS) {
    const r = raw?.[row.apiKey]
    next[row.apiKey] = {
      restrict: Boolean(r?.restrict),
      organization_ids: r?.organization_ids ? [...r.organization_ids] : [],
      user_ids: r?.user_ids ? [...r.user_ids] : [],
    }
  }
  accessDraft.value = next
}

function initDraft(data: FeatureFlagsPayload): void {
  const next: Partial<Record<ApiKey, boolean>> = {}
  for (const row of ROWS) {
    next[row.apiKey] = Boolean(data[row.apiKey])
  }
  draft.value = next
}

function parseUserIds(raw: string): number[] {
  const seen = new Set<number>()
  const out: number[] = []
  for (const part of raw.split(/[,，\s]+/)) {
    const s = part.trim()
    if (!s) {
      continue
    }
    const n = Number(s)
    if (!Number.isFinite(n) || n <= 0 || !Number.isInteger(n)) {
      continue
    }
    if (seen.has(n)) {
      continue
    }
    seen.add(n)
    out.push(n)
  }
  return out
}

function buildAccessBody(): Record<string, FeatureOrgAccessEntry> {
  const out: Record<string, FeatureOrgAccessEntry> = {}
  for (const row of ROWS) {
    const e = accessDraft.value[row.apiKey]
    out[row.apiKey] = {
      restrict: e.restrict,
      organization_ids: [...e.organization_ids],
      user_ids: [...e.user_ids],
    }
  }
  return out
}

async function persistFeatureAccess(): Promise<boolean> {
  try {
    await updateFeatureAccessMutation.mutateAsync(buildAccessBody())
    featureFlagsStore.markStale()
    await queryClient.invalidateQueries({ queryKey: ['featureFlags'] })
    return true
  } catch (err) {
    notify.error(formatHttpErrorDetail(err) || t('admin.featurePermissionsSaveFailed'))
    return false
  }
}

function openPermissionDialog(key: ApiKey): void {
  permissionDialogKey.value = key
  const entry = accessDraft.value[key]
  userIdsText.value = entry.user_ids.length ? entry.user_ids.join(', ') : ''
  dialogVisible.value = true
}

function closePermissionDialog(): void {
  dialogVisible.value = false
  permissionDialogKey.value = null
}

function onPermissionDialogClosed(): void {
  permissionDialogKey.value = null
}

async function applyPermissionDialog(): Promise<void> {
  const key = permissionDialogKey.value
  if (!key) {
    return
  }
  accessDraft.value[key].user_ids = parseUserIds(userIdsText.value)
  savingPermissions.value = true
  try {
    const ok = await persistFeatureAccess()
    if (ok) {
      notify.success(t('admin.featurePermissionsApplied'))
      closePermissionDialog()
    }
  } finally {
    savingPermissions.value = false
  }
}

function isRestricted(key: ApiKey): boolean {
  return Boolean(accessDraft.value[key]?.restrict)
}

function applyFeaturesPayload(data: FeatureFlagsPayload): void {
  initDraft(data)
  initAccessDraft(data.feature_org_access)
}

async function load(): Promise<void> {
  try {
    const [featuresResult, orgsResult] = await Promise.all([
      configFeaturesQuery.refetch(),
      organizationsQuery.refetch(),
    ])
    if (featuresResult.error) {
      notify.error(t('admin.featureLoadFailed'))
      return
    }
    if (featuresResult.data) {
      applyFeaturesPayload(featuresResult.data as FeatureFlagsPayload)
    }
    if (orgsResult.error) {
      notify.error(t('admin.featureLoadFailed'))
    }
  } catch {
    notify.error(t('admin.featureLoadFailed'))
  }
}

watch(
  () => configFeaturesQuery.data.value,
  (data) => {
    if (data) {
      applyFeaturesPayload(data as FeatureFlagsPayload)
    }
  },
  { immediate: true }
)

async function save(): Promise<void> {
  saving.value = true
  try {
    const payload: Record<string, string> = {}
    for (const row of ROWS) {
      const v = draft.value[row.apiKey]
      payload[row.envKey] = v ? 'True' : 'False'
    }
    await updateEnvSettingsMutation.mutateAsync(payload)
    await reloadEnvRuntimeMutation.mutateAsync()
    const accessOk = await persistFeatureAccess()
    if (!accessOk) {
      return
    }
    notify.success(t('admin.featuresSaved'))
    await load()
  } catch (err) {
    notify.error(formatHttpErrorDetail(err) || t('admin.featureSaveFailed'))
  } finally {
    saving.value = false
  }
}

onAdminEvent('admin:refresh_requested', ({ domain }) => {
  if (domain === 'features' || domain === 'config-features' || domain === 'all') {
    void load()
  }
})

watch(saving, (value) => {
  adminPanel.patchFeaturesToolbar({ saving: value })
})

onAdminEvent('admin:toolbar_action', (payload) => {
  if (payload.tab === 'settings' && payload.action === 'features_save') {
    void save()
  }
})

onMounted(() => {
  adminPanel.setFeaturesToolbar({ saving: saving.value })
  void load()
})

onUnmounted(() => {
  adminPanel.clearFeaturesToolbar()
})
</script>

<template>
  <div class="admin-features-tab max-w-3xl">
    <div
      v-if="loading"
      class="py-12 text-center text-gray-500"
    >
      {{ t('common.loading') }}
    </div>

    <div
      v-else
      class="space-y-4"
    >
      <div
        v-for="row in ROWS"
        :key="row.apiKey"
        class="flex flex-col gap-2 py-3 border-b border-stone-200 dark:border-stone-700"
      >
        <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
                {{ t(row.labelKey) }}
              </span>
              <el-tag
                v-if="isRestricted(row.apiKey)"
                size="small"
                type="warning"
              >
                {{ t('admin.featurePermissionsRestrictedBadge') }}
              </el-tag>
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {{ t(row.hintKey) }}
            </div>
          </div>
          <div class="flex flex-row items-center gap-2 shrink-0">
            <el-button
              size="small"
              class="admin-swiss-btn admin-swiss-btn--ghost"
              :disabled="saving"
              @click="openPermissionDialog(row.apiKey)"
            >
              {{ t('admin.featurePermissionsButton') }}
            </el-button>
            <el-switch
              v-model="draft[row.apiKey]"
              class="admin-swiss-switch"
              :disabled="saving"
            />
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitleKey ? t(dialogTitleKey) : ''"
      width="min(520px, 92vw)"
      destroy-on-close
      @closed="onPermissionDialogClosed"
    >
      <div
        v-if="permissionDialogKey"
        class="space-y-4"
      >
        <div>
          <div class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
            {{ t('admin.featurePermissionsRestrict') }}
          </div>
          <p class="text-xs text-gray-500 mb-2">
            {{ t('admin.featurePermissionsRestrictHint') }}
          </p>
          <el-switch
            v-model="accessDraft[permissionDialogKey].restrict"
            class="admin-swiss-switch"
          />
        </div>
        <div>
          <div class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
            {{ t('admin.featurePermissionsOrgs') }}
          </div>
          <el-select
            v-model="accessDraft[permissionDialogKey].organization_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            class="w-full"
            :placeholder="t('admin.featurePermissionsOrgsPlaceholder')"
          >
            <el-option
              v-for="o in orgOptions"
              :key="o.id"
              :label="orgLabel(o)"
              :value="o.id"
            />
          </el-select>
        </div>
        <div>
          <div class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
            {{ t('admin.featurePermissionsUserIds') }}
          </div>
          <p class="text-xs text-gray-500 mb-2">
            {{ t('admin.featurePermissionsUserIdsHint') }}
          </p>
          <el-input
            v-model="userIdsText"
            type="textarea"
            :rows="2"
            :placeholder="t('admin.featurePermissionsUserIdsPlaceholder')"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="closePermissionDialog">
          {{ t('admin.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="savingPermissions"
          :disabled="!permissionDialogKey"
          @click="applyPermissionDialog"
        >
          {{ t('admin.featurePermissionsApply') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
