/**
 * Windows-host Google i18n gap-fill library.
 * Live translation must run on the Windows host (VPN). WSL has no Google access.
 */
export { collectGaps, fillNamespace, loadMod, writeNamespace } from './gapFill.ts'
export { googleToForLocale, protectPlaceholders, restorePlaceholders, translateBatch } from './googleBatch.ts'
export { isKeepFill, KEEP_VALUES, PLACEHOLDER_RE } from './keepFill.ts'
export { NS_FILES, type Namespace } from './namespaces.ts'
export { setupFetchProxy } from './proxy.ts'
export { parseArgs, runGapFill } from './cli.ts'
