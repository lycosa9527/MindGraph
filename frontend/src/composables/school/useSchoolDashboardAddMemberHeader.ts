/**
 * Lets AdminPage header open the school dashboard add-member dialog.
 */
import { ref } from 'vue'

const openRequestVersion = ref(0)

export function requestOpenSchoolAddMemberDialog(): void {
  openRequestVersion.value += 1
}

export function useSchoolDashboardAddMemberOpenRequest() {
  return openRequestVersion
}
