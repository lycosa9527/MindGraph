/**
 * Route visible chrome through bilingual labels.
 *
 * - Template text `{{ t(...) }}` becomes `<I18nText>`.
 * - Element Plus label props that have a slot become that slot.
 * - Script `label: t(...)` also stores `labelKey` so shared controls can
 *   render the presenter line without dropping the primary string.
 *
 *   node scripts/codemod-bilingual-template.mjs
 *   node scripts/codemod-bilingual-template.mjs --check
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { parse } from '@vue/compiler-sfc'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')
const CHECK = process.argv.includes('--check')

const LABEL_SLOT_TAGS = new Map([
  ['el-table-column', 'header'],
  ['ElTableColumn', 'header'],
  ['el-form-item', 'label'],
  ['ElFormItem', 'label'],
  ['el-tab-pane', 'label'],
  ['ElTabPane', 'label'],
  ['el-descriptions-item', 'label'],
  ['ElDescriptionsItem', 'label'],
])

const OPTION_SLOT_TAGS = new Set(['el-option', 'ElOption'])

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === 'locales' || name === 'node_modules') continue
    const full = path.join(dir, name)
    const st = statSync(full)
    if (st.isDirectory()) walk(full, out)
    else if (name.endsWith('.vue') || name.endsWith('.ts')) out.push(full)
  }
  return out
}

function matchingCloser(source, openIndex, openChar, closeChar) {
  let depth = 0
  let i = openIndex
  let quote = ''
  let escape = false
  while (i < source.length) {
    const ch = source[i]
    if (quote) {
      if (escape) {
        escape = false
      } else if (ch === '\\') {
        escape = true
      } else if (ch === quote) {
        quote = ''
      } else if (quote === '`' && ch === '$' && source[i + 1] === '{') {
        const end = matchingCloser(source, i + 1, '{', '}')
        if (end < 0) return -1
        i = end
      }
      i += 1
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      i += 1
      continue
    }
    if (ch === openChar) depth += 1
    else if (ch === closeChar) {
      depth -= 1
      if (depth === 0) return i
    }
    i += 1
  }
  return -1
}

function splitTopLevel(source) {
  const parts = []
  let start = 0
  let depth = 0
  let quote = ''
  let escape = false
  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i]
    if (quote) {
      if (escape) escape = false
      else if (ch === '\\') escape = true
      else if (ch === quote) quote = ''
      else if (quote === '`' && ch === '$' && source[i + 1] === '{') {
        const end = matchingCloser(source, i + 1, '{', '}')
        if (end < 0) return null
        i = end
      }
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '(' || ch === '{' || ch === '[') depth += 1
    else if (ch === ')' || ch === '}' || ch === ']') depth -= 1
    else if (ch === ',' && depth === 0) {
      parts.push(source.slice(start, i))
      start = i + 1
    }
  }
  parts.push(source.slice(start))
  return parts
}

function parseStringLiteral(raw) {
  const text = raw.trim()
  if (text.length < 2) return null
  const q = text[0]
  if ((q !== '"' && q !== "'") || text[text.length - 1] !== q) return null
  if (text.slice(1, -1).includes(q)) return null
  return text.slice(1, -1)
}

/** Whole expression is a t() call. Null when it is not safe to reroute. */
function parseTExpression(expr) {
  const text = expr.trim()
  if (!text.startsWith('t(')) return null
  const close = matchingCloser(text, 1, '(', ')')
  if (close < 0 || text.slice(close + 1).trim()) return null
  const args = splitTopLevel(text.slice(2, close))
  if (!args || args.length < 1 || args.length > 2) return null
  const keyExpr = args[0].trim()
  if (!keyExpr) return null
  let params = null
  let fallbackKey = null
  let fallbackText = null
  if (args.length === 2) {
    const second = args[1].trim()
    if (!second) return null
    if (parseStringLiteral(second)) {
      // Literal missing-key fallback. Catalog English covers a missing key.
    } else if (second.startsWith('{')) {
      params = second
    } else if (second.startsWith('t(')) {
      const inner = parseTExpression(second)
      if (!inner || inner.key == null || inner.params || inner.fallbackKey || inner.fallbackText) {
        return null
      }
      fallbackKey = inner.key
    } else {
      // vue-i18n default string (often a raw error), not an interpolation object.
      fallbackText = second
    }
  }
  return { key: parseStringLiteral(keyExpr), keyExpr, params, fallbackKey, fallbackText }
}

