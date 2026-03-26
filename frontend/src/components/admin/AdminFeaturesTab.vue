<script setup lang="ts">
/**
 * Admin — toggle FEATURE_* flags (writes .env + runtime reload) and DB access rules.
 */
import { computed, onMounted, ref } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { useLanguage, useNotifications } from '@/composables'
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const notify = useNotifications()
const queryClient = useQueryClient()
const featureFlagsStore = useFeatureFlagsStore()

interface FeatureFlagsPayload {
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
    apiKey: 'feature_library',
    envKey: 'FEATURE_LIBRARY',
    labelKey: 'admin.feature.library',
    hintKey: 'admin.feature.libraryHint',
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
]

interface OrgOption {
  id: number
  name: string
  display_name?: string | null
}

const loading = ref(true)
const saving = ref(false)
const savingPermissions = ref(false)
const draft = ref<Partial<Record<ApiKey, boolean>>>({})
const accessDraft = ref<Record<ApiKey, FeatureOrgAccessEntry>>({} as Record<ApiKey, FeatureOrgAccessEntry>)
const orgOptions = ref<OrgOption[]>([])

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
  const res = await apiRequest('/api/auth/admin/feature-org-access', {
    method: 'PUT',
    body: JSON.stringify(buildAccessBody()),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    notify.error(formatHttpErrorDetail(err) || t('admin.featurePermissionsSaveFailed'))
    return false
  }
  featureFlagsStore.markStale()
  await queryClient.invalidateQueries({ queryKey: ['featureFlags'] })
  return true
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

async function load(): Promise<void> {
  loading.value = true
  try {
    const [featuresRes, orgsRes] = await Promise.all([
      apiRequest('/api/config/features'),
      apiRequest('/api/auth/admin/organizations'),
    ])
    if (!featuresRes.ok) {
      notify.error(t('admin.featureLoadFailed'))
      return
    }
    const data = (await featuresRes.json()) as FeatureFlagsPayload
    initDraft(data)
    initAccessDraft(data.feature_org_access)
    if (orgsRes.ok) {
      const list = (await orgsRes.json()) as unknown
      orgOptions.value = Array.isArray(list) ? (list as OrgOption[]) : []
    } else {
      orgOptions.value = []
    }
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const payload: Record<string, string> = {}
    for (const row of ROWS) {
      const v = draft.value[row.apiKey]
      payload[row.envKey] = v ? 'True' : 'False'
    }
    const putRes = await apiRequest('/api/auth/admin/env/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    if (!putRes.ok) {
      const err = await putRes.json().catch(() => ({}))
      const parsed = formatHttpErrorDetail(err)
      notify.error(parsed || t('admin.featureSaveFailed'))
      return
    }
    const reloadRes = await apiRequest('/api/auth/admin/env/reload-runtime', { method: 'POST' })
    if (!reloadRes.ok) {
      notify.error(t('admin.featuresReloadFailed'))
      return
    }
    const accessOk = await persistFeatureAccess()
    if (!accessOk) {
      return
    }
    notify.success(t('admin.featuresSaved'))
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="admin-features-tab max-w-3xl">
    <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
      {{ t('admin.featuresIntro') }}
    </p>
    <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
      {{ t('admin.featuresIntroAccess') }}
    </p>

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
        class="flex flex-col gap-2 py-3 border-b border-gray-200 dark:border-gray-700"
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
              :disabled="saving"
              @click="openPermissionDialog(row.apiKey)"
            >
              {{ t('admin.featurePermissionsButton') }}
            </el-button>
            <el-switch
              v-model="draft[row.apiKey]"
              :disabled="saving"
            />
          </div>
        </div>
      </div>

      <div class="pt-4">
        <el-button
          type="primary"
          :loading="saving"
          @click="save"
        >
          {{ t('admin.featuresSave') }}
        </el-button>
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
          <el-switch v-model="accessDraft[permissionDialogKey].restrict" />
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
