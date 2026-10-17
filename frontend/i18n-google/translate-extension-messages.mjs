/**
 * Translate chrome-extension messages from zh-CN into the interface-language picker locales.
 * Run on the Windows host (VPN). WSL cannot reach Google.
 *
 *   powershell -NoProfile -ExecutionPolicy Bypass -File i18n-google/translate-extension-on-host.ps1
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ProxyAgent, setGlobalDispatcher } from "undici";
import translate from "google-translate-api-x";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../..");
const extensionRoot = path.join(repoRoot, "chrome-extension");
const enPath = path.join(extensionRoot, "_locales/en/messages.json");
const zhPath = path.join(extensionRoot, "_locales/zh_CN/messages.json");

/** Picker codes that still need a catalog. en / zh already ship (no zh-tw in extension). */
const TARGETS = [
  ["es", "es", "_locales/es/messages.json"],
  ["az", "az", "i18n/az/messages.json"],
  ["th", "th", "_locales/th/messages.json"],
  ["fr", "fr", "_locales/fr/messages.json"],
  ["de", "de", "_locales/de/messages.json"],
  ["sq", "sq", "i18n/sq/messages.json"],
  ["ja", "ja", "_locales/ja/messages.json"],
  ["ko", "ko", "_locales/ko/messages.json"],
  ["pt", "pt", "_locales/pt_BR/messages.json"],
  ["ru", "ru", "_locales/ru/messages.json"],
  ["ar", "ar", "_locales/ar/messages.json"],
  ["fa", "fa", "_locales/fa/messages.json"],
  ["uz", "uz", "i18n/uz/messages.json"],
  ["nl", "nl", "_locales/nl/messages.json"],
  ["it", "it", "_locales/it/messages.json"],
  ["hi", "hi", "_locales/hi/messages.json"],
  ["si", "si", "i18n/si/messages.json"],
  ["ta", "ta", "_locales/ta/messages.json"],
  ["te", "te", "_locales/te/messages.json"],
  ["kn", "kn", "_locales/kn/messages.json"],
  ["ml", "ml", "_locales/ml/messages.json"],
  ["id", "id", "_locales/id/messages.json"],
  ["tl", "tl", "_locales/fil/messages.json"],
  ["vi", "vi", "_locales/vi/messages.json"],
  ["tr", "tr", "_locales/tr/messages.json"],
  ["pl", "pl", "_locales/pl/messages.json"],
  ["uk", "uk", "_locales/uk/messages.json"],
  ["ms", "ms", "_locales/ms/messages.json"],
  ["af", "af", "i18n/af/messages.json"],
  ["no", "no", "_locales/no/messages.json"],
  ["sv", "sv", "_locales/sv/messages.json"],
  ["da", "da", "_locales/da/messages.json"],
  ["fi", "fi", "_locales/fi/messages.json"],
  ["cs", "cs", "_locales/cs/messages.json"],
  ["sk", "sk", "_locales/sk/messages.json"],
  ["ro", "ro", "_locales/ro/messages.json"],
  ["hu", "hu", "_locales/hu/messages.json"],
  ["el", "el", "_locales/el/messages.json"],
  ["bg", "bg", "_locales/bg/messages.json"],
  ["hr", "hr", "_locales/hr/messages.json"],
  ["sr", "sr", "_locales/sr/messages.json"],
];

const PROTECT_RE = /\$\d+|MindGraph|MindMate/g;

/**
 * "设置" alone is ambiguous (set up vs Settings). These are UI nouns, same role as the
 * web app's Settings tab.
 */
const SETTINGS_LABEL = {
  es: "Configuración",
  az: "Parametrlər",
  th: "การตั้งค่า",
  fr: "Paramètres",
  de: "Einstellungen",
  sq: "Cilësimet",
  ja: "設定",
  ko: "설정",
  pt: "Configurações",
  ru: "Настройки",
  ar: "الإعدادات",
  fa: "تنظیمات",
  uz: "Sozlamalar",
  nl: "Instellingen",
  it: "Impostazioni",
  hi: "सेटिंग्स",
  si: "සැකසුම්",
  ta: "அமைப்புகள்",
  te: "సెట్టింగ్‌లు",
  kn: "ಸೆಟ್ಟಿಂಗ್‌ಗಳು",
  ml: "ക്രമീകരണങ്ങൾ",
  id: "Pengaturan",
  tl: "Mga Setting",
  vi: "Cài đặt",
  tr: "Ayarlar",
  pl: "Ustawienia",
  uk: "Налаштування",
  ms: "Tetapan",
  af: "Instellings",
  no: "Innstillinger",
  sv: "Inställningar",
  da: "Indstillinger",
  fi: "Asetukset",
  cs: "Nastavení",
  sk: "Nastavenia",
  ro: "Setări",
  hu: "Beállítások",
  el: "Ρυθμίσεις",
  bg: "Настройки",
  hr: "Postavke",
  sr: "Подешавања",
};
const CHUNK_SIZE = 12;
const BATCH_TIMEOUT_MS = 40_000;

