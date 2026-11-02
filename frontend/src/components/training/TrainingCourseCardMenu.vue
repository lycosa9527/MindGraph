<script setup lang="ts">
import { ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Edit3, MoreHorizontal, Trash2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { promptSwissGlassName } from '@/composables/sidebar/promptSwissGlassName'
import { titleAfterRename } from '@/composables/training/trainingCourseTitle'
import type { TrainingCourse } from '@/types/training'
import { deleteTrainingCourse, saveTrainingCourse } from '@/utils/trainingApi'

const props = defineProps<{
  course: TrainingCourse
}>()

const emit = defineEmits<{
  renamed: [course: TrainingCourse]
  deleted: [courseId: string]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const busy = ref(false)

const DELETE_DENIED: Record<string, 'training.course.systemLocked' | 'training.course.ownerOnly'> =
  {
    'System courses cannot be deleted': 'training.course.systemLocked',
    'Only the owner may delete this course': 'training.course.ownerOnly',
  }

function deleteFailureKey(
  error: unknown
): 'training.course.systemLocked' | 'training.course.ownerOnly' | 'training.course.deleteFailed' {
  const message = error instanceof Error ? error.message : ''
  return DELETE_DENIED[message] ?? 'training.course.deleteFailed'
}

async function renameCourse(): Promise<void> {
  const course = props.course
  const name = await promptSwissGlassName(
    t,
    'training.course.renameTitle',
    'training.course.renamePrompt',
    'training.courses',
    course.title,
    { maxLength: 120 }
  )
  if (!name || name === course.title.trim()) return
  busy.value = true
  try {
    const saved = await saveTrainingCourse(course.id, { title: titleAfterRename(course, name) })
    notify.successKey('training.course.renamed')
    emit('renamed', saved)
  } catch {
    notify.errorKey('training.course.renameFailed')
  } finally {
    busy.value = false
  }
}

async function removeCourse(): Promise<void> {
  const course = props.course
  try {
    await swissGlassConfirm(
      t('training.course.deleteConfirm', { title: course.title }),
      t('training.course.deleteTitle'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  busy.value = true
  try {
    await deleteTrainingCourse(course.id)
    notify.successKey('training.course.deleted')
    emit('deleted', course.id)
  } catch (error: unknown) {
    notify.errorKey(deleteFailureKey(error))
  } finally {
    busy.value = false
  }
}

function onCommand(command: string | number | Record<string, unknown>): void {
  if (busy.value || typeof command !== 'string') return
  if (command === 'rename') {
    void renameCourse()
    return
  }
  if (command === 'delete') void removeCourse()
}
</script>

<template>
  <div
    class="training-course-menu"
    @click.stop
  >
    <ElDropdown
      trigger="click"
      placement="bottom-end"
      popper-class="user-dropdown-popper"
      :disabled="busy"
      @command="onCommand"
    >
      <button
        type="button"
        class="training-course-menu__btn"
        :aria-label="t('training.course.actions')"
        :disabled="busy"
        @click.stop
      >
        <MoreHorizontal class="training-course-menu__icon" />
      </button>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem command="rename">
            <Edit3 class="mr-2 h-4 w-4" />
            <I18nText k="sidebar.actions.rename" />
          </ElDropdownItem>
          <ElDropdownItem
            v-if="!course.is_system"
            command="delete"
            divided
            class="user-dropdown-item--logout"
          >
            <Trash2 class="mr-2 h-4 w-4" />
            <I18nText k="sidebar.actions.delete" />
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
  </div>
</template>

<style scoped>
.training-course-menu {
  line-height: 0;
}
.training-course-menu__btn {
  display: flex;
  width: 1.75rem;
  height: 1.75rem;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgb(255 255 255 / 92%);
  color: #1c1917;
  box-shadow: 0 1px 2px rgb(28 25 23 / 28%);
  cursor: pointer;
}
.training-course-menu__btn:hover {
  background: #fff;
}
.training-course-menu__btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
.training-course-menu__btn:disabled {
  cursor: default;
  opacity: 0.7;
}
.training-course-menu__icon {
  width: 1rem;
  height: 1rem;
}
</style>
