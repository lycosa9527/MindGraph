/**
 * Full-screen retro pixel battle for /auth — black cat vs Ultraman with laser beams.
 * Gated by FEATURE_AUTH_PIXEL_BATTLE on the server.
 *
 * Fight choreography loops every ~32 seconds (1920 frames @ 60fps).
 */

export type AuthPixelBattleDispose = () => void

export const FIGHT_CYCLE_FRAMES = 1920

const W = 320
const H = 180

/** Palette indices → CSS colors (0 = transparent). */
const PALETTE: (string | null)[] = [
  null,
  '#05050c', // 1 night
  '#1a1040', // 2 sky
  '#2d1b69', // 3 sky glow
  '#0b0b0f', // 4 cat black
  '#1a1a24', // 5 cat shade
  '#a3e635', // 6 cat eye / beam
  '#bef264', // 7 beam core
  '#dc2626', // 8 ultraman red
  '#ef4444', // 9 red bright
  '#d4d4d8', // 10 silver
  '#fafafa', // 11 white
  '#fbbf24', // 12 gold accent
  '#4ade80', // 13 spark green
  '#fb7185', // 14 spark pink
  '#1e293b', // 15 ground
  '#334155', // 16 ground light
  '#facc15', // 17 star
  '#38bdf8', // 18 flash blue
]

type Sprite = number[][]

type PhaseId =
  | 'standoff'
  | 'advance'
  | 'cat_rush'
  | 'melee'
  | 'knockback'
  | 'beam_war'
  | 'leap'
  | 'finale'
  | 'recover'

interface FightPhase {
  start: number
  end: number
  id: PhaseId
  label: string
}

const PHASES: FightPhase[] = [
  { start: 0, end: 240, id: 'standoff', label: 'STANDOFF' },
  { start: 240, end: 420, id: 'advance', label: 'CLOSING IN' },
  { start: 420, end: 540, id: 'cat_rush', label: 'CAT RUSH!' },
  { start: 540, end: 720, id: 'melee', label: 'CLAW FIGHT' },
  { start: 720, end: 900, id: 'knockback', label: 'ULTRA COUNTER' },
  { start: 900, end: 1140, id: 'beam_war', label: 'BEAM WAR' },
  { start: 1140, end: 1380, id: 'leap', label: 'AERIAL STRIKE' },
  { start: 1380, end: 1680, id: 'finale', label: 'MAX POWER' },
  { start: 1680, end: FIGHT_CYCLE_FRAMES, id: 'recover', label: 'RESET' },
]

function plotSprite(
  ctx: CanvasRenderingContext2D,
  sprite: Sprite,
  ox: number,
  oy: number,
  scale = 1
): void {
  for (let y = 0; y < sprite.length; y += 1) {
    const row = sprite[y]
    for (let x = 0; x < row.length; x += 1) {
      const idx = row[x]
      if (!idx) {
        continue
      }
      const color = PALETTE[idx]
      if (!color) {
        continue
      }
      ctx.fillStyle = color
      ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale)
    }
  }
}

/** Black cat facing right — idle. */
const CAT_IDLE: Sprite = [
  [0, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 0, 4, 4, 4, 4, 6, 4, 6, 4, 4, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0],
  [0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 4, 4, 5, 4, 4, 4, 5, 4, 4, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0],
  [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0],
  [0, 0, 4, 4, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 0, 4, 4, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 0],
]

/** Black cat — lunge / strike. */
const CAT_LUNGE: Sprite = [
  [0, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 4, 4, 4, 4, 6, 4, 6, 4, 4, 4, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0],
  [0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0],
  [0, 0, 4, 4, 5, 4, 4, 4, 5, 4, 4, 0, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0],
  [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 0, 4, 4, 0, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 0, 4, 4, 0, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 0, 0, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0],
]

