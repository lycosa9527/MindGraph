<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useNotifications } from '@/composables'
import {
  type LlmControlField,
  type LlmControlView,
  fetchLlmControl,
  saveLlmControl,
} from '@/composables/queries/adminLlmControlApi'

const MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
const ENDPOINT_RE = /^ep-[A-Za-z0-9-]{8,64}$/
const DUMMY_ENDPOINT = 'ep-20250101000000-dummy'

const FIELD_LABEL: Record<string, string> = {
  DEEPSEEK_MODEL: 'admin.llmControl.field.deepseek',
  EXPRESS_MODEL: 'admin.llmControl.field.express',
  QWEN_MODEL_GENERATION: 'admin.llmControl.field.qwen',
  QWEN_MODEL_CLASSIFICATION: 'admin.llmControl.field.qwenClassify',
  ARK_DEEPSEEK_ENDPOINT: 'admin.llmControl.field.arkDeepseek',
  ARK_DOUBAO_ENDPOINT: 'admin.llmControl.field.arkDoubao',
  ARK_KIMI_ENDPOINT: 'admin.llmControl.field.arkKimi',
}

const ROUTE_LABEL: Record<string, string> = {
  deepseek: 'admin.llmControl.route.deepseek',
  express: 'admin.llmControl.route.express',
  qwen: 'admin.llmControl.route.qwen',
  qwen38: 'admin.llmControl.route.qwen38',
  doubao: 'admin.llmControl.route.doubao',
  kimi: 'admin.llmControl.route.kimi',
}

const ROUTE_NOTE: Record<string, string> = {
  deepseek: 'admin.llmControl.routeNote.deepseek',
  express: 'admin.llmControl.routeNote.express',
  qwen: 'admin.llmControl.routeNote.qwen',
  qwen38: 'admin.llmControl.routeNote.qwen38',
  doubao: 'admin.llmControl.routeNote.doubao',
  kimi: 'admin.llmControl.routeNote.kimi',
}

const STRATEGY_LABEL: Record<string, string> = {
  weighted: 'admin.llmControl.strategy.weighted',
  round_robin: 'admin.llmControl.strategy.roundRobin',
  random: 'admin.llmControl.strategy.random',
}

const STRATEGY_HINT: Record<string, string> = {
  weighted: 'admin.llmControl.strategy.weightedHint',
  round_robin: 'admin.llmControl.strategy.roundRobinHint',
  random: 'admin.llmControl.strategy.randomHint',
}

const notify = useNotifications()

const loading = ref(false)
const saving = ref(false)
const view = ref<LlmControlView | null>(null)
const drafts = ref<Record<string, string>>({})

const modelFields = computed(() =>
  (view.value?.fields ?? []).filter((field) => field.kind === 'model')
)
const endpointFields = computed(() =>
  (view.value?.fields ?? []).filter((field) => field.kind === 'endpoint')
)

function applyView(next: LlmControlView): void {
  view.value = next
  const nextDrafts: Record<string, string> = {}
  for (const field of next.fields) {
    nextDrafts[field.key] = field.value
  }
  drafts.value = nextDrafts
}

async function load(): Promise<void> {
  loading.value = true
  try {
    applyView(await fetchLlmControl())
  } catch {
    notify.errorKey('admin.llmControl.loadError')
  } finally {
    loading.value = false
  }
}

function fieldLabel(key: string): string {
  return FIELD_LABEL[key] ?? 'admin.llmControl.tab'
}

function routeLabel(id: string): string {
  return ROUTE_LABEL[id] ?? 'admin.llmControl.tab'
}

function routeNote(id: string): string {
  return ROUTE_NOTE[id] ?? 'admin.llmControl.fixed'
}

function strategyLabel(id: string): string {
  return STRATEGY_LABEL[id] ?? 'admin.llmControl.strategy.weighted'
}

function strategyHint(id: string): string {
  return STRATEGY_HINT[id] ?? 'admin.llmControl.strategy.weightedHint'
}

