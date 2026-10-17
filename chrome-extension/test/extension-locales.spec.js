/**
 * Extension interface locales — same 44 codes as the web language picker.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const extensionRoot = path.resolve(__dirname, "..");

const PICKER_CODES = [
  "zh-tw",
  "zh",
  "en",
  "es",
  "az",
  "th",
  "fr",
  "de",
  "sq",
  "ja",
  "ko",
  "pt",
  "ru",
  "ar",
  "fa",
  "uz",
  "nl",
  "it",
  "hi",
  "si",
  "ta",
  "te",
  "kn",
  "ml",
  "id",
  "tl",
  "vi",
  "tr",
  "pl",
  "uk",
  "ms",
  "af",
  "no",
  "sv",
  "da",
  "fi",
  "cs",
  "sk",
  "ro",
  "hu",
  "el",
  "bg",
  "hr",
  "sr",
];

/**
 * @param {string} relPath
 * @param {string} exportName
 */
function loadModule(relPath, exportName) {
  const abs = path.resolve(extensionRoot, relPath);
  const code = fs.readFileSync(abs, "utf8");
  const fn = new Function("globalThis", "self", `${code}\nreturn globalThis.${exportName};`);
  return fn(globalThis, globalThis);
}

describe("extension interface locales", () => {
  const locales = loadModule("extension-locales.js", "MindGraphExtensionLocales");

  it("lists the same 44 picker languages in the same order", () => {
    expect(locales.LOCALES.map((entry) => entry.code)).toEqual(PICKER_CODES);
    expect(new Set(locales.LOCALES.map((entry) => entry.nativeName)).size).toBe(44);
  });

  it("keeps Chrome-unsupported catalogs outside _locales", () => {
    const outside = locales.LOCALES.filter((entry) => entry.chrome == null).map((entry) => entry.code);
    expect(outside).toEqual(["az", "sq", "uz", "si", "af"]);
    outside.forEach((code) => {
      expect(locales.entryFor(code).messages.startsWith("i18n/")).toBe(true);
    });
    expect(locales.entryFor("tl").messages).toBe("_locales/fil/messages.json");
    expect(locales.entryFor("pt").messages).toBe("_locales/pt_BR/messages.json");
  });

  it("normalizes legacy storage values and browser tags", () => {
    expect(locales.normalizeUiLanguage(undefined)).toBe("auto");
    expect(locales.normalizeUiLanguage("zh_CN")).toBe("zh");
    expect(locales.normalizeUiLanguage("zh_TW")).toBe("zh-tw");
    expect(locales.normalizeUiLanguage("fr")).toBe("fr");
    expect(locales.normalizeUiLanguage("not-a-locale")).toBe("auto");
    expect(locales.matchUiLanguage("zh-HK")).toBe("zh-tw");
    expect(locales.matchUiLanguage("zh-CN")).toBe("zh");
    expect(locales.matchUiLanguage("pt-PT")).toBe("pt");
    expect(locales.matchUiLanguage("fil")).toBe("tl");
    expect(locales.matchUiLanguage("nb-NO")).toBe("no");
    expect(locales.matchUiLanguage("en-GB")).toBe("en");
    expect(locales.matchUiLanguage("ca")).toBeNull();
    expect(locales.matchUiLanguage("he")).toBeNull();
    expect(locales.entryFor("ar").rtl).toBe(true);
    expect(locales.entryFor("fa").rtl).toBe(true);
    expect(locales.entryFor("en").rtl).toBe(false);
  });

  it("maps picker codes onto prompt output languages", () => {
    const shared = loadModule("shared-mindgraph.js", "MindGraphShared");
    const allowed = ["zh", "zh-hant", "en", "fr", "pt", "tl", "az"];
    expect(shared.resolvePromptLanguageFromUiMode("fr", "en", allowed)).toBe("fr");
    expect(shared.resolvePromptLanguageFromUiMode("zh_TW", "en", allowed)).toBe("zh-hant");
    expect(shared.resolvePromptLanguageFromUiMode("zh_CN", "en", allowed)).toBe("zh");
    expect(shared.resolvePromptLanguageFromUiMode("tl", "en", allowed)).toBe("tl");
    expect(shared.resolvePromptLanguageFromUiMode("auto", "pt-BR", allowed)).toBe("pt");
    expect(shared.resolvePromptLanguageFromUiMode("auto", "zh-HK", allowed)).toBe("zh-hant");
    expect(shared.resolvePromptLanguageFromUiMode("fr", "ca", allowed)).toBe("fr");
    expect(shared.resolvePromptLanguageFromUiMode("auto", "ca", ["zh", "zh-hant", "en", "ca"])).toBe("ca");
    expect(shared.resolvePromptLanguageFromUiMode("auto", "he", ["zh", "zh-hant", "en", "he"])).toBe("he");
    expect(shared.resolvePromptLanguageFromUiMode("auto", "xx", allowed)).toBe("en");
  });

  it("substitutes chrome message placeholders", () => {
    expect(locales.applySubstitutions("Hello $1", ["Ada"])).toBe("Hello Ada");
    expect(locales.applySubstitutions("A $1 B $2", ["1", "2"])).toBe("A 1 B 2");
  });

  it("ships a message catalog for every picker language", () => {
    const en = JSON.parse(fs.readFileSync(path.join(extensionRoot, "_locales/en/messages.json"), "utf8"));
    const zh = JSON.parse(fs.readFileSync(path.join(extensionRoot, "_locales/zh_CN/messages.json"), "utf8"));
    const enKeys = Object.keys(en);
    locales.LOCALES.forEach((entry) => {
      const filePath = path.join(extensionRoot, entry.messages);
      const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
      expect(Object.keys(data), entry.code).toEqual(enKeys);
      enKeys.forEach((key) => {
        const message = data[key].message;
        expect(typeof message, `${entry.code}:${key}`).toBe("string");
        expect(message.trim().length, `${entry.code}:${key}`).toBeGreaterThan(0);
        expect(message, `${entry.code}:${key}`).not.toMatch(/__M?G\d+__/);
        expect(message, `${entry.code}:${key}`).not.toContain("__МГ");
        const source = zh[key].message;
        const sourceSlots = source.match(/\$\d+/g) || [];
        const messageSlots = message.match(/\$\d+/g) || [];
        expect(messageSlots, `${entry.code}:${key}`).toEqual(sourceSlots);
        for (const brand of ["MindGraph", "MindMate"]) {
          if (source.includes(brand)) {
            expect(message, `${entry.code}:${key}`).toContain(brand);
          }
        }
        if (source.includes("chrome://extensions")) {
          expect(message, `${entry.code}:${key}`).toContain("chrome://extensions");
        }
      });
    });
    const ptPt = path.join(extensionRoot, "_locales/pt_PT/messages.json");
    expect(fs.existsSync(ptPt)).toBe(true);
  });
});
