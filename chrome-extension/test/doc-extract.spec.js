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

  it("dedupes assets when duplicate relation keys repeat the same blocks", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    detailJson.relations["lesson_1.national_course_resource"] =
      detailJson.relations.national_course_resource;
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets.length).toBe(3);
    expect(new Set(assets.map((asset) => asset.id)).size).toBe(3);
  });

  it("keeps a single class hour labeled by file type", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets.map((asset) => asset.title).sort()).toEqual(["学习任务单", "课件", "教学设计"].sort());
  });

  it("prefixes the class hour when two periods reuse the same file names", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const first = detailJson.relations.national_course_resource;
    const second = first.map((block) => {
      const copy = JSON.parse(JSON.stringify(block));
      const nextId = `${block.id}-p2`;
      copy.id = nextId;
      copy.version_id = nextId;
      copy.global_title = { "zh-CN": "11.拆装玩具（第2课时）" };
      copy.custom_properties.global_resource_id = nextId;
      const rewrite = (value) => (typeof value === "string" ? value.replaceAll(block.id, nextId) : value);
      copy.ti_items = (copy.ti_items || []).map((item) => ({
        ...item,
        ti_storage: rewrite(item.ti_storage),
        ti_storages: (item.ti_storages || []).map(rewrite),
      }));
      return copy;
    });
    detailJson.relations.national_course_resource = first.concat(second);
    detailJson.resource_structure = {
      relations: [
        {
          id: "lesson_1",
          title: "第一课时",
          res_ref: ["$.relations.national_course_resource[0,1,2,3]"],
        },
        {
          id: "lesson_2",
          title: "第二课时",
          res_ref: ["$.relations.national_course_resource[4,5,6,7]"],
        },
      ],
    };
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets.map((asset) => asset.title)).toEqual([
      "第一课时 · 课件",
      "第一课时 · 教学设计",
      "第一课时 · 学习任务单",
      "第二课时 · 课件",
      "第二课时 · 教学设计",
      "第二课时 · 学习任务单",
    ]);
  });

  it("drops a second block that points at the same download path", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const blocks = detailJson.relations.national_course_resource;
    const courseware = blocks.find((block) => block.resource_type_code === "coursewares");
    const copy = JSON.parse(JSON.stringify(courseware));
    copy.id = "copy-id";
    copy.version_id = "copy-id";
    copy.custom_properties.global_resource_id = "copy-gid";
    detailJson.relations.national_course_resource = blocks.concat([copy]);
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets.filter((asset) => asset.alias === "coursewares")).toHaveLength(1);
  });
});

describe("extension tab job lock", () => {
  it("rejects overlapping jobs on the same tab", async () => {
    const jobsPath = path.resolve(repoRoot, "chrome-extension/extension-jobs.js");
    const code = fs.readFileSync(jobsPath, "utf8");
    const fn = new Function("globalThis", `${code}\nreturn globalThis.MindGraphExtensionJobs;`);
    const jobs = fn(globalThis);
    jobs.resetTabLocksForTests();
    let releaseFirst = () => {};
    const firstGate = new Promise((resolve) => {
      releaseFirst = resolve;
    });
    const first = jobs.withTabJobLock(12, async () => {
      await firstGate;
      return { ok: true, value: "first" };
    });
    const second = await jobs.withTabJobLock(12, async () => ({
      ok: true,
      value: "second",
    }));
    expect(second).toEqual({ ok: false, error: "errJobAlreadyRunning" });
    releaseFirst();
    await expect(first).resolves.toEqual({ ok: true, value: "first" });
  });
});

