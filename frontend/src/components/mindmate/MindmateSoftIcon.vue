<script setup lang="ts">
/**
 * Soft lavender icon set for MindMate seminar chat (rounded, outline + fill).
 */
export type MindmateSoftIconName =
  | 'members'
  | 'files'
  | 'artifacts'
  | 'highlights'
  | 'brief'
  | 'chat'
  | 'plus'
  | 'agent'
  | 'plugins'
  | 'mindgraph'
  | 'voice'
  | 'summary'
  | 'trace'
  | 'upload'
  | 'close'
  | 'trash'
  | 'chevron'

withDefaults(
  defineProps<{
    name: MindmateSoftIconName
    size?: number
  }>(),
  { size: 20 }
)
</script>

<template>
  <svg
    class="mm-soft-icon"
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <!-- 成员：圆框 + 实心人像 + 侧旁轮廓人 -->
    <g v-if="name === 'members'">
      <circle
        cx="10.2"
        cy="12"
        r="6.6"
        stroke="currentColor"
        stroke-width="2.1"
      />
      <circle
        cx="10.2"
        cy="9.6"
        r="2.05"
        fill="currentColor"
      />
      <path
        d="M6.55 15.7c.55-1.85 1.95-2.85 3.65-2.85s3.1 1 3.65 2.85"
        fill="currentColor"
      />
      <path
        d="M16.2 8.4c1.35.35 2.35 1.55 2.35 3.15 0 1.2-.55 2.2-1.45 2.85"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
      <circle
        cx="18.35"
        cy="7.15"
        r="1.15"
        fill="currentColor"
      />
    </g>

    <!-- 文件：叠页文档 + 横线 -->
    <g v-else-if="name === 'files'">
      <rect
        x="7.4"
        y="4.2"
        width="10.2"
        height="13.2"
        rx="2.4"
        stroke="currentColor"
        stroke-width="2"
      />
      <rect
        x="4.6"
        y="6.6"
        width="10.2"
        height="13.2"
        rx="2.4"
        fill="currentColor"
      />
      <path
        d="M7 11.2h5.2M7 14h4.1M7 16.8h3.2"
        stroke="#fff"
        stroke-width="1.7"
        stroke-linecap="round"
      />
    </g>

    <!-- 产物：圆角星芒 + 点缀圆点 -->
    <g v-else-if="name === 'artifacts'">
      <path
        d="M11.2 4.2c.35-1.05 1.85-1.05 2.2 0l1.05 3.15c.12.36.4.62.77.7l3.25.55c1.1.18 1.55 1.5.72 2.25l-2.45 2.2c-.28.25-.4.63-.33 1l.7 3.25c.23 1.08-.92 1.92-1.88 1.35l-2.85-1.7a1 1 0 0 0-1 0l-2.85 1.7c-.96.57-2.11-.27-1.88-1.35l.7-3.25a1 1 0 0 0-.33-1l-2.45-2.2c-.83-.75-.38-2.07.72-2.25l3.25-.55c.37-.08.65-.34.77-.7L11.2 4.2Z"
        fill="currentColor"
      />
      <circle
        cx="19.2"
        cy="6.2"
        r="1.35"
        fill="currentColor"
      />
      <path
        d="M18.4 16.6c.2-.6 1.05-.6 1.25 0l.45 1.35c.07.2.22.35.43.4l1.4.24c.6.1.85.82.4 1.23l-1.05.95c-.16.14-.23.35-.19.55l.3 1.4c.13.6-.5 1.05-1.03.74l-1.22-.73a.5.5 0 0 0-.5 0l-1.22.73c-.53.31-1.16-.14-1.03-.74l.3-1.4a.5.5 0 0 0-.19-.55l-1.05-.95c-.45-.41-.2-1.13.4-1.23l1.4-.24c.2-.05.36-.2.43-.4l.45-1.35Z"
        stroke="currentColor"
        stroke-width="1.35"
        stroke-linejoin="round"
      />
    </g>

    <!-- 精华：与侧栏 Lucide 图标同线宽的气泡 + 四角星 -->
    <g v-else-if="name === 'highlights'">
      <path
        d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M12 7 13 10.05 16.05 11.05 13 12.05 12 15.1 11 12.05 7.95 11.05 11 10.05Z"
        fill="currentColor"
        stroke="none"
      />
    </g>

    <!-- 对话：圆角气泡 + 点缀 -->
    <g v-else-if="name === 'chat'">
      <path
        d="M5.2 7.2c0-1.5 1.2-2.8 2.8-2.8h8c1.6 0 2.8 1.3 2.8 2.8v5.6c0 1.5-1.2 2.8-2.8 2.8H11l-3.4 2.6c-.55.42-1.35.02-1.35-.66V15.6c-1.1-.35-1.95-1.4-1.95-2.8V7.2Z"
        stroke="currentColor"
        stroke-width="2"
        stroke-linejoin="round"
      />
      <circle
        cx="9.2"
        cy="10"
        r="1.15"
        fill="currentColor"
      />
      <circle
        cx="12"
        cy="10"
        r="1.15"
        fill="currentColor"
      />
      <circle
        cx="14.8"
        cy="10"
        r="1.15"
        fill="currentColor"
      />
      <circle
        cx="18.6"
        cy="6.2"
        r="1.2"
        fill="currentColor"
      />
    </g>

    <!-- 主题条：双星 -->
    <g v-else-if="name === 'brief'">
      <path
        d="M10.5 3.8c.3-.9 1.6-.9 1.9 0l.9 2.7c.1.3.35.52.66.58l2.8.47c.95.16 1.33 1.28.62 1.92l-2.1 1.9c-.24.21-.34.53-.28.84l.6 2.8c.2.93-.79 1.65-1.62 1.16l-2.45-1.46a.9.9 0 0 0-.9 0L8.18 16.17c-.83.49-1.82-.23-1.62-1.16l.6-2.8a.9.9 0 0 0-.28-.84l-2.1-1.9c-.71-.64-.33-1.76.62-1.92l2.8-.47c.31-.06.56-.28.66-.58l.9-2.7Z"
        fill="currentColor"
      />
      <circle
        cx="18.6"
        cy="7"
        r="1.5"
        fill="currentColor"
      />
      <path
        d="M17.8 14.8c.18-.55.95-.55 1.13 0l.4 1.2c.06.18.2.32.38.36l1.25.21c.54.09.76.74.36 1.1l-.95.85a.45.45 0 0 0-.16.5l.27 1.25c.11.53-.45.94-.92.66l-1.1-.66a.45.45 0 0 0-.45 0l-1.1.66c-.47.28-1.03-.13-.92-.66l.27-1.25a.45.45 0 0 0-.16-.5l-.95-.85c-.4-.36-.18-1.01.36-1.1l1.25-.21c.18-.04.32-.18.38-.36l.4-1.2Z"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
      />
    </g>

    <!-- 加号：圆框 + 粗十字 -->
    <g v-else-if="name === 'plus'">
      <circle
        cx="12"
        cy="12"
        r="8.2"
        stroke="currentColor"
        stroke-width="2.1"
      />
      <path
        d="M12 8.2v7.6M8.2 12h7.6"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
      />
      <circle
        cx="17.8"
        cy="6.4"
        r="1.2"
        fill="currentColor"
      />
    </g>

    <!-- 智能体：圆框 + 耳机头像 -->
    <g v-else-if="name === 'agent'">
      <circle
        cx="12"
        cy="12"
        r="8.2"
        stroke="currentColor"
        stroke-width="2.1"
      />
      <circle
        cx="12"
        cy="10.2"
        r="2.3"
        fill="currentColor"
      />
      <path
        d="M7.8 16.4c.7-2 2.3-3.1 4.2-3.1s3.5 1.1 4.2 3.1"
        fill="currentColor"
      />
      <path
        d="M6.6 10.2v2.4c0 .9.7 1.6 1.6 1.6M17.4 10.2v2.4c0 .9-.7 1.6-1.6 1.6"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
      />
    </g>

    <!-- 插件：圆角拼图块 -->
    <g v-else-if="name === 'plugins'">
      <path
        d="M9.2 4.8h3.1c.7 0 1.1.55 1.1 1.15v1.1c0 .85.7 1.55 1.55 1.55h.1c.85 0 1.55-.7 1.55-1.55V5.95c0-.6.4-1.15 1.1-1.15H19c1 0 1.8.8 1.8 1.8v3.1c0 .7-.55 1.1-1.15 1.1h-1.1c-.85 0-1.55.7-1.55 1.55v.1c0 .85.7 1.55 1.55 1.55h1.1c.6 0 1.15.4 1.15 1.1V19c0 1-.8 1.8-1.8 1.8h-3.1c-.7 0-1.1-.55-1.1-1.15v-1.1c0-.85-.7-1.55-1.55-1.55h-.1c-.85 0-1.55.7-1.55 1.55v1.1c0 .6-.4 1.15-1.1 1.15H5.8c-1 0-1.8-.8-1.8-1.8v-3.1c0-.7.55-1.1 1.15-1.1h1.1c.85 0 1.55-.7 1.55-1.55v-.1c0-.85-.7-1.55-1.55-1.55h-1.1c-.6 0-1.15-.4-1.15-1.1V6.6c0-1 .8-1.8 1.8-1.8Z"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linejoin="round"
      />
      <circle
        cx="12"
        cy="12"
        r="1.7"
        fill="currentColor"
      />
    </g>

    <!-- MindGraph：节点连线 -->
    <g v-else-if="name === 'mindgraph'">
      <circle
        cx="6.5"
        cy="7"
        r="2.3"
        fill="currentColor"
      />
      <circle
        cx="17.5"
        cy="7"
        r="2.3"
        stroke="currentColor"
        stroke-width="1.9"
      />
      <circle
        cx="12"
        cy="17.2"
        r="2.5"
        fill="currentColor"
      />
      <path
        d="M8.4 8.3 10.4 15M15.6 8.3 13.6 15M8.8 7h6.4"
        stroke="currentColor"
        stroke-width="1.9"
        stroke-linecap="round"
      />
      <circle
        cx="19.6"
        cy="16.8"
        r="1.2"
        fill="currentColor"
      />
    </g>

    <!-- 语音：圆框 + 波形点 -->
    <g v-else-if="name === 'voice'">
      <circle
        cx="12"
        cy="12"
        r="8.2"
        stroke="currentColor"
        stroke-width="2.1"
      />
      <path
        d="M8.2 12.8c0-1.1.5-2.2 1.3-2.9.5-.4 1.1-.3 1.4.25L12 12l1.1-1.85c.3-.55.9-.65 1.4-.25.8.7 1.3 1.8 1.3 2.9 0 1.9-1.55 3.4-3.4 3.4S8.2 14.7 8.2 12.8Z"
        fill="currentColor"
      />
      <circle
        cx="17.6"
        cy="6.6"
        r="1.15"
        fill="currentColor"
      />
    </g>

    <!-- 总结：叠页说明 -->
    <g v-else-if="name === 'summary'">
      <rect
        x="6.8"
        y="3.8"
        width="11.4"
        height="14.4"
        rx="2.6"
        stroke="currentColor"
        stroke-width="2"
      />
      <rect
        x="4.4"
        y="6.2"
        width="11.4"
        height="14"
        rx="2.6"
        fill="currentColor"
      />
      <path
        d="M7 11h5.4M7 13.8h4.2M7 16.6h3.2"
        stroke="#fff"
        stroke-width="1.7"
        stroke-linecap="round"
      />
    </g>

    <!-- 痕迹：放大镜 + 点 -->
    <g v-else-if="name === 'trace'">
      <circle
        cx="10.4"
        cy="10.4"
        r="5.4"
        stroke="currentColor"
        stroke-width="2.1"
      />
      <path
        d="M14.6 14.6 19 19"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
      />
      <circle
        cx="10.4"
        cy="10.4"
        r="2"
        fill="currentColor"
      />
      <circle
        cx="18.8"
        cy="7"
        r="1.25"
        fill="currentColor"
      />
    </g>

    <!-- 上传：托盘 + 上箭头 -->
    <g v-else-if="name === 'upload'">
      <path
        d="M5.5 14.5v2.8c0 1.3 1 2.3 2.3 2.3h8.4c1.3 0 2.3-1 2.3-2.3v-2.8"
        stroke="currentColor"
        stroke-width="2.1"
        stroke-linecap="round"
      />
      <path
        d="M12 16.2V5.6"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
      />
      <path
        d="M8.4 8.6 12 5.2l3.6 3.4"
        stroke="currentColor"
        stroke-width="2.1"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle
        cx="17.8"
        cy="6.2"
        r="1.2"
        fill="currentColor"
      />
    </g>

    <!-- 关闭 -->
    <g v-else-if="name === 'close'">
      <circle
        cx="12"
        cy="12"
        r="8.2"
        stroke="currentColor"
        stroke-width="2"
      />
      <path
        d="m9.1 9.1 5.8 5.8M14.9 9.1l-5.8 5.8"
        stroke="currentColor"
        stroke-width="2.1"
        stroke-linecap="round"
      />
    </g>

    <!-- 删除 -->
    <g v-else-if="name === 'trash'">
      <path
        d="M5.8 8.2h12.4"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path
        d="M9 8.2V6.6c0-.9.7-1.6 1.6-1.6h2.8c.9 0 1.6.7 1.6 1.6v1.6"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
      />
      <path
        d="M7.6 8.2 8.5 18c.1 1 .95 1.75 1.95 1.75h3.1c1 0 1.85-.75 1.95-1.75l.9-9.8"
        stroke="currentColor"
        stroke-width="2"
        stroke-linejoin="round"
      />
      <circle
        cx="12"
        cy="13.2"
        r="1.15"
        fill="currentColor"
      />
    </g>

    <!-- 箭头 -->
    <g v-else-if="name === 'chevron'">
      <path
        d="m9.2 6.5 5.6 5.5-5.6 5.5"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </g>
  </svg>
</template>

<style scoped>
.mm-soft-icon {
  display: block;
  flex-shrink: 0;
  color: var(--mm-soft-icon, inherit);
}
</style>