function attrQuote(value) {
  if (!value.includes('"')) return `"${value}"`
  if (!value.includes("'")) return `'${value}'`
  return null
}

function vueAttr(name, value) {
  if (!value.includes('"')) return `${name}="${value}"`
  if (!value.includes("'")) return `${name}='${value}'`
  return null
}

function i18nTag(call, directive = '') {
  const keyAttr = call.key != null ? `k=${attrQuote(call.key)}` : `:k=${attrQuote(call.keyExpr)}`
  if (!keyAttr || keyAttr.endsWith('=null')) return null
  if (call.key == null && !attrQuote(call.keyExpr)) return null
  let attrs = `${directive}${keyAttr}`
  if (call.params) {
    const paramsAttr = attrQuote(call.params)
    if (!paramsAttr) return null
    attrs += ` :params=${paramsAttr}`
  }
  if (call.fallbackKey) attrs += ` fallback-key="${call.fallbackKey}"`
  if (call.fallbackText) {
    const fallbackAttr = attrQuote(call.fallbackText)
    if (!fallbackAttr) return null
    attrs += ` :fallback-text=${fallbackAttr}`
  }
  return `<I18nText ${attrs} />`
}

function scanDepth(source, onChar) {
  let depth = 0
  let quote = ''
  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i]
    if (quote) {
      if (ch === '\\') {
        i += 1
        continue
      }
      if (ch === quote) quote = ''
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '(' || ch === '{' || ch === '[') depth += 1
    else if (ch === ')' || ch === '}' || ch === ']') depth -= 1
    else if (depth === 0 && onChar(ch, i, source) === 'stop') break
  }
}

function splitLastOr(expr) {
  let at = -1
  scanDepth(expr, (ch, i, source) => {
    if (ch === '|' && source[i + 1] === '|') at = i
    return null
  })
  if (at < 0) return null
  return { left: expr.slice(0, at).trim(), right: expr.slice(at + 2).trim() }
}

function splitTernary(expr) {
  let qAt = -1
  let colonAt = -1
  let ternary = 0
  let depth = 0
  let quote = ''
  for (let i = 0; i < expr.length; i += 1) {
    const ch = expr[i]
    if (quote) {
      if (ch === '\\') {
        i += 1
        continue
      }
      if (ch === quote) quote = ''
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '(' || ch === '{' || ch === '[') depth += 1
    else if (ch === ')' || ch === '}' || ch === ']') depth -= 1
    else if (depth === 0 && ch === '?') {
      const next = expr[i + 1]
      if (next === '.' || next === '?') continue
      if (ternary === 0 && qAt < 0) qAt = i
      ternary += 1
    } else if (depth === 0 && ch === ':' && ternary > 0) {
      ternary -= 1
      if (ternary === 0 && qAt >= 0) {
        colonAt = i
        break
      }
    }
  }
  if (qAt < 0 || colonAt < 0) return null
  return {
    cond: expr.slice(0, qAt).trim(),
    yes: expr.slice(qAt + 1, colonAt).trim(),
    no: expr.slice(colonAt + 1).trim(),
  }
}

function textBranch(directive, expr) {
  const attr = vueAttr(directive, expr)
  if (!attr) return null
  return `<template ${attr}>{{ ${expr} }}</template>`
}

function branchTag(kind, cond, expr) {
  const call = parseTExpression(expr)
  if (call) {
    const directive = kind === 'if' ? `${vueAttr('v-if', cond)} ` : 'v-else '
    if (kind === 'if' && !vueAttr('v-if', cond)) return null
    return i18nTag(call, directive)
  }
  const nested = rewriteCompoundMustache(expr)
  if (nested) {
    if (kind === 'if') {
      const attr = vueAttr('v-if', cond)
      if (!attr) return null
      return `<template ${attr}>${nested}</template>`
    }
    return `<template v-else>${nested}</template>`
  }
  if (kind === 'if') return textBranch('v-if', cond) ? `<template ${vueAttr('v-if', cond)}>{{ ${expr} }}</template>` : null
  return `<template v-else>{{ ${expr} }}</template>`
}

