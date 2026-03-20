<script setup lang="ts">
/**
 * 教研组 management: compact list + per-row Edit (advanced channel settings
 * live inside the expanded panel); reorder/duplicate/archive on the row.
 */
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElMessage, ElMessageBox } from 'element-plus'

import { ArrowDown, ArrowUp, Copy, LayoutList, Plus, Settings, Trash2 } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import {
  type ChannelMember,
  type ChatChannel,
  type OrgMember,
  useWorkshopChatStore,
} from '@/stores/workshopChat'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'openChannelSettings', channelId: number): void
}>()

const { t } = useLanguage()
const router = useRouter()
const store = useWorkshopChatStore()
const authStore = useAuthStore()

const canManage = computed(() => authStore.isAdminOrManager)

const teachingGroups = computed(() => {
  const list = store.channels.filter(
    (c) => c.channel_type !== 'announce' && (c.parent_id === null || c.parent_id === undefined)
  )
  return [...list].sort((a, b) => {
    const ao = a.display_order ?? 0
    const bo = b.display_order ?? 0
    if (ao !== bo) {
      return ao - bo
    }
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
})

const membersCache = reactive<Record<number, ChannelMember[]>>({})
const membersLoading = reactive<Record<number, boolean>>({})
const inviteUserId = reactive<Record<number, number | undefined>>({})
/** Only one teaching group expanded for editing at a time. */
const editingGroupId = ref<number | null>(null)

const nameDrafts = reactive<Record<number, string>>({})
const descDrafts = reactive<Record<number, string>>({})

function syncDrafts(): void {
  teachingGroups.value.forEach((g) => {
    nameDrafts[g.id] = g.name
    descDrafts[g.id] = g.description ?? ''
  })
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      syncDrafts()
      editingGroupId.value = null
      void store.fetchOrgMembers({ limit: 200, offset: 0 })
    }
  }
)

watch(
  teachingGroups,
  () => {
    if (props.visible) {
      syncDrafts()
    }
  },
  { deep: true }
)

function visibilityValue(g: ChatChannel): 'public' | 'private' {
  return g.channel_type === 'private' ? 'private' : 'public'
}

async function confirmArchive(group: ChatChannel): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('workshop.archiveTeachingGroupConfirm'),
      t('workshop.archiveTeachingGroup'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  const ok = await store.archiveChannel(group.id)
  if (ok) {
    ElMessage.success(t('workshop.channelArchived'))
  } else {
    ElMessage.error(t('workshop.channelArchiveFailed'))
  }
}

function close(): void {
  emit('update:visible', false)
}

function addGroup(): void {
  store.openCreateChannel()
}

function browseTeachingGroups(): void {
  store.leaveWorkshopHomeView()
  store.showChannelBrowser = true
  store.selectChannel(null)
  store.selectDMPartner(null)
  emit('update:visible', false)
  void router.push('/workshop-chat')
}

function openGroupSettings(groupId: number): void {
  emit('update:visible', false)
  emit('openChannelSettings', groupId)
}

async function onVisibilityChange(channelId: number, value: string): Promise<void> {
  if (value !== 'public' && value !== 'private') {
    return
  }
  const ok = await store.updateChannelPermissions(channelId, {
    channel_type: value,
  })
  if (ok) {
    ElMessage.success(t('common.success'))
  } else {
    ElMessage.error(t('common.error'))
  }
}

async function saveNameAndDescription(channelId: number): Promise<void> {
  const name = nameDrafts[channelId]?.trim()
  if (!name) {
    ElMessage.warning(t('workshop.teachingGroupNameRequired'))
    return
  }
  const desc = descDrafts[channelId]?.trim() ?? ''
  const ok = await store.updateChannelDetails(channelId, {
    name,
    description: desc || null,
  })
  if (ok) {
    ElMessage.success(t('common.success'))
    editingGroupId.value = null
  } else {
    ElMessage.error(t('common.error'))
  }
}

function toggleEdit(groupId: number): void {
  if (editingGroupId.value === groupId) {
    syncDrafts()
    editingGroupId.value = null
    return
  }
  editingGroupId.value = groupId
  syncDrafts()
  void ensureMembersLoaded(groupId)
}

function cancelEditPanel(): void {
  syncDrafts()
  editingGroupId.value = null
}

