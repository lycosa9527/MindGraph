/**
 * Compare flattened message keys across all UI bundles vs zh (fail on drift).
 * Run from frontend/: npx tsx scripts/check-i18n-keys.ts
 */
import af from '../src/locales/messages/af'
import am from '../src/locales/messages/am'
import ar from '../src/locales/messages/ar'
import az from '../src/locales/messages/az'
import bg from '../src/locales/messages/bg'
import bn from '../src/locales/messages/bn'
import bs from '../src/locales/messages/bs'
import ca from '../src/locales/messages/ca'
import cs from '../src/locales/messages/cs'
import da from '../src/locales/messages/da'
import de from '../src/locales/messages/de'
import dv from '../src/locales/messages/dv'
import el from '../src/locales/messages/el'
import en from '../src/locales/messages/en'
import es from '../src/locales/messages/es'
import et from '../src/locales/messages/et'
import fa from '../src/locales/messages/fa'
import fi from '../src/locales/messages/fi'
import fr from '../src/locales/messages/fr'
import ha from '../src/locales/messages/ha'
import he from '../src/locales/messages/he'
import hi from '../src/locales/messages/hi'
import hr from '../src/locales/messages/hr'
import hu from '../src/locales/messages/hu'
import hy from '../src/locales/messages/hy'
import id from '../src/locales/messages/id'
import ig from '../src/locales/messages/ig'
import it from '../src/locales/messages/it'
import ja from '../src/locales/messages/ja'
import ka from '../src/locales/messages/ka'
import kk from '../src/locales/messages/kk'
import km from '../src/locales/messages/km'
import ko from '../src/locales/messages/ko'
import ky from '../src/locales/messages/ky'
import lo from '../src/locales/messages/lo'
import lt from '../src/locales/messages/lt'
import lv from '../src/locales/messages/lv'
import mk from '../src/locales/messages/mk'
import ml from '../src/locales/messages/ml'
import mn from '../src/locales/messages/mn'
import ms from '../src/locales/messages/ms'
import my from '../src/locales/messages/my'
import ne from '../src/locales/messages/ne'
import nl from '../src/locales/messages/nl'
import no from '../src/locales/messages/no'
import pl from '../src/locales/messages/pl'
import ps from '../src/locales/messages/ps'
import pt from '../src/locales/messages/pt'
import ro from '../src/locales/messages/ro'
import ru from '../src/locales/messages/ru'
import si from '../src/locales/messages/si'
import sk from '../src/locales/messages/sk'
import sl from '../src/locales/messages/sl'
import so from '../src/locales/messages/so'
import sq from '../src/locales/messages/sq'
import sr from '../src/locales/messages/sr'
import ss from '../src/locales/messages/ss'
import st from '../src/locales/messages/st'
import sv from '../src/locales/messages/sv'
import sw from '../src/locales/messages/sw'
import ta from '../src/locales/messages/ta'
import tg from '../src/locales/messages/tg'
import th from '../src/locales/messages/th'
import tk from '../src/locales/messages/tk'
import tl from '../src/locales/messages/tl'
import tn from '../src/locales/messages/tn'
import tr from '../src/locales/messages/tr'
import ug from '../src/locales/messages/ug'
import uk from '../src/locales/messages/uk'
import ur from '../src/locales/messages/ur'
import uz from '../src/locales/messages/uz'
import vi from '../src/locales/messages/vi'
import xh from '../src/locales/messages/xh'
import yo from '../src/locales/messages/yo'
import zh from '../src/locales/messages/zh'
import zhTw from '../src/locales/messages/zh-tw'
import zu from '../src/locales/messages/zu'

function keySet(messages: Record<string, string>): Set<string> {
  return new Set(Object.keys(messages))
}

function reportMissing(label: string, missing: string[]): void {
  if (missing.length === 0) {
    return
  }
  console.error(`${label} (${missing.length}):`)
  for (const k of missing.sort()) {
    console.error(`  - ${k}`)
  }
}

