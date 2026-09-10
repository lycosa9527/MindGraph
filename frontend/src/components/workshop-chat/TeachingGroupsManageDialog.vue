<script setup lang="ts">
/**
 * 教研组 management: add/delete in this modal, compact list + per-row Edit
 * (advanced channel settings live inside the expanded panel).
 */
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElMessage } from 'element-plus'

import {
  Archive,
  ArrowDown,
  ArrowUp,
  Copy,
  FolderKanban,
  LayoutList,
  Loader2,
  Plus,
  Settings,
  Trash2,
} from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { useLanguage } from '@/composables/core/useLanguage'
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

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const { t } = useLanguage()
const router = useRouter()
const store = useWorkshopChatStore()
const authStore = useAuthStore()

const canManage = computed(() => authStore.isAdminOrManager)
const addingGroup = ref(false)
const newGroupName = ref('')
const newGroupDescription = ref('')
const savingNewGroup = ref(false)

function canDeleteGroup(group: ChatChannel): boolean {
  if (canManage.value) {
    return true
  }
  const uid = Number(authStore.user?.id)
  return Number.isFinite(uid) && uid > 0 && uid === group.created_by
}

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
      addingGroup.value = false
      newGroupName.value = ''
      newGroupDescription.value = ''
      void store.fetchChannels({ force: true })
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
    await swissGlassConfirm(
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

async function confirmDelete(group: ChatChannel): Promise<void> {
  try {
    await swissGlassConfirm(
      t('workshop.deleteTeachingGroupConfirm'),
      t('workshop.deleteTeachingGroup'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  const ok = await store.deleteChannel(group.id)
  if (ok) {
    ElMessage.success(t('workshop.channelDeleted'))
  } else {
    ElMessage.error(t('workshop.channelDeleteFailed'))
  }
}

function close(): void {
  emit('update:visible', false)
}

function addGroup(): void {
  addingGroup.value = true
}

function cancelAddGroup(): void {
  addingGroup.value = false
  newGroupName.value = ''
  newGroupDescription.value = ''
}

async function submitNewGroup(): Promise<void> {
  const name = newGroupName.value.trim()
  if (!name) {
    ElMessage.warning(t('workshop.teachingGroupNameRequired'))
    return
  }
  savingNewGroup.value = true
  try {
    const result = await store.createChannel({
      name,
      description: newGroupDescription.value.trim() || null,
      parent_id: null,
    })
    if (result.ok) {
      ElMessage.success(t('workshop.createChannelSuccess'))
      cancelAddGroup()
      return
    }
    ElMessage.error(result.error || t('workshop.createChannelFailed'))
  } finally {
    savingNewGroup.value = false
  }
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
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.teachingGroups.ribbon')"
    :title="t('swissGlass.hero.teachingGroups.title')"
    :line1="t('swissGlass.hero.teachingGroups.line1')"
    :icon="FolderKanban"
    width="min(560px, 92vw)"
    :close-on-click-modal="false"
    dialog-class="tg-manage-dialog"
  >
    <p class="tg-manage-dialog__blurb">
      {{ t('workshop.manageTeachingGroupsBlurb') }}
    </p>

    <div class="tg-manage-dialog__actions">
      <button
        v-if="canManage"
        type="button"
        class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
        :disabled="addingGroup"
        @click="addGroup"
      >
        <span class="tg-manage-dialog__btn-inner">
          <Plus
            class="tg-manage-dialog__btn-icon"
            :size="16"
          />
          {{ t('workshop.addChannel') }}
        </span>
      </button>
      <button
        type="button"
        class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
        @click="browseTeachingGroups"
      >
        <span class="tg-manage-dialog__btn-inner">
          <LayoutList
            class="tg-manage-dialog__btn-icon"
            :size="16"
          />
          {{ t('workshop.browseChannels') }}
        </span>
      </button>
    </div>
    <p
      v-if="!canManage"
      class="tg-manage-dialog__need-admin"
    >
      {{ t('workshop.manageNeedAdmin') }}
    </p>
    <div
      v-if="addingGroup"
      class="tg-manage-dialog__add-form"
    >
      <div class="tg-manage-dialog__field">
        <span class="tg-manage-dialog__field-label">{{ t('workshop.channelNameLabel') }}</span>
        <el-input
          v-model="newGroupName"
          size="small"
          maxlength="100"
          show-word-limit
          class="tg-manage-dialog__name-input"
          :placeholder="t('workshop.channelNamePlaceholder')"
          :disabled="savingNewGroup"
          @keyup.enter="submitNewGroup"
        />
      </div>
      <div class="tg-manage-dialog__field">
        <span class="tg-manage-dialog__field-label">{{ t('workshop.topicDescription') }}</span>
        <el-input
          v-model="newGroupDescription"
          type="textarea"
          :rows="2"
          maxlength="500"
          show-word-limit
          size="small"
          :placeholder="t('workshop.topicDescriptionPlaceholder')"
          :disabled="savingNewGroup"
        />
      </div>
      <div class="tg-manage-dialog__add-actions">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
          :disabled="savingNewGroup"
          @click="cancelAddGroup"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
          :disabled="savingNewGroup"
          @click="submitNewGroup"
        >
          <Loader2
            v-if="savingNewGroup"
            class="w-3.5 h-3.5 animate-spin"
          />
          {{ t('workshop.addChannel') }}
        </button>
      </div>
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
            v-if="canManage || canDeleteGroup(g)"
            class="tg-manage-dialog__row-tools"
          >
            <template v-if="canManage">
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
                :title="t('workshop.moveUp')"
                :disabled="teachingGroups[0]?.id === g.id"
                @click="moveGroup(g.id, -1)"
              >
                <ArrowUp :size="16" />
              </button>
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
                :title="t('workshop.moveDown')"
                :disabled="teachingGroups[teachingGroups.length - 1]?.id === g.id"
                @click="moveGroup(g.id, 1)"
              >
                <ArrowDown :size="16" />
              </button>
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
                :title="t('workshop.duplicateTeachingGroup')"
                @click="duplicateGroup(g)"
              >
                <Copy :size="16" />
              </button>
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
                @click="toggleEdit(g.id)"
              >
                {{ editingGroupId === g.id ? t('common.cancel') : t('common.edit') }}
              </button>
            </template>
            <button
              v-if="canDeleteGroup(g)"
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
              @click="confirmArchive(g)"
            >
              <span class="tg-manage-dialog__btn-inner">
                <Archive
                  class="tg-manage-dialog__btn-icon"
                  :size="14"
                />
                {{ t('workshop.archiveTeachingGroup') }}
              </span>
            </button>
            <button
              v-if="canDeleteGroup(g)"
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--danger"
              @click="confirmDelete(g)"
            >
              <span class="tg-manage-dialog__btn-inner">
                <Trash2
                  class="tg-manage-dialog__btn-icon"
                  :size="14"
                />
                {{ t('workshop.deleteTeachingGroup') }}
              </span>
            </button>
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
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
                @click="submitInvite(g.id)"
              >
                {{ t('workshop.inviteMember') }}
              </button>
            </div>
          </div>

          <div class="tg-manage-dialog__panel-advanced">
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
              @click="openGroupSettings(g.id)"
            >
              <Settings
                class="tg-manage-dialog__advanced-icon"
                :size="16"
              />
              {{ t('workshop.channelSettings') }}
            </button>
          </div>

          <div class="tg-manage-dialog__panel-actions">
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
              @click="cancelEditPanel"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
              @click="saveNameAndDescription(g.id)"
            >
              {{ t('common.save') }}
            </button>
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
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="close"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped src="./TeachingGroupsManageDialog.css"></style>
