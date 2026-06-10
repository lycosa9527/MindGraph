<script setup lang="ts">
/**
 * School modal — General tab: display name, status, expiry, managers, school version.
 */
import { computed, watch } from 'vue'

import { useLanguage } from '@/composables'
import {
  effectiveMemberLimit,
  EXTRA_MEMBER_SEAT_PRESETS,
  EXTRA_MEMBER_SEATS_MAX,
  isUnlimitedMemberLimit,
  SCHOOL_TIER_LIMITS,
  SCHOOL_TIER_OPTIONS,
  type SchoolTier,
} from '@/constants/schoolTier'

const displayNameEdit = defineModel<string>('displayNameEdit', { required: true })
const expiresAtEdit = defineModel<string | null>('expiresAtEdit', { required: true })
const schoolTierEdit = defineModel<SchoolTier>('schoolTierEdit', { required: true })
const extraMemberSeatsEdit = defineModel<number>('extraMemberSeatsEdit', { required: true })

const props = defineProps<{
  orgName?: string
  orgActiveState: boolean
  orgUserCount?: number
  managers: { id: number; phone: string; name: string }[]
  orgUsers: { id: number; phone: string; name: string }[]
  managersLoading: boolean
  addManagersLoading: boolean
  lockLoading: boolean
  readOnly?: boolean
}>()

const pendingManagerIds = defineModel<number[]>('pendingManagerIds', { required: true })

const emit = defineEmits<{
  (e: 'toggleLock'): void
  (e: 'addManagers'): void
  (e: 'removeManager', userId: number): void
}>()

const { t } = useLanguage()

const MINDBOT_SWISS_SELECT_POPPER_WIDE =
  'mindbot-swiss-select-popper mindbot-swiss-select-popper--wide'

const labelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px]'

const tierLabelKey: Record<SchoolTier, string> = {
  trial: 'admin.schoolVersionTierTrial',
  lite: 'admin.schoolVersionTierLite',
  standard: 'admin.schoolVersionTierStandard',
  professional: 'admin.schoolVersionTierProfessional',
}

const baseMemberLimit = computed(() => SCHOOL_TIER_LIMITS[schoolTierEdit.value].memberLimit)

const effectiveMemberLimitValue = computed(() =>
  effectiveMemberLimit(schoolTierEdit.value, extraMemberSeatsEdit.value)
)

const showExtraMemberSeats = computed(() => schoolTierEdit.value !== 'trial')

const schoolTierHint = computed(() => {
  const current = props.orgUserCount ?? 0
  if (isUnlimitedMemberLimit(baseMemberLimit.value)) {
    return t('admin.schoolVersionHint', {
      current,
      limit: t('admin.unlimited'),
    })
  }
  return t('admin.extraMemberSeatsHint', {
    current,
    effectiveLimit: effectiveMemberLimitValue.value,
    base: baseMemberLimit.value,
    extra: extraMemberSeatsEdit.value,
  })
})

function selectExtraSeatPreset(value: number) {
  extraMemberSeatsEdit.value = value
}

watch(schoolTierEdit, (tier) => {
  if (tier === 'trial') {
    extraMemberSeatsEdit.value = 0
  }
})

const showLiteFeaturesHint = computed(
  () => schoolTierEdit.value === 'trial' || schoolTierEdit.value === 'lite'
)

const managerLimit = computed(() => SCHOOL_TIER_LIMITS[schoolTierEdit.value].managerLimit)

const managersRemaining = computed(() =>
  Math.max(0, managerLimit.value - props.managers.length)
)

const managerLimitHint = computed(() => {
  if (managerLimit.value <= 0) {
    return t('admin.schoolManagerNotAvailableTrial')
  }
  return t('admin.schoolManagerLimitHint', {
    current: props.managers.length,
    limit: managerLimit.value,
  })
})

