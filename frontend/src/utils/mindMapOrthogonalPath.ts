/**
 * Mind-map bracket-bus connectors: horizontal stem → vertical spine → rounded tee → branch.
 *
 * Matches classic mind-map style (horizontal stub, vertical bus, filleted branch exits).
 */

export const MINDMAP_CONNECTOR_MAX_RADIUS = 16
export const MINDMAP_CONNECTOR_TURN_RATIO = 0.45
/** Branches within this vertical distance of the parent use a flat horizontal tee. */
export const MINDMAP_CONNECTOR_FLAT_DY = 10
/** Minimum horizontal bus offset from the topic edge before the vertical trunk. */
export const MINDMAP_TOPIC_TRUNK_MIN_OFFSET = 28

export type MindMapOrthogonalPathOptions = {
  maxRadius?: number
  turnRatio?: number
  flatDyThreshold?: number
  /** Shared vertical trunk X for sibling stagger routing */
  trunkX?: number
}

export type MindMapBracketBusOptions = {
  maxRadius?: number
  flatDyThreshold?: number
  /** When true, draw parent stem + full vertical spine (once per sibling group). */
  drawSpine?: boolean
  /** Parallel to siblingYs — used to trim the spine to rounded tee join points. */
  siblingToXs?: number[]
  /**
   * Only child with an underline target: flat horizontal at the underline midline
   * (parent side → child), no vertical bus or rounded tee.
   */
  singleUnderlineChild?: boolean
  /**
   * Sole L1 branch on one side of the topic: straight connector (no rounded tee).
   */
  singleTopicSideChild?: boolean
}

function clampRadius(maxRadius: number, legA: number, legB: number): number {
  return Math.max(0, Math.min(maxRadius, Math.abs(legA), Math.abs(legB)))
}

function branchApproachY(
  toY: number,
  fromY: number,
  trunkX: number,
  toX: number,
  maxRadius: number,
  flatThreshold: number
): number {
  if (Math.abs(toY - fromY) < flatThreshold) return toY
  const hLen = Math.abs(toX - trunkX)
  const vLeg = Math.abs(toY - fromY)
  const r = clampRadius(maxRadius, hLen, Math.max(vLeg, hLen * 0.35))
  if (r <= 0.5) return toY
  return toY < fromY ? toY + r : toY - r
}

/** Vertical bus span — sibling branch Y only, trimmed to rounded tee join points. */
function computeSpineVerticalRange(
  branchYs: number[],
  fromY: number,
  trunkX: number,
  branchToXs: number[],
  maxRadius: number,
  flatThreshold: number
): { top: number; bottom: number } {
  let top = Infinity
  let bottom = -Infinity
  for (let i = 0; i < branchYs.length; i++) {
    const y = branchYs[i]!
    const toX = branchToXs[i] ?? trunkX
    const approach = branchApproachY(y, fromY, trunkX, toX, maxRadius, flatThreshold)
    top = Math.min(top, approach)
    bottom = Math.max(bottom, approach)
  }
  if (!Number.isFinite(top)) {
    return { top: fromY, bottom: fromY }
  }
  return { top, bottom }
}

function buildBusSpine(
  fromX: number,
  fromY: number,
  trunkX: number,
  spineTop: number,
  spineBottom: number
): string {
  const parts = [`M ${fromX} ${fromY}`, `L ${trunkX} ${fromY}`]

  if (spineBottom - spineTop < 0.5) {
    return parts.join(' ')
  }

  if (fromY <= spineTop + 0.5) {
    parts.push(`L ${trunkX} ${spineTop}`, `L ${trunkX} ${spineBottom}`)
  } else if (fromY >= spineBottom - 0.5) {
    parts.push(`L ${trunkX} ${spineBottom}`, `L ${trunkX} ${spineTop}`)
  } else {
    if (spineTop < fromY - 0.5) parts.push(`L ${trunkX} ${spineTop}`)
    if (spineBottom > fromY + 0.5) parts.push(`L ${trunkX} ${spineBottom}`)
  }

  return parts.join(' ')
}