/** Black cat — hurt / knocked back. */
const CAT_HURT: Sprite = [
  [0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 0, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 4, 4, 4, 8, 4, 4, 8, 4, 4, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0],
  [0, 0, 4, 4, 4, 4, 4, 4, 4, 0, 0, 0],
  [0, 0, 0, 4, 4, 4, 4, 4, 0, 0, 0, 0],
  [0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0, 0],
  [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 0],
  [0, 4, 4, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 4, 4, 0, 0, 0, 0, 4, 4, 0, 0, 0],
  [0, 0, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],
]

/** Ultraman facing left — stance. */
const ULTRA_IDLE: Sprite = [
  [0, 0, 0, 0, 10, 10, 10, 10, 10, 0, 0, 0],
  [0, 0, 0, 10, 10, 11, 11, 11, 10, 10, 0, 0],
  [0, 0, 10, 10, 11, 8, 11, 8, 11, 10, 10, 0],
  [0, 0, 10, 10, 11, 11, 11, 11, 11, 10, 10, 0],
  [0, 0, 0, 10, 10, 12, 12, 12, 10, 10, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 0, 0],
  [0, 0, 8, 8, 10, 8, 8, 10, 8, 8, 8, 0],
  [0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 0, 8, 8, 0, 0, 0],
]

/** Ultraman — beam pose. */
const ULTRA_BEAM: Sprite = [
  [0, 0, 0, 0, 10, 10, 10, 10, 10, 0, 0, 0, 0],
  [0, 0, 0, 10, 10, 11, 11, 11, 10, 10, 0, 0, 0],
  [0, 0, 10, 10, 11, 8, 11, 8, 11, 10, 10, 0, 0],
  [0, 0, 10, 10, 11, 11, 11, 11, 11, 10, 10, 0, 0],
  [0, 0, 0, 10, 10, 12, 12, 12, 10, 10, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 8, 8, 10, 8, 8, 10, 8, 8, 8, 0, 0],
  [0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0],
  [0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 0, 8, 8, 0, 0, 0, 0],
]

/** Ultraman — kick / advance. */
const ULTRA_KICK: Sprite = [
  [0, 0, 0, 0, 10, 10, 10, 10, 10, 0, 0, 0, 0, 0],
  [0, 0, 0, 10, 10, 11, 11, 11, 10, 10, 0, 0, 0, 0],
  [0, 0, 10, 10, 11, 8, 11, 8, 11, 10, 10, 0, 0, 0],
  [0, 0, 10, 10, 11, 11, 11, 11, 11, 10, 10, 0, 0, 0],
  [0, 0, 0, 10, 10, 12, 12, 12, 10, 10, 0, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 8, 0, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 8, 8, 10, 8, 8, 10, 8, 8, 8, 8, 0, 0],
  [0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 0, 0, 0, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 8, 8, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 0, 0, 0, 0, 8, 8, 0, 0, 0],
  [0, 0, 0, 8, 8, 8, 8, 8, 8, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 8, 8, 8, 8, 0, 0, 0, 0, 0, 0],
]

interface Spark {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  color: string
}

interface BattleState {
  tick: number
  beamPulse: number
  sparks: Spark[]
  shake: number
  flash: number
}

interface PhaseContext {
  phase: FightPhase
  local: number
  progress: number
}

function resolvePhase(tick: number): PhaseContext {
  const cycleTick = tick % FIGHT_CYCLE_FRAMES
  for (const phase of PHASES) {
    if (cycleTick >= phase.start && cycleTick < phase.end) {
      const span = phase.end - phase.start
      return {
        phase,
        local: cycleTick - phase.start,
        progress: span > 0 ? (cycleTick - phase.start) / span : 0,
      }
    }
  }
  return { phase: PHASES[0], local: 0, progress: 0 }
}

function easeOut(t: number): number {
  return 1 - (1 - t) ** 2
}

function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
}