async function ensureMembersLoaded(channelId: number): Promise<void> {
  if (membersLoading[channelId]) {
    return
  }
  membersLoading[channelId] = true
  try {
    const res = await apiRequest(`/api/chat/channels/${channelId}/members`)
    if (res.ok) {
      membersCache[channelId] = (await res.json()) as ChannelMember[]
    }
  } finally {
    membersLoading[channelId] = false
  }
}

function inviteOptions(channelId: number): OrgMember[] {
  const cached = membersCache[channelId]
  if (!cached?.length) {
    return store.orgMembers
  }
  const memberIds = new Set(cached.map((m) => m.user_id))
  return store.orgMembers.filter((u) => !memberIds.has(u.id))
}

async function submitInvite(channelId: number): Promise<void> {
  const uid = inviteUserId[channelId]
  if (uid == null) {
    ElMessage.warning(t('workshop.pickColleagueToInvite'))
    return
  }
  const ok = await store.inviteChannelMember(channelId, uid)
  if (ok) {
    ElMessage.success(t('workshop.inviteSuccess'))
    delete membersCache[channelId]
    inviteUserId[channelId] = undefined
    await ensureMembersLoaded(channelId)
  } else {
    ElMessage.error(t('workshop.inviteFailed'))
  }
}

async function duplicateGroup(group: ChatChannel): Promise<void> {
  const ok = await store.duplicateTeachingGroup(group.id)
  if (ok) {
    ElMessage.success(t('workshop.duplicateSuccess'))
  } else {
    ElMessage.error(t('workshop.duplicateFailed'))
  }
}

