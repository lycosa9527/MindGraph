/**
 * Freezes the account menu onto a course slide when that slide is locked.
 */
import { type Ref, inject, onBeforeUnmount, onMounted, ref } from 'vue'

import { refreshUserDropdownMenu } from '@/composables/sidebar/useUserDropdownMenu'
import { TRAINING_LOCK_SCOPE, registerTrainingUiLock } from '@/composables/training/trainingUiLock'

interface DropdownHandle {
  handleOpen?: () => void
  handleClose?: () => void
}

export function useSidebarUserMenuLock(
  dropdownRef: Ref<DropdownHandle | null>,
  collapsedDropdownRef: Ref<DropdownHandle | null>
): {
  onUserMenuVisible: (open: boolean) => void
} {
  const lockScope = inject(TRAINING_LOCK_SCOPE, '')
  const menuOpen = ref(false)
  let releaseMenuLock = (): void => undefined

  function onUserMenuVisible(open: boolean): void {
    menuOpen.value = open
    if (open) void refreshUserDropdownMenu()
  }

  function setUserMenuOpen(open: boolean): void {
    const api = dropdownRef.value || collapsedDropdownRef.value
    if (open && api?.handleOpen) {
      api.handleOpen()
      return
    }
    if (!open && api?.handleClose) {
      api.handleClose()
      return
    }
    menuOpen.value = open
  }

  onMounted(() => {
    releaseMenuLock = registerTrainingUiLock({
      key: 'user-dropdown',
      scope: lockScope,
      isOpen: () => menuOpen.value,
      setOpen: setUserMenuOpen,
    })
  })

  onBeforeUnmount(() => {
    releaseMenuLock()
  })

  return { onUserMenuVisible }
}
