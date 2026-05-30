<script setup lang="ts">
/**
 * Admin Performance tab — MindBot Swiss shell, metric cards + progress bars.
 */
import { computed } from 'vue'

import AdminSwissPerfCard from '@/components/admin/swiss/AdminSwissPerfCard.vue'
import { useLanguage } from '@/composables'
import { usePerformanceLive } from '@/composables/admin/usePerformanceLive'

const { t } = useLanguage()

const { loading, fetchError, latest } = usePerformanceLive()

function formatBytes(b: number): string {
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(2)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(2)} KB`
  return `${b} B`
}

function clampPct(n: number): number {
  if (Number.isNaN(n) || !Number.isFinite(n)) return 0
  return Math.min(100, Math.max(0, Math.round(n * 10) / 10))
}

const host = computed(() => (latest.value?.host as Record<string, unknown> | undefined) ?? null)
const proc = computed(() => (latest.value?.process as Record<string, unknown> | undefined) ?? null)
const net = computed(() => (latest.value?.network as Record<string, unknown> | undefined) ?? null)
const redis = computed(() => (latest.value?.redis as Record<string, unknown> | undefined) ?? null)
const ws = computed(() => (latest.value?.websockets as Record<string, unknown> | undefined) ?? null)
const act = computed(() => (latest.value?.activity as Record<string, unknown> | undefined) ?? null)
const aiCardStreaming = computed(() => {
  const raw = latest.value?.mindbot_ai_card_streaming as Record<string, unknown> | undefined
  if (!raw || typeof raw !== 'object') return null
  const now = raw.active_now
  if (typeof now !== 'number' || !Number.isFinite(now)) return null
  const max24 = raw.active_max_24h
  const cErr = raw.concurrency_error
  const pErr = raw.peak_24h_error
  return {
    activeNow: Math.max(0, Math.floor(now)),
    activeMax24h:
      typeof max24 === 'number' && Number.isFinite(max24) ? Math.max(0, Math.floor(max24)) : null,
    concurrencyError: typeof cErr === 'string' && cErr ? cErr : null,
    peak24hError: typeof pErr === 'string' && pErr ? pErr : null,
  }
})

const mindmateStreaming = computed(() => {
  const raw = latest.value?.mindmate_streaming as Record<string, unknown> | undefined
  if (!raw || typeof raw !== 'object') return null
  const now = raw.active_now
  if (typeof now !== 'number' || !Number.isFinite(now)) return null
  const max24 = raw.active_max_24h
  const cErr = raw.concurrency_error
  const pErr = raw.peak_24h_error
  return {
    activeNow: Math.max(0, Math.floor(now)),
    activeMax24h:
      typeof max24 === 'number' && Number.isFinite(max24) ? Math.max(0, Math.floor(max24)) : null,
    concurrencyError: typeof cErr === 'string' && cErr ? cErr : null,
    peak24hError: typeof pErr === 'string' && pErr ? pErr : null,
  }
})

const clusterMeta = computed(() => {
  const c = latest.value?.cluster as Record<string, unknown> | undefined
  if (!c) return null
  const n = c.workers_reporting
  if (typeof n !== 'number' || n < 2) return null
  return { n }
})

const hostRamCard = computed(() => {
  const h = host.value
  if (!h || h.error) return null
  const total = typeof h.mem_total_bytes === 'number' ? (h.mem_total_bytes as number) : 0
  const used = typeof h.mem_used_bytes === 'number' ? (h.mem_used_bytes as number) : 0
  const pct = typeof h.mem_percent === 'number' ? clampPct(h.mem_percent as number) : 0
  return {
    pct,
    line: t('admin.performance.ramFraction', {
      used: total ? formatBytes(used) : '—',
      total: total ? formatBytes(total) : '—',
    }),
  }
})

const appRamCard = computed(() => {
  const h = host.value
  const p = proc.value
  if (!h || h.error || !p || p.error) return null
  const total = typeof h.mem_total_bytes === 'number' ? (h.mem_total_bytes as number) : 0
  const rss = typeof p.rss_bytes === 'number' ? (p.rss_bytes as number) : 0
  const pct = total > 0 ? clampPct((rss / total) * 100) : 0
  const workerCount = typeof p.worker_count === 'number' ? p.worker_count : 1
  const pid = typeof p.pid === 'number' ? p.pid : null
  return {
    pct,
    line: t('admin.performance.ramFraction', {
      used: formatBytes(rss),
      total: total ? formatBytes(total) : '—',
    }),
    pid,
    workerCount,
  }
})

const hostCpuCard = computed(() => {
  const h = host.value
  if (!h || h.error) return null
  const pct = typeof h.cpu_percent === 'number' ? clampPct(h.cpu_percent as number) : 0
  const cpus = typeof h.cpu_count === 'number' ? h.cpu_count : null
  return {
    pct,
    sub: cpus != null ? t('admin.performance.logicalCpus', { n: String(cpus) }) : '',
  }
})

const processCpuCard = computed(() => {
  const p = proc.value
  if (!p || p.error) return null
  const sumRaw = typeof p.cpu_percent === 'number' ? (p.cpu_percent as number) : 0
  const maxRaw = typeof p.cpu_percent_max === 'number' ? (p.cpu_percent_max as number) : sumRaw
  const workerCount = typeof p.worker_count === 'number' ? p.worker_count : 1
  const ringPct = clampPct(Math.min(100, sumRaw))
  return {
    headerPct: clampPct(sumRaw),
    ringPct,
    maxPct: clampPct(maxRaw),
    workerCount,
    clusterHint:
      workerCount > 1
        ? t('admin.performance.processCpuSumHint', {
            sum: String(clampPct(sumRaw)),
            max: String(clampPct(maxRaw)),
            n: String(workerCount),
          })
        : '',
  }
})

const diskCard = computed(() => {
  const h = host.value
  if (!h || h.error) return null
  const d = h.disk_primary as Record<string, unknown> | undefined
  if (!d) return null
  const pct = typeof d.percent_used === 'number' ? clampPct(d.percent_used as number) : 0
  const mount = typeof d.mount === 'string' ? d.mount : '—'
  return {
    pct,
    line:
      typeof d.used_bytes === 'number' && typeof d.total_bytes === 'number'
        ? t('admin.performance.ramFraction', {
            used: formatBytes(d.used_bytes as number),
            total: formatBytes(d.total_bytes as number),
          })
        : mount,
  }
})

const netCards = computed(() => {
  const n = net.value
  if (!n || n.error) return null
  const up = typeof n.bytes_sent_per_sec === 'number' ? (n.bytes_sent_per_sec as number) : null
  const down = typeof n.bytes_recv_per_sec === 'number' ? (n.bytes_recv_per_sec as number) : null
  const fmt = (x: number) =>
    x >= 1048576 ? `${(x / 1048576).toFixed(2)} MB/s` : `${(x / 1024).toFixed(1)} KB/s`
  return {
    up: up != null ? fmt(up) : '—',
    down: down != null ? fmt(down) : '—',
  }
})

const redisCard = computed(() => {
  const r = redis.value
  if (!r || r.status !== 'healthy') return null
  const human = String(r.used_memory_human ?? '—')
  const peak = String(r.used_memory_peak_human ?? '—')
  const frag = r.mem_fragmentation_ratio
  const fragPct =
    typeof frag === 'number' && Number.isFinite(frag) ? clampPct(Math.min(frag * 25, 100)) : 0
  return { human, peak, fragPct, fragText: typeof frag === 'number' ? frag.toFixed(2) : '—' }
})

const connTiles = computed(() => {
  const w = ws.value
  const a = act.value
  const wOk = Boolean(w && !w.error)
  const aOk = Boolean(a && !a.error)
  if (!wOk && !aOk) return null
  return {
    chat: wOk && w ? Number(w.ws_chat_connections ?? 0) : null,
    workshop: wOk && w ? Number(w.ws_workshop_connections ?? 0) : null,
    wsRedis:
      wOk && w && typeof w.ws_active_total_redis === 'number'
        ? Number(w.ws_active_total_redis)
        : null,
    sessions: aOk && a ? Number(a.active_users_count ?? 0) : null,
    unique: aOk && a ? Number(a.unique_users_count ?? 0) : null,
  }
})

const appMeta = computed(() => {
  const a = latest.value?.app as Record<string, unknown> | undefined
  if (!a || a.error) return null
  return {
    version: String(a.version ?? '—'),
    uptime: typeof a.uptime_seconds === 'number' ? a.uptime_seconds : 0,
  }
})

const diskHint = computed(() => {
  const h = host.value
  const d = h?.disk_primary as Record<string, unknown> | undefined
  if (!h || h.error || !d || typeof d.mount !== 'string') return ''
  const used = typeof d.used_bytes === 'number' ? formatBytes(d.used_bytes as number) : '—'
  const free = typeof d.free_bytes === 'number' ? formatBytes(d.free_bytes as number) : '—'
  const total = typeof d.total_bytes === 'number' ? formatBytes(d.total_bytes as number) : '—'
  return t('admin.performance.diskHint', { mount: d.mount, used, free, total })
})

const redisDetailLine = computed(() => {
  const r = redis.value
  if (!r || r.status !== 'healthy') return ''
  const human = String(r.used_memory_human ?? '—')
  const peak = String(r.used_memory_peak_human ?? '—')
  const ver = String(r.redis_version ?? '—')
  const uptime = r.uptime_in_seconds != null ? String(r.uptime_in_seconds) : '—'
  return t('admin.performance.redisDetail', { human, peak, ver, uptime })
})

const diskExtraVolumes = computed(() => {
  const h = host.value
  if (!h || h.error || !Array.isArray(h.disk_volumes)) return []
  return h.disk_volumes as Array<{
    mount: string
    percent_used?: number
    used_bytes?: number
    free_bytes?: number
    total_bytes?: number
  }>
})

const wsExtraLines = computed(() => {
  const w = ws.value
  if (!w || w.error) return [] as string[]
  return [
    t('admin.performance.wsFanChat', {
      pub: String(w.ws_fanout_chat_published ?? 0),
      recv: String(w.ws_fanout_chat_received ?? 0),
    }),
    t('admin.performance.wsFanWorkshop', {
      pub: String(w.ws_fanout_workshop_published ?? 0),
      recv: String(w.ws_fanout_workshop_received ?? 0),
    }),
    t('admin.performance.wsAuthRate', {
      auth: String(w.ws_auth_failures ?? 0),
      rate: String(w.ws_rate_limit_hits ?? 0),
    }),
  ]
})

function pctLimitFlags(pct: number): { nearLimit: boolean; atLimit: boolean } {
  return {
    nearLimit: pct >= 70 && pct < 90,
    atLimit: pct >= 90,
  }
}

const progressColors = [
  { color: '#22d3ee', percentage: 60 },
  { color: '#fbbf24', percentage: 85 },
  { color: '#e30613', percentage: 100 },
]
</script>

<template>
  <div
    v-loading="loading"
    class="max-w-[1400px] mx-auto space-y-6"
  >
    <div>
      <h2 class="text-lg font-semibold text-[var(--swiss-text)]">
        {{ t('admin.performance.title') }}
      </h2>
      <p class="text-sm text-[var(--swiss-muted)] mt-1">
        {{ t('admin.performance.subtitle') }}
      </p>
    </div>

    <p
      v-if="clusterMeta"
      class="text-sm text-[var(--swiss-muted)] font-mono"
    >
      {{ t('admin.performance.workersReportingCluster', { n: String(clusterMeta.n) }) }}
    </p>

    <p
      v-if="fetchError"
      class="text-sm text-[var(--swiss-stat-danger-accent,#e30613)]"
    >
      {{ fetchError }}
    </p>

    <p
      v-if="appMeta"
      class="text-xs text-[var(--swiss-muted)] font-mono"
    >
      {{ t('admin.performance.version', { version: appMeta.version }) }}
      ·
      {{ t('admin.performance.uptimeSec', { sec: appMeta.uptime }) }}
    </p>

    <section
      v-if="hostRamCard || appRamCard || hostCpuCard || processCpuCard"
      aria-labelledby="perf-group-compute"
    >
      <h3
        id="perf-group-compute"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.performance.groupCompute') }}
      </h3>
      <div class="swiss-stat-card-grid swiss-stat-card-grid--wide">
        <AdminSwissPerfCard
          v-if="hostRamCard"
          :label="t('admin.performance.cardHostRam')"
          :pct="hostRamCard.pct"
          theme="storage"
          v-bind="pctLimitFlags(hostRamCard.pct)"
        >
          <template #sub>{{ hostRamCard.line }}</template>
        </AdminSwissPerfCard>

        <AdminSwissPerfCard
          v-if="appRamCard"
          :label="t('admin.performance.cardAppRam')"
          :pct="appRamCard.pct"
          theme="storage"
          v-bind="pctLimitFlags(appRamCard.pct)"
        >
          <template #sub>{{ appRamCard.line }}</template>
          <template
            v-if="appRamCard.workerCount > 1"
            #hint
          >
            {{ t('admin.performance.workersRssHint', { n: String(appRamCard.workerCount) }) }}
          </template>
          <template
            v-else-if="appRamCard.pid != null"
            #hint
          >
            {{ t('admin.performance.pidLabel', { pid: String(appRamCard.pid) }) }}
          </template>
        </AdminSwissPerfCard>

        <AdminSwissPerfCard
          v-if="hostCpuCard"
          :label="t('admin.performance.cardHostCpu')"
          :pct="hostCpuCard.pct"
          theme="warn"
          progress-variant="gauge"
          v-bind="pctLimitFlags(hostCpuCard.pct)"
        >
          <template
            v-if="hostCpuCard.sub"
            #sub
          >
            {{ hostCpuCard.sub }}
          </template>
        </AdminSwissPerfCard>

        <AdminSwissPerfCard
          v-if="processCpuCard"
          :label="t('admin.performance.cardProcessCpu')"
          :pct="processCpuCard.ringPct"
          theme="warn"
          progress-variant="gauge"
          v-bind="pctLimitFlags(processCpuCard.ringPct)"
        >
          <template #hint>
            {{
              processCpuCard.workerCount > 1
                ? processCpuCard.clusterHint
                : t('admin.performance.hintProcessCpuSingle')
            }}
          </template>
        </AdminSwissPerfCard>
      </div>
    </section>

    <section
      v-if="diskCard || netCards || diskExtraVolumes.length"
      aria-labelledby="perf-group-storage"
    >
      <h3
        id="perf-group-storage"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.performance.groupStorageNet') }}
      </h3>
      <div class="swiss-stat-card-grid swiss-stat-card-grid--wide">
        <AdminSwissPerfCard
          v-if="diskCard"
          :label="t('admin.performance.cardPrimaryDisk')"
          :pct="diskCard.pct"
          theme="storage"
          v-bind="pctLimitFlags(diskCard.pct)"
        >
          <template #sub>{{ diskCard.line }}</template>
          <template
            v-if="diskHint"
            #hint
          >
            {{ diskHint }}
          </template>
        </AdminSwissPerfCard>

        <AdminSwissPerfCard
          v-if="netCards"
          :label="t('admin.performance.sectionNetwork')"
          theme="integration"
          progress-variant="none"
        >
          <div class="swiss-stat-card__stat-grid">
            <div class="swiss-stat-card__stat-pill">
              <span class="swiss-stat-card__stat-pill-k">{{ t('admin.performance.netUp') }}</span>
              <span class="swiss-stat-card__stat-pill-v">{{ netCards.up }}</span>
            </div>
            <div class="swiss-stat-card__stat-pill">
              <span class="swiss-stat-card__stat-pill-k">{{ t('admin.performance.netDown') }}</span>
              <span class="swiss-stat-card__stat-pill-v">{{ netCards.down }}</span>
            </div>
          </div>
          <template #hint>
            {{ t('admin.performance.hintNetwork') }}
          </template>
        </AdminSwissPerfCard>
      </div>

      <div
        v-if="diskExtraVolumes.length"
        class="mt-4"
      >
        <div class="swiss-stat-card-group__title">{{ t('admin.performance.sectionOtherVolumes') }}</div>
        <el-table
          :data="diskExtraVolumes"
          size="small"
          class="font-mono mt-2"
          max-height="200"
        >
          <el-table-column
            prop="mount"
            :label="t('admin.performance.colVolumeMount')"
            min-width="120"
          />
          <el-table-column
            :label="t('admin.performance.colVolumePct')"
            width="100"
          >
            <template #default="{ row }">
              <el-progress
                v-if="row.percent_used != null"
                :percentage="clampPct(row.percent_used)"
                :stroke-width="8"
                :color="progressColors"
              />
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <section
      v-if="redisCard || connTiles || aiCardStreaming || mindmateStreaming"
      aria-labelledby="perf-group-platform"
    >
      <h3
        id="perf-group-platform"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.performance.groupPlatform') }}
      </h3>
      <div class="space-y-4">
        <div
          v-if="redisCard || connTiles"
          class="swiss-stat-card-grid--dual"
        >
          <AdminSwissPerfCard
            v-if="redisCard"
            :label="t('admin.performance.sectionRedis')"
            :pct="redisCard.fragPct"
            theme="integration"
            progress-variant="linear"
            v-bind="pctLimitFlags(redisCard.fragPct)"
          >
            <template #kpi>
              {{ redisCard.human }}
              · {{ t('admin.performance.peakLabel') }} {{ redisCard.peak }}
              · {{ t('admin.performance.fragLabel') }} {{ redisCard.fragText }}
            </template>
            <template
              v-if="redisDetailLine"
              #hint
            >
              {{ redisDetailLine }}
            </template>
          </AdminSwissPerfCard>

          <AdminSwissPerfCard
            v-if="connTiles"
            :label="t('admin.performance.sectionConnections')"
            theme="members"
            progress-variant="none"
          >
            <div class="swiss-stat-card__stat-grid">
              <div
                v-if="connTiles.chat != null"
                class="swiss-stat-card__stat-pill"
              >
                <span class="swiss-stat-card__stat-pill-k">{{ t('admin.performance.tileWsChat') }}</span>
                <span class="swiss-stat-card__stat-pill-v">{{ connTiles.chat }}</span>
              </div>
              <div
                v-if="connTiles.workshop != null"
                class="swiss-stat-card__stat-pill"
              >
                <span class="swiss-stat-card__stat-pill-k">{{
                  t('admin.performance.tileWsWorkshop')
                }}</span>
                <span class="swiss-stat-card__stat-pill-v">{{ connTiles.workshop }}</span>
              </div>
              <div
                v-if="connTiles.wsRedis != null"
                class="swiss-stat-card__stat-pill"
              >
                <span class="swiss-stat-card__stat-pill-k">{{ t('admin.performance.tileWsRedis') }}</span>
                <span class="swiss-stat-card__stat-pill-v">{{ connTiles.wsRedis }}</span>
              </div>
              <div
                v-if="connTiles.sessions != null"
                class="swiss-stat-card__stat-pill"
              >
                <span class="swiss-stat-card__stat-pill-k">{{ t('admin.performance.tileSessions') }}</span>
                <span class="swiss-stat-card__stat-pill-v">{{ connTiles.sessions }}</span>
              </div>
              <div
                v-if="connTiles.unique != null"
                class="swiss-stat-card__stat-pill"
              >
                <span class="swiss-stat-card__stat-pill-k">{{
                  t('admin.performance.tileUniqueUsers')
                }}</span>
                <span class="swiss-stat-card__stat-pill-v">{{ connTiles.unique }}</span>
              </div>
            </div>
            <template #hint>
              <span
                v-for="(line, idx) in wsExtraLines"
                :key="idx"
                class="block"
              >{{ line }}</span>
              {{ t('admin.performance.hintConnections') }}
            </template>
          </AdminSwissPerfCard>
        </div>

        <div
          v-if="aiCardStreaming || mindmateStreaming"
          class="swiss-stat-card-grid--dual"
        >
          <AdminSwissPerfCard
            v-if="aiCardStreaming"
            :label="t('admin.performance.sectionAiCardStreaming')"
            theme="mindgraph"
            progress-variant="none"
          >
            <template #kpi>{{ aiCardStreaming.activeNow }}</template>
            <p
              v-if="aiCardStreaming.concurrencyError"
              class="swiss-stat-card__sub text-[var(--swiss-stat-danger-accent,#e30613)]"
            >
              {{
                t('admin.performance.mindbotStreamingNowError', {
                  reason: aiCardStreaming.concurrencyError,
                })
              }}
            </p>
            <p class="swiss-stat-card__sub">
              {{ t('admin.performance.streamingMax24hLabel') }}
              {{ aiCardStreaming.activeMax24h != null ? aiCardStreaming.activeMax24h : '—' }}
            </p>
            <template #hint>
              <span
                v-if="aiCardStreaming.peak24hError"
                class="text-[var(--swiss-stat-danger-accent,#e30613)]"
              >
                {{
                  t('admin.performance.streamingMax24hError', {
                    reason: aiCardStreaming.peak24hError,
                  })
                }}
              </span>
              <span v-else>{{ t('admin.performance.hintAiCardStreaming') }}</span>
            </template>
          </AdminSwissPerfCard>

          <AdminSwissPerfCard
            v-if="mindmateStreaming"
            :label="t('admin.performance.sectionMindmateStreaming')"
            theme="mindmate"
            progress-variant="none"
          >
            <template #kpi>{{ mindmateStreaming.activeNow }}</template>
            <p
              v-if="mindmateStreaming.concurrencyError"
              class="swiss-stat-card__sub text-[var(--swiss-stat-danger-accent,#e30613)]"
            >
              {{
                t('admin.performance.mindmateStreamingNowError', {
                  reason: mindmateStreaming.concurrencyError,
                })
              }}
            </p>
            <p class="swiss-stat-card__sub">
              {{ t('admin.performance.streamingMax24hLabel') }}
              {{ mindmateStreaming.activeMax24h != null ? mindmateStreaming.activeMax24h : '—' }}
            </p>
            <template #hint>
              <span
                v-if="mindmateStreaming.peak24hError"
                class="text-[var(--swiss-stat-danger-accent,#e30613)]"
              >
                {{
                  t('admin.performance.streamingMax24hError', {
                    reason: mindmateStreaming.peak24hError,
                  })
                }}
              </span>
              <span v-else>{{ t('admin.performance.hintMindmateStreaming') }}</span>
            </template>
          </AdminSwissPerfCard>
        </div>
      </div>
    </section>
  </div>
</template>