function providerLabel(provider: string): string {
  if (provider === 'volcengine') {
    return 'admin.llmControl.provider.volcengine'
  }
  return 'admin.llmControl.provider.dashscope'
}

function targetKindLabel(kind: string): string {
  if (kind === 'endpoint') {
    return 'admin.llmControl.endpoint'
  }
  return 'admin.llmControl.modelName'
}

function formatCount(value: number): string {
  return new Intl.NumberFormat().format(value)
}

function fieldValid(field: LlmControlField): boolean {
  const value = (drafts.value[field.key] ?? '').trim()
  if (field.kind === 'model') {
    return MODEL_RE.test(value)
  }
  return ENDPOINT_RE.test(value) && value !== DUMMY_ENDPOINT
}

function restoreField(field: LlmControlField): void {
  drafts.value = { ...drafts.value, [field.key]: field.env_value }
}

const canSave = computed(() => {
  const current = view.value
  if (!current || saving.value) {
    return false
  }
  let changed = false
  for (const field of current.fields) {
    const draft = (drafts.value[field.key] ?? '').trim()
    if (draft !== field.value) {
      changed = true
      if (!fieldValid(field)) {
        return false
      }
    }
  }
  return changed
})

async function save(): Promise<void> {
  const current = view.value
  if (!current || !canSave.value) {
    return
  }
  const updates: Record<string, string | null> = {}
  for (const field of current.fields) {
    const draft = (drafts.value[field.key] ?? '').trim()
    if (draft !== field.value) {
      updates[field.key] = draft
    }
  }
  saving.value = true
  try {
    applyView(await saveLlmControl(updates))
    notify.successKey('admin.llmControl.saved')
  } catch (err) {
    const message = err instanceof Error ? err.message : ''
    if (message === 'redis_unavailable') {
      notify.errorKey('admin.llmControl.redisDown')
    } else if (message === 'invalid_value' || message === 'unknown_field') {
      notify.errorKey('admin.llmControl.invalid')
    } else {
      notify.errorKey('admin.llmControl.saveError')
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="admin-llm-control space-y-6">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold"><I18nText k="admin.llmControl.tab" /></span>
          <el-button
            size="small"
            :loading="loading"
            @click="load"
          >
            <I18nText k="admin.refresh" />
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="view && !view.redis_ok"
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
      >
        <I18nText k="admin.llmControl.redisDown" />
      </el-alert>
      <el-alert
        v-if="view && !view.tokens_ok"
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
      >
        <I18nText k="admin.llmControl.tokensUnavailable" />
      </el-alert>

      <div
        v-if="view"
        class="diagram"
      >
        <p class="policy-note">
          <I18nText k="admin.llmControl.policyNote" />
        </p>
        <p
          v-if="!view.balancing_enabled"
          class="policy-note"
        >
          <I18nText k="admin.llmControl.balancingOff" />
        </p>
        <h3 class="section-label">
          <I18nText k="admin.llmControl.strategyTitle" />
        </h3>
        <div class="strategy-row">
          <article
            v-for="item in view.strategies"
            :key="item.id"
            class="strategy-card"
            :class="{ 'strategy-card--active': item.active && view.balancing_enabled }"
          >
            <header>
              <I18nText :k="strategyLabel(item.id)" />
              <span
                v-if="item.active && view.balancing_enabled"
                class="active-pill"
              >
                <I18nText k="admin.llmControl.strategyActive" />
              </span>
            </header>
            <p><I18nText :k="strategyHint(item.id)" /></p>
          </article>
        </div>
        <div class="weight-block">
          <div class="weight-caption">
            <I18nText k="admin.llmControl.weightBar" />
            <span v-if="view.strategy !== 'weighted' || !view.balancing_enabled">
              <I18nText k="admin.llmControl.weightsUnused" />
            </span>
          </div>
          <div
            class="weight-bar"
            role="img"
          >
            <span
              class="weight-bar__dash"
              :style="{ width: `${view.weights.dashscope}%` }"
            />
            <span
              class="weight-bar__volc"
              :style="{ width: `${view.weights.volcengine}%` }"
            />
          </div>
          <div class="weight-legend">
            <span>
              <I18nText k="admin.llmControl.provider.dashscope" />
              {{ view.weights.dashscope }}%
            </span>
            <span>
              <I18nText k="admin.llmControl.provider.volcengine" />
              {{ view.weights.volcengine }}%
            </span>
          </div>
        </div>
        <section
          v-for="route in view.routes"
          :key="route.id"
          class="route"
        >
          <div class="route-name">
            <I18nText :k="routeLabel(route.id)" />
            <span class="route-mode">
              <I18nText :k="routeNote(route.id)" />
            </span>
          </div>
          <div
            class="route-mark"
            aria-hidden="true"
          >
            {{ route.split ? '⇉' : '→' }}
          </div>
          <div class="legs">
            <article
              v-for="leg in route.legs"
              :key="leg.id"
              class="leg"
              :class="leg.provider === 'volcengine' ? 'leg--volcengine' : 'leg--dashscope'"
            >
              <header class="leg-head">
                <I18nText :k="providerLabel(leg.provider)" />
                <span
                  v-if="leg.weight != null"
                  class="weight"
                >
                  <I18nText k="admin.llmControl.weight" />
                  {{ leg.weight }}%
                </span>
              </header>
              <p class="target">
                {{ leg.target }}
              </p>
              <p class="kind">
                <I18nText :k="targetKindLabel(leg.target_kind)" />
              </p>
              <p class="rpm">
                <I18nText k="admin.llmControl.appRpm" />
                {{ formatCount(leg.app_rpm) }} RPM
                <span v-if="leg.shares_app_rpm"
                  >· <I18nText k="admin.llmControl.sharedExpress"
                /></span>
              </p>
              <p
                v-if="leg.quota_kind === 'fixed' && leg.provider_rpm != null"
                class="rpm"
              >
                <I18nText k="admin.llmControl.providerQuota" />
                {{ formatCount(leg.provider_rpm) }} RPM
                <template v-if="leg.provider_tpm != null">
                  · {{ formatCount(leg.provider_tpm) }} TPM
                </template>
              </p>
              <p
                v-else-if="leg.quota_kind === 'dynamic'"
                class="rpm"
              >
                <I18nText k="admin.llmControl.providerQuota" />
                <I18nText k="admin.llmControl.dynamicLimit" />
              </p>
              <p
                v-else
                class="rpm"
              >
                <I18nText k="admin.llmControl.providerQuota" />
                <I18nText k="admin.llmControl.endpointQuota" />
              </p>
              <footer class="leg-stats">
                <span>{{ formatCount(leg.tokens) }} <I18nText k="admin.llmControl.tokens" /></span>
                <span
                  >{{ formatCount(leg.requests) }} <I18nText k="admin.llmControl.requests"
                /></span>
              </footer>
            </article>
          </div>
        </section>
      </div>
    </el-card>

    <el-card
      v-if="view"
      shadow="never"
    >
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold"><I18nText k="admin.llmControl.editTitle" /></span>
          <el-button
            type="primary"
            size="small"
            :disabled="!canSave"
            :loading="saving"
            @click="save"
          >
            <I18nText k="admin.llmControl.save" />
          </el-button>
        </div>
      </template>
      <p class="edit-hint">
        <I18nText k="admin.llmControl.editHint" />
      </p>
      <div class="edit-grid">
        <section>
          <h3><I18nText k="admin.llmControl.dashscopeModels" /></h3>
          <div
            v-for="field in modelFields"
            :key="field.key"
            class="field"
          >
            <label :for="field.key"><I18nText :k="fieldLabel(field.key)" /></label>
            <el-input
              :id="field.key"
              v-model="drafts[field.key]"
              size="small"
            />
            <p class="field-meta">
              <span v-if="field.overridden"><I18nText k="admin.llmControl.overridden" /></span>
              <span><I18nText k="admin.llmControl.envValue" />: {{ field.env_value }}</span>
              <el-button
                link
                type="primary"
                size="small"
                @click="restoreField(field)"
              >
                <I18nText k="admin.llmControl.restore" />
              </el-button>
            </p>
            <p
              v-if="drafts[field.key] && !fieldValid(field)"
              class="field-error"
            >
              <I18nText k="admin.llmControl.invalid" />
            </p>
          </div>
        </section>
        <section>
          <h3><I18nText k="admin.llmControl.volcengineEndpoints" /></h3>
          <div
            v-for="field in endpointFields"
            :key="field.key"
            class="field"
          >
            <label :for="field.key"><I18nText :k="fieldLabel(field.key)" /></label>
            <el-input
              :id="field.key"
              v-model="drafts[field.key]"
              size="small"
            />
            <p class="field-meta">
              <span v-if="field.overridden"><I18nText k="admin.llmControl.overridden" /></span>
              <span><I18nText k="admin.llmControl.envValue" />: {{ field.env_value }}</span>
              <el-button
                link
                type="primary"
                size="small"
                @click="restoreField(field)"
              >
                <I18nText k="admin.llmControl.restore" />
              </el-button>
            </p>
            <p
              v-if="drafts[field.key] && !fieldValid(field)"
              class="field-error"
            >
              <I18nText k="admin.llmControl.invalid" />
            </p>
          </div>
        </section>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.policy-note,
.diagram-note,
.edit-hint,
.field-meta,
.kind,
.leg-stats {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.policy-note {
  margin: 0 0 0.85rem;
}

.section-label {
  margin: 0 0 0.6rem;
  font-size: 14px;
  font-weight: 600;
}

.strategy-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.strategy-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 0.7rem 0.85rem;
  background: var(--el-fill-color-blank);
}

.strategy-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-weight: 600;
}

.strategy-card p {
  margin: 0.35rem 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.strategy-card--active {
  border-color: var(--el-color-primary);
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
}

.active-pill {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-primary);
}

.weight-block {
  margin-bottom: 0.25rem;
}

.weight-caption,
.weight-legend {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.weight-bar {
  display: flex;
  height: 10px;
  margin: 0.4rem 0;
  overflow: hidden;
  border-radius: 999px;
  background: var(--el-fill-color);
}

.weight-bar__dash {
  background: #625fff;
}

.weight-bar__volc {
  background: #3370ff;
}

.rpm {
  margin: 0.15rem 0 0;
  color: var(--el-text-color-regular);
  font-size: 12px;
}

.route {
  display: grid;
  grid-template-columns: 8.5rem 1.5rem minmax(0, 1fr);
  gap: 0.75rem;
  align-items: center;
  padding: 0.85rem 0;
  border-top: 1px solid var(--el-border-color-lighter);
}

.route-name {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-weight: 600;
}

.route-mode,
.weight {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.route-mark {
  text-align: center;
  color: var(--el-text-color-secondary);
}

.legs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0.75rem;
}

.leg {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 0.75rem 0.9rem;
  background: var(--el-fill-color-blank);
}

.leg--dashscope {
  border-top: 3px solid #625fff;
}

.leg--volcengine {
  border-top: 3px solid #3370ff;
}

.leg-head,
.leg-stats,
.field-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  justify-content: space-between;
}

.target {
  margin: 0.35rem 0 0.15rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.92rem;
  word-break: break-all;
}

.kind,
.leg-stats,
.field-meta,
.field-error,
.edit-hint {
  margin: 0.2rem 0 0;
}

.edit-hint {
  margin-bottom: 1rem;
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.5rem;
}

.edit-grid h3 {
  margin: 0 0 0.75rem;
  font-size: 14px;
  font-weight: 600;
}

.field {
  margin-bottom: 1rem;
}

.field label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 13px;
}

.field-error {
  color: var(--el-color-danger);
  font-size: 12px;
}

@media (max-width: 720px) {
  .route {
    grid-template-columns: 1fr;
  }

  .route-mark {
    display: none;
  }
}
</style>