async function moveGroup(groupId: number, delta: number): Promise<void> {
  const ids = teachingGroups.value.map((g) => g.id)
  const idx = ids.indexOf(groupId)
  const j = idx + delta
  if (idx < 0 || j < 0 || j >= ids.length) {
    return
  }
  const next = [...ids]
  const tmp = next[idx]
  next[idx] = next[j]
  next[j] = tmp
  const ok = await store.reorderTeachingGroups(next)
  if (ok) {
    ElMessage.success(t('common.success'))
  } else {
    ElMessage.error(t('common.error'))
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="t('workshop.manageTeachingGroups')"
    width="560px"
    append-to-body
    :close-on-click-modal="false"
    class="tg-manage-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <p class="tg-manage-dialog__blurb">
      {{ t('workshop.manageTeachingGroupsBlurb') }}
    </p>

    <div
      v-if="canManage"
      class="tg-manage-dialog__actions"
    >
      <el-button
        type="primary"
        size="small"
        class="tg-manage-dialog__btn-primary"
        @click="addGroup"
      >
        <span class="tg-manage-dialog__btn-inner">
          <Plus
            class="tg-manage-dialog__btn-icon"
            :size="16"
          />
          {{ t('workshop.addChannel') }}
        </span>
      </el-button>
      <el-button
        size="small"
        class="tg-manage-dialog__btn-secondary"
        @click="browseTeachingGroups"
      >
        <span class="tg-manage-dialog__btn-inner">
          <LayoutList
            class="tg-manage-dialog__btn-icon"
            :size="16"
          />
          {{ t('workshop.browseChannels') }}
        </span>
      </el-button>
    </div>

    <div
      v-if="teachingGroups.length > 0"
      class="tg-manage-dialog__list"
    >
      <div
        v-for="g in teachingGroups"
        :key="g.id"
        class="tg-manage-dialog__row"
        :class="{ 'tg-manage-dialog__row--editing': editingGroupId === g.id }"
      >
        <div class="tg-manage-dialog__row-summary">
          <span
            v-if="g.avatar"
            class="tg-manage-dialog__avatar"
            >{{ g.avatar }}</span
          >
          <div class="tg-manage-dialog__row-summary-main">
            <div class="tg-manage-dialog__row-title-line">
              <span class="tg-manage-dialog__row-name">{{ g.name }}</span>
              <span class="tg-manage-dialog__badge">
                {{
                  g.channel_type === 'private'
                    ? t('workshop.channelTypePrivate')
                    : t('workshop.channelTypePublic')
                }}
              </span>
              <span class="tg-manage-dialog__row-meta">
                {{ g.member_count }} {{ t('workshop.members') }}
              </span>
            </div>
            <p
              v-if="g.description && (!canManage || editingGroupId !== g.id)"
              class="tg-manage-dialog__row-desc-preview"
            >
              {{ g.description }}
            </p>
          </div>
          <div
            v-if="canManage"
            class="tg-manage-dialog__row-tools"
          >
            <el-button
              text
              size="small"
              class="tg-manage-dialog__icon-btn"
              :title="t('workshop.moveUp')"
              :disabled="teachingGroups[0]?.id === g.id"
              @click="moveGroup(g.id, -1)"
            >
              <ArrowUp :size="16" />
            </el-button>
            <el-button
              text
              size="small"
              class="tg-manage-dialog__icon-btn"
              :title="t('workshop.moveDown')"
              :disabled="teachingGroups[teachingGroups.length - 1]?.id === g.id"
              @click="moveGroup(g.id, 1)"
            >
              <ArrowDown :size="16" />
            </el-button>
            <el-button
              text
              size="small"
              class="tg-manage-dialog__icon-btn"
              :title="t('workshop.duplicateTeachingGroup')"
              @click="duplicateGroup(g)"
            >
              <Copy :size="16" />
            </el-button>
            <el-button
              size="small"
              class="tg-manage-dialog__edit-btn"
              @click="toggleEdit(g.id)"
            >
              {{ editingGroupId === g.id ? t('common.cancel') : t('common.edit') }}
            </el-button>
            <el-button
              text
              size="small"
              type="danger"
              class="tg-manage-dialog__icon-btn"
              :title="t('workshop.archiveTeachingGroup')"
              @click="confirmArchive(g)"
            >
              <Trash2 :size="16" />
            </el-button>
          </div>
        </div>

        <div
          v-if="canManage && editingGroupId === g.id"
          class="tg-manage-dialog__row-panel"
        >
          <div class="tg-manage-dialog__field">
            <span class="tg-manage-dialog__field-label">{{ t('workshop.channelNameLabel') }}</span>
            <el-input
              v-model="nameDrafts[g.id]"
              size="small"
              maxlength="100"
              show-word-limit
              class="tg-manage-dialog__name-input"
              :placeholder="t('workshop.channelNamePlaceholder')"
            />
          </div>
          <div class="tg-manage-dialog__field tg-manage-dialog__field--inline">
            <span class="tg-manage-dialog__field-label">{{ t('workshop.channelType') }}</span>
            <el-select
              size="small"
              class="tg-manage-dialog__visibility-select"
              :model-value="visibilityValue(g)"
              @change="(v: string) => onVisibilityChange(g.id, v)"
            >
              <el-option
                :label="t('workshop.channelTypePublic')"
                value="public"
              />
              <el-option
                :label="t('workshop.channelTypePrivate')"
                value="private"
              />
            </el-select>
          </div>
          <div class="tg-manage-dialog__field">
            <span class="tg-manage-dialog__field-label">{{ t('workshop.topicDescription') }}</span>
            <el-input
              v-model="descDrafts[g.id]"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              size="small"
              :placeholder="t('workshop.topicDescriptionPlaceholder')"
            />
          </div>

          <div class="tg-manage-dialog__members-block">
            <div class="tg-manage-dialog__members-heading">
              {{ t('workshop.teachingGroupMembers') }} ({{ g.member_count }})
            </div>
            <p
              v-if="membersLoading[g.id]"
              class="tg-manage-dialog__members-hint"
            >
              …
            </p>
            <ul
              v-else-if="membersCache[g.id]?.length"
              class="tg-manage-dialog__members-list"
            >
              <li
                v-for="m in membersCache[g.id]"
                :key="m.user_id"
                class="tg-manage-dialog__members-li"
              >
                {{ m.name }}
              </li>
            </ul>
            <p
              v-else
              class="tg-manage-dialog__members-hint"
            >
              —
            </p>
            <div class="tg-manage-dialog__invite-row">
              <el-select
                v-model="inviteUserId[g.id]"
                filterable
                clearable
                size="small"
                class="tg-manage-dialog__invite-select"
                :disabled="!!membersLoading[g.id]"
                :placeholder="t('workshop.inviteColleague')"
              >
                <el-option
                  v-for="u in inviteOptions(g.id)"
                  :key="u.id"
                  :label="u.name"
                  :value="u.id"
                />
              </el-select>
              <el-button
                size="small"
                type="primary"
                @click="submitInvite(g.id)"
              >
                {{ t('workshop.inviteMember') }}
              </el-button>
            </div>
          </div>

          <div class="tg-manage-dialog__panel-advanced">
            <el-button
              text
              size="small"
              class="tg-manage-dialog__advanced-btn"
              @click="openGroupSettings(g.id)"
            >
              <Settings
                class="tg-manage-dialog__advanced-icon"
                :size="16"
              />
              {{ t('workshop.channelSettings') }}
            </el-button>
          </div>

          <div class="tg-manage-dialog__panel-actions">
            <el-button
              size="small"
              @click="cancelEditPanel"
            >
              {{ t('common.cancel') }}
            </el-button>
            <el-button
              type="primary"
              size="small"
              @click="saveNameAndDescription(g.id)"
            >
              {{ t('common.save') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
    <p
      v-else
      class="tg-manage-dialog__empty"
    >
      {{ t('workshop.noTeachingGroupsListed') }}
    </p>

    <template #footer>
      <el-button
        size="small"
        @click="close"
      >
        {{ t('common.close') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.tg-manage-dialog__blurb {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.5;
  color: hsl(0deg 0% 38%);
}

.tg-manage-dialog__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.tg-manage-dialog__btn-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tg-manage-dialog__btn-icon {
  flex-shrink: 0;
}

.tg-manage-dialog__btn-primary {
  border-radius: 9999px;
  font-weight: 500;
}

.tg-manage-dialog__btn-secondary {
  border-radius: 9999px;
  font-weight: 500;
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-text-color: #1c1917;
}

.tg-manage-dialog__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: min(52vh, 420px);
  overflow-y: auto;
  padding-right: 2px;
}

.tg-manage-dialog__row {
  border: 1px solid hsl(0deg 0% 90%);
  border-radius: 8px;
  background: hsl(0deg 0% 99%);
  overflow: hidden;
}

.tg-manage-dialog__row--editing {
  border-color: hsl(210deg 30% 78%);
  box-shadow: 0 0 0 1px hsl(210deg 35% 88%);
}

.tg-manage-dialog__row-summary {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 10px 10px 12px;
}

.tg-manage-dialog__avatar {
  flex-shrink: 0;
  font-size: 1.15rem;
  line-height: 1.2;
}

.tg-manage-dialog__row-summary-main {
  flex: 1;
  min-width: 0;
}

.tg-manage-dialog__row-title-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}

.tg-manage-dialog__row-name {
  font-size: 14px;
  font-weight: 600;
  color: hsl(210deg 28% 22%);
  word-break: break-word;
}

.tg-manage-dialog__row-meta {
  font-size: 11px;
  color: hsl(0deg 0% 48%);
}

.tg-manage-dialog__row-desc-preview {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: hsl(0deg 0% 42%);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tg-manage-dialog__row-tools {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  max-width: 100%;
}

.tg-manage-dialog__edit-btn {
  border-radius: 6px;
  font-weight: 500;
  margin: 0 2px;
}

.tg-manage-dialog__field-label {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: hsl(0deg 0% 45%);
}

.tg-manage-dialog__field {
  margin-bottom: 12px;
}

.tg-manage-dialog__field--inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.tg-manage-dialog__field--inline .tg-manage-dialog__field-label {
  margin-bottom: 0;
}

.tg-manage-dialog__name-input {
  width: 100%;
}

.tg-manage-dialog__visibility-select {
  width: 140px;
}

.tg-manage-dialog__badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 35%);
}

.tg-manage-dialog__icon-btn {
  padding: 4px;
  min-height: 0;
}

.tg-manage-dialog__row-panel {
  padding: 12px 12px 12px;
  border-top: 1px solid hsl(0deg 0% 92%);
  background: hsl(0deg 0% 100%);
}

.tg-manage-dialog__panel-advanced {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid hsl(0deg 0% 93%);
}

.tg-manage-dialog__advanced-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  font-weight: 500;
  color: hsl(210deg 35% 38%);
}

.tg-manage-dialog__advanced-icon {
  flex-shrink: 0;
}

.tg-manage-dialog__panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.tg-manage-dialog__members-block {
  margin-bottom: 12px;
  padding-top: 4px;
}

.tg-manage-dialog__members-heading {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: hsl(210deg 25% 32%);
}

.tg-manage-dialog__members-list {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.5;
  color: hsl(0deg 0% 32%);
}

.tg-manage-dialog__members-li {
  margin-bottom: 2px;
}

.tg-manage-dialog__members-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: hsl(0deg 0% 55%);
}

.tg-manage-dialog__invite-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tg-manage-dialog__invite-select {
  flex: 1;
  min-width: 160px;
}

.tg-manage-dialog__empty {
  margin: 0;
  padding: 20px;
  font-size: 13px;
  text-align: center;
  color: hsl(0deg 0% 45%);
}
</style>