describe("page content capture helpers", () => {
  it("maps capture failures to i18n error keys", () => {
    loadModule("doc-extract/page-content-capture.js");
    expect(
      globalThis.MindGraphDocExtract.localizedCaptureErrorKey({ ok: false, error: "errExtractSmartEduLogin" }),
    ).toBe("errExtractSmartEduLogin");
    expect(globalThis.MindGraphDocExtract.localizedCaptureErrorKey({ ok: false })).toBe("errNoPageText");
  });

  it("builds web content payload from markdown capture", () => {
    loadModule("doc-extract/page-content-capture.js");
    const payload = globalThis.MindGraphDocExtract.captureResultToWebContentPayload(
      {
        ok: true,
        title: "Article",
        url: "https://example.com/a",
        markdown: "# Article\n\nBody",
      },
      "zh",
    );
    expect(payload).not.toBeNull();
    expect(payload.content_format).toBe("text/markdown");
    expect(payload.page_content).toContain("Body");
    expect(payload.language).toBe("zh");
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
    const plan = pdfs.find((asset) => asset.alias === "lesson_plandesign");
    expect(plan.pageCount).toBe(3);
  });

  it("orders lesson files so plans are OCR'd before slide decks", () => {
    loadModule("doc-extract/smartedu/markdown-extract.js");
    const ordered = globalThis.MindGraphDocExtract.orderSmartEduAssetsForOcr([
      { alias: "coursewares", title: "课件" },
      { alias: "after_class_exercise", title: "课后练习" },
      { alias: "lesson_plandesign", title: "教学设计" },
      { alias: "learning_task", title: "学习任务单" },
    ]);
    expect(ordered.map((asset) => asset.title)).toEqual([
      "教学设计",
      "学习任务单",
      "课后练习",
      "课件",
    ]);
  });

  it("keeps a text layer and falls back to OCR only when that layer is empty", () => {
    loadModule("doc-extract/smartedu/markdown-extract.js");
    const api = globalThis.MindGraphDocExtract;
    expect(api.chooseSmartEduPdfText("This lesson has enough local text.", "")).toContain("local text");
    expect(api.chooseSmartEduPdfText("", "教学目标：朗读课文，整体感知济南的冬天。")).toContain("教学目标");
    expect(api.chooseSmartEduPdfText("short", "x")).toBe("");
    expect(api.smartEduShouldRequestOcr("This lesson has enough local text.", true)).toBe(false);
    expect(api.smartEduShouldRequestOcr("", true)).toBe(true);
    expect(api.smartEduShouldRequestOcr("", false)).toBe(false);
    expect(api.smartEduOcrPageCap(12)).toBe(4);
    expect(api.smartEduOcrPageCap(12, 2)).toBe(2);
    expect(api.smartEduOcrPageCap(2)).toBe(2);
    expect(api.smartEduOcrPageCap(0)).toBe(0);
  });

  it("posts an image PDF to the account OCR endpoint", async () => {
    loadModule("doc-extract/smartedu/pdf-ocr-client.js");
    const blob = new Blob([new Uint8Array([0x25, 0x50, 0x44, 0x46])], { type: "application/pdf" });
    let posted = null;
    const fetchImpl = async (url, init) => {
      posted = { url, init };
      return {
        ok: true,
        json: async () => ({ text: "教学目标 朗读课文", source: "ocr" }),
      };
    };
    const text = await globalThis.MindGraphDocExtract.postSmartEduPdfForOcr(
      blob,
      4,
      { baseUrl: "https://mg.example", account: "teacher", token: "secret-token" },
      fetchImpl,
    );
    expect(text).toContain("教学目标");
    expect(posted.url).toBe("https://mg.example/api/extension/extract_pdf_text");
    expect(posted.init.method).toBe("POST");
    expect(posted.init.headers.Authorization).toBe("Bearer secret-token");
    expect(posted.init.body).toBeInstanceOf(FormData);
    expect(posted.init.body.get("image_based")).toBe("true");
  });

  it("treats a picture page with no text as image-based", () => {
    loadModule("doc-extract/text/pdf-extract-in-tab.js");
    const api = globalThis.__MGDocExtractPdf;
    expect(api.pageLooksImageBased(0, true)).toBe(true);
    expect(api.pageLooksImageBased(80, true)).toBe(false);
    expect(api.pageLooksImageBased(0, false)).toBe(false);
    expect(api.documentIsImageBased([{ imageLike: true }, { imageLike: true }])).toBe(true);
    expect(api.documentIsImageBased([{ imageLike: true }, { imageLike: false }])).toBe(false);
    expect(api.documentIsImageBased([])).toBe(false);
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

describe("mixed capture orchestrator", () => {
  it("finds pdf links on a page", async () => {
    loadModule("doc-extract/mixed-capture.js");
    const api = globalThis.MindGraphDocExtract;
    expect(typeof api.discoverLinkedPdfUrlsInTab).toBe("function");
  });
});

describe("mixed capture merge", () => {
  it("prepends page shell when it is not already inside the file extract", () => {
    loadModule("doc-extract/text/mixed-capture-merge.js");
    const api = globalThis.MindGraphDocExtract;
    const merged = api.mergePageShellWithDocuments(
      "Activity goals: compare seasonal imagery in the poem.\n".repeat(8),
      "## 课件\n\nPDF body about 济南的冬天。",
      32000,
    );
    expect(merged).toContain("## Web page");
    expect(merged).toContain("Activity goals");
    expect(merged).toContain("济南的冬天");
  });

  it("merges partial pdf.js text with OCR instead of picking one side", () => {
    loadModule("doc-extract/text/mixed-capture-merge.js");
    const api = globalThis.MindGraphDocExtract;
    const merged = api.mergePdfTextAndOcr(
      "Page 1 title only with enough characters here.",
      "教学目标：朗读课文，整体感知济南的冬天这篇散文的语言特点。",
      20,
    );
    expect(merged).toContain("Page 1 title");
    expect(merged).toContain("教学目标");
  });
});

describe("document asset helpers", () => {
  it("lists a CNKI PDF and a Wenku PDF, and skips videos", () => {
    loadModule("doc-extract/text/markdown-capture-policy.js");
    const api = globalThis.MindGraphDocExtract;
    expect(api.cnkiPreviewAsset({ pdfUrl: "https://docdown.cnki.net/a.pdf", title: "济南的冬天" })).toEqual({
      id: "cnki-pdf",
      title: "济南的冬天",
      alias: "pdf",
      localKind: "pdf",
      selected: true,
    });
    expect(api.cnkiPreviewAsset({ error: "CNKI_LOGIN_REQUIRED", title: "x" })).toBeNull();
    expect(api.wenkuPreviewAsset("https://wenku.baidu.com/view/abc.pdf", "课件")).toMatchObject({
      id: "wenku-pdf",
      title: "课件",
    });
    expect(api.wenkuPreviewAsset("", "课件")).toBeNull();
    const listed = api.listedDocumentAssets([
      { id: "1", title: "课件", localKind: "pdf" },
      { id: "2", title: "微课", alias: "micro_lesson_video", localKind: "m3u8" },
    ]);
    expect(listed.map((asset) => asset.id)).toEqual(["1"]);
  });
});

describe("jpeg-pdf assembler", () => {
  // Minimal 1×1 JPEG (SOF0 width/height = 1).
  const TINY_JPEG =
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U" +
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIy" +
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAA" +
    "AAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAA" +
    "AAAAAA/9oADAMBAAIQAxAAAAGfAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAQUCf//EABQRAQAAAAAAAAAAAAAA" +
    "AAAAAAD/2gAIAQMBAT8Bf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8Bf//Z";

  it("builds a PDF with JPEG image XObject", async () => {
    loadModule("doc-extract/engines/jpeg-pdf.js");
    const blob = await globalThis.MindGraphDocExtract.imagesToPdfBlob(
      [TINY_JPEG, TINY_JPEG],
      "test-doc",
      { pageWidth: 100, pageHeight: 200 },
    );
    expect(blob.type).toBe("application/pdf");
    const buf = new Uint8Array(await blob.arrayBuffer());
    const head = String.fromCharCode(...buf.slice(0, 8));
    expect(head.startsWith("%PDF-1.")).toBe(true);
    const text = new TextDecoder("latin1").decode(buf);
    expect(text).toContain("/Filter /DCTDecode");
    expect(text).toContain("/Count 2");
    expect(text).toContain("(test-doc)");
  });

  it("rejects non-JPEG data URLs", async () => {
    loadModule("doc-extract/engines/jpeg-pdf.js");
    await expect(
      globalThis.MindGraphDocExtract.imagesToPdfBlob(
        ["data:image/png;base64,aaa"],
        "x",
      ),
    ).rejects.toThrow("JPEG_DATA_URL_REQUIRED");
  });
});
