<script setup lang="ts">
/**
 * Admin user edit modal — MindBot geek Swiss dialog shell.
 */
import { computed, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  useAdminOrganizations,
  useAdminUser,
  useDeleteAdminSchoolUser,
  useDeleteAdminUser,
  useUpdateAdminSchoolUser,
  useUpdateAdminUser,
  useUpdateAdminUserRole,
} from '@/composables/queries'
import type { UserRole } from '@/types'
import { httpErrorDetail } from '@/utils/httpErrorDetail'
import {
  normalizeUserRole,
  userRoleLabel,
  userRoleSelectTiers,
} from '@/utils/userRoleDisplay'

const MINDBOT_ROLE_SELECT_POPPER =
  'mindbot-swiss-select-popper mindbot-swiss-select-popper--role'
const MINDBOT_SELECT_POPPER_WIDE = 'mindbot-swiss-select-popper mindbot-swiss-select-popper--wide'

export type AdminUserEditMode = 'global' | 'school'

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    userId: number | null
    fullEdit?: boolean
    mode?: AdminUserEditMode
    schoolOrgId?: number | null
  }>(),
  {
    fullEdit: false,
    mode: 'global',
    schoolOrgId: null,
  }
)

const emit = defineEmits<{
  saved: []
  deleted: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const orgsQuery = useAdminOrganizations()
const organizations = computed(() => orgsQuery.data.value ?? [])

const userIdRef = computed(() => props.userId)
const schoolOrgIdRef = computed(() => (props.mode === 'school' ? props.schoolOrgId : null))
const userQuery = useAdminUser(userIdRef, schoolOrgIdRef, {
  enabled: computed(() => visible.value && props.userId != null),
})
const updateUserMutation = useUpdateAdminUser()
const updateUserRoleMutation = useUpdateAdminUserRole()
const updateSchoolUserMutation = useUpdateAdminSchoolUser()
const deleteUserMutation = useDeleteAdminUser()
const deleteSchoolUserMutation = useDeleteAdminSchoolUser()

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const phoneEdit = ref('')
const emailEdit = ref('')
const nameEdit = ref('')
const organizationId = ref<number | null>(null)
const roleEdit = ref<UserRole>('teacher')
const detail = ref<Record<string, unknown> | null>(null)
const initialRole = ref<UserRole>('teacher')

const headerNote = computed(() => {
  if (props.userId == null) {
    return '—'
  }
  if (!detail.value) {
    return `UID ${props.userId}`
  }
  const phone = detail.value.phone
  const email = detail.value.email
  if (typeof phone === 'string' && phone.trim()) {
    return phone.trim()
  }
  if (typeof email === 'string' && email.trim()) {
    return email.trim()
  }
  return `UID ${props.userId}`
})

const diagramRemainingDisplay = computed(() => {
  const remaining = detail.value?.diagram_remaining
  const max = detail.value?.diagram_quota_max
  if (typeof remaining !== 'number') {
    return '—'
  }
  if (typeof max === 'number' && max <= 0) {
    return t('admin.unlimited')
  }
  if (typeof max === 'number') {
    return `${remaining} / ${max}`
  }
  return String(remaining)
})

const organizationReadonly = computed(() => {
  const name = detail.value?.organization_name
  if (typeof name === 'string' && name.trim()) {
    return name
  }
  return t('admin.accountNotSet')
})

const roleSelectTiers = computed(() => userRoleSelectTiers())

function roleLabel(role: UserRole): string {
  return userRoleLabel(t, role)
}

const deleteTargetName = computed(() => {
  const name = nameEdit.value.trim()
  if (name) {
    return name
  }
  const detailName = detail.value?.name
  if (typeof detailName === 'string' && detailName.trim()) {
    return detailName.trim()
  }
  const phone = phoneEdit.value.trim()
  if (phone) {
    return phone
  }
  const detailPhone = detail.value?.phone
  if (typeof detailPhone === 'string' && detailPhone.trim()) {
    return detailPhone.trim()
  }
  if (props.userId != null) {
    return `UID ${props.userId}`
  }
  return '—'
})

function onClose(): void {
  visible.value = false
}

function applyDetail(data: Record<string, unknown>): void {
  detail.value = data
  phoneEdit.value = typeof data.phone === 'string' ? data.phone : ''
  emailEdit.value = typeof data.email === 'string' ? data.email : ''
  nameEdit.value = typeof data.name === 'string' ? data.name : ''
  const orgId = data.organization_id
  organizationId.value = typeof orgId === 'number' ? orgId : null
  const role = normalizeUserRole(typeof data.role === 'string' ? data.role : null)
  roleEdit.value = role
  initialRole.value = role
}

async function loadDetail(): Promise<void> {
  if (props.userId == null) {
    return
  }
  if (props.mode === 'school' && props.schoolOrgId == null) {
    notify.error(t('admin.schoolUsersLoadError'))
    onClose()
    return
  }
  loading.value = true
  detail.value = null
  try {
    const result = await userQuery.refetch()
    const data = result.data as Record<string, unknown> | undefined
    if (!data) {
      notify.error(t('admin.schoolUsersLoadError'))
      onClose()
      return
    }
    applyDetail(data)
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolUsersLoadError')
    notify.error(message)
    onClose()
  } finally {
    loading.value = false
  }
}

function validateBeforeSave(): boolean {
  const trimmedName = nameEdit.value.trim()
  if (trimmedName.length < 2 || /\d/.test(trimmedName)) {
    notify.warning(t('auth.modal.fillRequired'))
    return false
  }
  if (props.fullEdit) {
    const phone = phoneEdit.value.trim()
    const email = emailEdit.value.trim()
    if (!phone && !email) {
      notify.warning(t('admin.accountPhoneOrEmailRequired'))
      return false
    }
    if (phone && (phone.length !== 11 || !phone.startsWith('1') || !/^\d+$/.test(phone))) {
      notify.warning(t('admin.phoneFormatHint'))
      return false
    }
  }
  return true
}

async function saveGlobalUser(): Promise<boolean> {
  if (props.userId == null) {
    return false
  }
  const body: Record<string, unknown> = {
    name: nameEdit.value.trim(),
    organization_id: organizationId.value,
  }
  const phone = phoneEdit.value.trim()
  const email = emailEdit.value.trim()
  if (phone) {
    body.phone = phone
  }
  if (email) {
    body.email = email
  } else if (props.fullEdit) {
    body.email = null
  }

  try {
    await updateUserMutation.mutateAsync({ userId: props.userId, body })
    if (roleEdit.value !== initialRole.value) {
      await updateUserRoleMutation.mutateAsync({ userId: props.userId, role: roleEdit.value })
    }
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolUsersUpdateError')
    notify.error(message)
    return false
  }
}

async function saveSchoolUser(): Promise<boolean> {
  if (props.userId == null || props.schoolOrgId == null) {
    return false
  }
  const body: Record<string, string> = { name: nameEdit.value.trim() }
  const phone = phoneEdit.value.trim()
  if (phone) {
    body.phone = phone
  }
  try {
    await updateSchoolUserMutation.mutateAsync({
      userId: props.userId,
      organizationId: props.schoolOrgId,
      body,
    })
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolUsersUpdateError')
    notify.error(message)
    return false
  }
}

async function deleteUser(): Promise<void> {
  if (props.userId == null || deleting.value) {
    return
  }
  if (props.mode === 'school' && props.schoolOrgId == null) {
    notify.error(t('admin.schoolUsersDeleteError'))
    return
  }

  deleting.value = true
  try {
    if (props.mode === 'school' && !props.fullEdit && props.schoolOrgId != null) {
      await deleteSchoolUserMutation.mutateAsync({
        userId: props.userId,
        organizationId: props.schoolOrgId,
      })
    } else {
      await deleteUserMutation.mutateAsync(props.userId)
    }
    notify.success(t('notification.deleted'))
    emit('deleted')
    onClose()
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolUsersDeleteError')
    notify.error(message)
  } finally {
    deleting.value = false
  }
}

async function confirmDeleteUser(): Promise<void> {
  if (props.userId == null || deleting.value || saving.value) {
    return
  }
  try {
    await ElMessageBox.confirm(
      t('admin.schoolDeleteUserConfirm', { name: deleteTargetName.value }),
      t('admin.delete'),
      {
        type: 'warning',
        customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--delete',
        modalClass: 'mindbot-swiss-backdrop',
        cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
        confirmButtonText: t('admin.delete'),
        cancelButtonText: t('common.cancel'),
        showClose: true,
      }
    )
  } catch {
    return
  }
  await deleteUser()
}

async function saveUser(): Promise<void> {
  if (props.userId == null || saving.value || !validateBeforeSave()) {
    return
  }
  saving.value = true
  try {
    const ok =
      props.mode === 'school' && !props.fullEdit
        ? await saveSchoolUser()
        : await saveGlobalUser()
    if (!ok) {
      return
    }
    notify.success(t('notification.saved'))
    emit('saved')
    onClose()
  } catch {
    notify.error(t('admin.schoolUsersUpdateError'))
  } finally {
    saving.value = false
  }
}

watch(visible, (open) => {
  if (open) {
    if (props.fullEdit || props.mode === 'global') {
      void orgsQuery.refetch()
    }
    void loadDetail()
  } else {
    detail.value = null
  }
})
</script>

<template>
  <el-dialog
    v-model="visible"
    class="mindbot-settings-dialog mindbot-swiss-dialog admin-user-edit-dialog"
    width="min(520px, 94vw)"
    destroy-on-close
    append-to-body
    align-center
    modal-class="mindbot-swiss-backdrop"
    :show-close="true"
  >
    <template #header>
      <div class="mindbot-swiss-header mindbot-config-header">
        <span class="mindbot-swiss-header__glyph">◇</span>
        <span class="mindbot-swiss-header__title">{{ t('admin.userEditModalTitle') }}</span>
        <span
          class="mindbot-swiss-header__divider"
          aria-hidden="true"
        >
          ·
        </span>
        <span class="mindbot-swiss-header__note">{{ headerNote }}</span>
      </div>
    </template>

    <div
      v-loading="loading"
      class="mindbot-config-body admin-user-edit-body"
      element-loading-background="rgba(2, 6, 23, 0.72)"
    >
      <div
        class="mindbot-config-scanlines"
        aria-hidden="true"
      />
      <div class="mindbot-swiss-form-wrap">
        <el-form
          v-if="detail && !loading"
          label-position="left"
          label-width="148px"
          class="mindbot-settings-form mindbot-swiss-form mindbot-compact space-y-0"
        >
          <el-form-item
            v-if="fullEdit || mode === 'school'"
            :label="t('admin.phone')"
          >
            <el-input
              v-model="phoneEdit"
              class="mindbot-swiss-input w-full max-w-md"
              inputmode="numeric"
              maxlength="11"
              :placeholder="t('admin.phonePlaceholder')"
              :disabled="!fullEdit && mode !== 'school'"
            />
          </el-form-item>

          <el-form-item
            v-if="fullEdit"
            :label="t('admin.email')"
          >
            <el-input
              v-model="emailEdit"
              class="mindbot-swiss-input w-full max-w-md"
              type="email"
              autocomplete="off"
              :placeholder="t('admin.emailPlaceholder')"
            />
          </el-form-item>

          <el-form-item :label="t('admin.name')">
            <el-input
              v-model="nameEdit"
              class="mindbot-swiss-input w-full max-w-md"
              :placeholder="t('auth.accountNamePlaceholder')"
            />
          </el-form-item>

          <el-form-item
            v-if="fullEdit"
            :label="t('admin.userType')"
          >
            <el-select
              v-model="roleEdit"
              class="mindbot-swiss-select mindbot-swiss-select--role w-full max-w-[11rem]"
              teleported
              filterable
              :popper-class="MINDBOT_ROLE_SELECT_POPPER"
            >
              <el-option-group
                v-for="tier in roleSelectTiers"
                :key="tier.tierLabelKey"
                :label="t(tier.tierLabelKey)"
              >
                <el-option
                  v-for="role in tier.roles"
                  :key="role"
                  :label="roleLabel(role)"
                  :value="role"
                />
              </el-option-group>
            </el-select>
          </el-form-item>

          <el-form-item :label="t('admin.organization')">
            <el-select
              v-if="fullEdit"
              v-model="organizationId"
              class="mindbot-swiss-select w-full max-w-md"
              teleported
              filterable
              clearable
              :placeholder="t('admin.filterBySchool')"
              :popper-class="MINDBOT_SELECT_POPPER_WIDE"
            >
              <el-option
                v-for="org in organizations"
                :key="org.id"
                :label="org.name"
                :value="org.id"
              >
                <span class="mindbot-swiss-select-option__label">{{ org.name }}</span>
              </el-option>
            </el-select>
            <el-input
              v-else
              class="mindbot-swiss-input w-full max-w-md"
              :model-value="organizationReadonly"
              disabled
            />
          </el-form-item>

          <el-form-item :label="t('admin.remainingResourcePoints')">
            <el-input
              class="mindbot-swiss-input w-full max-w-md tabular-nums"
              :model-value="diagramRemainingDisplay"
              disabled
            />
            <p
              v-if="fullEdit"
              class="mindbot-swiss-hint mt-2 text-xs leading-relaxed"
            >
              {{ t('admin.diagramRemainingHint') }}
            </p>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <template #footer>
      <div
        class="mindbot-dialog-footer flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <el-button
          v-if="userId != null"
          type="danger"
          plain
          class="mindbot-pill mindbot-pill--footer-danger order-2 self-start sm:order-1"
          :loading="deleting"
          :disabled="loading || !detail || saving"
          @click="confirmDeleteUser"
        >
          <el-icon class="mr-1"><Delete /></el-icon>
          {{ t('admin.delete') }}
        </el-button>
        <div
          class="order-1 flex w-full flex-col-reverse gap-2 sm:order-2 sm:ml-auto sm:w-auto sm:flex-row sm:items-center sm:justify-end sm:gap-2"
        >
          <el-button
            class="mindbot-pill mindbot-pill--footer-cancel"
            @click="onClose"
          >
            {{ t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            class="mindbot-pill mindbot-pill--footer-save"
            :loading="saving"
            :disabled="loading || !detail || deleting"
            @click="saveUser"
          >
            {{ t('common.save') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.admin-user-edit-dialog.mindbot-settings-dialog.mindbot-swiss-dialog {
  width: min(520px, 94vw) !important;
  max-width: 100%;
  border-radius: 2px;
  overflow: hidden;
}

.admin-user-edit-body {
  min-height: 12rem;
  max-height: min(70vh, 520px);
  overflow-y: auto;
}

.admin-user-edit-body :deep(.el-loading-mask) {
  border-radius: 2px;
}
</style>

<style scoped>
@import '@/styles/admin-mindbot-swiss-dialog-chrome.css';
</style>
