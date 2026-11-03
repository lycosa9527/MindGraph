/**
 * After a student replaces the initial password, the next login card
 * opens on the student tab with class code and name filled in.
 */

const STORAGE_KEY = 'mg_student_password_relogin'

export interface StudentReloginPrefill {
  classCode: string
  name: string
  /** True when the new password was stored and the old session was ended. */
  passwordSaved: boolean
}

export function stashStudentRelogin(prefill: StudentReloginPrefill): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(prefill))
  } catch {
    // Private mode: the login card still opens, without prefill.
  }
}

export function takeStudentRelogin(): StudentReloginPrefill | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    sessionStorage.removeItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as {
      classCode?: unknown
      name?: unknown
      passwordSaved?: unknown
    }
    return {
      classCode: typeof parsed.classCode === 'string' ? parsed.classCode : '',
      name: typeof parsed.name === 'string' ? parsed.name : '',
      passwordSaved: parsed.passwordSaved === true,
    }
  } catch {
    return null
  }
}
