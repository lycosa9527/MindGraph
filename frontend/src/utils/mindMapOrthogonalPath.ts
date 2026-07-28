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
  flatThreshold: number,
  /** Multi-sibling bus: still fillet tees near the parent Y (shared spine needs a Q). */
  roundDespiteFlat = false
): number {
  const dy = Math.abs(toY - fromY)
  if (!roundDespiteFlat && dy < flatThreshold) return toY
  const hLen = Math.abs(toX - trunkX)
  // Near-parent bus tees have tiny dy; use maxRadius so the fillet still has a vertical leg.
  const vLeg = Math.max(dy, roundDespiteFlat ? maxRadius : 0)
  const r = clampRadius(maxRadius, hLen, Math.max(vLeg, hLen * 0.35))
  if (r <= 0.5) return toY
  return toY < fromY ? toY + r : toY - r
}

type MindMapTeeSpec = {
  toX: number
  toY: number
  approachY: number
  radius: number
}

function resolveTeeRadius(
  toY: number,
  fromY: number,
  trunkX: number,
  toX: number,
  maxRadius: number,
  flatThreshold: number,
  roundDespiteFlat: boolean
): number {
  const hLen = Math.abs(toX - trunkX)
  if (hLen < 0.5) return 0
  const dy = Math.abs(toY - fromY)
  if (!roundDespiteFlat && dy < flatThreshold) return 0
  const vLeg = Math.max(dy, roundDespiteFlat ? maxRadius : 0)
  return clampRadius(maxRadius, hLen, Math.max(vLeg, hLen * 0.35))
}

function resolveTeeSpec(
  toY: number,
  fromY: number,
  trunkX: number,
  toX: number,
  maxRadius: number,
  flatThreshold: number,
  roundDespiteFlat: boolean
): MindMapTeeSpec {
  const radius = resolveTeeRadius(
    toY,
    fromY,
    trunkX,
    toX,
    maxRadius,
    flatThreshold,
    roundDespiteFlat
  )
  const approachY = branchApproachY(
    toY,
    fromY,
    trunkX,
    toX,
    maxRadius,
    flatThreshold,
    roundDespiteFlat
  )
  return { toX, toY, approachY, radius }
}

/**
 * Stem + vertical bus with filleted tees. Each Q is continuous from the bus (no
 * separate subpath along the trunk), so translucent strokes do not double-paint
 * at the curve→bus join. Horizontals to children are drawn by each edge stub.
 */
function buildSpineWithFilletTees(
  fromX: number,
  fromY: number,
  trunkX: number,
  tees: MindMapTeeSpec[]
): string {
  const parts = [`M ${fromX} ${fromY}`, `L ${trunkX} ${fromY}`]

  const uppers = tees
    .filter((tee) => tee.approachY < fromY - 0.5)
    .sort((a, b) => b.approachY - a.approachY)
  const lowers = tees
    .filter((tee) => tee.approachY > fromY + 0.5)
    .sort((a, b) => a.approachY - b.approachY)
  const atParent = tees.filter((tee) => Math.abs(tee.approachY - fromY) <= 0.5)

  function emitFillet(tee: MindMapTeeSpec): void {
    // Pen is at (trunkX, approachY). Fillet only — no horizontal (avoids double paint).
    if (tee.radius <= 0.5 || Math.abs(tee.approachY - tee.toY) < 0.5) return
    const sx = tee.toX >= trunkX ? 1 : -1
    parts.push(`Q ${trunkX} ${tee.toY} ${trunkX + sx * tee.radius} ${tee.toY}`)
    parts.push(`M ${trunkX} ${tee.approachY}`)
  }

  for (const tee of uppers) {
    parts.push(`L ${trunkX} ${tee.approachY}`)
    emitFillet(tee)
  }

  if (uppers.length > 0 && (lowers.length > 0 || atParent.length > 0)) {
    parts.push(`M ${trunkX} ${fromY}`)
  }

  for (const tee of atParent) {
    emitFillet(tee)
  }

  if (atParent.length > 0 && lowers.length > 0) {
    parts.push(`M ${trunkX} ${fromY}`)
  }

  for (const tee of lowers) {
    parts.push(`L ${trunkX} ${tee.approachY}`)
    emitFillet(tee)
  }

  return parts.join(' ')
}