function drawSky(ctx: CanvasRenderingContext2D, tick: number): void {
  for (let y = 0; y < H - 28; y += 1) {
    const t = y / (H - 28)
    const r = Math.round(5 + t * 20)
    const g = Math.round(5 + t * 8)
    const b = Math.round(20 + t * 60)
    ctx.fillStyle = `rgb(${r},${g},${b})`
    ctx.fillRect(0, y, W, 1)
  }
  for (let i = 0; i < 48; i += 1) {
    const sx = (i * 47 + tick * 0.15) % W
    const sy = (i * 31) % (H - 40)
    if ((i + Math.floor(tick / 30)) % 5 === 0) {
      ctx.fillStyle = PALETTE[17]!
      ctx.fillRect(Math.floor(sx), Math.floor(sy), 1, 1)
    }
  }
}

function drawGround(ctx: CanvasRenderingContext2D): void {
  for (let x = 0; x < W; x += 1) {
    const stripe = Math.floor(x / 8) % 2 === 0 ? 15 : 16
    ctx.fillStyle = PALETTE[stripe]!
    ctx.fillRect(x, H - 28, 1, 28)
  }
  ctx.fillStyle = PALETTE[1]!
  ctx.fillRect(0, H - 6, W, 6)
}

function drawBeam(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  outer: string,
  inner: string,
  width: number
): void {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.hypot(dx, dy) || 1
  const nx = -dy / len
  const ny = dx / len
  ctx.fillStyle = outer
  for (let t = 0; t <= len; t += 0.6) {
    const px = x1 + (dx * t) / len
    const py = y1 + (dy * t) / len
    for (let w = -width; w <= width; w += 1) {
      ctx.fillRect(Math.floor(px + nx * w), Math.floor(py + ny * w), 1, 1)
    }
  }
  ctx.fillStyle = inner
  for (let t = 0; t <= len; t += 0.8) {
    const px = x1 + (dx * t) / len
    const py = y1 + (dy * t) / len
    ctx.fillRect(Math.floor(px), Math.floor(py), 1, 1)
  }
}

function spawnSparks(sparks: Spark[], cx: number, cy: number, count: number): void {
  for (let i = 0; i < count; i += 1) {
    const angle = Math.random() * Math.PI * 2
    const speed = 0.5 + Math.random() * 2.2
    sparks.push({
      x: cx,
      y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 14 + Math.floor(Math.random() * 20),
      color: Math.random() > 0.5 ? PALETTE[13]! : PALETTE[14]!,
    })
  }
}

function drawSparks(ctx: CanvasRenderingContext2D, sparks: Spark[]): void {
  for (const s of sparks) {
    ctx.fillStyle = s.color
    ctx.fillRect(Math.floor(s.x), Math.floor(s.y), 1, 1)
  }
}

function stepSparks(sparks: Spark[]): void {
  for (let i = sparks.length - 1; i >= 0; i -= 1) {
    const s = sparks[i]
    s.x += s.vx
    s.y += s.vy
    s.vy += 0.04
    s.life -= 1
    if (s.life <= 0) {
      sparks.splice(i, 1)
    }
  }
}

function drawSpriteScaled(
  ctx: CanvasRenderingContext2D,
  sprite: Sprite,
  x: number,
  y: number,
  scale: number
): void {
  for (let sy = 0; sy < sprite.length; sy += 1) {
    for (let sx = 0; sx < sprite[sy].length; sx += 1) {
      const idx = sprite[sy][sx]
      if (!idx) {
        continue
      }
      ctx.fillStyle = PALETTE[idx]!
      ctx.fillRect(x + sx * scale, y + sy * scale, scale, scale)
    }
  }
}

function drawHud(ctx: CanvasRenderingContext2D, phase: FightPhase, tick: number): void {
  const sec = Math.floor((tick % FIGHT_CYCLE_FRAMES) / 60)
  const label = `${phase.label}  ${sec}s`
  ctx.fillStyle = 'rgba(0,0,0,0.45)'
  ctx.fillRect(4, 4, label.length * 5 + 8, 11)
  ctx.fillStyle = PALETTE[11]!
  for (let i = 0; i < label.length; i += 1) {
    const ch = label.charCodeAt(i)
    drawMiniChar(ctx, 8 + i * 5, 6, ch)
  }
}