function rewriteCompoundMustache(expr) {
  const text = expr.trim()
  if (text.endsWith('.toLowerCase()')) {
    const inner = parseTExpression(text.slice(0, -'.toLowerCase()'.length))
    if (inner) return i18nTag(inner)
  }
  const ternary = splitTernary(text)
  if (ternary && ternary.cond && ternary.yes && ternary.no) {
    const yes = branchTag('if', ternary.cond, ternary.yes)
    const no = branchTag('else', ternary.cond, ternary.no)
    if (yes && no && (parseTExpression(ternary.yes) || parseTExpression(ternary.no))) {
      return `${yes}${no}`
    }
    return null
  }
  const or = splitLastOr(text)
  if (or && parseTExpression(or.right)) {
    const yes = textBranch('v-if', or.left)
    const no = i18nTag(parseTExpression(or.right), 'v-else ')
    if (yes && no) return `${yes}${no}`
  }
  return null
}

function findMustacheEnd(source, open) {
  // `open` is the first brace of `{{`. Match from the second brace so the
  // expression does not swallow the closing pair.
  const close = matchingCloser(source, open + 1, '{', '}')
  if (close < 0 || source[close + 1] !== '}') return -1
  return close
}

function transformTextMustaches(input) {
  let out = ''
  let i = 0
  let changed = 0
  let state = 'text'
  let quote = ''
  while (i < input.length) {
    if (state === 'comment') {
      const end = input.indexOf('-->', i)
      if (end < 0) {
        out += input.slice(i)
        break
      }
      out += input.slice(i, end + 3)
      i = end + 3
      state = 'text'
      continue
    }
    if (state === 'tag') {
      const ch = input[i]
      out += ch
      i += 1
      if (quote) {
        if (ch === quote) quote = ''
        continue
      }
      if (ch === '"' || ch === "'") {
        quote = ch
        continue
      }
      if (ch === '>') state = 'text'
      continue
    }
    if (input.startsWith('<!--', i)) {
      state = 'comment'
      out += '<!--'
      i += 4
      continue
    }
    if (input[i] === '<') {
      state = 'tag'
      quote = ''
      out += '<'
      i += 1
      continue
    }
    if (input.startsWith('{{', i)) {
      const end = findMustacheEnd(input, i)
      if (end < 0) {
        out += input[i]
        i += 1
        continue
      }
      const expr = input.slice(i + 2, end)
      const call = parseTExpression(expr)
      const tag = call ? i18nTag(call) : rewriteCompoundMustache(expr)
      if (tag) {
        out += tag
        changed += 1
      } else {
        out += input.slice(i, end + 2)
      }
      i = end + 2
      continue
    }
    out += input[i]
    i += 1
  }
  return { text: out, changed }
}

function readTagName(tag) {
  const match = /^<\s*([A-Za-z][\w.-]*)/.exec(tag)
  return match ? match[1] : ''
}

function extractLabelAttr(tag) {
  const patterns = [':label="', ':label=\'', 'v-bind:label="', "v-bind:label='"]
  for (const prefix of patterns) {
    const at = tag.indexOf(prefix)
    if (at < 0) continue
    const q = prefix.endsWith('"') ? '"' : "'"
    const valueStart = at + prefix.length
    const valueEnd = tag.indexOf(q, valueStart)
    if (valueEnd < 0) return null
    const value = tag.slice(valueStart, valueEnd)
    const call = parseTExpression(value)
    if (!call) return null
    return { start: at, end: valueEnd + 1, call }
  }
  return null
}

function tagHasSlot(body, slot) {
  return body.includes(`#${slot}`) || body.includes(`v-slot:${slot}`)
}

