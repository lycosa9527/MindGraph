<script setup lang="ts">
/**
 * MindGraphContainer — /mindgraph always uses the current card gallery.
 */
import InternationalLanding from './InternationalLanding.vue'
</script>

<template>
  <InternationalLanding />
</template>

<!-- Teleported translate dropdown — width lives on popper, not scoped subtree -->
<style>
.mindgraph-translate-popper.el-popper {
  width: min(180px, calc(100vw - 24px)) !important;
  max-width: min(180px, calc(100vw - 24px)) !important;
  box-sizing: border-box !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.mindgraph-translate-popper .el-dropdown-menu {
  width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: stable;
}

.mindgraph-translate-popper .el-dropdown-menu__item {
  box-sizing: border-box;
  width: 100%;
  padding: 7px 14px !important;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  border-radius: 6px;
  transition:
    background 0.12s,
    color 0.12s;
}

.mindgraph-translate-popper .el-dropdown-menu__item:hover,
.mindgraph-translate-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.mindgraph-translate-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.mindgraph-translate-popper .translate-lang-row {
  box-sizing: border-box;
  width: 100%;
  padding: 0;
  overflow: hidden;
}
</style>