function drawMiniChar(ctx: CanvasRenderingContext2D, ox: number, oy: number, code: number): void {
  const glyphs: Record<number, number[][]> = {
    32: [],
    33: [[1], [1], [0], [1]],
    65: [
      [0, 1, 0],
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1],
    ],
    66: [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 1, 1],
    ],
    67: [
      [0, 1, 1],
      [1, 0, 0],
      [1, 0, 0],
      [0, 1, 1],
    ],
    68: [
      [1, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 0],
    ],
    69: [
      [1, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [1, 1, 1],
    ],
    70: [
      [1, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [1, 0, 0],
    ],
    73: [
      [1],
      [1],
      [1],
      [1],
    ],
    76: [
      [1, 0, 0],
      [1, 0, 0],
      [1, 0, 0],
      [1, 1, 1],
    ],
    77: [
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1],
      [1, 0, 1],
    ],
    78: [
      [1, 0, 1],
      [1, 1, 1],
      [1, 1, 1],
      [1, 0, 1],
    ],
    79: [
      [0, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0],
    ],
    80: [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 0],
    ],
    82: [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 1],
    ],
    83: [
      [0, 1, 1],
      [1, 0, 0],
      [0, 1, 0],
      [1, 1, 0],
    ],
    84: [
      [1, 1, 1],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
    ],
    85: [
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0],
    ],
    87: [
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
    ],
    48: [
      [1, 1],
      [1, 1],
      [1, 1],
      [1, 1],
    ],
    49: [[1], [1], [1], [1]],
    50: [
      [1, 1],
      [0, 1],
      [1, 0],
      [1, 1],
    ],
    51: [
      [1, 1],
      [0, 1],
      [1, 1],
      [1, 1],
    ],
    52: [
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 1],
      [0, 0, 1],
    ],
    53: [
      [1, 1, 1],
      [1, 0, 0],
      [0, 1, 1],
      [1, 1, 1],
    ],
    54: [
      [0, 1, 1],
      [1, 0, 0],
      [1, 1, 1],
      [1, 1, 1],
    ],
    55: [
      [1, 1, 1],
      [0, 0, 1],
      [0, 1, 0],
      [1, 0, 0],
    ],
    56: [
      [1, 1],
      [1, 1],
      [1, 1],
      [1, 1],
    ],
    57: [
      [1, 1, 1],
      [1, 1, 1],
      [0, 0, 1],
      [1, 1, 0],
    ],
  }
  const g = glyphs[code] ?? glyphs[32]!
  ctx.fillStyle = PALETTE[11]!
  for (let y = 0; y < g.length; y += 1) {
    for (let x = 0; x < g[y].length; x += 1) {
      if (g[y][x]) {
        ctx.fillRect(ox + x, oy + y, 1, 1)
      }
    }
  }
}

interface FighterPose {
  catSprite: Sprite
  ultraSprite: Sprite
  catX: number
  catY: number
  ultraX: number
  ultraY: number
  catBeam: boolean
  ultraBeam: boolean
  beamPower: number
  clashX: number
  clashY: number
  melee: boolean
}

