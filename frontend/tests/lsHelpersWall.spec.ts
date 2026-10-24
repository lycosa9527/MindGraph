import { describe, expect, it } from 'vitest'

import {
  assignmentAllowsResubmit,
  assignmentIsClosed,
  assignmentProgress,
  assignmentWithGrader,
  assignmentWithReviewCounted,
  beijingWallClockToIso,
  filterStudentAssignments,
  filterTeacherAssignments,
  formatLsDateTime,
  formatLsStudentLabel,
  homeworkGraderLabel,
  homeworkPublisherName,
  publishedAssignmentCount,
  studentCanOpenAssignment,
  studentCanResubmitAssignment,
  studentCanSubmitAssignment,
  studentCanViewAssignmentWall,
  submissionGraderNames,
  submissionHasUnnamedReview,
  submissionIsReviewed,
  unsubmittedTopicRows,
} from '@/composables/learningSpace/lsHelpers'
import type { LearningAssignment } from '@/utils/learningSpaceApi'
import { must } from '@/utils/must'

describe('lsHelpers learning space wall', () => {
  it('counts active and closed homework and skips drafts', () => {
    expect(
      publishedAssignmentCount([
        { status: 'active' },
        { status: 'active' },
        { status: 'closed' },
        { status: 'draft' },
      ])
    ).toBe(3)
    expect(publishedAssignmentCount([])).toBe(0)
  })

  it('shows naive UTC timestamps as Beijing time', () => {
    expect(formatLsDateTime('2026-10-22T06:00:49')).toBe('2026/10/22 14:00:49')
    expect(formatLsDateTime('2026-10-22T06:00:49Z')).toBe('2026/10/22 14:00:49')
    expect(formatLsDateTime('2026-10-22T06:00:49+00:00')).toBe('2026/10/22 14:00:49')
    expect(formatLsDateTime('2026-10-22T14:00:49+08:00')).toBe('2026/10/22 14:00:49')
    expect(formatLsDateTime(null)).toBe('—')
  })

  it('reads due-date inputs as Beijing wall time', () => {
    expect(beijingWallClockToIso('2026-10-22T18:00')).toBe('2026-10-22T10:00:00.000Z')
    expect(beijingWallClockToIso('2026-10-22T18:00:30')).toBe('2026-10-22T10:00:30.000Z')
  })

  it('closes an assignment from the UTC instant, not the browser clock', () => {
    const open: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '作业',
      instructions: '',
      template_diagram_id: 't1',
      due_at: '2099-01-01T00:00:00',
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
    }
    const closed: LearningAssignment = { ...open, due_at: '2000-01-01T00:00:00' }
    expect(assignmentIsClosed(open)).toBe(false)
    expect(assignmentIsClosed(closed)).toBe(true)
  })

  it('formats student name with organization', () => {
    expect(
      formatLsStudentLabel({
        student_name: '李俐俐',
        student_user_id: 1,
        organization_name: '北师大思维训练中心',
      })
    ).toBe('李俐俐 · 北师大思维训练中心')
  })

  it('hides assignment wall until the student submits', () => {
    const draft: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '作业',
      instructions: '',
      template_diagram_id: 't1',
      due_at: null,
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
      submission: {
        id: 1,
        assignment_id: 1,
        student_user_id: 2,
        diagram_id: 'd1',
        status: 'draft',
        submitted_at: null,
        due_at_override: null,
      },
    }
    expect(studentCanViewAssignmentWall(draft)).toBe(false)
    must(draft.submission).status = 'submitted'
    expect(studentCanViewAssignmentWall(draft)).toBe(true)
  })

  it('allows resubmit before deadline when enabled', () => {
    const submitted: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '作业',
      instructions: '',
      template_diagram_id: 't1',
      due_at: new Date(Date.now() + 86_400_000).toISOString(),
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
      submission: {
        id: 1,
        assignment_id: 1,
        student_user_id: 2,
        diagram_id: 'd1',
        status: 'submitted',
        submitted_at: new Date().toISOString(),
        due_at_override: null,
      },
    }
    expect(assignmentAllowsResubmit(submitted)).toBe(true)
    expect(studentCanResubmitAssignment(submitted)).toBe(true)
    expect(studentCanOpenAssignment(submitted)).toBe(true)
    expect(studentCanSubmitAssignment(submitted)).toBe(true)
  })

  it('blocks resubmit when teacher disables it', () => {
    const submitted: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '作业',
      instructions: '',
      template_diagram_id: 't1',
      due_at: null,
      ai_permissions: { allow_resubmit: false },
      status: 'active',
      created_by: 1,
      created_at: null,
      submission: {
        id: 1,
        assignment_id: 1,
        student_user_id: 2,
        diagram_id: 'd1',
        status: 'submitted',
        submitted_at: new Date().toISOString(),
        due_at_override: null,
      },
    }
    expect(assignmentAllowsResubmit(submitted)).toBe(false)
    expect(studentCanOpenAssignment(submitted)).toBe(false)
  })

  it('labels publishers and graders on homework cards', () => {
    expect(homeworkPublisherName('  王老师 ')).toBe('王老师')
    expect(homeworkPublisherName('  ')).toBe('—')
    expect(homeworkGraderLabel([' 李助教 ', '', ' 王老师 '])).toBe('李助教、王老师')
    expect(homeworkGraderLabel([])).toBe('')
    expect(submissionGraderNames({ reviewer_name: ' 李助教 ' })).toEqual(['李助教'])
    expect(submissionGraderNames(null)).toEqual([])
  })

  it('names a review only when the grader is known', () => {
    const graded = {
      reviewed_at: '2026-10-24T00:00:00Z',
      review_comment: null,
      review_scores: null,
      reviewer_name: '李助教',
    }
    expect(submissionHasUnnamedReview(graded)).toBe(false)
    expect(submissionHasUnnamedReview({ ...graded, reviewer_name: '  ' })).toBe(true)
    expect(
      submissionHasUnnamedReview({
        reviewed_at: null,
        review_comment: null,
        review_scores: null,
      })
    ).toBe(false)
    expect(submissionIsReviewed({ reviewed_by: 8 })).toBe(true)
    expect(submissionIsReviewed({ review_liked: true })).toBe(true)
    expect(submissionIsReviewed({ review_pinned: true })).toBe(true)
  })

  it('adds the grader who just saved a review onto the homework card', () => {
    const card: LearningAssignment = {
      id: 4,
      class_id: 1,
      title: '作业',
      instructions: '',
      template_diagram_id: 't1',
      due_at: null,
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_by_name: '王老师',
      created_at: null,
    }
    const named = assignmentWithGrader(card, ' 李助教 ')
    expect(named.reviewer_names).toEqual(['李助教'])
    expect(assignmentWithGrader(named, '李助教')).toBe(named)
    const both = assignmentWithGrader(named, '王老师')
    expect(both.reviewer_names).toEqual(['李助教', '王老师'])
    const unnamed = assignmentWithGrader(card, ' ')
    expect(unnamed.has_unnamed_review).toBe(true)
    expect(unnamed.reviewer_names).toBeUndefined()
  })

  it('keeps graded work in the submitted total and out of pending review', () => {
    const card: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '用双气泡图比较梅花和荷花',
      instructions: '',
      template_diagram_id: 't1',
      due_at: null,
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
      student_count: 7,
      submitted_count: 1,
      reviewed_count: 1,
    }
    const progress = assignmentProgress(card)
    expect(progress).toMatchObject({
      submitted: 1,
      total: 7,
      percent: 14,
      unsubmitted: 6,
      pendingReview: 0,
    })
    expect(progress.submitted + progress.unsubmitted).toBe(progress.total)
    expect(progress.pendingReview).toBeLessThanOrEqual(progress.submitted)
    const waiting = assignmentWithReviewCounted({ ...card, reviewed_count: 0 }, false)
    expect(assignmentProgress(waiting).pendingReview).toBe(0)
    expect(assignmentWithReviewCounted(waiting, true)).toBe(waiting)
    expect(filterTeacherAssignments([waiting], 'pending', '')).toEqual([])
    expect(filterTeacherAssignments([{ ...card, reviewed_count: 0 }], 'pending', '')).toEqual([
      { ...card, reviewed_count: 0 },
    ])
  })

  it('keeps unsubmitted counts on each assignment topic', () => {
    const base: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '光合作用',
      instructions: '',
      template_diagram_id: 't1',
      due_at: null,
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
      student_count: 7,
      submitted_count: 0,
    }
    const classes = new Map([
      [1, { name: '一班', student_count: 7 }],
      [2, { name: '二班', student_count: 7 }],
    ])
    const rows = unsubmittedTopicRows(
      [
        base,
        { ...base, id: 2, title: '细胞结构', submitted_count: 0 },
        { ...base, id: 3, title: '已交齐', submitted_count: 7 },
        { ...base, id: 4, class_id: 2, title: '光合作用', student_count: undefined },
      ],
      classes
    )
    expect(rows.map((row) => [row.title, row.className, row.unsubmitted])).toEqual([
      ['光合作用', '一班', 7],
      ['光合作用', '二班', 7],
      ['细胞结构', '', 7],
    ])
  })

  it('splits student homework into todo, submitted, and open deadlines', () => {
    const base: LearningAssignment = {
      id: 1,
      class_id: 1,
      title: '未开始',
      instructions: '',
      template_diagram_id: 't1',
      due_at: '2099-01-01T00:00:00',
      ai_permissions: {},
      status: 'active',
      created_by: 1,
      created_at: null,
    }
    const submitted: LearningAssignment = {
      ...base,
      id: 2,
      title: '已交',
      submission: {
        id: 2,
        assignment_id: 2,
        student_user_id: 9,
        diagram_id: 'd2',
        status: 'submitted',
        submitted_at: '2026-10-01T00:00:00',
        due_at_override: null,
      },
    }
    const returned: LearningAssignment = {
      ...base,
      id: 3,
      title: '退回',
      due_at: null,
      submission: {
        id: 3,
        assignment_id: 3,
        student_user_id: 9,
        diagram_id: 'd3',
        status: 'returned',
        submitted_at: null,
        due_at_override: null,
      },
    }
    const overdue: LearningAssignment = {
      ...base,
      id: 4,
      title: '过期',
      due_at: '2000-01-01T00:00:00',
    }
    const rows = [base, submitted, returned, overdue]
    expect(filterStudentAssignments(rows, 'all').map((row) => row.id)).toEqual([1, 2, 3, 4])
    expect(filterStudentAssignments(rows, 'todo').map((row) => row.id)).toEqual([1, 3, 4])
    expect(filterStudentAssignments(rows, 'submitted').map((row) => row.id)).toEqual([2])
    expect(filterStudentAssignments(rows, 'urgent').map((row) => row.id)).toEqual([1])
  })
})
