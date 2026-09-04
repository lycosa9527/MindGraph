<script setup lang="ts">
import type { Component } from 'vue'

import {
  Camera,
  Clipboard,
  FileCode2,
  FileText,
  Image,
  RotateCcw,
  Save,
  Share2,
  Upload,
} from '@lucide/vue'

import { useFeatureFlags } from '@/composables'
import { useLanguage } from '@/composables/core/useLanguage'
import type { SnapshotMetadata } from '@/composables/editor/useSnapshotHistory'
import { useAuthStore } from '@/stores'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

const props = withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
    snapshots?: SnapshotMetadata[]
    activeSnapshotVersion?: number | null
    recallingSnapshotVersion?: number | null
    isCollabGuest?: boolean
  }>(),
  {
    classic: false,
    disabled: false,
    snapshots: () => [],
    activeSnapshotVersion: null,
    recallingSnapshotVersion: null,
    isCollabGuest: false,
  }
)

const { t } = useLanguage()
const actions = useV3RibbonActions()
const authStore = useAuthStore()
const { featureCommunity } = useFeatureFlags()

const exportIcons: Record<string, Component> = {
  png: Image,
  svg: FileCode2,
  mg: FileText,
  clipboard: Clipboard,
  community: Share2,
}

function onSnapshotClick(event: MouseEvent, versionNumber: number): void {
  if (props.isCollabGuest || props.recallingSnapshotVersion != null) return
  if (event.ctrlKey || event.metaKey) {
    actions.deleteSnapshot(versionNumber)
    return
  }
  actions.recallSnapshot(versionNumber)
}
</script>

<template>
  <V3RibbonGroup
    v-if="classic"
    group="document"
    :label="t('canvas.v3.ribbon.groupDocument')"
    :classic="classic"
  >
    <template #lead>
      <V3RibbonCommand
        :label="t('common.save')"
        :icon="Save"
        variant="stacked"
        primary
        :disabled="disabled"
        :shortcut="t('canvas.toolbar.saveShortcut')"
        @click="actions.requestSave"
      />
    </template>
  </V3RibbonGroup>
  <V3RibbonGroup
    group="exchange"
    :label="t('canvas.v3.ribbon.groupExchange')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.import')"
      :icon="Upload"
      variant="stacked"
      :disabled="disabled"
      @click="actions.importMg"
    />
    <V3RibbonCommand
      v-for="item in classic ? actions.exportMenuItems : actions.exportMenuItems.slice(0, 1)"
      :key="item.command"
      :label="t(item.labelKey)"
      :icon="exportIcons[item.command]"
      variant="stacked"
      :disabled="disabled"
      @click="actions.exportFormat(item.command)"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.topBar.exportClipboard')"
      :icon="Clipboard"
      variant="stacked"
      :disabled="disabled"
      @click="actions.exportFormat('clipboard')"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.topBar.addWorksheetText')"
      :icon="FileText"
      variant="stacked"
      :disabled="disabled"
      @click="actions.requestWorksheetText"
    />
    <V3RibbonCommand
      v-if="classic && featureCommunity && authStore.isAuthenticated"
      :label="t('canvas.topBar.shareCommunity')"
      :icon="Share2"
      variant="stacked"
      :disabled="disabled"
      @click="actions.exportFormat('community')"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="versions"
    :label="t('canvas.v3.ribbon.groupVersions')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.moreAppSnapshot')"
      :icon="Camera"
      variant="stacked"
      :disabled="disabled || isCollabGuest"
      @click="actions.requestSnapshot"
    />
    <template v-if="classic">
      <button
        v-for="snap in snapshots"
        :key="snap.version_number"
        type="button"
        class="v3-snapshot-dot"
        :class="{ 'is-active': snap.version_number === activeSnapshotVersion }"
        :disabled="disabled || isCollabGuest"
        :title="t('canvas.topBar.snapshotBadgeTooltip', { n: snap.version_number })"
        @click="onSnapshotClick($event, snap.version_number)"
      >
        {{ snap.version_number }}
      </button>
    </template>
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="danger"
    :label="t('canvas.v3.ribbon.groupDanger')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.topBar.resetCanvas')"
      :icon="RotateCcw"
      variant="stacked"
      danger
      :disabled="disabled"
      @click="actions.resetTemplate"
    />
  </V3RibbonGroup>
</template>
