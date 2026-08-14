/**
 * Native English expertise-level templates. Do not assemble these from Chinese slots.
 */
import type { AiContentLevelId } from '@/config/aiContentLevels'

export const MIND_MAP_AUDIENCE_EN: Record<AiContentLevelId, string | undefined> = {
  general: undefined,
  primary: [
    'Write this content for a primary-school classroom.',
    'Voice: everyday concrete words only — no jargon, abstract labels, or acronyms.',
    'Length: short sentences; each line should be easy to read aloud to a child.',
    'Assume: daily life only. Do not assume any subject background.',
    'Depth: name things and give examples. No mechanisms, taxonomies, or cause-and-effect chains.',
  ].join('\n'),
  junior: [
    'Write this content for a middle-school classroom.',
    'Voice: clear everyday language. A light subject word is fine if you gloss it on first use.',
    'Length: short to medium sentences; one idea per sentence.',
    'Assume: general compulsory-education knowledge. Do not assume high-school specialization.',
    'Depth: what it is, simple grouping, and direct use. Little debate or theoretical models.',
  ].join('\n'),
  senior: [
    'Write this content for a high-school classroom.',
    'Voice: standard subject terminology is fine. Skip popular-science padding.',
    'Length: complete sentences that make relationships explicit.',
    'Assume: common high-school concepts in the subject.',
    'Depth: be abstract and complete — cause and effect, contrast, and when it applies. Not a university paper.',
  ].join('\n'),
  university: [
    'Write this content for a university course.',
    'Voice: disciplinary and academic terms. Do not define introductory words.',
    'Length: organize as an argument; slightly longer sentences are fine.',
    'Assume: undergraduate literacy and the basics of the field.',
    'Depth: use a disciplinary frame — mechanism, evidence, and limits. Name models or schools. No K–12 lesson tone.',
  ].join('\n'),
  adult: [
    'Write this content for adult professionals at work.',
    'Voice: clear and professional. Little classroom tone.',
    'Length: direct and action-oriented.',
    'Assume: workplace common sense. Do not assume a school-stage ladder.',
    'Depth: scenarios, decisions, and trade-offs. Little theorem-proving or exam-point lists.',
  ].join('\n'),
  expert: [
    'Write this content for an expert peer.',
    'Voice: domain terminology. No popular-science opening.',
    'Length: dense, precise, and short. Drop transition filler.',
    'Assume: a colleague in the field.',
    'Depth: mechanisms, bounds, disagreements, and counterexamples. No definition lessons, analogy stories, or teaching scaffolds.',
  ].join('\n'),
}
