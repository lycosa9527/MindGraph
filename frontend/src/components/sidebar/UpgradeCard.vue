<script setup lang="ts">
/**
 * UpgradeCard - Membership upgrade promotion card
 */
import { PlusCircle } from 'lucide-vue-next'
</script>

<template>
  <div class="upgrade-card p-4">
    <div class="bg-purple-50 rounded-xl p-4 shadow-sm">
      <div class="flex items-start mb-3">
        <div class="bg-purple-100 p-1.5 rounded-md mr-2">
          <PlusCircle class="w-4 h-4 text-purple-600" />
        </div>
        <div>
          <div class="font-medium text-gray-800 text-sm">升级会员</div>
          <div class="text-xs text-gray-600 mt-1">会员可解锁更多高阶功能与趣味玩法</div>
        </div>
      </div>
      <button
        class="w-full py-2 rounded-md border border-blue-500 text-blue-600 hover:bg-blue-50 transition-colors text-sm font-medium"
      >
        立即升级
      </button>
    </div>
  </div>
</template>
