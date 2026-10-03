<script setup lang="ts">
/**
 * Teacher Learning Space: dashboard, assignments, class roster.
 * Data and loads live on the Learning Space store.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { AlertTriangle, ArrowLeft, Clock3, FileText, Users } from '@lucide/vue'

import LearningSpaceThumbCover from '@/components/learningSpace/LearningSpaceThumbCover.vue'
import { swissGlassConfirm, useLanguage } from '@/composables'
import {
  assignmentIsClosed,
  assignmentProgress,
  formatLsDateTime,
  formatLsStudentLabel,
  greetHourLabel,
  submissionIsReviewed,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores'
import { useLearningSpaceStore } from '@/stores/learningSpace'
import type { LearningAssignment } from '@/utils/learningSpaceApi'

const { t } = useLanguage()
const authStore = useAuthStore()
const ls = useLearningSpaceStore()
const {
  teacherTab,
  selectedAssignmentId,
  canPublish,
  publishableClasses,
  canOpenClassAdmin,
  teacherMetrics,
  assignmentFilter,
  assignmentQuery,
  classes,
  selectedClassId,
  filteredAssignments,
  deletingAssignmentId,
  selectedAssignment,
  wallSubmissions,
  selectedClass,
  classStudents,
} = storeToRefs(ls)

const userName = computed(
  () => authStore.user?.username || authStore.user?.phone || t('learningSpace.userFallback')
)
const greetKey = computed(() => {
  const label = greetHourLabel(new Date().getHours())
  if (label === 'morning') return 'learningSpace.greetMorning'
  if (label === 'afternoon') return 'learningSpace.greetAfternoon'
  return 'learningSpace.greetEvening'
})

function statusLabel(status: string | undefined): string {
  if (status === 'submitted') return t('learningSpace.statusSubmitted')
  if (status === 'returned') return t('learningSpace.statusReturned')
  if (status === 'draft') return t('learningSpace.statusDraft')
  return t('learningSpace.notStarted')
}

function assignmentStatusBadge(assignment: LearningAssignment): { text: string; tone: string } {
  if (assignment.status === 'draft') return { text: t('learningSpace.filterDraft'), tone: 'draft' }
  if (assignmentIsClosed(assignment))
    return { text: t('learningSpace.statusClosed'), tone: 'closed' }
  return { text: t('learningSpace.statusActive'), tone: 'active' }
}

function classNameForAssignment(assignment: LearningAssignment): string {
  return (
    classes.value.find((row) => row.id === assignment.class_id)?.name || t('learningSpace.class')
  )
}

function progressFor(assignment: LearningAssignment) {
  const roster = classes.value.find((row) => row.id === assignment.class_id)?.student_count
  return assignmentProgress(assignment, roster)
}

function canDeleteAssignment(assignment: LearningAssignment): boolean {
  return canPublish.value && publishableClasses.value.some((row) => row.id === assignment.class_id)
}

async function onDelete(assignment: LearningAssignment): Promise<void> {
  try {
    await swissGlassConfirm(
      t('learningSpace.deleteAssignmentConfirm', { title: assignment.title }),
      t('learningSpace.deleteAssignment'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  await ls.deleteAssignment(assignment)
}
</script>

<template>
  <!-- Dashboard -->
  <template v-if="teacherTab === 'dashboard' && selectedAssignmentId == null">
    <div class="ls-page-head">
      <div>
        <h1>
          <I18nText
            :k="greetKey"
            :params="{ name: userName }"
          />
        </h1>
        <p>
          <I18nText
            k="learningSpace.dashboardHint"
            :params="{
              pending: teacherMetrics.pending,
              unsubmitted: teacherMetrics.unsubmitted,
            }"
          />
        </p>
      </div>
      <button
        v-if="canPublish && publishableClasses.length"
        type="button"
        class="ls-btn ls-btn--primary"
        @click="ls.openCreateAssignment()"
      >
        <I18nText k="learningSpace.createAssignment" />
      </button>
      <button
        v-else-if="canOpenClassAdmin"
        type="button"
        class="ls-btn ls-btn--primary"
        @click="ls.goCreateClass()"
      >
        <I18nText k="learningSpace.createClass" />
      </button>
    </div>

    <div class="ls-metrics">
      <button
        type="button"
        class="ls-metric"
        @click="ls.goTeacherAssignments('pending')"
      >
        <Clock3
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricPending" /></div>
        <div class="ls-metric__value">{{ teacherMetrics.pending }}</div>
        <div class="ls-metric__hint"><I18nText k="learningSpace.metricPendingHint" /></div>
      </button>
      <button
        type="button"
        class="ls-metric ls-metric--alert"
        @click="ls.goTeacherAssignments('all')"
      >
        <AlertTriangle
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label">
          <I18nText k="learningSpace.metricUnsubmitted" />
          <span class="ls-tag-focus"><I18nText k="learningSpace.focusTag" /></span>
        </div>
        <div class="ls-metric__value">{{ teacherMetrics.unsubmitted }}</div>
        <div class="ls-metric__hint">
          <I18nText k="learningSpace.metricUnsubmittedHint" />
        </div>
      </button>
      <button
        type="button"
        class="ls-metric"
        @click="ls.goTeacherAssignments('active')"
      >
        <FileText
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricActive" /></div>
        <div class="ls-metric__value">{{ teacherMetrics.active }}</div>
        <div class="ls-metric__hint"><I18nText k="learningSpace.metricActiveHint" /></div>
      </button>
      <button
        type="button"
        class="ls-metric"
        @click="ls.goTeacherClasses()"
      >
        <Users
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricClasses" /></div>
        <div class="ls-metric__value">{{ teacherMetrics.classCount }}</div>
        <div class="ls-metric__hint"><I18nText k="learningSpace.metricClassesHint" /></div>
      </button>
    </div>
  </template>

  <!-- Assignments list / detail -->
  <template v-else-if="teacherTab === 'assignments' || selectedAssignmentId != null">
    <template v-if="selectedAssignmentId == null">
      <div class="ls-page-head">
        <div>
          <h1><I18nText k="learningSpace.tabAssignments" /></h1>
          <p><I18nText k="learningSpace.assignmentsPageHint" /></p>
        </div>
        <button
          v-if="canPublish && publishableClasses.length"
          type="button"
          class="ls-btn ls-btn--primary"
          @click="ls.openCreateAssignment()"
        >
          <I18nText k="learningSpace.createAssignment" />
        </button>
        <button
          v-else-if="canOpenClassAdmin"
          type="button"
          class="ls-btn ls-btn--primary"
          @click="ls.goCreateClass()"
        >
          <I18nText k="learningSpace.createClass" />
        </button>
      </div>

      <div class="ls-filters">
        <div class="ls-pills">
          <button
            v-for="f in [
              ['all', 'learningSpace.filterAll'],
              ['active', 'learningSpace.filterActive'],
              ['pending', 'learningSpace.filterPending'],
            ] as const"
            :key="f[0]"
            type="button"
            class="ls-pill"
            :class="{ 'ls-pill--active': assignmentFilter === f[0] }"
            @click="assignmentFilter = f[0]"
          >
            <I18nText :k="f[1]" />
          </button>
        </div>
        <input
          v-model="assignmentQuery"
          class="ls-search"
          type="search"
          :placeholder="t('learningSpace.searchAssignments')"
        />
      </div>

      <div class="ls-class-filter">
        <span class="ls-class-filter__label"><I18nText k="learningSpace.class" /></span>
        <div class="ls-pills">
          <button
            v-for="c in classes"
            :key="c.id"
            type="button"
            class="ls-pill"
            :class="{ 'ls-pill--active': selectedClassId === c.id }"
            @click="ls.selectClass(c.id)"
          >
            {{ c.name }}
            <span
              v-if="c.organization_name"
              class="ls-pill__count"
              >{{ c.organization_name }}</span
            >
            <span class="ls-pill__count">{{ c.student_count }}</span>
            <span
              v-if="c.status === 'archived'"
              class="ls-pill__count"
              ><I18nText k="learningSpace.filterClosed"
            /></span>
          </button>
        </div>
      </div>

      <p
        v-if="!filteredAssignments.length"
        class="ls-empty"
      >
        <I18nText k="learningSpace.noAssignments" />
      </p>
      <div
        v-else
        class="ls-card-grid"
      >
        <article
          v-for="a in filteredAssignments"
          :key="a.id"
          class="ls-asg-card"
        >
          <div class="ls-asg-card__top">
            <div>
              <h3 class="ls-asg-card__title">{{ a.title }}</h3>
              <p class="ls-asg-card__meta">
                {{ classNameForAssignment(a) }} · <I18nText k="learningSpace.due" />：{{
                  formatLsDateTime(a.due_at)
                }}
              </p>
            </div>
            <span
              class="ls-status"
              :class="`ls-status--${assignmentStatusBadge(a).tone}`"
            >
              {{ assignmentStatusBadge(a).text }}
            </span>
          </div>
          <div class="ls-progress">
            <div class="ls-progress__row">
              <span>
                <I18nText
                  k="learningSpace.submittedProgress"
                  :params="{
                    done: progressFor(a).submitted,
                    total: progressFor(a).total,
                  }"
                />
              </span>
              <span>{{ progressFor(a).percent }}%</span>
            </div>
            <div class="ls-progress__bar">
              <div
                class="ls-progress__fill"
                :style="{ width: `${progressFor(a).percent}%` }"
              />
            </div>
          </div>
          <div class="ls-asg-card__stats">
            <span class="ls-stat-warn">
              <I18nText
                k="learningSpace.unsubmittedCount"
                :params="{
                  n: progressFor(a).unsubmitted,
                }"
              />
            </span>
            <span>
              <I18nText
                k="learningSpace.pendingReviewCount"
                :params="{
                  n: a.submitted_count ?? 0,
                }"
              />
            </span>
          </div>
          <div class="ls-asg-card__foot">
            <div class="ls-asg-card__dates">
              <template v-if="a.instructions">{{ a.instructions }}</template
              ><I18nText
                v-else
                k="learningSpace.noInstructions"
              />
            </div>
            <div class="ls-asg-card__actions">
              <button
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                @click="ls.openRequirements(a)"
              >
                <I18nText k="learningSpace.viewRequirements" />
              </button>
              <button
                v-if="canDeleteAssignment(a)"
                type="button"
                class="ls-btn ls-btn--danger-soft ls-btn--sm"
                :disabled="deletingAssignmentId === a.id"
                @click="onDelete(a)"
              >
                <I18nText k="learningSpace.deleteAssignment" />
              </button>
              <button
                type="button"
                class="ls-btn ls-btn--primary ls-btn--sm"
                @click="ls.openAssignmentDetail(a.id)"
              >
                <I18nText k="learningSpace.detailAndGrade" />
              </button>
            </div>
          </div>
        </article>
      </div>
    </template>

    <template v-else-if="selectedAssignment">
      <button
        type="button"
        class="ls-back"
        @click="ls.closeAssignmentDetail()"
      >
        <ArrowLeft :size="15" />
        <I18nText k="learningSpace.backToList" />
      </button>
      <div class="ls-page-head">
        <div>
          <h1>{{ selectedAssignment.title }}</h1>
          <p>
            {{ classNameForAssignment(selectedAssignment) }} ·
            <I18nText k="learningSpace.due" />：{{ formatLsDateTime(selectedAssignment.due_at) }}
          </p>
        </div>
        <div class="ls-page-head__actions">
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="ls.openRequirements(selectedAssignment)"
          >
            <I18nText k="learningSpace.viewRequirements" />
          </button>
          <button
            v-if="canDeleteAssignment(selectedAssignment)"
            type="button"
            class="ls-btn ls-btn--danger-soft ls-btn--sm"
            :disabled="deletingAssignmentId === selectedAssignment.id"
            @click="onDelete(selectedAssignment)"
          >
            <I18nText k="learningSpace.deleteAssignment" />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--primary ls-btn--sm"
            @click="ls.showSubmissionStatus = true"
          >
            <I18nText k="learningSpace.submissionStatus" />
          </button>
        </div>
      </div>

      <div class="ls-section-title">
        <h2><I18nText k="learningSpace.submissionsBoard" /></h2>
      </div>
      <p
        v-if="!wallSubmissions.length"
        class="ls-empty"
      >
        <I18nText k="learningSpace.noSubmissions" />
      </p>
      <div
        v-else
        class="ls-thumb-grid"
      >
        <article
          v-for="s in wallSubmissions"
          :key="s.id"
          class="ls-thumb-card"
          role="button"
          tabindex="0"
          @click="ls.openReview(s)"
          @keydown.enter.prevent="ls.openReview(s)"
        >
          <div class="ls-thumb-card__cover">
            <LearningSpaceThumbCover :thumbnail-url="s.diagram_thumbnail" />
          </div>
          <div class="ls-thumb-card__name">
            {{ formatLsStudentLabel(s) }}
          </div>
          <div class="ls-thumb-card__meta">
            {{ statusLabel(s.status) }} ·
            {{ formatLsDateTime(s.submitted_at) }}
          </div>
          <button
            type="button"
            class="ls-btn ls-btn--sm"
            :class="submissionIsReviewed(s) ? 'ls-btn--ghost' : 'ls-btn--primary'"
            @click.stop="ls.openReview(s)"
          >
            <I18nText
              v-if="submissionIsReviewed(s)"
              k="learningSpace.reviewed"
            /><I18nText
              v-else
              k="learningSpace.goReview"
            />
          </button>
        </article>
      </div>
    </template>
  </template>

  <!-- Classes -->
  <template v-else-if="teacherTab === 'classes'">
    <div class="ls-page-head">
      <div>
        <h1><I18nText k="learningSpace.tabClasses" /></h1>
        <p><I18nText k="learningSpace.classesPageHint" /></p>
      </div>
      <button
        v-if="canOpenClassAdmin"
        type="button"
        class="ls-btn ls-btn--primary"
        @click="ls.goCreateClass()"
      >
        <I18nText k="learningSpace.createClass" />
      </button>
    </div>
    <p
      v-if="!classes.length"
      class="ls-empty"
    >
      <I18nText k="learningSpace.noClassesYet" />
    </p>
    <div class="ls-class-row">
      <button
        v-for="c in classes"
        :key="c.id"
        type="button"
        class="ls-class-card"
        :class="{ 'ls-class-card--active': selectedClassId === c.id }"
        @click="ls.selectClass(c.id)"
      >
        <h3>{{ c.name }}</h3>
        <p v-if="c.organization_name || c.teacher_name">
          {{ [c.organization_name, c.teacher_name].filter(Boolean).join(' · ') }}
        </p>
        <p>
          <I18nText
            k="learningSpace.studentCount"
            :params="{ n: c.student_count }"
          />
          ·
          {{ c.class_code }}
          <template v-if="c.status === 'archived'">
            · <I18nText k="learningSpace.filterClosed" />
          </template>
        </p>
        <p>
          <span class="ls-link"><I18nText k="learningSpace.viewRoster" /></span>
        </p>
      </button>
    </div>
    <section
      v-if="selectedClass"
      class="ls-roster"
    >
      <h2 style="margin: 0; font-size: 1.05rem; font-weight: 720">
        {{ selectedClass.name }} — <I18nText k="learningSpace.rosterTitle" />
      </h2>
      <p class="ls-muted">
        <I18nText
          k="learningSpace.rosterLoginHint"
          :params="{ n: classStudents.length || selectedClass.student_count }"
        />
      </p>
      <p class="ls-muted ls-roster__login-how">
        <I18nText k="learningSpace.rosterLoginHow" />
      </p>
      <div
        v-if="classStudents.length"
        class="ls-roster-table-wrap"
      >
        <table class="ls-roster-table">
          <thead>
            <tr>
              <th><I18nText k="learningSpace.rosterColName" /></th>
              <th><I18nText k="learningSpace.rosterColClassCode" /></th>
              <th><I18nText k="learningSpace.rosterColPassword" /></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in classStudents"
              :key="s.id"
            >
              <td class="ls-roster-table__name">{{ s.name }}</td>
              <td>
                <code class="ls-roster-code">{{ selectedClass.class_code }}</code>
              </td>
              <td>
                <code class="ls-roster-code">
                  <template v-if="s.initial_password">{{ s.initial_password }}</template
                  ><I18nText
                    v-else
                    k="learningSpace.passwordHidden"
                  />
                </code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p
        v-else
        class="ls-empty"
      >
        <I18nText k="learningSpace.rosterEmpty" />
      </p>
    </section>
  </template>
</template>