function normalizeProxyUrl(raw) {
  const text = raw.trim();
  if (!text) return text;
  if (/^https?:\/\//i.test(text)) return text;
  return `http://${text}`;
}

function readWindowsSystemProxyUrl() {
  if (process.platform !== "win32") return null;
  try {
    const enableOut = execSync(
      'reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable',
      { encoding: "utf8" },
    );
    if (!/\b0x1\b/.test(enableOut)) return null;
    const serverOut = execSync(
      'reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer',
      { encoding: "utf8" },
    );
    const line = serverOut.split(/\r?\n/).find((row) => row.includes("ProxyServer"));
    if (!line) return null;
    const match = line.match(/ProxyServer\s+REG_SZ\s+(\S.*)$/);
    if (!match) return null;
    return normalizeProxyUrl(match[1].trim());
  } catch {
    return null;
  }
}

function setupProxy() {
  const fromCli = process.argv.find((arg) => arg.startsWith("--proxy="));
  const fromEnv = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.ALL_PROXY;
  const url = (fromCli ? fromCli.slice("--proxy=".length) : "") || fromEnv || readWindowsSystemProxyUrl() || "";
  if (!url) {
    console.log("[proxy] none (direct). Pass --proxy=http://127.0.0.1:PORT if Google is blocked.");
    return;
  }
  setGlobalDispatcher(new ProxyAgent(normalizeProxyUrl(url)));
  console.log("[proxy]", normalizeProxyUrl(url));
}

function hasCjk(value) {
  return /\p{Script=Han}/u.test(value);
}

function protect(value) {
  const tokens = [];
  let index = 0;
  const text = value.replace(PROTECT_RE, (token) => {
    tokens.push(token);
    const marker = `__MG${index}__`;
    index += 1;
    return marker;
  });
  return { text, tokens };
}

function restore(value, tokens) {
  let out = value;
  for (let i = 0; i < tokens.length; i += 1) {
    const latin = [
      `__MG${i}__`,
      `__ MG${i} __`,
      `__MG${i} __`,
      `__ MG${i}__`,
    ];
    // Serbian (and other Cyrillic targets) transliterate the Latin token letters.
    const cyrillic = latin.map((form) => form.replaceAll("M", "М").replaceAll("G", "Г"));
    [...latin, ...cyrillic].forEach((form) => {
      if (out.includes(form)) {
        out = out.split(form).join(tokens[i]);
      }
    });
  }
  return out;
}

function placeholders(value) {
  return value.match(/\$\d+/g) || [];
}

function samePlaceholders(source, translated) {
  const left = placeholders(source);
  const right = placeholders(translated);
  if (left.length !== right.length) return false;
  return left.every((token, index) => token === right[index]);
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function withTimeout(work, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`translate timeout ${ms}ms`));
    }, ms);
    work.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

/**
 * @param {string[]} texts
 * @param {string} to
 * @returns {Promise<string[]>}
 */
async function translateBatch(texts, to) {
  const prepared = texts.map((text) => protect(text));
  const out = [];
  for (let cursor = 0; cursor < prepared.length; cursor += CHUNK_SIZE) {
    const slice = prepared.slice(cursor, cursor + CHUNK_SIZE);
    const inputs = slice.map((item) => item.text);
    const end = cursor + slice.length;
    console.log(`    ${to} ${cursor + 1}-${end}/${prepared.length}`);
    let attempt = 0;
    let done = false;
    let lastErr = null;
    while (attempt < 5 && !done) {
      try {
        const res = await withTimeout(
          translate(inputs, { from: "zh-CN", to, forceTo: true, forceBatch: true }),
          BATCH_TIMEOUT_MS,
        );
        const arr = Array.isArray(res) ? res : [res];
        for (let i = 0; i < slice.length; i += 1) {
          const raw = (arr[i] && arr[i].text) || "";
          out.push(restore(raw, slice[i].tokens));
        }
        done = true;
      } catch (err) {
        lastErr = err;
        attempt += 1;
        console.warn(`    ${to} retry ${attempt}/5 at ${cursor + 1}: ${String(err)}`);
        await sleep(2000 * attempt);
      }
    }
    if (!done) {
      console.error(`batch failed (${to}) at ${cursor}`, lastErr);
      for (let i = 0; i < slice.length; i += 1) {
        out.push("");
      }
    }
    await sleep(400);
  }
  return out;
}

function localeFilter() {
  const arg = process.argv.find((item) => item.startsWith("--locale="));
  if (!arg) return null;
  return new Set(
    arg
      .slice("--locale=".length)
      .split(",")
      .map((code) => code.trim())
      .filter(Boolean),
  );
}

function catalogComplete(filePath, enMessages, zhMessages) {
  if (!fs.existsSync(filePath)) return false;
  let data;
  try {
    data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return false;
  }
  const keys = Object.keys(enMessages);
  for (const key of keys) {
    const row = data[key];
    if (!row || typeof row.message !== "string" || !row.message.trim()) return false;
    const source = zhMessages[key].message;
    if (!samePlaceholders(source, row.message)) return false;
  }
  return true;
}

