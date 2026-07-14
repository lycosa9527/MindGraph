/**
 * Case Square field meta from API (subjects, grades, recommended tags).
 */
import { computed } from 'vue'

import { useQuery } from '@tanstack/vue-query'

import { GRADE_OPTIONS, SUBJECT_OPTIONS, sortCaseSquareFieldValues } from '@/components/caseSquare/caseSquareShared'
import { getCaseSquareMeta, type CaseSquareMeta } from '@/utils/apiClient'

export function useCaseSquareMeta() {
  const query = useQuery({
    queryKey: ['caseSquareMeta'],
    queryFn: () => getCaseSquareMeta(),
    staleTime: 5 * 60 * 1000,
  })

  const meta = computed((): CaseSquareMeta | undefined => query.data.value)

  const subjectOptions = computed(() => {
    const fromApi = meta.value?.subjects
    if (fromApi?.length) {
      return sortCaseSquareFieldValues(fromApi, SUBJECT_OPTIONS).map((s) => ({ value: s, label: s }))
    }
    return SUBJECT_OPTIONS.map((s) => ({ value: s, label: s }))
  })

  const gradeOptions = computed(() => {
    const fromApi = meta.value?.grades
    if (fromApi?.length) {
      return sortCaseSquareFieldValues(fromApi, GRADE_OPTIONS).map((g) => ({ value: g, label: g }))
    }
    return GRADE_OPTIONS.map((g) => ({ value: g, label: g }))
  })

  const recommendedTags = computed(() => meta.value?.recommended_tags ?? [])

  return {
    meta,
    subjectOptions,
    gradeOptions,
    recommendedTags,
    isLoading: computed(() => query.isLoading.value),
    refetch: () => query.refetch(),
  }
}
