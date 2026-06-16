import { extractEchoesToVendorJson } from './extract-echoes.ts'
import { runImport } from './merge.ts'
import { refreshVendorSnapshots } from './refresh-vendor.ts'

const args = new Set(process.argv.slice(2))
const shouldRefresh = args.has('--refresh')
const shouldRefreshEchoes = args.has('--refresh-echoes')
const shouldExtractEchoes = args.has('--extract-echoes')

async function main(): Promise<void> {
  if (shouldRefresh || shouldRefreshEchoes) {
    await refreshVendorSnapshots({
      wisdom: shouldRefresh || !shouldRefreshEchoes,
      echoes: shouldRefreshEchoes,
    })
  }
  if (shouldExtractEchoes) {
    const { zhCount, enCount } = extractEchoesToVendorJson()
    console.log(`extracted echoes-zh.json: ${zhCount} quotes`)
    console.log(`extracted echoes-en.json: ${enCount} quotes`)
  }
  const { zhCount, enCount } = runImport()
  console.log(`sidebar-quotes-zh.json: ${zhCount} quotes`)
  console.log(`sidebar-quotes-en.json: ${enCount} quotes`)
}

main().catch((error: unknown) => {
  console.error(error)
  process.exit(1)
})
