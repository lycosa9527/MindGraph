<script setup lang="ts">
/**
 * Role control — add member modal (light Swiss stone shell).
 */
import { computed, nextTick, ref, watch } from 'vue'

import { Close, Loading, Search, UserFilled } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import type { CandidateUser } from '@/composables/admin/useAdminRoleControl'

const visible = defineModel<boolean>('visible', { required: true })
const searchQuery = defineModel<string>('searchQuery', { required: true })

const props = defineProps<{
  roleTabLabel: string
  results: CandidateUser[]
  loading: boolean
  hasRun: boolean
  grantingId: number | null
  roleLabelFor: (role: string) => string
  showSchoolInResults?: boolean
}>()

const emit = defineEmits<{
  grant: [user: CandidateUser]
  search: []
}>()

const { t } = useLanguage()

const searchInputRef = ref<HTMLInputElement | null>(null)

const modalTitle = computed(() =>
  t('admin.addRoleMemberModalTitle', { role: props.roleTabLabel })
)

const showEmptyState = computed(
  () =>
    searchQuery.value.trim().length >= 2 &&
    (props.loading || (props.hasRun && props.results.length === 0))
)

function closeModal(): void {
  visible.value = false
}

function onGrant(user: CandidateUser): void {
  emit('grant', user)
}

function schoolLabel(user: CandidateUser): string {
  return (user.organization_name || user.organization_code || '').trim()
}

watch(visible, async (open) => {
  if (open) {
    await nextTick()
    searchInputRef.value?.focus()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="admin-role-add-modal">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div
          class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]"
          aria-hidden="true"
          @click="closeModal"
        />

        <div
          class="relative w-full max-w-lg max-h-[90vh] flex flex-col"
          role="dialog"
          aria-modal="true"
          :aria-label="modalTitle"
          @click.stop
          @keydown.esc="closeModal"
        >
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative shrink-0">
              <el-button
                :icon="Close"
                circle
                text
                class="admin-role-add-modal__close"
                :aria-label="t('common.cancel')"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight px-6">
                {{ modalTitle }}
              </h2>
            </div>

            <div class="p-8 space-y-4 overflow-y-auto">
              <label
                class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                for="role-add-member-search"
              >
                {{ t('admin.searchUserByNameOrPhone') }}
              </label>
              <div class="admin-role-add-modal__search">
                <el-icon class="admin-role-add-modal__search-icon">
                  <Search />
                </el-icon>
                <input
                  id="role-add-member-search"
                  ref="searchInputRef"
                  v-model="searchQuery"
                  type="search"
                  autocomplete="off"
                  :placeholder="t('admin.searchUserByNameOrPhone')"
                  class="admin-role-add-modal__input"
                  @keyup.enter="emit('search')"
                />
              </div>

              <div
                v-if="showEmptyState"
                class="admin-role-add-modal__empty"
              >
                <template v-if="loading">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <p>{{ t('admin.loading') }}</p>
                </template>
                <template v-else>
                  <el-icon :size="32"><UserFilled /></el-icon>
                  <p>{{ t('admin.roleAddMemberNoSearchResults') }}</p>
                </template>
              </div>

              <ul
                v-else-if="results.length > 0"
                class="admin-role-add-modal__list"
              >
                <li
                  v-for="user in results"
                  :key="user.id"
                  class="admin-role-add-modal__row"
                >
                  <div class="min-w-0">
                    <p class="admin-role-add-modal__name">
                      {{ user.name || user.phone }}
                    </p>
                    <p class="admin-role-add-modal__meta">
                      {{ user.phone }} · {{ t('admin.currentRole') }}:
                      {{ roleLabelFor(user.role) }}
                      <template v-if="showSchoolInResults && schoolLabel(user)">
                        · {{ t('admin.schoolName') }}: {{ schoolLabel(user) }}
                      </template>
                    </p>
                  </div>
                  <button
                    type="button"
                    class="admin-role-add-modal__grant"
                    :disabled="grantingId === user.id"
                    @click="onGrant(user)"
                  >
                    <el-icon
                      v-if="grantingId === user.id"
                      class="is-loading"
                    >
                      <Loading />
                    </el-icon>
                    {{ t('admin.grantRole') }}
                  </button>
                </li>
              </ul>

              <p
                v-else
                class="admin-role-add-modal__hint"
              >
                {{ t('admin.roleAddMemberSearchHint') }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.admin-role-add-modal-enter-active,
.admin-role-add-modal-leave-active {
  transition: opacity 0.2s ease;
}

.admin-role-add-modal-enter-active .relative,
.admin-role-add-modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.admin-role-add-modal-enter-from,
.admin-role-add-modal-leave-to {
  opacity: 0;
}

.admin-role-add-modal-enter-from .relative,
.admin-role-add-modal-leave-to .relative {
  transform: scale(0.97);
}

.admin-role-add-modal__close {
  position: absolute;
  top: 16px;
  inset-inline-end: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}

.admin-role-add-modal__search {
  position: relative;
}

.admin-role-add-modal__search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  color: #a8a29e;
  pointer-events: none;
}

.admin-role-add-modal__input {
  width: 100%;
  padding: 0.75rem 1rem 0.75rem 2.75rem;
  border: 0;
  border-radius: 0.5rem;
  background: #fafaf9;
  color: #1c1917;
  font-size: 0.9375rem;
  transition:
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.admin-role-add-modal__input::placeholder {
  color: #a8a29e;
}

.admin-role-add-modal__input:focus {
  outline: none;
  background: #fff;
  box-shadow: 0 0 0 2px #1c1917;
}

.admin-role-add-modal__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2.5rem 1rem;
  color: #78716c;
  font-size: 0.875rem;
}

.admin-role-add-modal__empty p {
  margin: 0;
}

.admin-role-add-modal__hint {
  margin: 0;
  padding: 1.5rem 0.5rem;
  text-align: center;
  font-size: 0.8125rem;
  color: #78716c;
  line-height: 1.5;
}

.admin-role-add-modal__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 16rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-role-add-modal__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #fafaf9;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.admin-role-add-modal__row:hover {
  border-color: #d6d3d1;
  background: #f5f5f4;
}

.admin-role-add-modal__name {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #1c1917;
}

.admin-role-add-modal__meta {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: #78716c;
}

.admin-role-add-modal__grant {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-width: 4.5rem;
  padding: 0.45rem 0.85rem;
  border: 1px solid #b3d8ff;
  border-radius: 9999px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease;
}

.admin-role-add-modal__grant:hover:not(:disabled) {
  background: #d9ecff;
  border-color: #79bbff;
  color: #337ecc;
}

.admin-role-add-modal__grant:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
