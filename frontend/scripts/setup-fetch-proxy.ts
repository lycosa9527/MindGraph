/**
 * Route Node's global `fetch` (undici) through an HTTP(S) proxy so libraries like
 * `google-translate-api-x` work when a VPN exposes a local proxy (Clash, V2Ray, etc.).
 *
 * Resolution order:
 * 1. `--proxy=http://host:port` on the command line (if argv is passed in)
 * 2. `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` environment variables
 * 3. On Windows only: current-user "LAN" proxy from the registry (Internet Settings)
 */
import { execSync } from 'node:child_process'
import { ProxyAgent, setGlobalDispatcher } from 'undici'

function normalizeProxyUrl(raw: string): string {
  const t = raw.trim()
  if (!t) return t
  if (/^https?:\/\//i.test(t)) return t
  return `http://${t}`
}

/** Parse `ProxyServer` REG_SZ: `127.0.0.1:7890` or `http=host:port;https=host:port` */
function parseWindowsProxyServerRegSz(value: string): string | null {
  const v = value.trim()
  if (!v) return null
  if (v.includes('=')) {
    const httpsPart = v.match(/https=([^;]+)/i)
    const httpPart = v.match(/http=([^;]+)/i)
    const hostPort = (httpsPart?.[1] ?? httpPart?.[1])?.trim()
    if (hostPort) return normalizeProxyUrl(hostPort)
    return null
  }
  return normalizeProxyUrl(v)
}

function readWindowsSystemProxyUrl(): string | null {
  if (process.platform !== 'win32') return null
  try {
    const enableOut = execSync(
      'reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable',
      { encoding: 'utf8' }
    )
    if (!/\b0x1\b/.test(enableOut)) return null

    const serverOut = execSync(
      'reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer',
      { encoding: 'utf8' }
    )
    const line = serverOut.split(/\r?\n/).find((l) => l.includes('ProxyServer'))
    if (!line) return null
    const m = line.match(/ProxyServer\s+REG_SZ\s+(\S.*)$/)
    if (!m) return null
    return parseWindowsProxyServerRegSz(m[1].trim())
  } catch {
    return null
  }
}

function proxyFromEnv(): string | null {
  const u =
    process.env.HTTPS_PROXY?.trim() ||
    process.env.HTTP_PROXY?.trim() ||
    process.env.ALL_PROXY?.trim()
  return u ? normalizeProxyUrl(u) : null
}

function proxyFromArgv(argv: readonly string[]): string | null {
  const raw = argv.find((a) => a.startsWith('--proxy='))
  if (!raw) return null
  const v = raw.slice('--proxy='.length).trim()
  return v ? normalizeProxyUrl(v) : null
}

function redactProxyForLog(url: string): string {
  try {
    const u = new URL(url)
    if (u.password) u.password = '****'
    return u.toString()
  } catch {
    return url
  }
}

/**
 * Apply proxy to Node's fetch dispatcher. Call once before any HTTP(S) requests.
 * @returns The proxy URL used, or null for a direct connection.
 */
export function setupFetchProxy(argv: readonly string[] = process.argv): string | null {
  const fromCli = proxyFromArgv(argv)
  const fromEnv = proxyFromEnv()
  const fromWin = readWindowsSystemProxyUrl()
  const url = fromCli ?? fromEnv ?? fromWin

  if (!url) {
    console.log(
      '[proxy] none (direct). Set HTTPS_PROXY or use Windows system proxy, or pass --proxy='
    )
    return null
  }

  setGlobalDispatcher(new ProxyAgent(url))
  console.log('[proxy]', redactProxyForLog(url))
  return url
}
