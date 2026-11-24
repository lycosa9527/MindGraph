<script setup lang="ts">
import { type ComputedRef, computed, inject, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, ChevronDown, Clock, Edit3, MoreHorizontal, Trash2 } from '@lucide/vue'

import { useMindMapRibbonActions } from '@/canvas-ribbon/useMindMapRibbonActions'
import MmToolbarLabel from '@/components/canvas/MmToolbarLabel.vue'
import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  CURRENT_DIAGRAM_VERSION,
  canMutateDiagramSnapshots,
  formatSnapshotCreatedAt,
  newestSnapshotIdentity,
  snapshotDisplayLabel,
  snapshotsNewestFirst,
} from '@/composables/editor/diagramSnapshotVersions'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'

const props = withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  { compact: false }
)

const { t, currentLanguage } = useLanguage()
const ribbon = useMindMapRibbonActions()
const diagramStore = useDiagramSession()
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
  snapshotsNewestFirst(snapshotHistory.snapshots.value).map((snap) => {
    const fallback = t('canvas.ribbon.historySnapshot', { n: snap.version_number })
    return {
      id: snap.id,
      versionNumber: snap.version_number,
      title: snap.title?.trim() || '',
      label: snapshotDisplayLabel(snap, fallback),
      timeLabel: formatSnapshotCreatedAt(snap.created_at, currentLanguage.value),
      isActive: snapshotHistory.activeSnapshotVersion.value === snap.version_number,
      isRecalling: snapshotHistory.recallingVersion.value === snap.version_number,
    }
  })
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

function onRenameSnapshot(versionNumber: number): void {
  if (!canMutateSnapshots.value || isBusy.value) return
  closeDropdown()
  // Let the nested menu finish closing before the prompt mounts above it.
  void Promise.resolve().then(() => ribbon.renameSnapshot(versionNumber))
}

function onDeleteSnapshot(versionNumber: number): void {
  if (!canMutateSnapshots.value || isBusy.value) return
  closeDropdown()
  void Promise.resolve().then(() => ribbon.deleteSnapshot(versionNumber))
}

watch(
  () => snapshotHistory.isTaking.value,
  (taking, wasTaking) => {
    if (taking && !wasTaking) {
      newestIdentityWhenTakeStarted.value = newestSnapshotIdentity(snapshotHistory.snapshots.value)
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
    <I18nTooltip
      k="canvas.ribbon.historyVersionsTip"
      placement="bottom"
      :disabled="dropdownOpen"
    >
      <span class="inline-flex shrink-0">
        <ElDropdown
          v-model:visible="dropdownOpen"
          trigger="click"
          placement="bottom-start"
          :hide-on-click="false"
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
            <MmToolbarLabel
              class="mm-btn__label"
              k="canvas.ribbon.historyVersions"
              :short="props.compact"
            />
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
                v-if="!isCurrentActive"
                type="button"
                class="mm-history-versions__item mm-history-versions__item--plain"
                :class="{ 'is-dimmed': isRestoringCurrent }"
                :disabled="isBusy"
                role="menuitem"
                data-testid="mindmap-history-versions-current"
                @click="onSelectCurrent"
              >
                <span class="mm-history-versions__item-row">
                  <span class="mm-history-versions__item-label"
                    ><I18nText k="canvas.ribbon.historyBackToLatest"
                  /></span>
                </span>
              </button>
              <div
                v-for="row in historyRows"
                :key="row.id"
                class="mm-history-versions__item"
                :class="{ 'is-active': row.isActive, 'is-dimmed': row.isRecalling }"
                role="menuitem"
                :aria-current="row.isActive ? 'true' : undefined"
                :data-testid="`mindmap-history-versions-snap-${row.versionNumber}`"
              >
                <button
                  type="button"
                  class="mm-history-versions__item-main"
                  :disabled="isBusy"
                  @click="onSelectSnapshot(row.versionNumber)"
                >
                  <span class="mm-history-versions__item-copy">
                    <span class="mm-history-versions__item-label">{{ row.label }}</span>
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
                </button>
                <ElDropdown
                  trigger="click"
                  placement="bottom-end"
                  teleported
                  popper-class="mm-history-versions-item-more-popper"
                  @click.stop
                >
                  <button
                    type="button"
                    class="mm-history-versions__more"
                    :disabled="isBusy"
                    :aria-label="t('canvas.ribbon.historySnapshotMore')"
                    :data-testid="`mindmap-history-versions-more-${row.versionNumber}`"
                    @click.stop
                  >
                    <MoreHorizontal :size="16" />
                  </button>
                  <template #dropdown>
                    <ElDropdownMenu class="diagram-history-more__menu">
                      <ElDropdownItem
                        :disabled="isBusy"
                        @click="onRenameSnapshot(row.versionNumber)"
                      >
                        <span class="diagram-history-more__row">
                          <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                          <I18nText k="canvas.ribbon.historyRename" />
                        </span>
                      </ElDropdownItem>
                      <ElDropdownItem
                        divided
                        :disabled="isBusy"
                        @click="onDeleteSnapshot(row.versionNumber)"
                      >
                        <span class="diagram-history-more__row diagram-history-more__row--danger">
                          <Trash2 class="w-4 h-4 shrink-0" />
                          <I18nText k="canvas.ribbon.historyDelete" />
                        </span>
                      </ElDropdownItem>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </div>
              <p
                v-if="!historyRows.length"
                class="mm-history-versions__empty"
              >
                <I18nText k="canvas.ribbon.historyEmpty" />
              </p>
            </div>
          </template>
        </ElDropdown>
      </span>
    </I18nTooltip>
  </div>
</template>
