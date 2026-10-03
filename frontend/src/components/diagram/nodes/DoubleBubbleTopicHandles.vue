<script setup lang="ts">
/**
 * One source handle on each side of a double-bubble topic.
 * Every similarity or difference on that side meets at this point.
 */
import { Handle, Position } from '@vue-flow/core'
</script>

<template>
  <Handle
    id="left"
    type="source"
    :position="Position.Left"
  />
  <Handle
    id="right"
    type="source"
    :position="Position.Right"
  />
</template>
