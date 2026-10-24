<script setup lang="ts">
/**
 * Student Learning Space: home, class assignments, portfolio.
 * Data and loads live on the Learning Space store.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { ArrowLeft, ClipboardList, Clock3, FileText, Users } from '@lucide/vue'

import LearningSpaceCreditLine from '@/components/learningSpace/LearningSpaceCreditLine.vue'
import LearningSpaceThumbCover from '@/components/learningSpace/LearningSpaceThumbCover.vue'
import LearningSpaceWorkGrader from '@/components/learningSpace/LearningSpaceWorkGrader.vue'
import { useLanguage } from '@/composables'
import {
  assignmentDiagramType,
  beijingHour,
  formatLsDateTime,
  formatLsStudentLabel,
  greetHourLabel,
  studentAssignmentDone,
  studentCanOpenAssignment,
  studentCanResubmitAssignment,
  submissionGraderNames,
  submissionHasUnnamedReview,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores'
import { useLearningSpaceStore } from '@/stores/learningSpace'

const { t } = useLanguage()
const authStore = useAuthStore()
const ls = useLearningSpaceStore()
const {
  studentTab,
  studentDetail,
  context,
  studentTodoCount,
  studentSubmittedCount,
  myPortfolio,
  studentUrgentCount,
  studentAssignmentFilter,
  filteredStudentAssignments,
  studentCanViewDetailWall,
  detailClassWall,
  myDetailSubmission,
} = storeToRefs(ls)

const studentAssignmentFilters = [
  { id: 'all', labelKey: 'learningSpace.filterAll' },
  { id: 'todo', labelKey: 'learningSpace.metricTodo' },
  { id: 'submitted', labelKey: 'learningSpace.metricSubmitted' },
  { id: 'urgent', labelKey: 'learningSpace.metricUrgent' },
] as const

const userName = computed(
  () => authStore.user?.username || authStore.user?.phone || t('learningSpace.userFallback')
)
const greetKey = computed(() => {
  const label = greetHourLabel(beijingHour())
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
</script>

<template>
  <template v-if="studentTab === 'home' && !studentDetail">
    <div class="ls-page-head">
      <div>
        <h1>
          <I18nText
            :k="greetKey"
            :params="{ name: userName }"
          />
        </h1>
        <p v-if="context?.class">{{ context.class.name }} · {{ context.class.class_code }}</p>
      </div>
    </div>
    <div class="ls-metrics">
      <button
        type="button"
        class="ls-metric"
        @click="ls.goStudentAssignments('todo')"
      >
        <ClipboardList
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricTodo" /></div>
        <div class="ls-metric__value">{{ studentTodoCount }}</div>
      </button>
      <button
        type="button"
        class="ls-metric"
        @click="ls.goStudentAssignments('submitted')"
      >
        <FileText
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricSubmitted" /></div>
        <div class="ls-metric__value">{{ studentSubmittedCount }}</div>
      </button>
      <button
        type="button"
        class="ls-metric"
        @click="ls.setStudentTab('works')"
      >
        <Users
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricWorks" /></div>
        <div class="ls-metric__value">{{ myPortfolio.length }}</div>
      </button>
      <button
        type="button"
        class="ls-metric ls-metric--alert"
        @click="ls.goStudentAssignments('urgent')"
      >
        <Clock3
          class="ls-metric__icon"
          :size="20"
        />
        <div class="ls-metric__label"><I18nText k="learningSpace.metricUrgent" /></div>
        <div class="ls-metric__value">{{ studentUrgentCount }}</div>
      </button>
    </div>
  </template>

  <template v-else-if="studentTab === 'assignments' || studentDetail">
    <template v-if="!studentDetail">
      <div class="ls-page-head">
        <div>
          <h1><I18nText k="learningSpace.tabClassAssignments" /></h1>
          <p><I18nText k="learningSpace.classAssignmentsHint" /></p>
        </div>
      </div>
      <div class="ls-filters">
        <div class="ls-pills">
          <button
            v-for="f in studentAssignmentFilters"
            :key="f.id"
            type="button"
            class="ls-pill"
            :class="{ 'ls-pill--active': studentAssignmentFilter === f.id }"
            @click="ls.goStudentAssignments(f.id)"
          >
            <I18nText :k="f.labelKey" />
          </button>
        </div>
      </div>
      <p
        v-if="!filteredStudentAssignments.length"
        class="ls-empty"
      >
        <I18nText k="learningSpace.noAssignments" />
      </p>
      <div
        v-else
        class="ls-card-grid"
      >
        <article
          v-for="a in filteredStudentAssignments"
          :key="a.id"
          class="ls-asg-card"
          role="button"
          tabindex="0"
          @click="ls.openStudentDetail(a.id)"
          @keydown.enter.prevent="ls.openStudentDetail(a.id)"
        >
          <div class="ls-asg-card__top">
            <h3 class="ls-asg-card__title">{{ a.title }}</h3>
            <span
              class="ls-status"
              :class="`ls-status--${
                studentAssignmentDone(a)
                  ? 'active'
                  : a.submission?.status === 'returned'
                    ? 'closed'
                    : 'draft'
              }`"
            >
              {{ statusLabel(a.submission?.status) }}
            </span>
          </div>
          <p class="ls-asg-card__meta">
            <I18nText k="learningSpace.due" />：{{ formatLsDateTime(a.due_at) }}
          </p>
          <p class="ls-asg-card__meta">
            <LearningSpaceCreditLine
              :publisher-name="a.created_by_name"
              :grader-names="submissionGraderNames(a.submission)"
              :unnamed-review="submissionHasUnnamedReview(a.submission)"
            />
          </p>
          <div class="ls-asg-card__actions">
            <button
              type="button"
              class="ls-btn ls-btn--primary ls-btn--sm"
              @click.stop="ls.openStudentDetail(a.id)"
            >
              <I18nText k="learningSpace.viewAssignment" />
            </button>
          </div>
        </article>
      </div>
    </template>
    <template v-else-if="studentDetail">
      <button
        type="button"
        class="ls-back"
        @click="ls.closeStudentDetail()"
      >
        <ArrowLeft :size="15" />
        <I18nText k="learningSpace.backToList" />
      </button>
      <div class="ls-page-head">
        <div>
          <h1>{{ studentDetail.title }}</h1>
          <p class="ls-detail-meta">
            <I18nText k="learningSpace.diagramTypeLabel" />
            <I18nText :k="`learningSpace.diagramType.${assignmentDiagramType(studentDetail)}`" />
            <template v-if="studentDetail.due_at">
              · <I18nText k="learningSpace.due" />
              {{ formatLsDateTime(studentDetail.due_at) }}
            </template>
            ·
            <LearningSpaceCreditLine
              :publisher-name="studentDetail.created_by_name"
              :grader-names="submissionGraderNames(studentDetail.submission)"
              :unnamed-review="submissionHasUnnamedReview(studentDetail.submission)"
            />
          </p>
        </div>
        <div class="ls-page-head__actions">
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="ls.openRequirements(studentDetail)"
          >
            <I18nText k="learningSpace.viewRequirements" />
          </button>
          <button
            v-if="studentCanOpenAssignment(studentDetail)"
            type="button"
            class="ls-btn ls-btn--primary ls-btn--sm"
            @click="ls.openStudentAssignment(studentDetail)"
          >
            <I18nText
              v-if="studentCanResubmitAssignment(studentDetail)"
              k="learningSpace.editAndResubmit"
            /><I18nText
              v-else
              k="learningSpace.doHomework"
            />
          </button>
          <button
            v-else-if="!studentAssignmentDone(studentDetail)"
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            disabled
          >
            <I18nText k="learningSpace.homeworkClosed" />
          </button>
          <button
            v-if="myDetailSubmission && !studentCanResubmitAssignment(studentDetail)"
            type="button"
            class="ls-btn ls-btn--primary ls-btn--sm"
            @click="ls.openReview(myDetailSubmission, 'view')"
          >
            <I18nText k="learningSpace.myWorkBtn" />
          </button>
          <button
            v-else-if="myDetailSubmission && studentCanResubmitAssignment(studentDetail)"
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="ls.openReview(myDetailSubmission, 'view')"
          >
            <I18nText k="learningSpace.myWorkBtn" />
          </button>
        </div>
      </div>

      <p
        v-if="studentDetail.instructions"
        class="ls-detail-brief"
      >
        {{ studentDetail.instructions }}
      </p>

      <section v-if="studentCanViewDetailWall">
        <div class="ls-section-title">
          <h2><I18nText k="learningSpace.assignmentWall" /></h2>
        </div>
        <p
          v-if="!detailClassWall.length"
          class="ls-empty"
        >
          <I18nText k="learningSpace.noClassWallYet" />
        </p>
        <div
          v-else
          class="ls-thumb-grid"
        >
          <article
            v-for="s in detailClassWall"
            :key="s.id"
            class="ls-thumb-card"
            role="button"
            tabindex="0"
            @click="ls.openReview(s, 'view')"
            @keydown.enter.prevent="ls.openReview(s, 'view')"
          >
            <div class="ls-thumb-card__cover">
              <LearningSpaceThumbCover :thumbnail-url="s.diagram_thumbnail" />
            </div>
            <div class="ls-thumb-card__name">
              {{ formatLsStudentLabel(s) }}
            </div>
            <div class="ls-thumb-card__meta">
              {{ formatLsDateTime(s.submitted_at) }}
              <LearningSpaceWorkGrader :submission="s" />
            </div>
          </article>
        </div>
      </section>
      <p
        v-else
        class="ls-empty"
      >
        <I18nText k="learningSpace.classWallSubmitFirst" />
      </p>
    </template>
  </template>

  <template v-else-if="studentTab === 'works'">
    <div class="ls-page-head">
      <div>
        <h1><I18nText k="learningSpace.tabMyPortfolio" /></h1>
        <p><I18nText k="learningSpace.myPortfolioHint" /></p>
      </div>
    </div>
    <p
      v-if="!myPortfolio.length"
      class="ls-empty"
    >
      <I18nText k="learningSpace.noWorks" />
    </p>
    <div
      v-else
      class="ls-thumb-grid"
    >
      <article
        v-for="s in myPortfolio"
        :key="s.id"
        class="ls-thumb-card"
        role="button"
        tabindex="0"
        @click="ls.openReview(s, 'view')"
        @keydown.enter.prevent="ls.openReview(s, 'view')"
      >
        <div class="ls-thumb-card__cover">
          <LearningSpaceThumbCover :thumbnail-url="s.diagram_thumbnail" />
        </div>
        <div class="ls-thumb-card__name">
          <template v-if="s.assignment_title">{{ s.assignment_title }}</template
          ><I18nText
            v-else
            k="learningSpace.assignments"
          />
        </div>
        <div class="ls-thumb-card__meta">
          {{ statusLabel(s.status) }}
          <LearningSpaceWorkGrader :submission="s" />
        </div>
      </article>
    </div>
  </template>
</template>
