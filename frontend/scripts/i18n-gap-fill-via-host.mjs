/**
 * Google i18n gap-fill must run on the Windows host (VPN / system proxy).
 * WSL cannot reach Google. Dry-run (--dry-run) may run locally in WSL to count gaps.
 *
 * Override: MINDGRAPH_I18N_GAP_FILL_DIRECT=1 runs node i18n-google/cli.ts in-process
 * (Cursor Cloud / Linux CI — no Windows host).
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = join(__dirname, '..')
const CLI = join(FRONTEND_ROOT, 'i18n-google', 'cli.ts')
const HOST_PS1 = join(FRONTEND_ROOT, 'i18n-google', 'run-on-windows-host.ps1')

function isWslLinux() {
  if (process.platform !== 'linux') return false
  try {
    return readFileSync('/proc/version', 'utf8').toLowerCase().includes('microsoft')
  } catch {
    return false
  }
}

function toWindowsPath(posixPath) {
  const r = spawnSync('wslpath', ['-w', posixPath], { encoding: 'utf8' })
  if (r.status === 0 && r.stdout?.trim()) {
    return r.stdout.trim()
  }
  return posixPath
}

function runNodeCli(extraArgv) {
  const r = spawnSync(process.execPath, [CLI, ...extraArgv], {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    env: process.env,
  })
  process.exit(r.status ?? 1)
}

function runOnWindowsHost(extraArgv) {
  if (!existsSync(HOST_PS1)) {
    console.error(`Missing host runner: ${HOST_PS1}`)
    process.exit(1)
  }
  const ps1Win = toWindowsPath(HOST_PS1)
  const args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1Win, ...extraArgv]
  const r = spawnSync('powershell.exe', args, {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    env: process.env,
  })
  if (r.error) {
    console.error(r.error.message)
    console.error(
      'Could not start powershell.exe. Run gap-fill from Windows PowerShell in frontend/:',
      `powershell -File i18n-google/run-on-windows-host.ps1 ${extraArgv.join(' ')}`
    )
    process.exit(1)
  }
  process.exit(r.status ?? 1)
}

const argv = process.argv.slice(2)
const dryRun = argv.includes('--dry-run')

if (process.env.MINDGRAPH_I18N_GAP_FILL_DIRECT === '1') {
  runNodeCli(argv)
}

if (process.platform === 'win32') {
  runNodeCli(argv)
}

if (isWslLinux()) {
  if (dryRun) {
    console.log('[i18n:gap-fill] dry-run on WSL (no Google). Live fill uses Windows host VPN.')
    runNodeCli(argv)
  }
  console.log('[i18n:gap-fill] Live Google translate → Windows host (VPN / system proxy).')
  runOnWindowsHost(argv)
}

console.log(
  '[i18n:gap-fill] Non-WSL Linux: set MINDGRAPH_I18N_GAP_FILL_DIRECT=1 if Google is reachable.'
)
runNodeCli(argv)