function transformLabelProps(input) {
  let out = ''
  let i = 0
  let changed = 0
  let state = 'text'
  let quote = ''
  let tagStart = -1
  while (i < input.length) {
    if (state === 'comment') {
      const end = input.indexOf('-->', i)
      if (end < 0) {
        out += input.slice(i)
        break
      }
      out += input.slice(i, end + 3)
      i = end + 3
      state = 'text'
      continue
    }
    if (state === 'text') {
      if (input.startsWith('<!--', i)) {
        state = 'comment'
        out += '<!--'
        i += 4
        continue
      }
      if (input[i] === '<') {
        state = 'tag'
        quote = ''
        tagStart = out.length
      }
      out += input[i]
      i += 1
      continue
    }
    const ch = input[i]
    out += ch
    i += 1
    if (quote) {
      if (ch === quote) quote = ''
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      continue
    }
    if (ch !== '>') continue
    state = 'text'
    const tag = out.slice(tagStart)
    const name = readTagName(tag)
    const label = extractLabelAttr(tag)
    if (!label) continue
    const slot = LABEL_SLOT_TAGS.get(name)
    const option = OPTION_SLOT_TAGS.has(name)
    if (!slot && !option) continue
    const selfClosing = tag.endsWith('/>')
    if (!selfClosing) {
      const close = `</${name}>`
      const rest = input.slice(i)
      const closeAt = rest.indexOf(close)
      if (closeAt >= 0 && tagHasSlot(rest.slice(0, closeAt), slot || 'default')) continue
    }
    const element = i18nTag(label.call)
    if (!element) continue
    if (option) {
      // Keep :label so the closed select shows the primary string. The slot
      // is the open list, where the presenter line can sit under it.
      if (!selfClosing) {
        const close = `</${name}>`
        const rest = input.slice(i)
        const closeAt = rest.indexOf(close)
        if (closeAt >= 0 && rest.slice(0, closeAt).includes('<I18nText')) continue
      }
      const open = selfClosing ? tag.replace(/\s*\/>$/, '>') : tag
      if (selfClosing) {
        out = `${out.slice(0, tagStart) + open}\n${element}\n</${name}>`
      } else {
        out = out.slice(0, tagStart) + open + element
      }
      changed += 1
      continue
    }
    const tagWithout = `${tag.slice(0, label.start)}${tag.slice(label.end)}`
    const cleaned = tagWithout.replace(/\s+\/>$/, ' />').replace(/\s+>/, '>')
    const slotBlock = `\n<template #${slot}>\n${element}\n</template>`
    if (selfClosing) {
      const open = cleaned.replace(/\s*\/>$/, '>')
      out = `${out.slice(0, tagStart) + open + slotBlock}\n</${name}>`
    } else {
      out = out.slice(0, tagStart) + cleaned + slotBlock
    }
    changed += 1
  }
  return { text: out, changed }
}

function labelBindingFromI18n(tag) {
  const lit = /(?<!:)k="([^"]*)"/.exec(tag) ?? /(?<!:)k='([^']*)'/.exec(tag)
  const dyn = /:k="([^"]*)"/.exec(tag) ?? /:k='([^']*)'/.exec(tag)
  const params = /:params="([^"]*)"/.exec(tag) ?? /:params='([^']*)'/.exec(tag)
  let call = ''
  if (lit) call = `t('${lit[1].replace(/'/g, "\\'")}')`
  else if (dyn) call = `t(${dyn[1]})`
  else return null
  if (params) {
    call = call.slice(0, -1) + `, ${params[1]})`
  }
  if (call.includes('"')) return null
  return `:label="${call}"`
}

function repairOptions(input) {
  let out = ''
  let i = 0
  let changed = 0
  while (i < input.length) {
    const optionAt = Math.min(
      ...['<el-option', '<ElOption'].map((token) => {
        const at = input.indexOf(token, i)
        return at < 0 ? Number.POSITIVE_INFINITY : at
      })
    )
    if (!Number.isFinite(optionAt)) {
      out += input.slice(i)
      break
    }
    const name = input.startsWith('<ElOption', optionAt) ? 'ElOption' : 'el-option'
    const boundary = input[optionAt + name.length + 1]
    if (boundary !== ' ' && boundary !== '\n' && boundary !== '\r' && boundary !== '>' && boundary !== '/') {
      out += input.slice(i, optionAt + name.length)
      i = optionAt + name.length
      continue
    }
    out += input.slice(i, optionAt)
    const openEnd = input.indexOf('>', optionAt)
    if (openEnd < 0) {
      out += input.slice(optionAt)
      break
    }
    const selfClosing = input[openEnd - 1] === '/'
    if (selfClosing) {
      out += input.slice(optionAt, openEnd + 1)
      i = openEnd + 1
      continue
    }
    const close = `</${name}>`
    const closeAt = input.indexOf(close, openEnd)
    if (closeAt < 0) {
      out += input.slice(optionAt)
      break
    }
    let open = input.slice(optionAt, openEnd + 1)
    let body = input.slice(openEnd + 1, closeAt)
    const first = /<I18nText\b[^>]*\/>/.exec(body)
    if (first) {
      const dyn = /:k="([^"]*)"/.exec(first[0]) ?? /:k='([^']*)'/.exec(first[0])
      const quoted = dyn ? `:label="t('${dyn[1]}')"` : ''
      if (dyn && open.includes(quoted)) {
        open = open.replace(quoted, `:label="t(${dyn[1]})"`)
        changed += 1
      } else if (!/[:\w-]label=/.test(open)) {
        const binding = labelBindingFromI18n(first[0])
        if (binding) {
          open = open.replace(/>$/, ` ${binding}>`)
          changed += 1
        }
      }
    }
    const direct = body.match(/^\s*<I18nText\b[^>]*\/>\s*/)
    if (direct && body.slice(direct[0].length).includes('<I18nText')) {
      body = body.slice(direct[0].length)
      changed += 1
    }
    out += open + body + close
    i = closeAt + close.length
  }
  return { text: out, changed }
}