function writeCatalog(filePath, enMessages, messagesByKey) {
  const out = {};
  Object.keys(enMessages).forEach((key) => {
    out[key] = {
      message: messagesByKey[key],
      description: enMessages[key].description,
    };
  });
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(out, null, 2)}\n`, "utf8");
}

async function translateLocale(code, googleTo, relPath, enMessages, zhMessages) {
  const filePath = path.join(extensionRoot, relPath);
  if (catalogComplete(filePath, enMessages, zhMessages)) {
    console.log(`skip ${code} (complete)`);
    return;
  }
  const keys = Object.keys(enMessages);
  const jobs = [];
  const resolved = {};
  keys.forEach((key) => {
    const source = zhMessages[key].message;
    if (!hasCjk(source)) {
      resolved[key] = source;
      return;
    }
    jobs.push({ key, source });
  });
  console.log(`${code} → ${googleTo}: ${jobs.length} strings`);
  const translated = await translateBatch(
    jobs.map((job) => job.source),
    googleTo,
  );
  let fallbacks = 0;
  jobs.forEach((job, index) => {
    const value = (translated[index] || "").trim();
    if (job.source === "设置" && SETTINGS_LABEL[code]) {
      resolved[job.key] = SETTINGS_LABEL[code];
      return;
    }
    if (!value || !samePlaceholders(job.source, value)) {
      resolved[job.key] = enMessages[job.key].message;
      fallbacks += 1;
      console.warn(`    fallback en: ${code} ${job.key}`);
      return;
    }
    resolved[job.key] = value;
  });
  writeCatalog(filePath, enMessages, resolved);
  console.log(`wrote ${relPath} (${fallbacks} english fallbacks)`);
  if (code === "pt") {
    const ptPt = path.join(extensionRoot, "_locales/pt_PT/messages.json");
    fs.mkdirSync(path.dirname(ptPt), { recursive: true });
    fs.copyFileSync(filePath, ptPt);
    console.log("copied _locales/pt_PT/messages.json");
  }
}

async function translateOne(source, to) {
  const prepared = protect(source);
  let attempt = 0;
  let lastErr = null;
  while (attempt < 5) {
    try {
      const res = await withTimeout(
        translate(prepared.text, { from: "zh-CN", to, forceTo: true, forceBatch: false }),
        BATCH_TIMEOUT_MS,
      );
      const raw = (Array.isArray(res) ? res[0] : res)?.text || "";
      return restore(raw, prepared.tokens).trim();
    } catch (err) {
      lastErr = err;
      attempt += 1;
      console.warn(`    ${to} single retry ${attempt}/5: ${String(err)}`);
      await sleep(2000 * attempt);
    }
  }
  console.error(`single failed (${to})`, lastErr);
  return "";
}

/**
 * Retranslate strings that were copied from English because a batch ate $1 placeholders.
 * @param {string} code
 * @param {string} googleTo
 * @param {string} relPath
 * @param {object} enMessages
 * @param {object} zhMessages
 */
async function repairLocale(code, googleTo, relPath, enMessages, zhMessages) {
  const filePath = path.join(extensionRoot, relPath);
  const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const jobs = [];
  Object.keys(enMessages).forEach((key) => {
    const source = zhMessages[key].message;
    if (source === "设置" && SETTINGS_LABEL[code]) {
      data[key].message = SETTINGS_LABEL[code];
      return;
    }
    if (!hasCjk(source)) return;
    if (data[key].message !== enMessages[key].message) return;
    jobs.push({ key, source });
  });
  console.log(`${code} repair ${jobs.length} english copies`);
  for (const job of jobs) {
    const value = await translateOne(job.source, googleTo);
    if (!value || !samePlaceholders(job.source, value)) {
      console.warn(`    still en: ${code} ${job.key}`);
      console.warn(`      got: ${JSON.stringify(value)}`);
      continue;
    }
    data[job.key].message = value;
    console.log(`    fixed ${job.key}`);
    await sleep(350);
  }
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  if (code === "pt") {
    const ptPt = path.join(extensionRoot, "_locales/pt_PT/messages.json");
    fs.copyFileSync(filePath, ptPt);
  }
}

async function main() {
  setupProxy();
  const enMessages = JSON.parse(fs.readFileSync(enPath, "utf8"));
  const zhMessages = JSON.parse(fs.readFileSync(zhPath, "utf8"));
  const enKeys = Object.keys(enMessages);
  const zhKeys = Object.keys(zhMessages);
  if (enKeys.length !== zhKeys.length || enKeys.some((key) => !zhMessages[key])) {
    throw new Error("en and zh_CN message keys differ");
  }
  const only = localeFilter();
  const repair = process.argv.includes("--repair");
  for (const [code, googleTo, relPath] of TARGETS) {
    if (only && !only.has(code)) continue;
    if (repair) {
      await repairLocale(code, googleTo, relPath, enMessages, zhMessages);
    } else {
      await translateLocale(code, googleTo, relPath, enMessages, zhMessages);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
