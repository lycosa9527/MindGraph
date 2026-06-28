<script setup lang="ts">
/**
 * Knowledge Space — package groups (Zotero-style collections).
 *
 * Lists File Center packages, each expandable to reveal its sources, with a
 * link back to the diagram the package is bound to.
 */
import { computed, ref } from 'vue'

import { ChevronDown, ChevronRight, ExternalLink, FileText, Folder } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { usePackageDetail, usePackages } from '@/composables/fileCenter/useFileCenter'

const { t } = useLanguage()

const packagesQuery = usePackages()
const packages = computed(() => packagesQuery.data.value?.packages ?? [])

const expandedId = ref<number | null>(null)
const detailQuery = usePackageDetail(expandedId)
const expandedDocuments = computed(() => detailQuery.data.value?.documents ?? [])

function toggle(packageId: number): void {
  expandedId.value = expandedId.value === packageId ? null : packageId
}

function sourceBadge(source: string | null): string {
  switch (source) {
    case 'chrome_extension':
      return t('fileCenterLibrary.badgeExtension')
    case 'knowledge_space':
      return t('fileCenterLibrary.badgeUpload')
    default:
      return t('fileCenterLibrary.badgeCanvas')
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return t('fileCenter.statusReady')
    case 'failed':
      return t('fileCenter.statusFailed')
    default:
      return t('fileCenter.statusIndexing')
  }
}
</script>

<template>
  <div
    v-if="packages.length > 0"
    class="mb-4 rounded-xl border border-slate-200 bg-white"
  >
    <div class="border-b border-slate-100 px-4 py-3">
      <h3 class="text-sm font-semibold text-slate-800">
        {{ t('fileCenterLibrary.title') }}
      </h3>
      <p class="mt-0.5 text-xs text-slate-400">
        {{ t('fileCenterLibrary.subtitle') }}
      </p>
    </div>

    <ul class="divide-y divide-slate-100">
      <li
        v-for="pkg in packages"
        :key="pkg.id"
        class="px-4 py-2.5"
      >
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="flex min-w-0 flex-1 items-center gap-2 text-left"
            @click="toggle(pkg.id)"
          >
            <component
              :is="expandedId === pkg.id ? ChevronDown : ChevronRight"
              class="h-4 w-4 shrink-0 text-slate-400"
              :stroke-width="2"
            />
            <Folder
              class="h-4 w-4 shrink-0 text-amber-500"
              :stroke-width="2"
            />
            <span class="truncate text-sm font-medium text-slate-700">
              {{ pkg.name || t('fileCenter.defaultPackageName') }}
            </span>
            <span class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
              {{ sourceBadge(pkg.source) }}
            </span>
          </button>

          <span class="shrink-0 text-xs text-slate-400">
            {{
              t('fileCenter.corpusStatus', {
                completed: pkg.completed_count,
                total: pkg.document_count,
              })
            }}
          </span>

          <a
            v-if="pkg.diagram_id"
            :href="`/canvas?diagramId=${pkg.diagram_id}&openDocSummary=1`"
            class="shrink-0 text-slate-400 transition-colors hover:text-blue-600"
            :title="t('fileCenterLibrary.openDiagram')"
          >
            <ExternalLink
              class="h-4 w-4"
              :stroke-width="2"
            />
          </a>
        </div>

        <ul
          v-if="expandedId === pkg.id"
          class="mt-2 space-y-1 pl-10"
        >
          <li
            v-if="expandedDocuments.length === 0"
            class="py-1 text-xs text-slate-400"
          >
            {{ t('fileCenter.noSources') }}
          </li>
          <li
            v-for="doc in expandedDocuments"
            :key="doc.id"
            class="flex items-center gap-2 py-1"
          >
            <FileText
              class="h-3.5 w-3.5 shrink-0 text-slate-400"
              :stroke-width="2"
            />
            <span class="truncate text-xs text-slate-600">{{ doc.file_name }}</span>
            <span
              class="ml-auto shrink-0 text-[10px]"
              :class="{
                'text-emerald-600': doc.status === 'completed',
                'text-rose-500': doc.status === 'failed',
                'text-blue-500': doc.status !== 'completed' && doc.status !== 'failed',
              }"
            >
              {{ statusLabel(doc.status) }}
            </span>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>