function enclosingObjectHas(source, at, needles) {
  let depth = 0
  let start = -1
  for (let i = at; i >= 0; i -= 1) {
    const ch = source[i]
    if (ch === '}') depth += 1
    else if (ch === '{') {
      if (depth === 0) {
        start = i
        break
      }
      depth -= 1
    }
  }
  if (start < 0) return false
  const close = matchingCloser(source, start, '{', '}')
  if (close < 0) return false
  const body = source.slice(start, close)
  return needles.some((needle) => body.includes(needle))
}

function injectLabelKeys(source) {
  let out = ''
  let i = 0
  let changed = 0
  while (i < source.length) {
    const at = source.indexOf('label:', i)
    if (at < 0) {
      out += source.slice(i)
      break
    }
    const between = source.slice(i, at)
    out += between
    const lineStart = source.lastIndexOf('\n', at) + 1
    const line = source.slice(lineStart, at).trim()
    if (line.startsWith('//') || line.startsWith('*') || line.startsWith('/*')) {
      out += 'label:'
      i = at + 'label:'.length
      continue
    }
    const afterColon = source.slice(at + 'label:'.length)
    const ws = /^(\s*)/.exec(afterColon)?.[1] ?? ''
    const rest = afterColon.slice(ws.length)
    if (!rest.startsWith('t(')) {
      out += 'label:'
      i = at + 'label:'.length
      continue
    }
    const close = matchingCloser(rest, 1, '(', ')')
    if (close < 0) {
      out += 'label:'
      i = at + 'label:'.length
      continue
    }
    let callEnd = close + 1
    const asString = /^\s+as\s+string/.exec(rest.slice(callEnd))
    if (asString) callEnd += asString[0].length
    const callText = rest.slice(0, close + 1)
    const parsed = parseTExpression(callText)
    const ahead = rest.slice(callEnd, callEnd + 80)
    if (!parsed || ahead.includes('labelKey') || enclosingObjectHas(source, at, ['borderColor', 'pointRadius'])) {
      out += 'label:'
      i = at + 'label:'.length
      continue
    }
    const keyBit = parsed.key != null ? attrQuote(parsed.key)?.slice(1, -1) : null
    const keyCode = parsed.key != null && keyBit != null ? `'${parsed.key.replace(/'/g, "\\'")}'` : parsed.keyExpr
    let extra = `, labelKey: ${keyCode}`
    if (parsed.params) extra += `, labelParams: ${parsed.params}`
    out += `label:${ws}${rest.slice(0, callEnd)}${extra}`
    changed += 1
    i = at + 'label:'.length + ws.length + callEnd
  }
  return { text: out, changed }
}

function assertFixture(name, actual, expected) {
  if (actual !== expected) {
    throw new Error(`${name}\nactual: ${actual}\nexpected: ${expected}`)
  }
}

