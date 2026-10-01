import { describe, expect, it } from 'vitest'

import {
  assignmentAllowsResubmit,
  formatLsStudentLabel,
  studentCanOpenAssignment,
  studentCanResubmitAssignment,
  studentCanSubmitAssignment,
  studentCanViewAssignmentWall,
} from '@/composables/learningSpace/lsHelpers'
import type { LearningAssignment } from '@/utils/learningSpaceApi'

describe('lsHelpers learning space wall', () => {
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
      submission: { id: 1, assignment_id: 1, student_user_id: 2, diagram_id: 'd1', status: 'draft', submitted_at: null, due_at_override: null },
    }
    expect(studentCanViewAssignmentWall(draft)).toBe(false)
    draft.submission!.status = 'submitted'
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
})