/** Horizontal from fillet end (or trunk for flat tees) to the child. */
function buildBranchHorizontalStub(
  trunkX: number,
  fromY: number,
  toX: number,
  toY: number,
  maxRadius: number,
  flatThreshold: number,
  roundDespiteFlat: boolean
): string {
  const tee = resolveTeeSpec(toY, fromY, trunkX, toX, maxRadius, flatThreshold, roundDespiteFlat)
  if (tee.radius <= 0.5 || Math.abs(tee.approachY - tee.toY) < 0.5) {
    return `M ${trunkX} ${toY} L ${toX} ${toY}`
  }
  const sx = toX >= trunkX ? 1 : -1
  return `M ${trunkX + sx * tee.radius} ${toY} L ${toX} ${toY}`
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

  // Sole underline child: flat horizontal at the underline midline (parent → child).
  if (options.singleUnderlineChild && branchYs.length === 1) {
    return `M ${fromX} ${fromY} L ${toX} ${toY}`
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

  // Shared vertical spine: the near-parent child must still get a Q tee, otherwise
  // it meets the bus at a sharp 90° while farther siblings look rounded (debug: sharp_or_flat).
  const roundDespiteFlat = branchYs.length > 1

  const branchToXs =
    options.siblingToXs && options.siblingToXs.length === branchYs.length
      ? options.siblingToXs
      : branchYs.map(() => toX)

  const stub = buildBranchHorizontalStub(
    trunkX,
    fromY,
    toX,
    toY,
    maxR,
    flatThreshold,
    roundDespiteFlat
  )

  // Non-spine edges: horizontal only. Fillets live on the spine path so the Q never
  // retraces the bus (opacity would thicken at the join).
  if (!drawSpine) {
    return stub
  }

  if (branchYs.length === 1) {
    const sx = toX >= trunkX ? 1 : -1
    const hLen = Math.abs(toX - trunkX)
    const vLeg = Math.abs(toY - fromY)
    const r = clampRadius(maxR, hLen, Math.max(vLeg, hLen * 0.35))
    if (Math.abs(toY - fromY) < flatThreshold) {
      return `M ${fromX} ${fromY} L ${trunkX} ${fromY} L ${toX} ${toY}`
    }
    const approachY = branchApproachY(toY, fromY, trunkX, toX, maxR, flatThreshold)
    if (Math.abs(approachY - toY) < 0.5 || r <= 0.5) {
      return `M ${fromX} ${fromY} L ${trunkX} ${fromY} L ${toX} ${toY}`
    }
    // Single child: one continuous path (stem → bus → fillet → child).
    return [
      `M ${fromX} ${fromY}`,
      `L ${trunkX} ${fromY}`,
      `L ${trunkX} ${approachY}`,
      `Q ${trunkX} ${toY} ${trunkX + sx * r} ${toY}`,
      `L ${toX} ${toY}`,
    ].join(' ')
  }

  const tees = branchYs.map((y, i) =>
    resolveTeeSpec(y, fromY, trunkX, branchToXs[i] ?? toX, maxR, flatThreshold, roundDespiteFlat)
  )
  const spine = buildSpineWithFilletTees(fromX, fromY, trunkX, tees)
  return `${spine} ${stub}`
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
  const absDx = Math.abs(dx)
  if (absDx < 0.5) return sourceX

  // Never place the trunk on/past the child. A fixed 28px min offset used to
  // overshoot when the parent→child gap shrank (width SoT mismatch), leaving
  // hLen≈0 so buildRoundedTeeBranch dropped the Q and corners went sharp 90°.
  const teeClearance = Math.min(MINDMAP_CONNECTOR_MAX_RADIUS + 4, Math.max(4, absDx / 2))
  const maxOffset = Math.max(0, absDx - teeClearance)
  const ratioSpan = absDx * MINDMAP_CONNECTOR_TURN_RATIO
  const preferred = Math.max(
    Math.min(MINDMAP_TOPIC_TRUNK_MIN_OFFSET, maxOffset),
    Math.min(ratioSpan, maxOffset)
  )
  const offset = Math.min(maxOffset, preferred)
  return flowingRight ? sourceX + offset : sourceX - offset
}
