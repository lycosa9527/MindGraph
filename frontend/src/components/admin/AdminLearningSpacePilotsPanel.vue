<script setup lang="ts">
/**
 * Learning Space admin — pilot teachers sub-page.
 */
import { onMounted, ref } from 'vue'

import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  type AdminOrganizationOption,
  fetchAdminOrganizations,
  fetchAdminUsers,
} from '@/composables/queries/adminApi'
import {
  type LearningPilot,
  type LearningTeacherSearchRow,
  createAdminPilot,
  deleteAdminPilot,
  listAdminPilots,
  patchAdminPilot,
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

async function onSearchTeachers(): Promise<void> {
  const q = teacherQuery.value.trim()
  const orgId = teacherOrgFilter.value === '' ? null : Number(teacherOrgFilter.value)
  if (!q && orgId == null) {
    notify.warning(t('admin.learningSpace.searchHint'))
    return
  }
  searching.value = true
  try {
    const res = await fetchAdminUsers({
      page: 1,
      page_size: 50,
      search: q,
      organization_id: orgId ?? undefined,
    })
    const pilotIds = new Set(pilots.value.map((p) => p.teacher_user_id))
    teacherHits.value = res.users
      .map((row) => {
        const id = Number(row.id)
        const organizationId =
          row.organization_id == null || row.organization_id === ''
            ? null
            : Number(row.organization_id)
        const role = typeof row.role === 'string' ? row.role : ''
        return {
          id,
          name: typeof row.name === 'string' ? row.name : '',
          phone: typeof row.phone === 'string' ? row.phone : null,
          email: typeof row.email === 'string' ? row.email : null,
          role,
          organization_id: Number.isFinite(organizationId as number) ? organizationId : null,
          organization_name:
            typeof row.organization_name === 'string' ? row.organization_name : '',
          already_pilot: pilotIds.has(id),
        }
      })
      .filter((row) => row.role !== 'student' && row.organization_id != null)
    if (teacherHits.value.length === 0) {
      notify.info(t('admin.learningSpace.searchEmpty'))
    }
  } catch {
    notify.error(t('admin.learningSpace.searchFailed'))
  } finally {
    searching.value = false
  }
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

onMounted(() => {
  void loadOrgs()
  void loadPilots()
})

defineExpose({ reload: loadPilots })
</script>

<template>
  <div class="ls-panel">
    <p
      v-if="loading"
      class="ls-muted"
    >
      {{ t('common.loading') }}
    </p>

    <section class="ls-section">
      <h3 class="ls-h">{{ t('admin.learningSpace.addPilotSection') }}</h3>
      <p class="ls-muted">{{ t('admin.learningSpace.pilotWorkflowHint') }}</p>
      <div
        v-if="canEdit()"
        class="ls-row"
      >
        <input
          v-model="teacherQuery"
          type="text"
          class="ls-input ls-input--wide"
          :placeholder="t('admin.learningSpace.teacherSearchPlaceholder')"
          @keydown.enter.prevent="onSearchTeachers"
        />
        <select
          v-model="teacherOrgFilter"
          class="ls-input ls-select"
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
          type="button"
          class="ls-primary"
          :disabled="searching"
          @click="onSearchTeachers"
        >
          {{ searching ? t('common.loading') : t('admin.learningSpace.searchTeachers') }}
        </button>
      </div>
      <table
        v-if="teacherHits.length"
        class="ls-table"
      >
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
                class="ls-ghost"
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
    </section>

    <section class="ls-section">
      <h3 class="ls-h">{{ t('admin.learningSpace.pilotList') }}</h3>
      <p
        v-if="!pilots.length && !loading"
        class="ls-muted"
      >
        {{ t('admin.learningSpace.pilotsEmpty') }}
      </p>
      <table
        v-else
        class="ls-table"
      >
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
                class="ls-ghost"
                :disabled="!p.enabled"
                @click="goAddClass(p)"
              >
                {{ t('admin.learningSpace.addClass') }}
              </button>
              <button
                type="button"
                class="ls-ghost"
                @click="onTogglePilot(p)"
              >
                {{ p.enabled ? t('admin.learningSpace.disable') : t('admin.learningSpace.enable') }}
              </button>
              <button
                type="button"
                class="ls-ghost ls-ghost--danger"
                @click="onDeletePilot(p)"
              >
                {{ t('admin.learningSpace.delete') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.ls-panel {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}
.ls-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.ls-h {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #1c1917;
}
.ls-muted {
  color: #78716c;
  font-size: 0.875rem;
  margin: 0;
}
.ls-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.ls-input {
  min-width: 9rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.5rem;
  background: #fafaf9;
}
.ls-input--wide {
  min-width: 14rem;
  flex: 1 1 12rem;
}
.ls-select {
  min-width: 12rem;
  max-width: 20rem;
}
.ls-primary,
.ls-ghost {
  padding: 0.45rem 0.85rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}
.ls-primary {
  background: #1c1917;
  color: #fff;
  border: none;
}
.ls-primary:disabled,
.ls-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ls-ghost {
  background: #fff;
  border: 1px solid #d6d3d1;
  color: #292524;
}
.ls-ghost--danger {
  color: #b91c1c;
  border-color: #fecaca;
}
.ls-ghost--danger:hover {
  background: #fef2f2;
}
.ls-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.ls-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.ls-table th,
.ls-table td {
  text-align: left;
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid #f5f5f4;
}
</style>
