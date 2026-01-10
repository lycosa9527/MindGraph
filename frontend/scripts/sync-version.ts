/**
 * Sync version from root VERSION file to package.json
 * Runs as prebuild hook to ensure version consistency
 */
import { readFileSync, writeFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

interface PackageJson {
  name: string
  version: string
  [key: string]: unknown
}

const __dirname = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(__dirname, '../..')
const frontendDir = resolve(__dirname, '..')

// Read version from root VERSION file
const versionFile = resolve(rootDir, 'VERSION')
const version = readFileSync(versionFile, 'utf8').trim()

// Update package.json
const packagePath = resolve(frontendDir, 'package.json')
const pkg: PackageJson = JSON.parse(readFileSync(packagePath, 'utf8'))
pkg.version = version
writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + '\n')

console.log(`Synced version to ${version}`)