const NON_ZH_BUNDLES: { label: string; mod: Record<string, string> }[] = [
  { label: 'en', mod: en as Record<string, string> },
  { label: 'az', mod: az as Record<string, string> },
  { label: 'th', mod: th as Record<string, string> },
  { label: 'zh-tw', mod: zhTw as Record<string, string> },
  { label: 'fr', mod: fr as Record<string, string> },
  { label: 'de', mod: de as Record<string, string> },
  { label: 'dv', mod: dv as Record<string, string> },
  { label: 'ja', mod: ja as Record<string, string> },
  { label: 'ko', mod: ko as Record<string, string> },
  { label: 'pt', mod: pt as Record<string, string> },
  { label: 'ru', mod: ru as Record<string, string> },
  { label: 'ar', mod: ar as Record<string, string> },
  { label: 'nl', mod: nl as Record<string, string> },
  { label: 'it', mod: it as Record<string, string> },
  { label: 'hi', mod: hi as Record<string, string> },
  { label: 'id', mod: id as Record<string, string> },
  { label: 'vi', mod: vi as Record<string, string> },
  { label: 'tr', mod: tr as Record<string, string> },
  { label: 'pl', mod: pl as Record<string, string> },
  { label: 'ps', mod: ps as Record<string, string> },
  { label: 'uk', mod: uk as Record<string, string> },
  { label: 'ms', mod: ms as Record<string, string> },
  { label: 'es', mod: es as Record<string, string> },
  { label: 'et', mod: et as Record<string, string> },
  { label: 'sv', mod: sv as Record<string, string> },
  { label: 'da', mod: da as Record<string, string> },
  { label: 'fi', mod: fi as Record<string, string> },
  { label: 'no', mod: no as Record<string, string> },
  { label: 'cs', mod: cs as Record<string, string> },
  { label: 'ro', mod: ro as Record<string, string> },
  { label: 'el', mod: el as Record<string, string> },
  { label: 'he', mod: he as Record<string, string> },
  { label: 'fa', mod: fa as Record<string, string> },
  { label: 'sw', mod: sw as Record<string, string> },
  { label: 'tl', mod: tl as Record<string, string> },
  { label: 'bn', mod: bn as Record<string, string> },
  { label: 'bs', mod: bs as Record<string, string> },
  { label: 'ta', mod: ta as Record<string, string> },
  { label: 'ca', mod: ca as Record<string, string> },
  { label: 'bg', mod: bg as Record<string, string> },
  { label: 'hr', mod: hr as Record<string, string> },
  { label: 'hu', mod: hu as Record<string, string> },
  { label: 'hy', mod: hy as Record<string, string> },
  { label: 'am', mod: am as Record<string, string> },
  { label: 'ka', mod: ka as Record<string, string> },
  { label: 'km', mod: km as Record<string, string> },
  { label: 'kk', mod: kk as Record<string, string> },
  { label: 'ky', mod: ky as Record<string, string> },
  { label: 'lo', mod: lo as Record<string, string> },
  { label: 'lt', mod: lt as Record<string, string> },
  { label: 'lv', mod: lv as Record<string, string> },
  { label: 'mk', mod: mk as Record<string, string> },
  { label: 'ml', mod: ml as Record<string, string> },
  { label: 'mn', mod: mn as Record<string, string> },
  { label: 'my', mod: my as Record<string, string> },
  { label: 'ne', mod: ne as Record<string, string> },
  { label: 'si', mod: si as Record<string, string> },
  { label: 'sk', mod: sk as Record<string, string> },
  { label: 'sl', mod: sl as Record<string, string> },
  { label: 'sq', mod: sq as Record<string, string> },
  { label: 'sr', mod: sr as Record<string, string> },
  { label: 'tg', mod: tg as Record<string, string> },
  { label: 'tk', mod: tk as Record<string, string> },
  { label: 'ug', mod: ug as Record<string, string> },
  { label: 'ur', mod: ur as Record<string, string> },
  { label: 'uz', mod: uz as Record<string, string> },
  { label: 'af', mod: af as Record<string, string> },
  { label: 'ha', mod: ha as Record<string, string> },
  { label: 'ig', mod: ig as Record<string, string> },
  { label: 'so', mod: so as Record<string, string> },
  { label: 'ss', mod: ss as Record<string, string> },
  { label: 'st', mod: st as Record<string, string> },
  { label: 'tn', mod: tn as Record<string, string> },
  { label: 'xh', mod: xh as Record<string, string> },
  { label: 'yo', mod: yo as Record<string, string> },
  { label: 'zu', mod: zu as Record<string, string> },
]

function main(): void {
  const kZh = keySet(zh as Record<string, string>)
  let failed = false

  for (const { label, mod } of NON_ZH_BUNDLES) {
    const kMod = keySet(mod)
    const only = [...kZh].filter((k) => !kMod.has(k))
    const extra = [...kMod].filter((k) => !kZh.has(k))
    reportMissing(`Missing in ${label} (vs zh)`, only)
    reportMissing(`Extra in ${label} (not in zh)`, extra)
    if (only.length > 0 || extra.length > 0) {
      failed = true
    }
  }

  if (failed) {
    process.exit(1)
  }
  console.log(`OK: i18n key parity (${kZh.size} keys × ${1 + NON_ZH_BUNDLES.length} locales).`)
}

main()
