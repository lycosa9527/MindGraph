<script setup lang="ts">
/**
 * Learning Space admin — pilot teachers sub-page.
 */
import { computed, onMounted, ref, watch } from 'vue'

import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  type AdminOrganizationOption,
  fetchAdminOrganizations,
} from '@/composables/queries/adminApi'
import {
  type LearningPilot,
  type LearningTeacherSearchRow,
  createAdminPilot,
  deleteAdminPilot,
  listAdminPilots,
  patchAdminPilot,
  searchAdminTeachers,
} from '@/utils/learningSpaceApi'

const emit = defineEmits<{
  refreshed: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const router = useRouter()

const canEdit = () => can('tab.learning_space.edit')

const loading = ref(false)
const searching = ref(false)
const pilots = ref<LearningPilot[]>([])
const organizations = ref<AdminOrganizationOption[]>([])
const teacherHits = ref<LearningTeacherSearchRow[]>([])

const teacherQuery = ref('')
const teacherOrgFilter = ref<number | ''>('')
const selectedTeacherId = ref<number | ''>('')

const schoolSelected = computed(() => teacherOrgFilter.value !== '')
const selectedTeacher = computed(
  () => teacherHits.value.find((row) => row.id === Number(selectedTeacherId.value)) ?? null
)

function teacherOptionLabel(row: LearningTeacherSearchRow): string {
  const label = row.name.trim() || row.phone || row.email || `#${row.id}`
  if (row.already_pilot) {
    return `${label} · ${t('admin.learningSpace.alreadyPilot')}`
  }
  return label
}

async function loadOrgs(): Promise<void> {
  try {
    organizations.value = await fetchAdminOrganizations()
  } catch {
    organizations.value = []
  }
}

async function loadPilots(): Promise<void> {
  loading.value = true
  try {
    const res = await listAdminPilots()
    pilots.value = res.items
    emit('refreshed')
  } catch {
    notify.error(t('admin.learningSpace.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadTeachers(opts?: { quiet?: boolean }): Promise<void> {
  const q = teacherQuery.value.trim()
  const orgId = teacherOrgFilter.value === '' ? null : Number(teacherOrgFilter.value)
  if (!q && orgId == null) {
    if (!opts?.quiet) {
      notify.warning(t('admin.learningSpace.searchHint'))
    }
    return
  }
  searching.value = true
  try {
    const res = await searchAdminTeachers({
      q,
      organization_id: orgId,
      limit: 200,
    })
    const pilotIds = new Set(pilots.value.map((p) => p.teacher_user_id))
    teacherHits.value = (Array.isArray(res.items) ? res.items : []).map((row) => ({
      ...row,
      already_pilot: row.already_pilot || pilotIds.has(row.id),
    }))
    const stillThere = teacherHits.value.some((row) => row.id === Number(selectedTeacherId.value))
    if (!stillThere) {
      selectedTeacherId.value = ''
    }
    if (teacherHits.value.length === 0 && !opts?.quiet) {
      notify.info(t('admin.learningSpace.searchEmpty'))
    }
  } catch {
    teacherHits.value = []
    selectedTeacherId.value = ''
    notify.error(t('admin.learningSpace.searchFailed'))
  } finally {
    searching.value = false
  }
}

async function onSearchTeachers(): Promise<void> {
  await loadTeachers()
}

async function onMakeSelectedPilot(): Promise<void> {
  if (selectedTeacher.value == null) {
    notify.warning(t('admin.learningSpace.selectTeacherPlaceholder'))
    return
  }
  await onMakePilot(selectedTeacher.value)
}

async function onMakePilot(row: LearningTeacherSearchRow): Promise<void> {
  if (row.organization_id == null) {
    notify.warning(t('admin.learningSpace.teacherNoOrg'))
    return
  }
  if (row.already_pilot) {
    notify.warning(t('admin.learningSpace.alreadyPilot'))
    return
  }
  try {
    await createAdminPilot({
      teacher_user_id: row.id,
      organization_id: row.organization_id,
    })
    notify.success(t('admin.learningSpace.pilotCreated'))
    row.already_pilot = true
    teacherHits.value = teacherHits.value.map((hit) =>
      hit.id === row.id ? { ...hit, already_pilot: true } : hit
    )
    await loadPilots()
  } catch {
    notify.error(t('admin.learningSpace.saveFailed'))
  }
}

async function onTogglePilot(pilot: LearningPilot): Promise<void> {
  if (pilot.enabled && (pilot.class_count ?? 0) > 0) {
    const ok = window.confirm(
      t('admin.learningSpace.disablePilotConfirm', { count: pilot.class_count ?? 0 })
    )
    if (!ok) return
  }
  try {
    await patchAdminPilot(pilot.id, !pilot.enabled)
    await loadPilots()
  } catch {
    notify.error(t('admin.learningSpace.saveFailed'))
  }
}

async function onDeletePilot(pilot: LearningPilot): Promise<void> {
  const name = pilot.teacher_name?.trim() || '—'
  const count = pilot.class_count ?? 0
  const ok = window.confirm(
    count > 0
      ? t('admin.learningSpace.deletePilotConfirmWithClasses', { name, count })
      : t('admin.learningSpace.deletePilotConfirm', { name })
  )
  if (!ok) return
  try {
    await deleteAdminPilot(pilot.id)
    notify.success(t('admin.learningSpace.pilotDeleted'))
    teacherHits.value = teacherHits.value.map((row) =>
      row.id === pilot.teacher_user_id ? { ...row, already_pilot: false } : row
    )
    await loadPilots()
  } catch (err) {
    const message = err instanceof Error && err.message.trim() ? err.message : ''
    notify.error(message || t('admin.learningSpace.saveFailed'))
  }
}

function goAddClass(pilot: LearningPilot): void {
  void router.replace({
    query: {
      ...router.currentRoute.value.query,
      tab: 'learning_space',
      subtab: 'classes',
      teacher_user_id: String(pilot.teacher_user_id),
    },
  })
}

watch(teacherOrgFilter, (orgId) => {
  selectedTeacherId.value = ''
  teacherHits.value = []
  if (orgId === '') {
    return
  }
  void loadTeachers({ quiet: true })
})

onMounted(() => {
  void loadOrgs()
  void loadPilots()
})

defineExpose({ reload: loadPilots })
</script>

<template>
  <div class="ls-admin-stack">
    <p
      v-if="loading"
      class="ls-muted"
    >
      {{ t('common.loading') }}
    </p>

    <section class="ls-admin-card">
      <div class="ls-section-title">
        <h2>{{ t('admin.learningSpace.addPilotSection') }}</h2>
      </div>
      <p class="ls-muted">{{ t('admin.learningSpace.pilotWorkflowHint') }}</p>
      <div
        v-if="canEdit()"
        class="ls-toolbar"
      >
        <select
          v-if="schoolSelected"
          v-model="selectedTeacherId"
          class="ls-control ls-control--wide"
          :disabled="searching || teacherHits.length === 0"
        >
          <option value="">
            {{
              searching
                ? t('common.loading')
                : t('admin.learningSpace.selectTeacherPlaceholder')
            }}
          </option>
          <option
            v-for="row in teacherHits"
            :key="row.id"
            :value="row.id"
            :disabled="row.already_pilot"
          >
            {{ teacherOptionLabel(row) }}
          </option>
        </select>
        <input
          v-else
          v-model="teacherQuery"
          type="text"
          class="ls-control ls-control--wide"
          :placeholder="t('admin.learningSpace.teacherSearchPlaceholder')"
          @keydown.enter.prevent="onSearchTeachers"
        />
        <select
          v-model="teacherOrgFilter"
          class="ls-control ls-control--select"
        >
          <option value="">
            {{ t('admin.learningSpace.allOrganizations') }}
          </option>
          <option
            v-for="org in organizations"
            :key="org.id"
            :value="org.id"
          >
            {{ org.name }}
          </option>
        </select>
        <button
          v-if="schoolSelected"
          type="button"
          class="ls-btn ls-btn--primary"
          :disabled="searching || selectedTeacher == null || selectedTeacher.already_pilot"
          @click="onMakeSelectedPilot"
        >
          {{ t('admin.learningSpace.makePilot') }}
        </button>
        <button
          v-else
          type="button"
          class="ls-btn ls-btn--primary"
          :disabled="searching"
          @click="onSearchTeachers"
        >
          {{ searching ? t('common.loading') : t('admin.learningSpace.searchTeachers') }}
        </button>
      </div>
      <div
        v-if="teacherHits.length"
        class="ls-table-wrap"
      >
        <table class="ls-table">
          <thead>
            <tr>
              <th>{{ t('auth.name') }}</th>
              <th>{{ t('admin.learningSpace.phone') }}</th>
              <th>{{ t('admin.learningSpace.organization') }}</th>
              <th v-if="canEdit()" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in teacherHits"
              :key="row.id"
            >
              <td>{{ row.name || row.phone || '—' }}</td>
              <td>{{ row.phone || '—' }}</td>
              <td>{{ row.organization_name || '—' }}</td>
              <td v-if="canEdit()">
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  :disabled="row.already_pilot || row.organization_id == null"
                  @click="onMakePilot(row)"
                >
                  {{
                    row.already_pilot
                      ? t('admin.learningSpace.alreadyPilot')
                      : t('admin.learningSpace.makePilot')
                  }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="ls-admin-card">
      <div class="ls-section-title">
        <h2>{{ t('admin.learningSpace.pilotList') }}</h2>
      </div>
      <p
        v-if="!pilots.length && !loading"
        class="ls-muted"
      >
        {{ t('admin.learningSpace.pilotsEmpty') }}
      </p>
      <div
        v-else
        class="ls-table-wrap"
      >
        <table class="ls-table">
          <thead>
            <tr>
              <th>{{ t('auth.name') }}</th>
              <th>{{ t('admin.learningSpace.organization') }}</th>
              <th>{{ t('admin.learningSpace.enabled') }}</th>
              <th>{{ t('admin.learningSpace.classCount') }}</th>
              <th v-if="canEdit()" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in pilots"
              :key="p.id"
            >
              <td>{{ p.teacher_name || '—' }}</td>
              <td>{{ p.organization_name || '—' }}</td>
              <td>{{ p.enabled ? t('admin.learningSpace.yes') : t('admin.learningSpace.no') }}</td>
              <td>{{ p.class_count ?? 0 }}</td>
              <td
                v-if="canEdit()"
                class="ls-actions"
              >
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  :disabled="!p.enabled"
                  @click="goAddClass(p)"
                >
                  {{ t('admin.learningSpace.addClass') }}
                </button>
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="onTogglePilot(p)"
                >
                  {{ p.enabled ? t('admin.learningSpace.disable') : t('admin.learningSpace.enable') }}
                </button>
                <button
                  type="button"
                  class="ls-btn ls-btn--danger-soft ls-btn--sm"
                  @click="onDeletePilot(p)"
                >
                  {{ t('admin.learningSpace.delete') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
