import { existsSync, readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const CHINA_GEO_PATH = resolve(frontendDir, 'public/data/china-geo.json')
const MIN_FEATURES = 10

function main(): void {
  if (!existsSync(CHINA_GEO_PATH)) {
    throw new Error(
      `Missing China GeoJSON for national data center: ${CHINA_GEO_PATH}\n` +
        'Run: MINDGRAPH_NON_INTERACTIVE=1 python scripts/setup/dashboard_install.py\n' +
        'Then copy static/data/china-geo.json to frontend/public/data/china-geo.json'
    )
  }

  const parsed = JSON.parse(readFileSync(CHINA_GEO_PATH, 'utf8')) as {
    type?: string
    features?: unknown[]
  }
  if (parsed.type !== 'FeatureCollection') {
    throw new Error(`China GeoJSON must be a FeatureCollection: ${CHINA_GEO_PATH}`)
  }
  const featureCount = Array.isArray(parsed.features) ? parsed.features.length : 0
  if (featureCount < MIN_FEATURES) {
    throw new Error(
      `China GeoJSON has too few features (${featureCount} < ${MIN_FEATURES}): ${CHINA_GEO_PATH}`
    )
  }

  console.log(`check-china-geo-shipped OK (${featureCount} features)`)
}

main()
