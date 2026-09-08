import { ref } from 'vue'

const STORAGE_KEY = 'mindgraph.mindmap.followNodeStyleToolbar'

const followEnabled = ref(readStoredFollow())

function readStoredFollow(): boolean {
  if (typeof localStorage === 'undefined') return true
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === '0') return false
    if (raw === '1') return true
  } catch {
    /* private mode */
  }
  return true
}

function persistFollow(value: boolean): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  } catch {
    /* private mode */
  }
}

export function setFollowNodeStyleToolbar(value: boolean): void {
  followEnabled.value = value
  persistFollow(value)
}

/** When on, the node style bar follows the selection; when off it is hidden. */
export function useFollowNodeStyleToolbar() {
  return {
    followEnabled,
    setFollowEnabled: setFollowNodeStyleToolbar,
  }
}
