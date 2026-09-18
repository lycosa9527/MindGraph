/**
 * Thin wrapper — implementation lives in `frontend/i18n-google/`.
 * Windows host only for live Google calls. WSL cannot reach Google.
 */
import { runGapFill } from '../i18n-google/cli.ts'

runGapFill().catch((err: unknown) => {
  console.error(err)
  process.exit(1)
})
