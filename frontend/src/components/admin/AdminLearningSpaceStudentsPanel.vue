<script setup lang="ts">
/**
 * Learning Space admin — cross-class student management.
 */
import { computed, onMounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { normalizeSchoolTier } from '@/constants/schoolTier'
import { userRoleLabel } from '@/utils/userRoleDisplay'
import {
  type LearningClassRow,
  type LearningStudentRow,
  adminResetPassword,
  listAdminClasses,
  listAdminStudentsGlobal,
  removeAdminClassMember,
} from '@/utils/learningSpaceApi'

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()

const canEdit = computed(() => can('tab.learning_space.edit'))

const loading = ref(false)
const classes = ref<LearningClassRow[]>([])
const students = ref<LearningStudentRow[]>([])
const summary = ref({ classroom_count: 0, enrolled_count: 0, total: 0 })
const page = ref(1)
const pageSize = ref(50)
const totalPages = ref(1)
const total = ref(0)

const search = ref('')
const filterClassId = ref<number | ''>('')
const filterMemberKind = ref<'all' | 'classroom' | 'enrolled'>('all')

function memberKindLabel(row: LearningStudentRow): string {
  if (row.member_kind === 'enrolled') {
    return t('admin.learningSpace.memberEnrolled')
  }
  return t('admin.learningSpace.memberClassroom')
}

function memberOrgLabel(row: LearningStudentRow): string {
  const org = (row.organization_name || '').trim()
  if (org) return org
  if (row.member_kind === 'enrolled' && row.role) {
    return userRoleLabel(t, row.role, row.school_tier ? normalizeSchoolTier(row.school_tier) : null)
  }
  return '—'
}

function canRemove(row: LearningStudentRow): boolean {
  return row.member_kind === 'classroom' || row.membership_role === 'learner'
}

async function loadClasses(): Promise<void> {
  try {
    const res = await listAdminClasses()
    classes.value = res.items
  } catch {
    classes.value = []
  }
}

async function loadStudents(): Promise<void> {
  loading.value = true
  try {
    const res = await listAdminStudentsGlobal({
      class_id: filterClassId.value === '' ? undefined : Number(filterClassId.value),
      member_kind: filterMemberKind.value === 'all' ? undefined : filterMemberKind.value,
      search: search.value,
      page: page.value,
      page_size: pageSize.value,
    })
    students.value = res.items
    summary.value = res.summary
    total.value = res.pagination.total
    totalPages.value = res.pagination.total_pages
  } catch {
    notify.error(t('admin.learningSpace.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onRemove(row: LearningStudentRow): Promise<void> {
  if (row.class_id == null) return
  try {
    await swissGlassConfirm(
      t('admin.learningSpace.removeMemberConfirm', { name: row.name }),
      t('admin.learningSpace.removeFromClass'),
      {
        type: 'warning',
        confirmButtonText: t('admin.learningSpace.removeFromClass'),
        cancelButtonText: t('common.cancel'),
      }
    )
  } catch {
    return
  }
  try {
    await removeAdminClassMember(row.class_id, row.id)
    notify.success(t('admin.learningSpace.memberRemoved', { name: row.name }))
    await loadStudents()
  } catch {
    notify.error(t('admin.learningSpace.saveFailed'))
  }
}

async function onResetPassword(row: LearningStudentRow): Promise<void> {
  if (row.member_kind !== 'classroom') return
  try {
    await adminResetPassword(row.id)
    notify.success(t('admin.learningSpace.passwordReset', { name: row.name }))
    await loadStudents()
  } catch {
    notify.error(t('admin.learningSpace.saveFailed'))
  }
}

function onSearch(): void {
  page.value = 1
  void loadStudents()
}

function goPage(next: number): void {
  if (next < 1 || next > totalPages.value) return
  page.value = next
  void loadStudents()
}

watch([filterClassId, filterMemberKind], () => {
  page.value = 1
  void loadStudents()
})

onMounted(async () => {
  await loadClasses()
  await loadStudents()
})
</script>

<template>
  <section class="ls-section">
    <header class="ls-section__head">
      <div>
        <h2>{{ t('admin.learningSpace.studentList') }}</h2>
        <p class="ls-muted">{{ t('admin.learningSpace.studentsIntro') }}</p>
      </div>
    </header>

    <div class="ls-summary-cards">
      <div class="ls-summary-card">
        <span class="ls-summary-card__label">{{ t('admin.learningSpace.summaryClassroom') }}</span>
        <strong>{{ summary.classroom_count }}</strong>
      </div>
      <div class="ls-summary-card">
        <span class="ls-summary-card__label">{{ t('admin.learningSpace.summaryEnrolled') }}</span>
        <strong>{{ summary.enrolled_count }}</strong>
      </div>
      <div class="ls-summary-card">
        <span class="ls-summary-card__label">{{ t('admin.learningSpace.summaryTotal') }}</span>
        <strong>{{ summary.total }}</strong>
      </div>
    </div>

    <div class="ls-toolbar ls-toolbar--wrap">
      <input
        v-model="search"
        type="search"
        class="ls-control"
        :placeholder="t('admin.learningSpace.studentSearchPlaceholder')"
        @keydown.enter.prevent="onSearch"
      />
      <select
        v-model="filterClassId"
        class="ls-control"
      >
        <option value="">{{ t('admin.learningSpace.filterAllClasses') }}</option>
        <option
          v-for="cls in classes"
          :key="cls.id"
          :value="cls.id"
        >
          {{ cls.name }} · {{ cls.class_code }}
        </option>
      </select>
      <select
        v-model="filterMemberKind"
        class="ls-control"
      >
        <option value="all">{{ t('admin.learningSpace.filterAllMemberKinds') }}</option>
        <option value="classroom">{{ t('admin.learningSpace.memberClassroom') }}</option>
        <option value="enrolled">{{ t('admin.learningSpace.memberEnrolled') }}</option>
      </select>
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-btn--sm"
        @click="onSearch"
      >
        {{ t('admin.learningSpace.searchTeachers') }}
      </button>
    </div>

    <p
      v-if="loading"
      class="ls-muted"
    >
      {{ t('common.loading') }}
    </p>
    <table
      v-else
      class="ls-table"
    >
      <thead>
        <tr>
          <th>ID</th>
          <th>{{ t('auth.name') }}</th>
          <th>{{ t('admin.learningSpace.className') }}</th>
          <th>{{ t('admin.learningSpace.teacher') }}</th>
          <th>{{ t('admin.learningSpace.memberKind') }}</th>
          <th>{{ t('admin.learningSpace.organization') }}</th>
          <th>{{ t('admin.learningSpace.phone') }}</th>
          <th>{{ t('admin.learningSpace.currentPassword') }}</th>
          <th>{{ t('admin.learningSpace.status') }}</th>
          <th>{{ t('admin.learningSpace.mustChangePassword') }}</th>
          <th v-if="canEdit" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in students"
          :key="`${row.class_id}-${row.id}`"
        >
          <td>{{ row.id }}</td>
          <td>{{ row.name }}</td>
          <td>{{ row.class_name || '—' }}</td>
          <td>{{ row.teacher_name || '—' }}</td>
          <td>{{ memberKindLabel(row) }}</td>
          <td>{{ memberOrgLabel(row) }}</td>
          <td>{{ row.phone || '—' }}</td>
          <td>
            <code v-if="row.member_kind === 'classroom' && row.initial_password">
              {{ row.initial_password }}
            </code>
            <span v-else class="ls-muted">—</span>
          </td>
          <td>
            {{
              row.class_status === 'archived'
                ? t('admin.learningSpace.statusArchived')
                : t('admin.learningSpace.statusActive')
            }}
          </td>
          <td>
            {{
              row.must_change_password ? t('admin.learningSpace.yes') : t('admin.learningSpace.no')
            }}
          </td>
          <td v-if="canEdit">
            <div class="ls-row-actions">
              <button
                v-if="row.member_kind === 'classroom'"
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                @click="onResetPassword(row)"
              >
                {{ t('admin.learningSpace.resetPassword') }}
              </button>
              <button
                v-if="canRemove(row)"
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                @click="onRemove(row)"
              >
                {{ t('admin.learningSpace.removeFromClass') }}
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <p
      v-if="!loading && !students.length"
      class="ls-muted"
    >
      {{ t('admin.learningSpace.studentsGlobalEmpty') }}
    </p>

    <div
      v-if="totalPages > 1"
      class="ls-toolbar"
    >
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-btn--sm"
        :disabled="page <= 1"
        @click="goPage(page - 1)"
      >
        {{ t('admin.previous') }}
      </button>
      <span class="ls-muted">{{ page }} / {{ totalPages }} · {{ total }}</span>
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-btn--sm"
        :disabled="page >= totalPages"
        @click="goPage(page + 1)"
      >
        {{ t('admin.next') }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.ls-summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.ls-summary-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  background: rgb(255 255 255 / 0.72);
  border: 1px solid rgb(15 23 42 / 0.08);
}

.ls-summary-card__label {
  font-size: 0.8125rem;
  color: rgb(100 116 139);
}

.ls-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}
</style>
