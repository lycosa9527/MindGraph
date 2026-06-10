import { describe, expect, it } from 'vitest'

import {
  effectiveMemberLimit,
  SCHOOL_TIER_LIMITS,
  SCHOOL_TIER_OPTIONS,
  isPaidSchoolTier,
  mergeSchoolTierFeatures,
  normalizeSchoolTier,
  tierFeaturesForSchoolTier,
} from '@/constants/schoolTier'

describe('schoolTier constants', () => {
  it('includes trial as the first tier option', () => {
    expect(SCHOOL_TIER_OPTIONS[0]).toBe('trial')
    expect(SCHOOL_TIER_OPTIONS).toEqual(['trial', 'lite', 'standard', 'professional'])
  })

  it('defines limits for every tier slug', () => {
    for (const tier of SCHOOL_TIER_OPTIONS) {
      if (tier === 'trial') {
        expect(SCHOOL_TIER_LIMITS[tier].memberLimit).toBe(0)
        expect(SCHOOL_TIER_LIMITS[tier].managerLimit).toBe(0)
        expect(SCHOOL_TIER_LIMITS[tier].diagramsPerMember).toBe(20)
      } else {
        expect(SCHOOL_TIER_LIMITS[tier].memberLimit).toBeGreaterThan(0)
      }
    }
  })

  it('normalizeSchoolTier defaults unknown values to trial', () => {
    expect(normalizeSchoolTier(null)).toBe('trial')
    expect(normalizeSchoolTier(undefined)).toBe('trial')
    expect(normalizeSchoolTier('')).toBe('trial')
    expect(normalizeSchoolTier('bogus')).toBe('trial')
    expect(normalizeSchoolTier('TRIAL')).toBe('trial')
    expect(normalizeSchoolTier('standard')).toBe('standard')
  })

  it('treats trial like lite for premium feature gating', () => {
    expect(tierFeaturesForSchoolTier('trial').online_collab).toBe(false)
    expect(tierFeaturesForSchoolTier('lite').online_collab).toBe(false)
    expect(tierFeaturesForSchoolTier('standard').online_collab).toBe(true)
  })

  it('mergeSchoolTierFeatures respects trial defaults', () => {
    const merged = mergeSchoolTierFeatures('trial', { online_collab: true })
    expect(merged.online_collab).toBe(true)
    expect(merged.api_token).toBe(false)
  })

  it('treats zero manager limit as unavailable on trial', () => {
    expect(SCHOOL_TIER_LIMITS.trial.managerLimit).toBe(0)
  })

  it('isPaidSchoolTier excludes trial', () => {
    expect(isPaidSchoolTier('trial')).toBe(false)
    expect(isPaidSchoolTier('lite')).toBe(true)
    expect(isPaidSchoolTier('standard')).toBe(true)
    expect(isPaidSchoolTier('professional')).toBe(true)
  })

  it('effectiveMemberLimit adds extra seats above tier base', () => {
    expect(effectiveMemberLimit('lite', 10)).toBe(60)
    expect(effectiveMemberLimit('standard', 50)).toBe(170)
    expect(effectiveMemberLimit('trial', 50)).toBe(0)
  })
})