function buildRoundedTeeBranch(
  trunkX: number,
  fromY: number,
  toX: number,
  toY: number,
  maxRadius: number
): string {
  const sx = toX >= trunkX ? 1 : -1
  const hLen = Math.abs(toX - trunkX)
  if (hLen < 0.5) {
    return `M ${trunkX} ${toY} L ${toX} ${toY}`
  }

  const vLeg = Math.abs(toY - fromY)
  const r = clampRadius(maxRadius, hLen, Math.max(vLeg, hLen * 0.35))
  if (r <= 0.5) {
    return `M ${trunkX} ${toY} L ${toX} ${toY}`
  }

  const approachY = toY < fromY ? toY + r : toY - r
  return [
    `M ${trunkX} ${approachY}`,
    `Q ${trunkX} ${toY} ${trunkX + sx * r} ${toY}`,
    `L ${toX} ${toY}`,
  ].join(' ')
}

/**
 * Bracket-bus path for one child edge. Sibling group shares trunkX; one edge draws the spine.
 */
export function buildMindMapBracketBusPath(
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  trunkX: number,
  siblingYs: number[],
  options: MindMapBracketBusOptions = {}
): string {
  const maxR = options.maxRadius ?? MINDMAP_CONNECTOR_MAX_RADIUS
  const flatThreshold = options.flatDyThreshold ?? MINDMAP_CONNECTOR_FLAT_DY
  const drawSpine = options.drawSpine ?? false
  const branchYs = siblingYs.length > 0 ? siblingYs : [toY]

  // Sole underline child: flat horizontal at the shared connection anchor Y.
  if (options.singleUnderlineChild && branchYs.length === 1) {
    return `M ${fromX} ${fromY} L ${toX} ${fromY}`
  }

  // Sole topic-side L1 branch: orthogonal segments only (no Q-rounded tee).
  if (options.singleTopicSideChild && branchYs.length === 1) {
    if (Math.abs(toY - fromY) < flatThreshold) {
      return `M ${fromX} ${fromY} L ${toX} ${fromY}`
    }
    return `M ${fromX} ${fromY} L ${trunkX} ${fromY} L ${trunkX} ${toY} L ${toX} ${toY}`
  }

  const allFlat = branchYs.every((y) => Math.abs(y - fromY) < flatThreshold)
  if (allFlat) {
    if (!drawSpine) {
      return `M ${trunkX} ${toY} L ${toX} ${toY}`
    }
    return `M ${fromX} ${fromY} L ${trunkX} ${fromY} L ${toX} ${toY}`
  }

  const branchToXs =
    options.siblingToXs && options.siblingToXs.length === branchYs.length
      ? options.siblingToXs
      : branchYs.map(() => toX)
  const { top: spineTop, bottom: spineBottom } = computeSpineVerticalRange(
    branchYs,
    fromY,
    trunkX,
    branchToXs,
    maxR,
    flatThreshold
  )
  const branch = buildRoundedTeeBranch(trunkX, fromY, toX, toY, maxR)

  if (!drawSpine) {
    return branch
  }

  if (branchYs.length === 1) {
    const sx = toX >= trunkX ? 1 : -1
    const hLen = Math.abs(toX - trunkX)
    const vLeg = Math.abs(toY - fromY)
    const r = clampRadius(maxR, hLen, Math.max(vLeg, hLen * 0.35))
    if (Math.abs(toY - fromY) < flatThreshold) {
      return `M ${fromX} ${fromY} L ${trunkX} ${fromY} L ${toX} ${toY}`
    }
    const approachY = toY < fromY ? toY + r : toY - r
    return [
      `M ${fromX} ${fromY}`,
      `L ${trunkX} ${fromY}`,
      `L ${trunkX} ${approachY}`,
      `Q ${trunkX} ${toY} ${trunkX + sx * r} ${toY}`,
      `L ${toX} ${toY}`,
    ].join(' ')
  }

  return `${buildBusSpine(fromX, fromY, trunkX, spineTop, spineBottom)} ${branch}`
}

