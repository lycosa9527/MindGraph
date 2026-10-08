<script setup lang="ts">
/**
 * Other-settings control: bind platform experts to this school.
 * One expert can be bound to several schools. Saving this school does not
 * remove bindings on the others.
 */
import { ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  type ExpertSchoolBindingOption,
  fetchAdminExpertSchoolBinding,
  updateAdminExpertSchoolBinding,
} from '@/composables/queries/adminApi'

const props = defineProps<{
  orgId: number
  readOnly?: boolean
  active?: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()

const MINDBOT_SWISS_SELECT_POPPER_WIDE =
  'mindbot-swiss-select-popper mindbot-swiss-select-popper--wide'

const labelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px]'

const loading = ref(false)
const ready = ref(false)
const experts = ref<ExpertSchoolBindingOption[]>([])
const boundUserIds = ref<number[]>([])
let loadGeneration = 0
let pendingLoad: Promise<void> | null = null

function expertLabel(row: ExpertSchoolBindingOption): string {
  return row.name?.trim() || row.phone?.trim() || row.email?.trim() || String(row.id)
}

async function loadBindings(): Promise<void> {
  const generation = ++loadGeneration
  const orgId = props.orgId
  loading.value = true
  ready.value = false
  const task = (async () => {
    try {
      const data = await fetchAdminExpertSchoolBinding(orgId)
      if (generation !== loadGeneration) {
        return
      }
      experts.value = data.experts
      boundUserIds.value = [...data.bound_user_ids]
      ready.value = true
    } catch {
      if (generation !== loadGeneration) {
        return
      }
      experts.value = []
      boundUserIds.value = []
      notify.errorKey('admin.expertSchoolBindingLoadError')
    } finally {
      if (generation === loadGeneration) {
        loading.value = false
      }
    }
  })()
  pendingLoad = task
  try {
    await task
  } finally {
    if (pendingLoad === task) {
      pendingLoad = null
    }
  }
}

async function saveBindings(): Promise<boolean> {
  if (pendingLoad) {
    await pendingLoad
  }
  if (props.readOnly || !ready.value) {
    return true
  }
  try {
    const data = await updateAdminExpertSchoolBinding(props.orgId, boundUserIds.value)
    experts.value = data.experts
    boundUserIds.value = [...data.bound_user_ids]
    return true
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.expertSchoolBindingLoadError'))
    return false
  }
}

watch(
  () => [props.orgId, props.active] as const,
  ([, active]) => {
    if (active === false) {
      return
    }
    void loadBindings()
  },
  { immediate: true }
)

defineExpose({ saveBindings })
</script>

<template>
  <div
    class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
      <span :class="labelClass"><I18nText k="admin.expertSchoolBindingLabel" /></span>
      <div class="flex-1 min-w-0 max-w-2xl space-y-1.5">
        <el-select
          v-model="boundUserIds"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          :loading="loading"
          :disabled="props.readOnly || loading || experts.length === 0"
          :placeholder="
            experts.length > 0
              ? t('admin.expertSchoolBindingPlaceholder')
              : t('admin.expertSchoolBindingEmpty')
          "
          class="mindbot-swiss-select w-full"
          teleported
          :popper-class="MINDBOT_SWISS_SELECT_POPPER_WIDE"
        >
          <el-option
            v-for="row in experts"
            :key="row.id"
            :label="expertLabel(row)"
            :value="row.id"
          />
        </el-select>
        <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
          <I18nText k="admin.expertSchoolBindingHint" />
        </p>
      </div>
    </div>
  </div>
</template>
