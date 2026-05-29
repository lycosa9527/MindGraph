<script setup lang="ts">
/**
 * School modal — General tab: display name, status, expiry, invitation, managers.
 */
import { Refresh, Share } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'

const displayNameEdit = defineModel<string>('displayNameEdit', { required: true })
const expiresAtEdit = defineModel<string | null>('expiresAtEdit', { required: true })

defineProps<{
  orgName?: string
  orgActiveState: boolean
  invitationCode: string
  invitationCodeLoading?: boolean
  managers: { id: number; phone: string; name: string }[]
  orgUsers: { id: number; phone: string; name: string }[]
  managersLoading: boolean
  addManagersLoading: boolean
  lockLoading: boolean
  refreshCodeLoading: boolean
}>()

const pendingManagerIds = defineModel<number[]>('pendingManagerIds', { required: true })

const emit = defineEmits<{
  (e: 'toggleLock'): void
  (e: 'refreshInvitationCode'): void
  (e: 'copyShareMessage'): void
  (e: 'addManagers'): void
  (e: 'removeManager', userId: number): void
}>()

const { t } = useLanguage()

const labelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px]'
</script>

<template>
  <div class="school-general-tab space-y-4">
    <div
      class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4 space-y-4"
    >
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.displayNameLabel') }}</span>
        <el-input
          v-model="displayNameEdit"
          :placeholder="orgName"
          clearable
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.status') }}</span>
        <div class="flex flex-wrap items-center gap-2 flex-1 min-w-0">
          <span
            class="school-general-status-badge"
            :class="
              orgActiveState
                ? 'school-general-status-badge--active'
                : 'school-general-status-badge--locked'
            "
          >
            {{ orgActiveState ? t('admin.enabled') : t('admin.disabled') }}
          </span>
          <el-button
            :loading="lockLoading"
            plain
            class="mindbot-pill shrink-0"
            :class="orgActiveState ? 'mindbot-pill--lock' : 'mindbot-pill--unlock'"
            @click="emit('toggleLock')"
          >
            {{ orgActiveState ? t('admin.lockOrganization') : t('admin.unlockOrganization') }}
          </el-button>
        </div>
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.expirationDate') }}</span>
        <el-date-picker
          v-model="expiresAtEdit"
          type="date"
          :placeholder="t('admin.noExpiration')"
          value-format="YYYY-MM-DD"
          clearable
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.invitationCode') }}</span>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center flex-1 min-w-0 max-w-2xl">
          <el-input
            :model-value="invitationCode"
            readonly
            class="mindbot-swiss-input font-mono flex-1 min-w-0"
            :placeholder="invitationCodeLoading ? t('admin.loading') : '—'"
          />
          <div class="flex flex-wrap items-center gap-2 shrink-0">
            <el-button
              :loading="refreshCodeLoading"
              plain
              class="mindbot-pill mindbot-pill--rotate shrink-0"
              @click="emit('refreshInvitationCode')"
            >
              <el-icon class="mr-1"><Refresh /></el-icon>
              {{ t('admin.refreshInvitationCode') }}
            </el-button>
            <el-button
              plain
              class="mindbot-pill mindbot-pill--copy shrink-0"
              :disabled="!invitationCode"
              @click="emit('copyShareMessage')"
            >
              <el-icon class="mr-1"><Share /></el-icon>
              {{ t('admin.copyShareMessage') }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.managers') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-2">
          <div
            v-if="managersLoading"
            class="mindbot-swiss-hint text-sm"
          >
            {{ t('admin.loading') }}
          </div>
          <template v-else>
            <div
              v-if="managers.length"
              class="flex flex-wrap gap-2"
            >
              <span
                v-for="m in managers"
                :key="m.id"
                class="school-general-chip"
              >
                <span class="school-general-chip__label">{{ m.name || m.phone }}</span>
                <button
                  type="button"
                  class="school-general-chip__remove"
                  :aria-label="t('admin.removeManager')"
                  @click="emit('removeManager', m.id)"
                >
                  ×
                </button>
              </span>
            </div>
            <p
              v-else
              class="mindbot-swiss-hint text-xs m-0"
            >
              {{ t('admin.noManagersFound') }}
            </p>
            <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
              <el-select
                v-model="pendingManagerIds"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                :disabled="orgUsers.length === 0"
                :placeholder="
                  orgUsers.length > 0
                    ? t('admin.addSchoolManagers')
                    : t('admin.noUsersToAddAsManager')
                "
                class="mindbot-swiss-select flex-1 min-w-0"
              >
                <el-option
                  v-for="u in orgUsers"
                  :key="u.id"
                  :label="u.name || u.phone"
                  :value="u.id"
                />
              </el-select>
              <el-button
                plain
                class="mindbot-pill mindbot-pill--copy shrink-0"
                :loading="addManagersLoading"
                :disabled="pendingManagerIds.length === 0"
                @click="emit('addManagers')"
              >
                {{ t('admin.addSchoolManagersButton') }}
              </el-button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