function computePose(ctx: PhaseContext, tick: number): FighterPose {
  const scale = 5
  const groundY = H - 28
  const baseCatX = 8
  const baseUltraX = W - 10 - ULTRA_IDLE[0].length * scale
  const { phase, local, progress } = ctx

  let catSprite = CAT_IDLE
  let ultraSprite = ULTRA_IDLE
  let catX = baseCatX
  let ultraX = baseUltraX
  let catYOffset = 0
  let ultraYOffset = 0
  let catBeam = true
  let ultraBeam = true
  let beamPower = 1
  let clashX = W / 2
  let melee = false

  switch (phase.id) {
    case 'standoff':
      catX = baseCatX
      ultraX = baseUltraX
      beamPower = 0.6 + Math.sin(tick * 0.1) * 0.2
      clashX = W / 2 + Math.sin(tick * 0.06) * 8
      break
    case 'advance':
      catX = baseCatX + easeOut(progress) * 42
      ultraX = baseUltraX - easeOut(progress) * 38
      catSprite = Math.floor(local / 10) % 2 === 0 ? CAT_IDLE : CAT_LUNGE
      ultraSprite = Math.floor(local / 12) % 2 === 0 ? ULTRA_IDLE : ULTRA_BEAM
      beamPower = 0.8 + progress * 0.6
      clashX = (catX + ultraX + 40) / 2
      break
    case 'cat_rush':
      catX = baseCatX + 42 + easeInOut(progress) * 58
      ultraX = baseUltraX - 20
      catSprite = CAT_LUNGE
      ultraSprite = ULTRA_BEAM
      beamPower = 1.2
      clashX = catX + CAT_LUNGE[0].length * scale
      catBeam = local % 20 < 14
      break
    case 'melee':
      catX = baseCatX + 100 + Math.sin(local * 0.35) * 6
      ultraX = baseUltraX - 58 + Math.sin(local * 0.35 + 1) * 5
      catSprite = Math.floor(local / 6) % 2 === 0 ? CAT_LUNGE : CAT_IDLE
      ultraSprite = Math.floor(local / 8) % 2 === 0 ? ULTRA_KICK : ULTRA_IDLE
      catBeam = false
      ultraBeam = false
      melee = true
      clashX = (catX + ultraX + 50) / 2
      break
    case 'knockback':
      catX = baseCatX + 100 - easeOut(progress) * 72
      ultraX = baseUltraX - 58 + easeOut(progress) * 24
      catSprite = CAT_HURT
      ultraSprite = ULTRA_KICK
      catBeam = progress < 0.35
      ultraBeam = true
      beamPower = 1.4
      clashX = catX + 30
      break
    case 'beam_war':
      catX = baseCatX + 28 + Math.sin(local * 0.08) * 4
      ultraX = baseUltraX - 34 + Math.sin(local * 0.08 + 2) * 4
      catSprite = Math.floor(local / 8) % 2 === 0 ? CAT_IDLE : CAT_LUNGE
      ultraSprite = ULTRA_BEAM
      beamPower = 1.6 + Math.sin(local * 0.2) * 0.5
      clashX = W / 2 + Math.sin(local * 0.12) * 18
      break
    case 'leap':
      catX = baseCatX + 40 + progress * 70
      ultraX = baseUltraX - 40
      catYOffset = -Math.sin(progress * Math.PI) * 42
      catSprite = CAT_LUNGE
      ultraSprite = ULTRA_BEAM
      beamPower = 1.3
      clashX = catX + 20
      catBeam = progress < 0.55
      ultraBeam = true
      break
    case 'finale':
      catX = baseCatX + 52
      ultraX = baseUltraX - 48
      catSprite = CAT_LUNGE
      ultraSprite = ULTRA_BEAM
      beamPower = 2.4 + Math.sin(local * 0.4) * 0.6
      clashX = W / 2 + Math.sin(local * 0.25) * 10
      break
    case 'recover':
      catX = baseCatX + (1 - progress) * 44
      ultraX = baseUltraX - (1 - progress) * 40
      catSprite = CAT_IDLE
      ultraSprite = ULTRA_IDLE
      beamPower = 0.4 + progress * 0.3
      catBeam = local % 40 < 20
      ultraBeam = local % 40 < 20
      clashX = W / 2
      break
    default:
      break
  }

  const catY = groundY - catSprite.length * scale - 2 + catYOffset
  const ultraY = groundY - ultraSprite.length * scale - 2 + ultraYOffset
  const clashY = (catY + 12 + ultraY + 20) / 2

  return {
    catSprite,
    ultraSprite,
    catX,
    catY,
    ultraX,
    ultraY,
    catBeam,
    ultraBeam,
    beamPower,
    clashX,
    clashY,
    melee,
  }
}

