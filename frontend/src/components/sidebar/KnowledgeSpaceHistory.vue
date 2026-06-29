<script setup lang="ts">
/**
 * KnowledgeSpaceHistory - Sidebar package list for Knowledge Space.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { ElMessageBox, ElScrollbar } from 'element-plus'

import { Folder, Trash2 } from '@lucide/vue'

import { notify, useLanguage } from '@/composables'
import {
  type KnowledgePackage,
  useFileCenterMutations,
  usePackages,
} from '@/composables/fileCenter/useFileCenter'
import { useKnowledgeSpaceStore } from '@/stores/knowledgeSpace'
import { MAX_KNOWLEDGE_PACKAGES } from '@/utils/knowledgePackageLimit'

const { t } = useLanguage()
const router = useRouter()
const store = useKnowledgeSpaceStore()

const packagesQuery = usePackages()
const packages = computed(() => packagesQuery.data.value?.packages ?? [])
const isLoading = computed(() => packagesQuery.isLoading.value)
const packageCountLabel = computed(() => `${packages.value.length}/${MAX_KNOWLEDGE_PACKAGES}`)

const { deletePackage } = useFileCenterMutations()

function packageLabel(pkg: KnowledgePackage): string {
  return pkg.name?.trim() || t('fileCenter.defaultPackageName')
}

function isActive(packageId: number): boolean {
  return store.activePackageId === packageId
}

function handleSelect(pkg: KnowledgePackage): void {
  store.selectPackage(pkg.id)
  if (!router.currentRoute.value.path.startsWith('/knowledge-space')) {
    void router.push('/knowledge-space')
  }
}

async function handleDelete(packageId: number): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('fileCenter.confirmDeletePackage'),
      t('fileCenter.deletePackage'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    await deletePackage.mutateAsync(packageId)
    if (store.activePackageId === packageId) {
      store.selectPackage(null)
    }
    notify.success(t('sidebar.knowledgeSpaceHistory.deleted'))
  } catch (error) {
    if (error !== 'cancel') {
      notify.error(t('fileCenter.deleteFailed'))
    }
  }
}
</script>

<template>
  <div
    class="knowledge-space-history flex flex-col h-full border-t border-stone-200 relative overflow-hidden"
  >
    <div class="px-4 py-3 flex items-center justify-between">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ t('sidebar.knowledgeSpaceHistory.title') }}
      </div>
      <div class="text-xs text-stone-400">
        {{ packageCountLabel }}
      </div>
    </div>

    <ElScrollbar class="flex-1 px-4 pb-4">
      <div
        v-if="isLoading"
        class="py-8 text-center text-xs text-stone-400"
      >
        {{ t('common.loading') }}
      </div>

      <div
        v-else-if="packages.length === 0"
        class="text-center py-8"
      >
        <Folder class="w-8 h-8 mx-auto mb-2 text-stone-300" />
        <p class="text-xs text-stone-400">
          {{ t('sidebar.knowledgeSpaceHistory.empty') }}
        </p>
        <p class="text-xs text-stone-300 mt-1">
          {{ t('sidebar.knowledgeSpaceHistory.capacity', { n: MAX_KNOWLEDGE_PACKAGES }) }}
        </p>
      </div>

      <ul
        v-else
        class="space-y-0.5"
      >
        <li
          v-for="pkg in packages"
          :key="pkg.id"
          class="package-item"
          :class="{ active: isActive(pkg.id) }"
          @click="handleSelect(pkg)"
        >
          <Folder
            class="h-4 w-4 shrink-0 text-amber-500"
            :stroke-width="2"
          />
          <div class="package-info min-w-0 flex-1">
            <div class="package-name truncate">
              {{ packageLabel(pkg) }}
            </div>
            <div class="package-meta">
              {{
                t('fileCenter.corpusStatus', {
                  completed: pkg.completed_count,
                  total: pkg.document_count,
                })
              }}
            </div>
          </div>
          <button
            type="button"
            class="delete-btn"
            :title="t('sidebar.actions.delete')"
            @click.stop="handleDelete(pkg.id)"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </li>
      </ul>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.knowledge-space-history {
  min-height: 120px;
}

.package-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.package-item:hover {
  background-color: #f5f5f4;
}

.package-item.active {
  background-color: #eff6ff;
}

.package-item.active .package-name {
  color: #1d4ed8;
  font-weight: 500;
}

.package-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #57534e;
  font-size: 13px;
}

.package-meta {
  font-size: 10px;
  color: #a8a29e;
  margin-top: 1px;
}

.delete-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  border: none;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    background-color 0.15s ease,
    color 0.15s ease;
}

.package-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background-color: #fee2e2;
  color: #dc2626;
}
</style>
