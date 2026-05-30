<script setup lang="ts">
/**
 * One MindBot pane inside the school edit modal (DingTalk, log, monitor tabs).
 */
import { computed, onMounted, ref, watch } from 'vue'

import { Loading, Plus } from '@element-plus/icons-vue'

import AdminMindBotConfigForm from '@/components/admin/AdminMindBotConfigForm.vue'
import {
  clearAdminMindBotOrgSession,
  getAdminMindBotOrgSession,
  MINDBOT_BOT_CAP,
} from '@/composables/admin/useAdminMindBotConfig'
import { useLanguage } from '@/composables'

const props = defineProps<{
  orgId: number
  embeddedPane: 'dingtalk' | 'log' | 'monitor'
  active?: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const { t } = useLanguage()
const session = getAdminMindBotOrgSession(props.orgId)

const MINDBOT_SWISS_SELECT_POPPER = 'mindbot-swiss-select-popper'
const {
  loading,
  saving,
  rotating,
  orgConfigs,
  dialogMode,
  formOrgId,
  editingConfigId,
  editingRow,
  dingtalkSecretReplaceMode,
  difyApiKeyReplaceMode,
  form,
  canLoadUsage,
  buildCallbackUrlByToken,
  beginCreateForOrg,
  beginEditRow,
  loadConfigsForOrg,
  saveConfig,
  rotateCallbackUrl,
  deleteConfig,
  copyUrl,
  startReplaceDingtalkSecret,
  startReplaceDifyApiKey,
} = session

const selectedConfigId = ref<number | null>(null)

const orgBotRows = computed(() => orgConfigs.value)
const canAddBot = computed(() => orgBotRows.value.length < MINDBOT_BOT_CAP)
const showDeleteBot = computed(
  () => dialogMode.value === 'edit' && orgBotRows.value.length > 0
)

function resolveEditingBotRow() {
  if (editingRow.value) {
    return editingRow.value
  }
  const selectedId = selectedConfigId.value
  if (selectedId != null) {
    return orgBotRows.value.find((item) => item.id === selectedId)
  }
  return orgBotRows.value[0]
}
const showToolbar = computed(() => props.embeddedPane === 'dingtalk')
const mindbotUnavailable = computed(() => session.featureDisabled.value)
const sessionReady = computed(() => {
  if (mindbotUnavailable.value) {
    return true
  }
  if (loading.value) {
    return false
  }
  return formOrgId.value === props.orgId
})

const botSelectOptions = computed(() =>
  orgBotRows.value.map((row) => ({
    id: row.id,
    label: row.bot_label?.trim() || row.dingtalk_robot_code || `#${row.id}`,
  }))
)

async function ensureLoaded(): Promise<void> {
  if (sessionReady.value && formOrgId.value === props.orgId) {
    selectedConfigId.value = editingConfigId.value
    return
  }
  await loadConfigsForOrg(props.orgId, selectedConfigId.value)
  selectedConfigId.value = editingConfigId.value
}

function onSelectBot(configId: number): void {
  const row = orgBotRows.value.find((item) => item.id === configId)
  if (!row) {
    return
  }
  selectedConfigId.value = configId
  beginEditRow(row)
}

function onAddBot(): void {
  if (!canAddBot.value) {
    return
  }
  selectedConfigId.value = null
  beginCreateForOrg(props.orgId)
}

async function onDeleteCurrentBot(): Promise<void> {
  const row = resolveEditingBotRow()
  if (!row) {
    return
  }
  const deleted = await deleteConfig(row)
  if (!deleted) {
    return
  }
  emit('refresh')
  selectedConfigId.value = null
  await ensureLoaded()
}

async function saveSettings(): Promise<boolean> {
  const saved = await saveConfig()
  if (saved) {
    selectedConfigId.value = editingConfigId.value
  }
  return saved
}

watch(
  () => props.active,
  (isActive) => {
    if (isActive) {
      void ensureLoaded()
    }
  },
  { immediate: true }
)

watch(
  () => props.orgId,
  () => {
    selectedConfigId.value = null
    if (props.active) {
      void ensureLoaded()
    }
  }
)

onMounted(() => {
  if (props.active) {
    void ensureLoaded()
  }
})

defineExpose({
  saving,
  saveSettings,
  clearSession: () => clearAdminMindBotOrgSession(props.orgId),
})
</script>

<template>
  <div
    v-if="mindbotUnavailable"
    class="text-sm text-gray-600 dark:text-gray-400 py-4"
  >
    {{ t('admin.feature.mindbotHint') }}
  </div>
  <div
    v-else-if="!sessionReady"
    class="flex justify-center py-10"
  >
    <el-icon
      class="is-loading"
      :size="28"
    >
      <Loading />
    </el-icon>
  </div>
  <div
    v-else
    class="school-mindbot-pane space-y-3"
  >
    <div
      v-if="showToolbar"
      class="school-mindbot-toolbar"
    >
      <el-select
        v-if="orgBotRows.length > 0 && dialogMode === 'edit'"
        :model-value="selectedConfigId ?? undefined"
        class="school-mindbot-bot-select mindbot-swiss-select"
        :popper-class="MINDBOT_SWISS_SELECT_POPPER"
        :placeholder="t('admin.schoolModal.mindbotSelectBot')"
        @update:model-value="onSelectBot($event as number)"
      >
        <el-option
          v-for="opt in botSelectOptions"
          :key="opt.id"
          :label="opt.label"
          :value="opt.id"
        >
          <span class="mindbot-swiss-select-option__label">{{ opt.label }}</span>
        </el-option>
      </el-select>
      <el-button
        plain
        type="primary"
        class="school-mindbot-toolbar-btn mindbot-pill mindbot-pill--copy"
        :disabled="!canAddBot"
        @click="onAddBot"
      >
        <el-icon class="mr-0.5"><Plus /></el-icon>
        {{ t('admin.schoolModal.mindbotAddBot') }}
      </el-button>
      <el-button
        v-if="showDeleteBot"
        type="danger"
        plain
        class="school-mindbot-toolbar-btn mindbot-pill mindbot-pill--footer-danger"
        @click="onDeleteCurrentBot"
      >
        {{ t('admin.mindbot.delete') }}
      </el-button>
    </div>
    <p
      v-if="showToolbar && dialogMode === 'create'"
      class="mindbot-config-banner rounded-sm border px-3 py-2 text-xs font-mono leading-snug m-0"
    >
      {{ t('admin.schoolModal.mindbotCreateHint', { cap: MINDBOT_BOT_CAP }) }}
    </p>
    <AdminMindBotConfigForm
      v-model:form="form"
      v-model:form-org-id="formOrgId"
      :mode="dialogMode"
      :editing-org-row="editingRow"
      :feature-mindbot="true"
      :dingtalk-secret-replace-mode="dingtalkSecretReplaceMode"
      :dify-api-key-replace-mode="difyApiKeyReplaceMode"
      :can-load-usage="canLoadUsage"
      :rotating="rotating"
      :build-callback-url="buildCallbackUrlByToken"
      :embedded-pane="embeddedPane"
      hide-org-select
      use-org-dify-credentials
      @rotate-callback="rotateCallbackUrl()"
      @copy-url="copyUrl($event)"
      @replace-dingtalk-secret="startReplaceDingtalkSecret()"
      @replace-dify-api-key="startReplaceDifyApiKey()"
    />
  </div>
</template>

<style scoped>
.school-mindbot-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  max-width: 100%;
}

.school-mindbot-toolbar :deep(.school-mindbot-bot-select.el-select) {
  width: 12rem;
  max-width: min(14rem, 100%);
  flex: 0 0 auto;
}

.school-mindbot-toolbar-btn.el-button {
  flex: 0 0 auto;
}

.mindbot-config-banner {
  border-color: rgba(34, 211, 238, 0.28);
  color: var(--mindbot-swiss-text);
  background: linear-gradient(
    105deg,
    rgba(227, 6, 19, 0.12) 0%,
    rgba(34, 211, 238, 0.08) 55%,
    rgba(167, 139, 250, 0.06) 100%
  );
}
</style>
