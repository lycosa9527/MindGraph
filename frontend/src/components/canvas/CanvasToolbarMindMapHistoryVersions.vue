<script setup lang="ts">
import { computed, inject, ref, watch, type ComputedRef } from 'vue'

import { ElDropdown, ElTooltip } from 'element-plus'

import { Camera, Check, ChevronDown, Clock } from '@lucide/vue'

import { useMindMapRibbonActions } from '@/canvas-ribbon/useMindMapRibbonActions'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  CURRENT_DIAGRAM_VERSION,
  canMutateDiagramSnapshots,
  formatSnapshotCreatedAt,
  newestSnapshotIdentity,
  snapshotsNewestFirst,
} from '@/composables/editor/diagramSnapshotVersions'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'
import { useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  { compact: false }
)

const { t, currentLanguage } = useLanguage()
const notify = useNotifications()
const ribbon = useMindMapRibbonActions()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()
const snapshotHistory = useSnapshotHistory()

const collabCanvas = inject<{ isDiagramOwner?: ComputedRef<boolean> } | undefined>(
  'collabCanvas',
  undefined
)

const dropdownOpen = ref(false)
const newestIdentityWhenTakeStarted = ref('')

const canMutateSnapshots = computed(() =>
  canMutateDiagramSnapshots({
    collabSessionActive: diagramStore.collabSessionActive,
    isDiagramOwner: collabCanvas?.isDiagramOwner?.value,
  })
)

const historyRows = computed(() =>
  snapshotsNewestFirst(snapshotHistory.snapshots.value).map((snap) => ({
    id: snap.id,
    versionNumber: snap.version_number,
    timeLabel: formatSnapshotCreatedAt(snap.created_at, currentLanguage.value),
    isActive: snapshotHistory.activeSnapshotVersion.value === snap.version_number,
    isRecalling: snapshotHistory.recallingVersion.value === snap.version_number,
  }))
)

const isBusy = computed(
  () => snapshotHistory.recallingVersion.value !== null || snapshotHistory.isTaking.value
)
const isCurrentActive = computed(() => snapshotHistory.activeSnapshotVersion.value === null)
const isRestoringCurrent = computed(
  () => snapshotHistory.recallingVersion.value === CURRENT_DIAGRAM_VERSION
)

function closeDropdown(): void {
  dropdownOpen.value = false
}

function onSelectCurrent(): void {
  closeDropdown()
  if (!canMutateSnapshots.value || isBusy.value || isCurrentActive.value) return
  ribbon.restoreCurrentVersion()
}

function onSelectSnapshot(versionNumber: number): void {
  closeDropdown()
  if (!canMutateSnapshots.value || isBusy.value) return
  if (snapshotHistory.activeSnapshotVersion.value === versionNumber) return
  ribbon.recallSnapshot(versionNumber)
}

function onTakeSnapshot(): void {
  if (!canMutateSnapshots.value || isBusy.value) return
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }
  if (!savedDiagramsStore.activeDiagramId) {
    notify.warning(t('canvas.toolbar.snapshotSaveFirst'))
    return
  }
  ribbon.requestSnapshot()
}

watch(
  () => snapshotHistory.isTaking.value,
  (taking, wasTaking) => {
    if (taking && !wasTaking) {
      newestIdentityWhenTakeStarted.value = newestSnapshotIdentity(
        snapshotHistory.snapshots.value
      )
      return
    }
    const nextIdentity = newestSnapshotIdentity(snapshotHistory.snapshots.value)
    if (
      wasTaking &&
      !taking &&
      nextIdentity !== '' &&
      nextIdentity !== newestIdentityWhenTakeStarted.value
    ) {
      dropdownOpen.value = true
    }
  }
)
</script>

<template>
  <div
    v-if="canMutateSnapshots"
    class="mm-history-versions"
    data-testid="mindmap-history-versions"
  >
    <ElTooltip
      :content="t('canvas.ribbon.historyVersionsTip')"
      placement="bottom"
      :disabled="dropdownOpen"
    >
      <span class="inline-flex shrink-0">
        <ElDropdown
          v-model:visible="dropdownOpen"
          trigger="click"
          placement="bottom-start"
          popper-class="mm-toolbar-popper mm-toolbar-popper--history"
        >
          <button
            type="button"
            class="mm-btn mm-history-versions__main is-expanded"
            :class="{ 'is-busy': isBusy }"
            :aria-label="t('canvas.ribbon.historyVersions')"
            :aria-busy="isBusy"
            data-testid="mindmap-history-versions-trigger"
          >
            <Clock class="w-4 h-4" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('canvas.ribbon.historyVersions') }}</span
            >
            <ChevronDown
              :size="12"
              class="mm-btn__chevron"
            />
          </button>
          <template #dropdown>
            <div
              class="mm-history-versions__menu"
              role="menu"
              :aria-label="t('canvas.ribbon.historyVersions')"
              data-testid="mindmap-history-versions-menu"
            >
              <button
                type="button"
                class="mm-history-versions__item"
                :class="{ 'is-active': isCurrentActive, 'is-dimmed': isRestoringCurrent }"
                :disabled="isBusy"
                role="menuitem"
                :aria-current="isCurrentActive ? 'true' : undefined"
                data-testid="mindmap-history-versions-current"
                @click="onSelectCurrent"
              >
                <span class="mm-history-versions__item-row">
                  <span class="mm-history-versions__item-label">{{
                    t('canvas.ribbon.historyCurrent')
                  }}</span>
                  <Check
                    v-if="isCurrentActive"
                    class="mm-history-versions__check"
                    :size="16"
                  />
                </span>
              </button>
              <button
                v-for="row in historyRows"
                :key="row.id"
                type="button"
                class="mm-history-versions__item"
                :class="{ 'is-active': row.isActive, 'is-dimmed': row.isRecalling }"
                :disabled="isBusy"
                role="menuitem"
                :aria-current="row.isActive ? 'true' : undefined"
                :data-testid="`mindmap-history-versions-snap-${row.versionNumber}`"
                @click="onSelectSnapshot(row.versionNumber)"
              >
                <span class="mm-history-versions__item-row">
                  <span class="mm-history-versions__item-copy">
                    <span class="mm-history-versions__item-label">{{
                      t('canvas.ribbon.historySnapshot', { n: row.versionNumber })
                    }}</span>
                    <span
                      v-if="row.timeLabel"
                      class="mm-history-versions__item-time"
                      >{{ row.timeLabel }}</span
                    >
                  </span>
                  <Check
                    v-if="row.isActive"
                    class="mm-history-versions__check"
                    :size="16"
                  />
                </span>
              </button>
              <p
                v-if="!historyRows.length"
                class="mm-history-versions__empty"
              >
                {{ t('canvas.ribbon.historyEmpty') }}
              </p>
            </div>
          </template>
        </ElDropdown>
      </span>
    </ElTooltip>
    <ElTooltip
      :content="t('canvas.ribbon.historyTakeSnapshot')"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-history-versions__camera"
        :disabled="isBusy"
        :aria-label="t('canvas.ribbon.historyTakeSnapshot')"
        data-testid="mindmap-history-versions-camera"
        @click="onTakeSnapshot"
      >
        <Camera class="w-3.5 h-3.5" />
      </button>
    </ElTooltip>
  </div>
</template>
