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

  it("matches cnki flowpdf reader", () => {
    loadModule("doc-extract/hosts.js");
    const entry = globalThis.MindGraphDocExtract.matchHost(
      "https://kns.cnki.net/reader/flowpdf?filename=ZLCY2026061500V&tablename=capjlast",
    );
    expect(entry.id).toBe("cnki");
    expect(entry.label).toBe("中国知网");
  });
});

describe("cnki url parser", () => {
  it("classifies flowpdf reader URLs", () => {
    loadModule("doc-extract/cnki/url-parser.js");
    const parsed = globalThis.MindGraphDocExtract.parseCnkiPageUrl(
      "https://kns.cnki.net/reader/flowpdf?filename=ZLCY2026061500V&tablename=capjlast&product=CAPJ",
    );
    expect(parsed).not.toBeNull();
    expect(parsed.kind).toBe("flowpdf");
    expect(parsed.filename).toBe("ZLCY2026061500V");
    expect(parsed.tablename).toBe("capjlast");
  });

  it("classifies kcms detail URLs", () => {
    loadModule("doc-extract/cnki/url-parser.js");
    const parsed = globalThis.MindGraphDocExtract.parseCnkiPageUrl(
      "https://kns.cnki.net/kcms2/article/abstract?v=abc",
    );
    expect(parsed).not.toBeNull();
    expect(parsed.kind).toBe("detail");
  });

  it("builds flowpdf download candidates without invoice param", () => {
    loadModule("doc-extract/cnki/url-parser.js");
    const urls = globalThis.MindGraphDocExtract.buildCnkiReaderDownloadCandidates(
      "https://kns.cnki.net/reader/flowpdf?filename=ZLCY2026061500V&tablename=capjlast&product=CAPJ",
    );
    expect(urls.length).toBeGreaterThanOrEqual(2);
    expect(urls.some((url) => url.includes("/reader/api/download?"))).toBe(true);
    expect(urls.some((url) => url.includes("filename=ZLCY2026061500V"))).toBe(true);
    expect(urls.some((url) => url.includes("tablename=capjlast"))).toBe(true);
  });

  it("builds invoice-only flowpdf download candidates", () => {
    loadModule("doc-extract/cnki/url-parser.js");
    const urls = globalThis.MindGraphDocExtract.buildCnkiReaderDownloadCandidates(
      "https://kns.cnki.net/reader/flowpdf?invoice=abc123&platform=NZKPT",
    );
    expect(urls.length).toBeGreaterThanOrEqual(2);
    expect(urls.some((url) => url.includes("/reader/api/download?invoice=abc123"))).toBe(true);
    expect(urls.some((url) => url.includes("/reader/download/pdf?invoice=abc123"))).toBe(true);
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

  it("mgatFetchInit always omits site session cookies", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", `${code}\nreturn globalThis.MindGraphShared;`);
    const shared = fn(globalThis, globalThis);
    expect(shared.mgatFetchInit({ method: "POST" })).toEqual({ method: "POST", credentials: "omit" });
    expect(shared.mgatFetchInit({ credentials: "include" }).credentials).toBe("omit");
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

describe("extract to markdown", () => {
  it("formats document title, url, and body", () => {
    loadModule("doc-extract/hosts.js");
    loadModule("doc-extract/extract-to-markdown.js");
    const md = globalThis.MindGraphDocExtract.formatDocumentMarkdown(
      "Sample Paper",
      "Abstract line one.\n\nSection two.",
      "https://kns.cnki.net/reader/flowpdf?filename=abc",
      8000,
    );
    expect(md).toContain("# Sample Paper");
    expect(md).toContain("https://kns.cnki.net/reader/flowpdf?filename=abc");
    expect(md).toContain("Abstract line one.");
    expect(md).toContain("Section two.");
  });

  it("truncates long bodies to max chars", () => {
    loadModule("doc-extract/hosts.js");
    loadModule("doc-extract/extract-to-markdown.js");
    const body = "x".repeat(500);
    const md = globalThis.MindGraphDocExtract.formatDocumentMarkdown("T", body, "https://a.test", 120);
    expect(md.length).toBeLessThanOrEqual(120);
    expect(md.endsWith("…")).toBe(true);
  });
});

describe("smartedu markdown extract", () => {
  it("keeps only PDF document assets from lesson metadata", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    loadModule("doc-extract/smartedu/markdown-extract.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    const pdfs = globalThis.MindGraphDocExtract.filterSmartEduPdfAssets(assets);
    expect(pdfs.length).toBe(3);
    expect(pdfs.map((asset) => asset.alias).sort()).toEqual(
      ["coursewares", "learning_task", "lesson_plandesign"].sort(),
    );
  });

  it("combines lesson sections into markdown", () => {
    loadModule("doc-extract/smartedu/markdown-extract.js");
    const md = globalThis.MindGraphDocExtract.combineSmartEduLessonMarkdown(
      "11.拆装玩具",
      "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=abc",
      [
        { title: "课件", text: "Slide one content." },
        { title: "教学设计", text: "Teaching plan body." },
        { title: "学习任务单", text: "Worksheet tasks." },
      ],
      8000,
    );
    expect(md).toContain("# 11.拆装玩具");
    expect(md).toContain("## 课件");
    expect(md).toContain("## 教学设计");
    expect(md).toContain("## 学习任务单");
    expect(md).toContain("Slide one content.");
  });
});

describe("blob to text", () => {
  it("detects PDF magic bytes", () => {
    loadModule("doc-extract/extract-to-markdown.js");
    loadModule("doc-extract/text/blob-to-text.js");
    const pdfHeader = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]);
    expect(globalThis.MindGraphDocExtract.isPdfBytes(pdfHeader.buffer)).toBe(true);
    expect(globalThis.MindGraphDocExtract.isPdfBytes(new Uint8Array([1, 2, 3, 4]).buffer)).toBe(false);
  });

  it("strips HTML to plain text", () => {
    loadModule("doc-extract/text/blob-to-text.js");
    const text = globalThis.MindGraphDocExtract.stripHtmlToPlainText(
      "<p>Hello <strong>world</strong></p>",
    );
    expect(text).toContain("Hello");
    expect(text).toContain("world");
  });

  it("caps wenku pdf pages at preview limit", () => {
    loadModule("doc-extract/wenku/preview-notice.js");
    loadModule("doc-extract/text/markdown-capture-policy.js");
    const limits = globalThis.MindGraphDocExtract.markdownLimitsForHost({ id: "wenku", engine: "canvas-pdf" });
    expect(limits.pdfMaxPages).toBe(8);
    expect(limits.previewNotice).toBe("mindmateNoticeWenkuPreview");
  });

  it("marks smartedu wenku cnki as file-first MindMate hosts", () => {
    loadModule("doc-extract/text/markdown-capture-policy.js");
    expect(globalThis.MindGraphDocExtract.hostRequiresFileExtract({ id: "smartedu" })).toBe(true);
    expect(globalThis.MindGraphDocExtract.hostRequiresFileExtract({ id: "wenku" })).toBe(true);
    expect(globalThis.MindGraphDocExtract.hostRequiresFileExtract({ id: "cnki" })).toBe(true);
    expect(globalThis.MindGraphDocExtract.hostRequiresFileExtract({ id: "zhihu" })).toBe(false);
  });

  it("exports arrayBufferToBase64 for PDF offscreen fallback", () => {
    const abs = path.resolve(repoRoot, "chrome-extension", "offscreen-blobs.js");
    const code = fs.readFileSync(abs, "utf8");
    const fn = new Function("globalThis", "self", code);
    fn(globalThis, globalThis);
    const pdfHeader = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]);
    const base64 = globalThis.MindGraphOffscreenBlobs.arrayBufferToBase64(pdfHeader.buffer);
    expect(base64).toBe("JVBERi0=");
  });
});

describe("browser pdf tab", () => {
  it("detects https and file PDF tab URLs", () => {
    const sharedPath = path.resolve(repoRoot, "chrome-extension/shared-mindgraph.js");
    const code = fs.readFileSync(sharedPath, "utf8");
    const fn = new Function("globalThis", "self", `${code}\nreturn globalThis.MindGraphShared;`);
    const shared = fn(globalThis, globalThis);
    expect(shared.isBrowserPdfTabUrl("https://example.com/docs/report.pdf")).toBe(true);
    expect(shared.isBrowserPdfTabUrl("file:///C:/Users/me/paper.pdf")).toBe(true);
    expect(shared.isBrowserPdfTabUrl("https://example.com/article")).toBe(false);
    expect(shared.isRestrictedTabUrl("file:///C:/local/doc.pdf")).toBe(false);
  });
});