function tierOptionLabel(tier: SchoolTier): string {
  const limits = SCHOOL_TIER_LIMITS[tier]
  if (tier === 'trial') {
    return t('admin.schoolVersionTierOptionTrial', {
      label: t(tierLabelKey[tier]),
      diagrams: limits.diagramsPerMember ?? 20,
      storage: limits.diagramStorageGbPerMember,
    })
  }
  return t('admin.schoolVersionTierOption', {
    label: t(tierLabelKey[tier]),
    members: limits.memberLimit,
    managers: limits.managerLimit,
    storage: limits.diagramStorageGbPerMember,
  })
}
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
          :disabled="props.readOnly"
          clearable
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.schoolVersionLabel') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-1.5">
          <el-select
            v-model="schoolTierEdit"
            :disabled="props.readOnly"
            class="mindbot-swiss-select w-full"
            teleported
            :popper-class="MINDBOT_SWISS_SELECT_POPPER_WIDE"
          >
            <el-option
              v-for="tier in SCHOOL_TIER_OPTIONS"
              :key="tier"
              :label="tierOptionLabel(tier)"
              :value="tier"
            >
              <span class="mindbot-swiss-select-option__label">{{ tierOptionLabel(tier) }}</span>
            </el-option>
          </el-select>
          <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
            {{ schoolTierHint }}
          </p>
          <p
            v-if="showLiteFeaturesHint"
            class="mindbot-swiss-hint text-xs m-0 leading-relaxed text-amber-800/90"
          >
            {{ t('admin.schoolVersionLiteFeaturesHint') }}
          </p>
        </div>
      </div>

      <div
        v-if="showExtraMemberSeats"
        class="flex flex-col gap-3 sm:flex-row sm:items-start"
      >
        <span :class="labelClass">{{ t('admin.extraMemberSeatsLabel') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-2">
          <div class="flex flex-wrap gap-2">
            <el-button
              v-for="preset in EXTRA_MEMBER_SEAT_PRESETS"
              :key="preset"
              plain
              size="small"
              class="mindbot-pill shrink-0"
              :class="extraMemberSeatsEdit === preset ? 'mindbot-pill--copy' : ''"
              :disabled="props.readOnly"
              @click="selectExtraSeatPreset(preset)"
            >
              {{ t('admin.extraMemberSeatsPreset', { count: preset }) }}
            </el-button>
          </div>
          <el-input-number
            v-model="extraMemberSeatsEdit"
            :min="0"
            :max="EXTRA_MEMBER_SEATS_MAX"
            :step="1"
            :disabled="props.readOnly"
            controls-position="right"
            class="mindbot-swiss-input w-full max-w-xs"
          />
        </div>
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
            v-if="!props.readOnly"
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
          :disabled="props.readOnly"
          :placeholder="t('admin.noExpiration')"
          value-format="YYYY-MM-DD"
          clearable
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
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
                  v-if="!props.readOnly"
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
            <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
              {{ managerLimitHint }}
            </p>
            <div
              v-if="!props.readOnly"
              class="flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <el-select
                v-model="pendingManagerIds"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                :multiple-limit="managersRemaining"
                :disabled="orgUsers.length === 0 || managersRemaining === 0"
                :placeholder="
                  orgUsers.length > 0
                    ? t('admin.addSchoolManagers')
                    : t('admin.noUsersToAddAsManager')
                "
                class="mindbot-swiss-select flex-1 min-w-0"
                :popper-class="MINDBOT_SWISS_SELECT_POPPER_WIDE"
              >
                <el-option
                  v-for="u in orgUsers"
                  :key="u.id"
                  :label="u.name || u.phone"
                  :value="u.id"
                >
                  <span class="mindbot-swiss-select-option__label">{{ u.name || u.phone }}</span>
                </el-option>
              </el-select>
              <el-button
                plain
                class="mindbot-pill mindbot-pill--copy shrink-0"
                :loading="addManagersLoading"
                :disabled="pendingManagerIds.length === 0 || managersRemaining === 0"
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
