<script setup lang="ts">
/**
 * MG全国数据中心 — China map dashboard (super-admin only).
 * Mounted only from AdminPublicDashboardTab (fullscreen admin embed).
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { ArrowLeft, Loading, Refresh } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import { formatCompactNumber, usePublicDashboard } from '@/composables/dashboard/usePublicDashboard'

const { t } = useLanguage()
const router = useRouter()
const mapEl = ref<HTMLElement | null>(null)

const {
  isLoading,
  stats,
  activities,
  isRefreshing,
  activityText,
  formatActivityTime,
  refreshActivityPanel,
} = usePublicDashboard(mapEl)

function activityKey(
  item: { timestamp: string; user: string; diagram_type?: string },
  index: number
) {
  return `${item.timestamp}-${item.user}-${item.diagram_type || ''}-${index}`
}

function backToAdmin(): void {
  const state = window.history.state as { back?: string | null } | null
  const previous = state?.back
  if (typeof previous === 'string' && (previous === '/admin' || previous.startsWith('/admin?'))) {
    router.back()
    return
  }
  void router.push({
    path: '/admin',
    query: { tab: 'settings', subtab: 'roles' },
  })
}
</script>

<template>
  <div class="public-dashboard">
    <button
      type="button"
      class="back-to-admin"
      :title="t('admin.publicDashboard.backToAdmin')"
      :aria-label="t('admin.publicDashboard.backToAdmin')"
      @click="backToAdmin"
    >
      <el-icon :size="18"><ArrowLeft /></el-icon>
      <span>{{ t('admin.publicDashboard.backToAdmin') }}</span>
    </button>
    <div class="map-container">
      <div
        ref="mapEl"
        class="china-map"
      />
      <div class="map-title-overlay">
        <h1>{{ t('publicDashboard.title') }}</h1>
        <div class="map-subtitle">{{ t('publicDashboard.subtitle') }}</div>
      </div>
    </div>

    <div
      v-if="isLoading"
      class="loading-overlay"
    >
      <el-icon
        class="is-loading"
        :size="36"
      >
        <Loading />
      </el-icon>
    </div>

    <div class="stats-overlay">
      <div class="overlay-header">
        <h2>{{ t('publicDashboard.statsTitle') }}</h2>
        <span class="pulse-indicator" />
      </div>
      <div class="stats-grid">
        <div class="stat-card">
          <h3>{{ t('publicDashboard.connectedUsers') }}</h3>
          <div class="stat-value">{{ formatCompactNumber(stats.connected_users) }}</div>
          <div class="stat-label">{{ t('publicDashboard.activeNow') }}</div>
        </div>
        <div class="stat-card">
          <h3>{{ t('publicDashboard.registeredUsers') }}</h3>
          <div class="stat-value">{{ formatCompactNumber(stats.registered_users) }}</div>
          <div class="stat-label">{{ t('publicDashboard.totalUsers') }}</div>
        </div>
        <div class="stat-card">
          <h3>{{ t('publicDashboard.tokensToday') }}</h3>
          <div class="stat-value">{{ formatCompactNumber(stats.tokens_used_today) }}</div>
          <div class="stat-label">{{ t('publicDashboard.today') }}</div>
        </div>
        <div class="stat-card">
          <h3>{{ t('publicDashboard.totalTokens') }}</h3>
          <div class="stat-value">{{ formatCompactNumber(stats.total_tokens_used) }}</div>
          <div class="stat-label">{{ t('publicDashboard.allTime') }}</div>
        </div>
      </div>
    </div>

    <div class="activity-overlay">
      <div class="overlay-header">
        <h2>{{ t('publicDashboard.activityTitle') }}</h2>
        <div class="header-actions">
          <button
            type="button"
            class="refresh-btn"
            :disabled="isRefreshing"
            :title="t('publicDashboard.refresh')"
            @click="refreshActivityPanel"
          >
            <el-icon :class="{ 'is-loading': isRefreshing }"><Refresh /></el-icon>
          </button>
          <div class="live-indicator">
            <span class="live-dot" />
            <span>LIVE</span>
          </div>
        </div>
      </div>
      <div class="activity-stream">
        <div
          v-if="activities.length === 0"
          class="activity-empty"
        >
          {{ t('publicDashboard.noActivity') }}
        </div>
        <div
          v-for="(item, index) in activities"
          :key="activityKey(item, index)"
          class="activity-item"
        >
          <span class="timestamp">{{ formatActivityTime(item.timestamp) }}</span>
          <strong class="user">{{ item.user }}</strong>
          <span class="action">{{ activityText(item.diagram_type) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.public-dashboard {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #0a0e27;
  color: #e2e8f0;
}

.back-to-admin {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 200;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.85rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.72);
  backdrop-filter: blur(12px);
  color: #e2e8f0;
  font-size: 0.85rem;
  cursor: pointer;
}

.back-to-admin:hover {
  background: rgba(30, 41, 59, 0.9);
  border-color: rgba(148, 163, 184, 0.55);
}

.map-container {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.china-map {
  width: 100%;
  height: 100%;
}

.map-title-overlay {
  position: absolute;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  text-align: center;
  pointer-events: none;
}

.map-title-overlay h1 {
  margin: 0 0 0.5rem;
  font-size: clamp(1.75rem, 4vw, 3rem);
  font-weight: 700;
  letter-spacing: 2px;
  background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.map-subtitle {
  font-size: 0.95rem;
  color: rgba(226, 232, 240, 0.7);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 14, 39, 0.55);
  color: #93c5fd;
}

.stats-overlay,
.activity-overlay {
  position: absolute;
  z-index: 100;
  pointer-events: auto;
}

.stats-overlay {
  top: 30px;
  left: 30px;
  width: 320px;
  max-width: calc(100% - 60px);
}

.activity-overlay {
  right: 30px;
  bottom: 30px;
  width: 380px;
  max-width: calc(100% - 60px);
  max-height: min(48vh, 420px);
  display: flex;
  flex-direction: column;
  background: rgba(30, 41, 59, 0.72);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  padding: 1rem;
}

.overlay-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}

.overlay-header h2 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #e2e8f0;
}

.pulse-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 10px #10b981;
  animation: pulse 2s ease-in-out infinite;
}

.stats-grid {
  display: grid;
  gap: 0.85rem;
}

.stat-card {
  position: relative;
  padding: 1rem 1.15rem;
  border-radius: 14px;
  background: rgba(30, 41, 59, 0.75);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.stat-card h3 {
  margin: 0 0 0.35rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #94a3b8;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.2;
}

.stat-label {
  margin-top: 0.2rem;
  font-size: 0.75rem;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.45);
  color: #cbd5e1;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  color: #86efac;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  animation: pulse 1.6s ease-in-out infinite;
}

.activity-stream {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-right: 0.25rem;
}

.activity-empty {
  color: #64748b;
  font-size: 0.85rem;
  padding: 0.5rem 0;
}

.activity-item {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
  align-items: baseline;
  padding: 0.55rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  font-size: 0.85rem;
  animation: slideIn 0.35s ease-out;
}

.activity-item .timestamp {
  color: #64748b;
  font-variant-numeric: tabular-nums;
  min-width: 4.5rem;
}

.activity-item .user {
  color: #93c5fd;
}

.activity-item .action {
  color: #e2e8f0;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.65;
    transform: scale(1.15);
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(16px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (max-width: 900px) {
  .stats-overlay {
    top: 12px;
    left: 12px;
    width: min(280px, calc(100% - 24px));
  }

  .activity-overlay {
    right: 12px;
    bottom: 12px;
    width: min(340px, calc(100% - 24px));
    max-height: 36vh;
  }

  .map-title-overlay {
    top: 12px;
  }
}
</style>