function renderFrame(ctx: CanvasRenderingContext2D, state: BattleState, showHud: boolean): void {
  const phaseCtx = resolvePhase(state.tick)
  const pose = computePose(phaseCtx, state.tick)
  const scale = 5

  ctx.save()
  if (state.shake > 0) {
    const sx = (Math.random() - 0.5) * state.shake
    const sy = (Math.random() - 0.5) * state.shake
    ctx.translate(sx, sy)
    state.shake *= 0.88
    if (state.shake < 0.15) {
      state.shake = 0
    }
  }

  drawSky(ctx, state.tick)
  drawGround(ctx)

  drawSpriteScaled(ctx, pose.catSprite, pose.catX, pose.catY, scale)
  drawSpriteScaled(ctx, pose.ultraSprite, pose.ultraX, pose.ultraY, scale)

  const catBeamX = pose.catX + pose.catSprite[0].length * scale - 2
  const catEyeY = pose.catY + 2 * scale + scale / 2
  const ultraArmX = pose.ultraX - 2
  const ultraArmY = pose.ultraY + 7 * scale
  const beamW = Math.max(1, Math.floor(pose.beamPower + Math.sin(state.beamPulse) * 1.2))

  if (pose.catBeam) {
    drawBeam(
      ctx,
      catBeamX,
      catEyeY,
      pose.clashX,
      pose.clashY,
      PALETTE[6]!,
      PALETTE[7]!,
      beamW
    )
  }
  if (pose.ultraBeam) {
    drawBeam(
      ctx,
      ultraArmX,
      ultraArmY,
      pose.clashX,
      pose.clashY,
      PALETTE[9]!,
      PALETTE[11]!,
      beamW
    )
  }

  if (pose.melee && state.tick % 5 === 0) {
    spawnSparks(state.sparks, pose.clashX, pose.clashY, 4)
    state.shake = Math.max(state.shake, 1.8)
  } else if ((pose.catBeam || pose.ultraBeam) && state.tick % 6 === 0) {
    spawnSparks(state.sparks, pose.clashX, pose.clashY, 2 + Math.floor(pose.beamPower))
    state.shake = Math.max(state.shake, pose.beamPower * 0.6)
  }

  if (phaseCtx.phase.id === 'finale' && state.tick % 10 === 0) {
    spawnSparks(state.sparks, pose.clashX, pose.clashY, 6)
    state.flash = 0.35
    state.shake = Math.max(state.shake, 3.5)
  }

  drawSparks(ctx, state.sparks)

  if (showHud) {
    drawHud(ctx, phaseCtx.phase, state.tick)
  }

  if (state.flash > 0) {
    ctx.fillStyle = `rgba(56, 189, 248, ${state.flash})`
    ctx.fillRect(0, 0, W, H)
    state.flash *= 0.82
    if (state.flash < 0.02) {
      state.flash = 0
    }
  }

  ctx.restore()
}

export function initAuthPixelBattle(
  canvas: HTMLCanvasElement,
  options?: { showHud?: boolean }
): AuthPixelBattleDispose {
  const showHud = options?.showHud ?? false
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reducedMotion) {
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = PALETTE[1]!
      ctx.fillRect(0, 0, W, H)
      plotSprite(ctx, CAT_IDLE, 24, H - 70, 5)
      plotSprite(ctx, ULTRA_IDLE, W - 70, H - 72, 5)
    }
    return () => {}
  }

  const ctx = canvas.getContext('2d', { alpha: false })
  if (!ctx) {
    return () => {}
  }

  canvas.width = W
  canvas.height = H

  const state: BattleState = {
    tick: 0,
    beamPulse: 0,
    sparks: [],
    shake: 0,
    flash: 0,
  }

  let rafId = 0
  const loop = (): void => {
    state.tick += 1
    state.beamPulse += 0.35
    stepSparks(state.sparks)
    renderFrame(ctx, state, showHud)
    rafId = window.requestAnimationFrame(loop)
  }

  rafId = window.requestAnimationFrame(loop)

  return () => {
    window.cancelAnimationFrame(rafId)
  }
}
