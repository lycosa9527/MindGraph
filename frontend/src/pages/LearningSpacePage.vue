<script setup lang="ts">
/**
 * Learning Space shell. Teacher and student bodies read the store.
 * Route: /learning-space and /m/learning-space
 */
import { onMounted, onUnmounted, ref } from 'vue'

import { storeToRefs } from 'pinia'

import LearningSpaceAssignModal from '@/components/learningSpace/LearningSpaceAssignModal.vue'
import LearningSpaceHeader from '@/components/learningSpace/LearningSpaceHeader.vue'
import LearningSpaceRequirementsModal from '@/components/learningSpace/LearningSpaceRequirementsModal.vue'
import LearningSpaceReviewModal from '@/components/learningSpace/LearningSpaceReviewModal.vue'
import LearningSpaceStudentBody from '@/components/learningSpace/LearningSpaceStudentBody.vue'
import LearningSpaceSubmissionStatusModal from '@/components/learningSpace/LearningSpaceSubmissionStatusModal.vue'
import LearningSpaceTeacherBody from '@/components/learningSpace/LearningSpaceTeacherBody.vue'
import { swissGlassConfirm, useLanguage, useNotifications } from '@/composables'
import { assignmentEvalDimensions } from '@/composables/learningSpace/lsHelpers'
import { useLearningSpaceStore } from '@/stores/learningSpace'
import '@/styles/learning-space.css'

const { t } = useLanguage()
const notify = useNotifications()
const ls = useLearningSpaceStore()
const {
  loading,
  isStudent,
  isPilot,
  showLsHeader,
  teacherTab,
  studentTab,
  pendingGradeCount,
  studentTodoCount,
  showShellSwitch,
  mustChangePassword,
  changingPassword,
  context,
  showCreateForm,
  publishableClasses,
  showSubmissionStatus,
  selectedAssignment,
  classStudents,
  submittedStudentIds,
  showReview,
  reviewMode,
  reviewSubmission,
  studentAssignments,
  showRequirements,
  reqAssignment,
} = storeToRefs(ls)

const newPassword = ref('')
const confirmPassword = ref('')

function classNameForAssignment(classId: number): string {
  return ls.classes.find((row) => row.id === classId)?.name || t('learningSpace.class')
}

async function onChangePassword(): Promise<void> {
  if (newPassword.value.length < 6) {
    notify.warningKey('learningSpace.passwordMin6')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    notify.warningKey('auth.modal.passwordMismatch')
    return
  }
  const message = await ls.changePassword(newPassword.value)
  if (message === null) {
    newPassword.value = ''
    confirmPassword.value = ''
    notify.successKey('learningSpace.savePassword')
    return
  }
  notify.error(message || t('learningSpace.saveFailed'))
}

async function onReturnSubmission(submissionId: number): Promise<void> {
  try {
    await swissGlassConfirm(t('learningSpace.returnConfirm'), t('learningSpace.return'), {
      confirmButtonText: t('learningSpace.return'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  await ls.returnForRevision(submissionId)
}

onMounted(() => {
  ls.attach()
})

onUnmounted(() => {
  ls.detach()
})
</script>

<template>
  <div class="ls-app">
    <LearningSpaceHeader
      v-if="showLsHeader"
      :mode="isStudent ? 'student' : 'teacher'"
      :teacher-tab="teacherTab"
      :student-tab="studentTab"
      :pending-badge="isStudent ? studentTodoCount : pendingGradeCount"
      :show-shell-switch="showShellSwitch"
      @update:teacher-tab="ls.setTeacherTab"
      @update:student-tab="ls.setStudentTab"
      @update:mode="ls.setShellMode"
    />

    <div class="ls-app__body">
      <div class="ls-app__inner">
        <p
          v-if="loading"
          class="ls-muted"
        >
          <I18nText k="common.loading" />
        </p>

        <section
          v-else-if="isStudent && mustChangePassword"
          class="ls-gate"
        >
          <h2><I18nText k="learningSpace.changePasswordTitle" /></h2>
          <p class="ls-muted"><I18nText k="learningSpace.changePasswordHint" /></p>
          <div
            class="ls-form-grid"
            style="margin-top: 1rem"
          >
            <label class="ls-field">
              <I18nText k="auth.modal.newPassword" />
              <input
                v-model="newPassword"
                type="password"
                autocomplete="new-password"
              />
            </label>
            <label class="ls-field">
              <I18nText k="auth.modal.confirmPassword" />
              <input
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
              />
            </label>
            <button
              type="button"
              class="ls-btn ls-btn--primary"
              :disabled="
                changingPassword || newPassword.length < 6 || newPassword !== confirmPassword
              "
              @click="onChangePassword"
            >
              <I18nText k="learningSpace.savePassword" />
            </button>
          </div>
        </section>

        <LearningSpaceTeacherBody v-else-if="isPilot" />
        <LearningSpaceStudentBody v-else-if="isStudent" />

        <section
          v-else-if="!loading"
          class="ls-empty"
        >
          <I18nText k="learningSpace.noAccess" />
        </section>
      </div>
    </div>

    <LearningSpaceAssignModal
      v-model="showCreateForm"
      :classes="publishableClasses"
      @created="ls.onAssignmentCreated()"
    />
    <LearningSpaceSubmissionStatusModal
      v-model="showSubmissionStatus"
      :class-name="selectedAssignment ? classNameForAssignment(selectedAssignment.class_id) : ''"
      :students="classStudents"
      :submitted-ids="[...submittedStudentIds]"
    />
    <LearningSpaceReviewModal
      v-model="showReview"
      :mode="reviewMode"
      :submission="reviewSubmission"
      :dimensions="
        reviewMode === 'edit'
          ? assignmentEvalDimensions(selectedAssignment)
          : assignmentEvalDimensions(
              studentAssignments.find((a) => a.id === reviewSubmission?.assignment_id) ?? null
            )
      "
      :assignment-title="
        reviewMode === 'edit'
          ? selectedAssignment?.title || ''
          : reviewSubmission?.assignment_title || ''
      "
      @save="ls.saveReview"
      @extend="ls.extendDue"
      @return="onReturnSubmission"
    />
    <LearningSpaceRequirementsModal
      v-model="showRequirements"
      :assignment="reqAssignment"
      :audience="isStudent ? 'student' : 'teacher'"
      :class-name="
        reqAssignment
          ? isStudent
            ? context?.class?.name || t('learningSpace.class')
            : classNameForAssignment(reqAssignment.class_id)
          : ''
      "
    />
  </div>
</template>
