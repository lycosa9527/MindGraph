/**
 * Node smoke tests for shared-mindgraph.js (load via vm in extension global shape).
 */
"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scriptPath = path.join(__dirname, "..", "shared-mindgraph.js");
const code = fs.readFileSync(scriptPath, "utf8");
const ctx = { console, self: {}, URL };
vm.createContext(ctx);
vm.runInContext(code, ctx);
const { MindGraphShared } = ctx.self;
assert(MindGraphShared, "MindGraphShared should be defined");

assert.strictEqual(
  MindGraphShared.DEFAULT_MINDGRAPH_BASE_URL,
  "https://mg.mindspringedu.com",
);
assert.strictEqual(MindGraphShared.MINDMAP_GENERATE_PORT, "mindmap-generate");
assert.strictEqual(MindGraphShared.normalizeBaseUrl("https://a.com/"), "https://a.com");
assert.strictEqual(MindGraphShared.sanitizeFilename("x<y>"), "x_y_.png");
assert.strictEqual(MindGraphShared.isRestrictedTabUrl("file:///a"), true);
assert.strictEqual(MindGraphShared.isRestrictedTabUrl("https://a.com/"), false);

const pl = { page_content: "hi", content_format: "text/plain", page_title: "t", page_url: "u", language: "en" };
const b1 = MindGraphShared.buildPngRequestBody(pl, {});
assert.strictEqual(b1.width, undefined);
const b2 = MindGraphShared.buildPngRequestBody(pl, { pngWidth: 800, pngHeight: 600 });
assert.strictEqual(b2.width, 800);
assert.strictEqual(b2.height, 600);

const codes = ["en", "zh", "zh-hant", "de", "fr"];
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("en", "zh-CN", codes), "en");
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("zh_CN", "en", codes), "zh");
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("zh_TW", "en", codes), "zh-hant");
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("auto", "en-US", codes), "en");
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("auto", "zh-TW", codes), "zh-hant");
assert.strictEqual(MindGraphShared.resolvePromptLanguageFromUiMode("auto", "de-DE", codes), "de");

console.log("shared-mindgraph tests ok");
