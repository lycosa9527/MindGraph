import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

/**
 * Load an IIFE doc-extract module into globalThis for unit tests.
 * @param {string} relPath
 */
function loadModule(relPath) {
  const abs = path.resolve(repoRoot, "chrome-extension", relPath);
  const code = fs.readFileSync(abs, "utf8");
  const fn = new Function(
    "globalThis",
    "self",
    `${code}\nreturn globalThis.MindGraphDocExtract;`,
  );
  return fn(globalThis, globalThis);
}

describe("doc-extract hosts", () => {
  it("matches docin host", () => {
    loadModule("doc-extract/hosts.js");
    const entry = globalThis.MindGraphDocExtract.matchHost("https://www.docin.com/p-123.html");
    expect(entry.id).toBe("docin");
    expect(entry.engine).toBe("canvas-pdf");
  });

  it("matches wenku host separately from smartedu", () => {
    loadModule("doc-extract/hosts.js");
    const wenku = globalThis.MindGraphDocExtract.matchHost("https://wenku.baidu.com/view/abc123.html");
    expect(wenku.id).toBe("wenku");
    expect(wenku.label).toBe("百度文库");
    expect(wenku.engine).toBe("canvas-pdf");
  });

  it("matches smartedu host", () => {
    loadModule("doc-extract/hosts.js");
    const entry = globalThis.MindGraphDocExtract.matchHost(
      "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=abc",
    );
    expect(entry.id).toBe("smartedu");
  });
});

describe("extract user messages", () => {
  it("maps CANVAS_EMPTY to errExtractNoPages", () => {
    loadModule("doc-extract/user-messages.js");
    expect(globalThis.MindGraphDocExtract.resolveExtractErrorKey("CANVAS_EMPTY", { id: "docin" })).toBe(
      "errExtractNoPages",
    );
  });

  it("maps SmartEdu metadata failure to login hint", () => {
    loadModule("doc-extract/user-messages.js");
    expect(
      globalThis.MindGraphDocExtract.resolveExtractErrorKey("SmartEdu metadata HTTP 403", {
        id: "smartedu",
      }),
    ).toBe("errExtractSmartEduLogin");
  });
});

describe("wenku preview notice", () => {
  it("flags 8-page wenku preview with VIP hints", () => {
    loadModule("doc-extract/wenku/preview-notice.js");
    const notice = globalThis.MindGraphDocExtract.evaluateWenkuPreviewNotice(
      8,
      "wenku.baidu.com",
      "开通文库VIP 剩余3页",
    );
    expect(notice).not.toBeNull();
    expect(notice.key).toBe("statusWenkuPreviewLimited");
    expect(notice.pageCount).toBe("8");
  });

  it("does not flag wenku when many pages and no paywall", () => {
    loadModule("doc-extract/wenku/preview-notice.js");
    const notice = globalThis.MindGraphDocExtract.evaluateWenkuPreviewNotice(
      20,
      "wenku.baidu.com",
      "full document",
    );
    expect(notice).toBeNull();
  });
});

describe("smartedu url-parser", () => {
  it("parses classActivity activityId", () => {
    loadModule("doc-extract/smartedu/url-parser.js");
    const parsed = globalThis.MindGraphDocExtract.parseSmartEduUrl(
      "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=b45c766e-e428-3d16-c04c-022cf976fc7e",
    );
    expect(parsed).not.toBeNull();
    expect(parsed.activityId).toBe("b45c766e-e428-3d16-c04c-022cf976fc7e");
    expect(parsed.detailUrl).toContain("b45c766e-e428-3d16-c04c-022cf976fc7e");
  });
});

describe("smartedu metadata fixture", () => {
  it("extracts document assets from shared fixture", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets.length).toBeGreaterThanOrEqual(3);
    expect(assets.some((a) => a.alias === "micro_lesson_video")).toBe(false);
    expect(assets.some((a) => a.localKind === "m3u8")).toBe(false);
    const cw = assets.find((a) => a.alias === "coursewares");
    expect(cw.format).toBe("pdf");
  });
});

describe("shared-mindgraph helpers", () => {
  it("normalizes base URL", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", `${code}\nreturn globalThis.MindGraphShared;`);
    const shared = fn(globalThis, globalThis);
    expect(shared.normalizeBaseUrl("https://example.com/")).toBe("https://example.com");
  });

  it("detects Edge client header from user agent", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", "navigator", `${code}\nreturn globalThis.MindGraphShared;`);
    const edgeNav = { userAgent: "Mozilla/5.0 Edg/120.0.0.0" };
    const sharedEdge = fn(globalThis, globalThis, edgeNav);
    expect(sharedEdge.mgClientHeader()).toBe("edge-extension");
    const chromeNav = { userAgent: "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36" };
    const sharedChrome = fn(globalThis, globalThis, chromeNav);
    expect(sharedChrome.mgClientHeader()).toBe("chrome-extension");
  });

  it("recognizes duplicate offscreen errors", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", `${code}\nreturn globalThis.MindGraphShared;`);
    const shared = fn(globalThis, globalThis);
    expect(shared.isOffscreenDuplicateError(new Error("Only a single offscreen document may be created"))).toBe(true);
    expect(shared.isOffscreenDuplicateError(new Error("network failed"))).toBe(false);
  });

  it("prefers offscreen blob URLs on Edge", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", "navigator", `${code}\nreturn globalThis.MindGraphShared;`);
    const edgeNav = { userAgent: "Mozilla/5.0 Edg/120.0.0.0" };
    const sharedEdge = fn(globalThis, globalThis, edgeNav);
    expect(sharedEdge.preferOffscreenBlobUrls()).toBe(true);
    const chromeNav = { userAgent: "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36" };
    const sharedChrome = fn(globalThis, globalThis, chromeNav);
    expect(sharedChrome.preferOffscreenBlobUrls()).toBe(false);
  });
});

describe("smartedu token parse", () => {
  it("parses nested ND_UC_AUTH value (tchMaterial-parser shape)", () => {
    loadModule("doc-extract/smartedu/token.js");
    const inner = JSON.stringify({ access_token: "mg-test-token-abc" });
    const outer = JSON.stringify({ value: inner, expires: 9999999999 });
    expect(globalThis.MindGraphDocExtract.parseSmartEduAuthStorageValue(outer)).toBe(
      "mg-test-token-abc",
    );
  });

  it("parses flat access_token object", () => {
    loadModule("doc-extract/smartedu/token.js");
    const raw = JSON.stringify({ access_token: "flat-token" });
    expect(globalThis.MindGraphDocExtract.parseSmartEduAuthStorageValue(raw)).toBe("flat-token");
  });
});