function selfTest() {
  assertFixture(
    'simple',
    transformTextMustaches('<p>{{ t(\'admin.save\') }}</p>').text,
    '<p><I18nText k="admin.save" /></p>'
  )
  assertFixture(
    'attr untouched',
    transformTextMustaches('<el-input :placeholder="t(\'admin.save\')" />').text,
    '<el-input :placeholder="t(\'admin.save\')" />'
  )
  assertFixture(
    'params',
    transformTextMustaches('{{ t(\'a.b\', { n: 1 }) }}').text,
    '<I18nText k="a.b" :params="{ n: 1 }" />'
  )
  assertFixture(
    'lowercase becomes bilingual text',
    transformTextMustaches('{{ t(\'a\').toLowerCase() }}').text,
    '<I18nText k="a" />'
  )
  assertFixture(
    'ternary',
    transformTextMustaches('{{ loading ? t(\'a.on\') : t(\'a.off\') }}').text,
    '<I18nText v-if="loading" k="a.on" /><I18nText v-else k="a.off" />'
  )
  assertFixture(
    'nested ternary',
    transformTextMustaches(
      "{{ on ? t('a.on') : off ? t('a.off') : t('a.idle') }}"
    ).text,
    '<I18nText v-if="on" k="a.on" /><template v-else><I18nText v-if="off" k="a.off" /><I18nText v-else k="a.idle" /></template>'
  )
  assertFixture(
    'optional chain or',
    transformTextMustaches("{{ row.document?.title || t('a.untitled') }}").text,
    '<template v-if="row.document?.title">{{ row.document?.title }}</template><I18nText v-else k="a.untitled" />'
  )
  assertFixture(
    'fallback or',
    transformTextMustaches('{{ title || t(\'a.untitled\') }}').text,
    '<template v-if="title">{{ title }}</template><I18nText v-else k="a.untitled" />'
  )
  assertFixture(
    'fallback key',
    transformTextMustaches('{{ t(`errors.${errorMessage}`, t(\'errors.generic\')) }}').text,
    '<I18nText :k="`errors.${errorMessage}`" fallback-key="errors.generic" />'
  )
  assertFixture(
    'fallback string',
    transformTextMustaches('{{ t(\'canvas.toolbar.save\', \'保存\') }}').text,
    '<I18nText k="canvas.toolbar.save" />'
  )
  const column = transformLabelProps('<el-table-column prop="a" :label="t(\'admin.name\')" />').text
  if (!column.includes('#header') || !column.includes('k="admin.name"') || column.includes(':label=')) {
    throw new Error(`column rewrite failed: ${column}`)
  }
  const injected = injectLabelKeys("{ label: t('admin.today'), value: 'today' }").text
  if (injected !== "{ label: t('admin.today'), labelKey: 'admin.today', value: 'today' }") {
    throw new Error(`inject failed: ${injected}`)
  }
}

function transformVue(source, filename) {
  const parsed = parse(source, { filename })
  if (parsed.errors.length) return { text: source, changed: 0 }
  const ranges = []
  let changed = 0
  const template = parsed.descriptor.template
  if (template) {
    const mustaches = transformTextMustaches(template.content)
    const labels = transformLabelProps(mustaches.text)
    const repaired = repairOptions(labels.text)
    if (mustaches.changed || labels.changed || repaired.changed) {
      ranges.push({
        start: template.loc.start.offset,
        end: template.loc.end.offset,
        text: repaired.text,
      })
      changed += mustaches.changed + labels.changed + repaired.changed
    }
  }
  for (const block of [parsed.descriptor.script, parsed.descriptor.scriptSetup]) {
    if (!block) continue
    const injected = injectLabelKeys(block.content)
    if (injected.changed) {
      ranges.push({
        start: block.loc.start.offset,
        end: block.loc.end.offset,
        text: injected.text,
      })
      changed += injected.changed
    }
  }
  if (!ranges.length) return { text: source, changed: 0 }
  ranges.sort((a, b) => b.start - a.start)
  let text = source
  for (const range of ranges) {
    text = text.slice(0, range.start) + range.text + text.slice(range.end)
  }
  return { text, changed }
}

function transformTs(source) {
  return injectLabelKeys(source)
}

selfTest()

let filesChanged = 0
let edits = 0
for (const file of walk(ROOT)) {
  const source = readFileSync(file, 'utf8')
  const result = file.endsWith('.vue')
    ? transformVue(source, file)
    : transformTs(source)
  if (!result.changed || result.text === source) continue
  filesChanged += 1
  edits += result.changed
  if (!CHECK) writeFileSync(file, result.text)
}

if (CHECK && filesChanged) {
  console.error(`bilingual template check failed: ${edits} sites in ${filesChanged} files`)
  process.exit(1)
}
console.log(`${CHECK ? 'ok' : 'updated'} ${edits} sites in ${filesChanged} files`)
