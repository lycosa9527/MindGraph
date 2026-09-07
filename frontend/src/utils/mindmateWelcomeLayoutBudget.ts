/** Layout budget for MindMate welcome + sidebar chrome across common displays. */

export interface ViewportSpec {
  name: string
  width: number
  height: number
}

export const COMMON_MINDMATE_VIEWPORTS: ViewportSpec[] = [
  { name: '720p', width: 1280, height: 720 },
  { name: '1366x768 laptop', width: 1366, height: 768 },
  { name: 'iPad landscape', width: 1024, height: 768 },
  { name: 'iPad portrait', width: 768, height: 1024 },
  { name: 'iPad Pro 11 portrait', width: 834, height: 1194 },
  { name: '1440x900 laptop', width: 1440, height: 900 },
  { name: '1080p', width: 1920, height: 1080 },
  { name: '1440p', width: 2560, height: 1440 },
  { name: '4K', width: 3840, height: 2160 },
  { name: '5K', width: 5120, height: 2880 },
]

const SIDEBAR_WIDTH = 240
const TOOLBAR_HEIGHT = 56
const SIDEBAR_HEADER_HEIGHT = 60
const ACCOUNT_ROW_HEIGHT = 72
const ACCOUNT_ROW_WITH_PROMO = 168
const COMPOSER_MIN = 320
const COMPOSER_MAX = 768
const CLUSTER_GUTTER = 24

function clamp(min: number, value: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function mindmateStageSize(
  width: number,
  height: number
): { stageWidth: number; stageHeight: number; icpHeight: number } {
  const icpHeight = height <= 700 ? 24 : 36
  return {
    stageWidth: Math.max(0, width - SIDEBAR_WIDTH),
    stageHeight: height - TOOLBAR_HEIGHT - icpHeight,
    icpHeight,
  }
}

export function welcomeClusterHeight(viewportHeight: number, stageHeight: number): number {
  const avatar = viewportHeight <= 700 ? 64 : clamp(64, stageHeight * 0.14, 128)
  const titleBlock = 72
  const suggest = viewportHeight <= 700 ? 108 : clamp(108, stageHeight * 0.18, 140)
  const input = 88
  const gaps = clamp(20, viewportHeight * 0.05, 64)
  return avatar + titleBlock + suggest + input + gaps
}

export function welcomeComposerWidth(stageWidth: number): number {
  return clamp(COMPOSER_MIN, stageWidth - CLUSTER_GUTTER * 2, COMPOSER_MAX)
}

export function sidebarAccountFits(viewportHeight: number): boolean {
  const footer = viewportHeight <= 800 ? ACCOUNT_ROW_HEIGHT : ACCOUNT_ROW_WITH_PROMO
  return SIDEBAR_HEADER_HEIGHT + footer + 96 <= viewportHeight
}

export function welcomeFitsViewport(width: number, height: number): boolean {
  const { stageWidth, stageHeight } = mindmateStageSize(width, height)
  const cluster = welcomeClusterHeight(height, stageHeight)
  const composer = welcomeComposerWidth(stageWidth)
  return (
    stageHeight >= cluster &&
    stageWidth >= composer + CLUSTER_GUTTER &&
    sidebarAccountFits(height)
  )
}
