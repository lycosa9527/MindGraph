import { describe, expect, it } from 'vitest'

import {
  TRAINING_ROLES,
  clampRoleWidth,
  isTrainingRoleId,
  resizeRoleWidth,
  roleWidth,
  trainingRolePlaybackSrc,
  trainingRoleSrc,
  trainingRoleThumb,
} from '@/config/trainingRoles'
import type { TrainingStepOverlay } from '@/types/training'

describe('trainingRoles', () => {
  it('ships twenty role clips with public WebP urls', () => {
    expect(TRAINING_ROLES).toHaveLength(20)
    expect(isTrainingRoleId('11-clap')).toBe(true)
    expect(isTrainingRoleId('ghost')).toBe(false)
    expect(trainingRoleSrc('11-clap')).toBe('/training/roles/11-clap.webp')
    expect(trainingRoleThumb('11-clap')).toBe('/training/roles/11-clap-thumb.webp')
    expect(trainingRolePlaybackSrc('11-clap')).toBe(
      '/api/training/assets/roles/11-clap.webp'
    )
    expect(trainingRolePlaybackSrc('ghost')).toBe(
      '/api/training/assets/roles/01-look-here.webp'
    )
  })

  it('clamps and resizes role width from the right edge', () => {
    expect(clampRoleWidth(2)).toBe(8)
    expect(clampRoleWidth(90)).toBe(48)
    expect(roleWidth({ kind: 'role' })).toBe(18)
    const overlay: TrainingStepOverlay = { kind: 'role', x: 80, y: 70, w: 20 }
    resizeRoleWidth(overlay, 86)
    expect(overlay.w).toBe(16)
  })
})
