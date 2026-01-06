/**
 * Sync version from ../VERSION file to package.json
 * Run before build to ensure package.json version matches VERSION file
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const versionFile = path.resolve(__dirname, '../../VERSION')
const packageFile = path.resolve(__dirname, '../package.json')

try {
  const version = fs.readFileSync(versionFile, 'utf8').trim()
  const pkg = JSON.parse(fs.readFileSync(packageFile, 'utf8'))

  if (pkg.version !== version) {
    pkg.version = version
    fs.writeFileSync(packageFile, JSON.stringify(pkg, null, 2) + '\n')
    console.log(`Updated package.json version to ${version}`)
  } else {
    console.log(`Version already synced: ${version}`)
  }
} catch (err) {
  console.error('Failed to sync version:', err.message)
  process.exit(1)
}