/**
 * Build an H → V → H orthogonal path with Q-rounded corners (rightward flow).
 * For leftward flow, sx = -1 mirrors the same logic.
 */
export function buildMindMapOrthogonalPath(
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  options: MindMapOrthogonalPathOptions = {}
): string {
  const dx = toX - fromX
  const dy = toY - fromY
  const flatThreshold = options.flatDyThreshold ?? MINDMAP_CONNECTOR_FLAT_DY

  const midX = options.trunkX ?? fromX + dx * (options.turnRatio ?? MINDMAP_CONNECTOR_TURN_RATIO)

  if (Math.abs(dx) < 0.5) {
    return `M ${fromX} ${fromY} L ${toX} ${toY}`
  }

  // Nearly collinear with parent — flat horizontal avoids corner kinks on the shared bus.
  if (Math.abs(dy) < flatThreshold) {
    return `M ${fromX} ${fromY} L ${midX} ${fromY} L ${toX} ${fromY}`
  }

  if (Math.abs(dy) < 0.5) {
    return `M ${fromX} ${fromY} L ${midX} ${fromY} L ${toX} ${toY}`
  }

  const sx = dx >= 0 ? 1 : -1
  const sy = dy >= 0 ? 1 : -1

  const maxRadius = options.maxRadius ?? MINDMAP_CONNECTOR_MAX_RADIUS
  const absDy = Math.abs(dy)
  let r1 = clampRadius(maxRadius, midX - fromX, dy)
  let r2 = clampRadius(maxRadius, toX - midX, dy)

  // Prevent overlapping corner arcs on short vertical legs (avoids visible "kinks").
  if (absDy > 0.5 && r1 + r2 > absDy) {
    const scale = absDy / (r1 + r2)
    r1 *= scale
    r2 *= scale
  }

  const parts: string[] = [`M ${fromX} ${fromY}`]

  if (r1 <= 0 && r2 <= 0) {
    parts.push(`L ${midX} ${fromY}`, `L ${midX} ${toY}`, `L ${toX} ${toY}`)
    return parts.join(' ')
  }

  if (r1 > 0) {
    parts.push(`L ${midX - sx * r1} ${fromY}`)
    parts.push(`Q ${midX} ${fromY} ${midX} ${fromY + sy * r1}`)
  } else {
    parts.push(`L ${midX} ${fromY}`)
  }

  if (r2 > 0) {
    parts.push(`L ${midX} ${toY - sy * r2}`)
    parts.push(`Q ${midX} ${toY} ${midX + sx * r2} ${toY}`)
  } else {
    parts.push(`L ${midX} ${toY}`)
  }

  parts.push(`L ${toX} ${toY}`)
  return parts.join(' ')
}

/**
 * Topic → branch uses the same bracket-bus topology as inner edges.
 */
export function buildMindMapTopicBranchPath(
  topicX: number,
  topicY: number,
  targetX: number,
  targetY: number,
  trunkX: number,
  siblingYs: number[] = [],
  options: MindMapBracketBusOptions = {}
): string {
  return buildMindMapBracketBusPath(
    topicX,
    topicY,
    targetX,
    targetY,
    trunkX,
    siblingYs.length > 0 ? siblingYs : [targetY],
    options
  )
}

/**
 * Compute a shared trunk X for all edges from the same parent so sibling
 * branches use one vertical bus (staggered split routing).
 */
export function computeMindMapSharedTrunkX(
  sourceX: number,
  targetXs: number[],
  fallbackTargetX: number
): number {
  const xs = targetXs.length > 0 ? targetXs : [fallbackTargetX]
  const flowingRight = sourceX <= fallbackTargetX
  const nearestTargetX = flowingRight ? Math.min(...xs) : Math.max(...xs)
  const dx = nearestTargetX - sourceX
  const ratioSpan = Math.abs(dx) * MINDMAP_CONNECTOR_TURN_RATIO
  const offset = Math.max(MINDMAP_TOPIC_TRUNK_MIN_OFFSET, ratioSpan)
  return flowingRight ? sourceX + offset : sourceX - offset
}
