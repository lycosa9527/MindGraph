import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

/**
 * @param {string} relPath
 * @param {string} exportName
 */
function loadModule(relPath, exportName) {
  const abs = path.resolve(repoRoot, "chrome-extension", relPath);
  const code = fs.readFileSync(abs, "utf8");
  const fn = new Function(
    "globalThis",
    "self",
    `${code}\nreturn globalThis.${exportName};`,
  );
  return fn(globalThis, globalThis);
}

describe("mindmate capture debug", () => {
  it("redacts token-like debug fields", () => {
    loadModule("mindmate-capture-debug.js", "MindGraphMindMate");
    const sanitized = globalThis.MindGraphMindMate.captureDebug.sanitizeDebugValue({
      smarteduToken: "abcdefgh123456789",
      title: "课件",
    });
    expect(sanitized.smarteduToken).toBe("[redacted]");
    expect(sanitized.title).toBe("课件");
  });

  it("formats last capture hint from steps", async () => {
    loadModule("mindmate-capture-debug.js", "MindGraphMindMate");
    const dbg = globalThis.MindGraphMindMate.captureDebug;
    dbg.beginCapture({ tabId: 1, pageUrl: "https://basic.smartedu.cn/x", hostId: "smartedu" });
    dbg.log("smartedu.token", "no SmartEdu token");
    await dbg.finishCapture({
      ok: false,
      error: "errExtractSmartEduLogin",
      hostId: "smartedu",
      pageUrl: "https://basic.smartedu.cn/x",
      markdownLen: 0,
    });
    const hint = await dbg.formatLastCaptureHint();
    expect(hint).toContain("host=smartedu");
    expect(hint).toContain("smartedu.token");
  });
});

describe("mindmate capture progress", () => {
  it("formats SmartEdu asset progress messages", async () => {
    loadModule("mindmate-capture-progress.js", "MindGraphMindMate");
    const prog = globalThis.MindGraphMindMate.captureProgress;
    const t = (key, subs) => {
      if (key === "mindmatePageContextSmarteduAssets") {
        return `assets:${subs[0]}`;
      }
      if (key === "mindmatePageContextSmarteduDownloading") {
        return `dl:${subs.join(",")}`;
      }
      if (key === "mindmatePageContextSmarteduReady") {
        return `ready:${subs.join(",")}`;
      }
      return key;
    };
    await prog.publishCaptureProgress({
      phase: "smartedu_detected",
      messageKey: "mindmatePageContextSmarteduAssets",
      messageSubs: ["3"],
    });
    const detected = await prog.getCaptureProgress();
    expect(prog.formatCaptureProgressMessage(t, detected)).toBe("assets:3");
    await prog.publishCaptureProgress({
      phase: "smartedu_download",
      messageKey: "mindmatePageContextSmarteduDownloading",
      messageSubs: ["1", "3", "课件.pdf"],
    });
    const downloading = await prog.getCaptureProgress();
    expect(prog.formatCaptureProgressMessage(t, downloading)).toBe("dl:1,3,课件.pdf");
    await prog.finishCaptureProgress({
      ok: true,
      source: "smartedu-pdf",
      title: "小数除法",
      markdownLen: 4200,
      assetTotal: 3,
    });
    const ready = await prog.getCaptureProgress();
    expect(prog.formatCaptureProgressMessage(t, ready)).toBe("ready:3,4200,小数除法");
  });

  it("formats cached page context ready notice", () => {
    loadModule("mindmate-capture-progress.js", "MindGraphMindMate");
    const prog = globalThis.MindGraphMindMate.captureProgress;
    const t = (key, subs) => `${key}:${subs.join("|")}`;
    const genericNotice = prog.formatCachedPageContextNotice(t, {
      title: "Article",
      markdown: "x".repeat(120),
      source: "page-markdown",
      hostId: "generic",
    });
    expect(genericNotice).toBe("mindmatePageContextReadyGeneric:120|Article");
    const knownNotice = prog.formatCachedPageContextNotice(t, {
      title: "Article",
      markdown: "x".repeat(120),
      source: "page-markdown",
      hostId: "article",
    });
    expect(knownNotice).toBe("mindmatePageContextReady:Article|120");
  });

  it("finishes generic capture with character count notice", async () => {
    loadModule("mindmate-capture-progress.js", "MindGraphMindMate");
    const prog = globalThis.MindGraphMindMate.captureProgress;
    const t = (key, subs) => `${key}:${subs.join("|")}`;
    await prog.finishCaptureProgress({
      ok: true,
      hostId: "generic",
      title: "News page",
      markdownLen: 3456,
      source: "dom-markdown",
    });
    const ready = await prog.getCaptureProgress();
    expect(prog.formatCaptureProgressMessage(t, ready)).toBe(
      "mindmatePageContextReadyGeneric:3456|News page",
    );
  });
});

describe("mindmate markdown render", () => {
  it("renders headings, lists, code, and links safely", () => {
    loadModule("mindmate-markdown.js", "MindGraphMindMate");
    const html = globalThis.MindGraphMindMate.renderMarkdownToHtml(
      "## 认知冲突\n\n- **迷思概念**：减法一定变小\n- [示例](https://example.com)\n\n```\nPOE\n```",
    );
    expect(html).toContain("<h2>");
    expect(html).toContain("<strong>迷思概念</strong>");
    expect(html).toContain('<a href="https://example.com"');
    expect(html).toContain("<pre><code");
    expect(html).not.toContain("<script");
  });

  it("rejects unsafe link protocols", () => {
    loadModule("mindmate-markdown.js", "MindGraphMindMate");
    const html = globalThis.MindGraphMindMate.renderInlineMarkdown("[x](javascript:alert(1))");
    expect(html).not.toContain("<a ");
    expect(html).toContain("[x](javascript:alert(1))");
  });

  it("escapes raw html in source", () => {
    loadModule("mindmate-markdown.js", "MindGraphMindMate");
    const html = globalThis.MindGraphMindMate.renderMarkdownToHtml("<img onerror=alert(1)>");
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("<img");
  });

  it("renders plain assistant text without markdown syntax", () => {
    loadModule("mindmate-markdown.js", "MindGraphMindMate");
    const html = globalThis.MindGraphMindMate.renderMarkdownToHtml("你好，这是普通回复。");
    expect(html).toContain("mindmate-md");
    expect(html).toContain("你好，这是普通回复。");
    expect(html).not.toContain("<script");
  });

  it("leaves empty assistant content unset for markdown mode", () => {
    loadModule("mindmate-markdown.js", "MindGraphMindMate");
    const bubble = {
      classNames: [],
      classList: {
        add: (name) => {
          bubble.classNames.push(name);
        },
        remove: (name) => {
          bubble.classNames = bubble.classNames.filter((c) => c !== name);
        },
      },
      innerHTML: "prev",
      textContent: "",
    };
    Object.defineProperty(bubble, "textContent", {
      configurable: true,
      get: () => bubble._text || "",
      set: (value) => {
        bubble._text = value;
        bubble.innerHTML = "";
      },
    });
    globalThis.MindGraphMindMate.applyMessageBubbleContent(bubble, "   ", "assistant");
    expect(bubble.classNames).not.toContain("mindmate-msg-bubble-md");
    expect(bubble.textContent).toBe("   ");
  });

  it("stores raw markdown in session thread, not rendered html", () => {
    loadModule("mindmate-session.js", "MindGraphMindMate");
    const stored = globalThis.MindGraphMindMate.buildStoredThread("auth", "conv", 2, [
      { id: "a1", role: "assistant", text: "## Title\n\n**bold**" },
      { id: "u1", role: "user", text: "Question?" },
    ]);
    expect(stored.messages[0].text).toBe("## Title\n\n**bold**");
    expect(stored.messages[0].text).not.toContain("<h2>");
  });

  it("popup script order loads markdown before panel", () => {
    const html = fs.readFileSync(path.resolve(repoRoot, "chrome-extension/popup.html"), "utf8");
    const markdownIdx = html.indexOf("mindmate-markdown.js");
    const panelIdx = html.indexOf("mindmate-panel.js");
    expect(markdownIdx).toBeGreaterThan(-1);
    expect(panelIdx).toBeGreaterThan(markdownIdx);
  });
});

describe("mindmate sse", () => {
  it("parses data lines and stops when handler returns false", async () => {
    loadModule("mindmate-sse.js", "MindGraphMindMate");
    const chunks = ['data: {"event":"message","answer":"Hi"}\n\n', 'data: {"event":"done"}\n\n'];
    let index = 0;
    const reader = {
      read: async () => {
        if (index >= chunks.length) {
          return { done: true, value: undefined };
        }
        const value = new TextEncoder().encode(chunks[index]);
        index += 1;
        return { done: false, value };
      },
      releaseLock: () => {},
    };
    const seen = [];
    await globalThis.MindGraphMindMate.consumeSseDataLines(reader, (payload) => {
      seen.push(payload.event);
      return payload.event !== "message";
    });
    expect(seen).toEqual(["message"]);
  });
});

describe("mindmate session thread", () => {
  it("round-trips stored thread state", () => {
    loadModule("mindmate-session.js", "MindGraphMindMate");
    const built = globalThis.MindGraphMindMate.buildStoredThread("auth-1", "conv-1", 2, [
      { id: "m1", role: "user", text: "Hi" },
      { id: "m2", role: "assistant", text: "Hello" },
    ]);
    const parsed = globalThis.MindGraphMindMate.parseStoredThread(built);
    expect(parsed.authKey).toBe("auth-1");
    expect(parsed.conversationId).toBe("conv-1");
    expect(parsed.userMessageCount).toBe(2);
    expect(parsed.messages).toHaveLength(2);
  });

  it("drops invalid message entries", () => {
    loadModule("mindmate-session.js", "MindGraphMindMate");
    const parsed = globalThis.MindGraphMindMate.parseStoredThread({
      authKey: "a",
      conversationId: "c1",
      userMessageCount: 1,
      messages: [{ id: "ok", role: "user", text: "x" }, { id: "bad", role: "bot", text: "nope" }],
    });
    expect(parsed.messages).toEqual([{ id: "ok", role: "user", text: "x" }]);
  });

  it("scopes page context to auth key", () => {
    loadModule("mindmate-session.js", "MindGraphMindMate");
    const ctx = globalThis.MindGraphMindMate.parseStoredPageContext(
      {
        authKey: "auth-a",
        tabId: 3,
        url: "https://example.com/page",
        title: "Page",
        markdown: "# Title",
      },
      "auth-a",
    );
    expect(ctx).toMatchObject({ url: "https://example.com/page", markdown: "# Title" });
    expect(
      globalThis.MindGraphMindMate.parseStoredPageContext(
        { authKey: "auth-a", url: "https://example.com", markdown: "x" },
        "auth-b",
      ),
    ).toBeNull();
    expect(
      globalThis.MindGraphMindMate.parseStoredPageContext(
        { url: "https://example.com", markdown: "x" },
        "auth-a",
      ),
    ).toBeNull();
  });
});

describe("mindmate compose page context", () => {
  it("attaches only on the first message of a new conversation", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    expect(globalThis.MindGraphMindMate.shouldAttachPageContext(null, 0)).toBe(true);
    expect(globalThis.MindGraphMindMate.shouldAttachPageContext(null, 1)).toBe(false);
    expect(globalThis.MindGraphMindMate.shouldAttachPageContext("conv-1", 0)).toBe(false);
  });

  it("builds education prompt with markdown and user question", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    const t = (key, subs) => {
      if (key === "mindmatePageContextIntro") {
        return "INTRO";
      }
      if (key === "mindmatePageContextRouting") {
        return "ROUTING";
      }
      if (key === "mindmatePageContextGuidance") {
        return "GUIDANCE";
      }
      if (key === "mindmatePageContextMaterialHeader") {
        return "MATERIAL";
      }
      if (key === "mindmatePageContextMeta") {
        return `META:${subs[0]}:${subs[1]}:${subs[2]}`;
      }
      if (key === "mindmatePageContextQuestion") {
        return `Q:${subs[0]}`;
      }
      if (key === "mindmatePageContextSource_page_markdown") {
        return "generic-extract";
      }
      return key;
    };
    const msg = globalThis.MindGraphMindMate.buildFirstMessageWithPageContext(t, "Explain this lesson", {
      title: "Lesson A",
      url: "https://example.com/lesson",
      markdown: "## Section\n\nBody text",
    });
    expect(msg).toContain("INTRO");
    expect(msg).toContain("ROUTING");
    expect(msg).toContain("GUIDANCE");
    expect(msg).toContain("MATERIAL");
    expect(msg).toContain("META:Lesson A:https://example.com/lesson:generic-extract");
    expect(msg).toContain("## Section");
    expect(msg).toContain("Q:Explain this lesson");
    expect(msg.indexOf("Q:Explain this lesson")).toBeLessThan(msg.indexOf("GUIDANCE"));
    expect(msg.indexOf("Q:Explain this lesson")).toBeLessThan(msg.indexOf("## Section"));
    expect(msg.length).toBeLessThanOrEqual(5000);
  });

  it("maps extract source codes to Dify-facing labels", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    const t = (key) => {
      if (key === "mindmatePageContextSource_smartedu_pdf") {
        return "SmartEdu PDF";
      }
      if (key === "mindmatePageContextSource_page_markdown") {
        return "Web extract";
      }
      return key;
    };
    expect(globalThis.MindGraphMindMate.formatPageContextSourceLabel(t, "smartedu-pdf")).toBe(
      "SmartEdu PDF",
    );
    expect(globalThis.MindGraphMindMate.formatPageContextSourceLabel(t, "page-pdfjs")).toBe(
      "Web extract",
    );
  });

  it("resolves page context before incrementing user message count", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    const t = (key, subs) => {
      if (key === "mindmatePageContextQuestion" && subs) {
        return subs[0];
      }
      return key;
    };
    const pageCtx = { title: "T", url: "https://example.com", markdown: "Body" };
    const beforeSend = globalThis.MindGraphMindMate.shouldAttachPageContext(null, 0);
    const afterSend = globalThis.MindGraphMindMate.shouldAttachPageContext(null, 1);
    expect(beforeSend).toBe(true);
    expect(afterSend).toBe(false);
    const composed = globalThis.MindGraphMindMate.buildFirstMessageWithPageContext(
      t,
      "Question?",
      pageCtx,
    );
    expect(composed).toContain("Body");
    expect(composed).toContain("Question?");
  });

  it("displayUserMessageFromDifyQuery hides extraction body for history", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    const t = (key, subs) => {
      if (key === "mindmatePageContextIntro") {
        return "INTRO";
      }
      if (key === "mindmatePageContextRouting") {
        return "ROUTING";
      }
      if (key === "mindmatePageContextGuidance") {
        return "GUIDANCE";
      }
      if (key === "mindmatePageContextMaterialHeader") {
        return "**[Reference material: page body]**";
      }
      if (key === "mindmatePageContextMeta") {
        return `META:${subs[0]}:${subs[1]}:${subs[2]}`;
      }
      if (key === "mindmatePageContextQuestion") {
        return `**User question (classify intent and answer from this line):** ${subs[0]}`;
      }
      if (key === "mindmatePageContextSource_page_markdown") {
        return "generic-extract";
      }
      return key;
    };
    const composed = globalThis.MindGraphMindMate.buildFirstMessageWithPageContext(t, "Explain this lesson", {
      title: "Lesson A",
      url: "https://example.com/lesson",
      markdown: "## Section\n\nBody text",
    });
    expect(globalThis.MindGraphMindMate.displayUserMessageFromDifyQuery(composed)).toBe(
      "Explain this lesson",
    );
    expect(globalThis.MindGraphMindMate.displayUserMessageFromDifyQuery("Plain follow-up")).toBe(
      "Plain follow-up",
    );
  });
});

describe("mindmate page markdown", () => {
  /**
   * @returns {Document}
   */
  function loadMarkdownApi(html) {
    const code = fs.readFileSync(
      path.resolve(repoRoot, "chrome-extension/mindmate-page-markdown.js"),
      "utf8",
    );
    const dom = new (class {
      constructor(markup) {
        this.body = { innerHTML: markup };
      }
      querySelector(sel) {
        if (sel === "#viewer") {
          return {
            querySelectorAll: (innerSel) => {
              if (innerSel.includes("textLayer")) {
                return [
                  { textContent: "Hello", getBoundingClientRect: () => ({ top: 10, left: 0 }) },
                  { textContent: "world", getBoundingClientRect: () => ({ top: 10, left: 40 }) },
                  { textContent: "Second line", getBoundingClientRect: () => ({ top: 30, left: 0 }) },
                ];
              }
              return [];
            },
          };
        }
        if (sel === "main") {
          return {
            tagName: "MAIN",
            childNodes: [],
            querySelectorAll: () => [],
          };
        }
        return null;
      }
    })(html);
    const fn = new Function(
      "globalThis",
      "document",
      `${code}\nreturn globalThis.__MGMindMatePageMarkdown;`,
    );
    return fn(globalThis, dom);
  }

  it("extracts PDF.js text layer in reading order", () => {
    const api = loadMarkdownApi(`<div id="viewer"><div class="textLayer"></div></div>`);
    const viewer = { querySelectorAll: () => [] };
    const md = api.extractPdfJsTextLayerMarkdown({
      querySelectorAll: (sel) => {
        if (sel.includes("textLayer")) {
          return [
            { textContent: "Hello", getBoundingClientRect: () => ({ top: 10, left: 0 }) },
            { textContent: "world", getBoundingClientRect: () => ({ top: 10, left: 40 }) },
            { textContent: "Second line", getBoundingClientRect: () => ({ top: 30, left: 0 }) },
          ];
        }
        return [];
      },
    });
    expect(md).toContain("Hello world");
    expect(md).toContain("Second line");
  });

  it("findArticleRoot prefers main on normal pages", () => {
    const code = fs.readFileSync(
      path.resolve(repoRoot, "chrome-extension/mindmate-page-markdown.js"),
      "utf8",
    );
    const mainNode = { tagName: "MAIN" };
    const documentMock = {
      body: mainNode,
      location: { pathname: "/article", href: "https://example.com/article" },
      querySelector: (sel) => (sel === "main" ? mainNode : null),
    };
    const fn = new Function(
      "globalThis",
      "document",
      "window",
      `${code}\nreturn globalThis.__MGMindMatePageMarkdown;`,
    );
    const api = fn(globalThis, documentMock, { location: documentMock.location });
    const root = api.findArticleRoot();
    expect(root.tagName).toBe("MAIN");
  });

  it("extractPageMarkdownAsync skips selection when auto-scanning generic pages", async () => {
    const code = fs.readFileSync(
      path.resolve(repoRoot, "chrome-extension/mindmate-page-markdown.js"),
      "utf8",
    );
    class MockElement {
      getAttribute() {
        return null;
      }
      get classList() {
        return { contains: () => false };
      }
    }
    class MockTextNode {
      constructor(text) {
        this.nodeType = 3;
        this.textContent = text;
      }
    }
    class MockArticle extends MockElement {
      constructor(text) {
        super();
        this.tagName = "ARTICLE";
        this.innerText = text;
        this.childNodes = [new MockTextNode(text)];
      }
      querySelectorAll() {
        return [];
      }
    }
    const articleNode = new MockArticle(
      "Main article body text with enough characters for extraction.",
    );
    const documentMock = {
      body: articleNode,
      title: "Example",
      location: { pathname: "/news", href: "https://example.com/news" },
      querySelector: (sel) => (sel === "article" ? articleNode : null),
    };
    const selectionMock = { toString: () => "User highlighted snippet" };
    const fn = new Function(
      "globalThis",
      "document",
      "window",
      "Element",
      "Node",
      `${code}\nreturn globalThis.__MGMindMatePageMarkdown;`,
    );
    const api = fn(
      globalThis,
      documentMock,
      {
        location: documentMock.location,
        getSelection: () => selectionMock,
      },
      MockElement,
      { TEXT_NODE: 3, ELEMENT_NODE: 1 },
    );
    const withSelection = await api.extractPageMarkdownAsync(8000);
    expect(withSelection.fromSelection).toBe(true);
    expect(withSelection.markdown).toContain("User highlighted");
    const autoScan = await api.extractPageMarkdownAsync(8000, { skipSelection: true });
    expect(autoScan.fromSelection).toBe(false);
    expect(autoScan.markdown).toContain("Main article body");
    expect(autoScan.markdown).not.toContain("User highlighted");
  });
});

describe("mindmate stream errors", () => {
  it("maps server SSE error events to failed stream results", async () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("mindmate-sse.js", "MindGraphMindMate");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    expect(
      globalThis.MindGraphMindMate.mapStreamErrorFromPayload({ error_type: "daily_token_cap" }),
    ).toBe("errMindMateDailyTokenCap");
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      body: {
        getReader() {
          return {
            read: async () => ({
              done: false,
              value: new TextEncoder().encode(
                'data: {"event":"error","error_type":"daily_token_cap"}\n\n',
              ),
            }),
            releaseLock: () => {},
          };
        },
      },
    });
    try {
      const result = await globalThis.MindGraphMindMate.streamMessage(
        {
          baseUrl: "https://example.com",
          account: "13800000000",
          token: "tok",
          requestId: "req-1",
        },
        {
          message: "hi",
          userId: "u1",
          conversationId: null,
          signal: new AbortController().signal,
        },
      );
      expect(result).toEqual({ ok: false, error: "errMindMateDailyTokenCap" });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

describe("extension security helpers", () => {
  it("parses positive integers and bounded tokens", () => {
    loadModule("extension-security.js", "MindGraphExtensionSecurity");
    const sec = globalThis.MindGraphExtensionSecurity;
    expect(sec.parsePositiveInt(3)).toBe(3);
    expect(sec.parsePositiveInt("12")).toBe(12);
    expect(sec.parsePositiveInt(0)).toBeNull();
    expect(sec.parseSmartEduToken(" abc ")).toBe("abc");
    expect(sec.parseSmartEduToken("")).toBeNull();
  });
});

describe("canvas diagram link helpers", () => {
  it("builds canvas urls for each server preset", () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    const shared = globalThis.MindGraphShared;
    expect(shared.resolveMindGraphSettings({ baseUrlPresetId: "production" }).baseUrl).toBe(
      "https://mg.mindspringedu.com",
    );
    expect(shared.resolveMindGraphSettings({ baseUrlPresetId: "test" }).baseUrl).toBe(
      "https://test.mindspringedu.com",
    );
    expect(shared.resolveMindGraphSettings({ baseUrlPresetId: "local" }).baseUrl).toBe(
      "http://localhost:9527",
    );
    expect(shared.buildCanvasDiagramUrl("local", "abc-123")).toBe(
      "http://localhost:9527/canvas?diagramId=abc-123",
    );
    expect(shared.buildCanvasDiagramUrl("test", "abc-123")).toBe(
      "https://test.mindspringedu.com/canvas?diagramId=abc-123",
    );
    const res = {
      headers: {
        get(name) {
          if (name === "Content-Disposition") {
            return 'attachment; filename="mindgraph-diagram-uuid.png"';
          }
          return "";
        },
      },
    };
    expect(shared.parseDiagramIdFromPngResponse(res)).toBe("diagram-uuid");
  });
});

describe("base url presets", () => {
  it("maps stored origins to preset ids", () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    const shared = globalThis.MindGraphShared;
    expect(shared.resolveBaseUrlPresetId("https://mg.mindspringedu.com/")).toBe("production");
    expect(shared.resolveBaseUrlPresetId("https://test.mindspringedu.com")).toBe("test");
    expect(shared.resolveBaseUrlPresetId("http://localhost:9527")).toBe("local");
    expect(shared.resolveBaseUrlPresetId("http://127.0.0.1:9527")).toBe("local");
    expect(shared.baseUrlFromPresetId("local")).toBe("http://localhost:9527");
  });
});

describe("extension storage hygiene", () => {
  it("builds stable auth keys", () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("extension-storage.js", "MindGraphExtensionStorage");
    const key = globalThis.MindGraphExtensionStorage.buildMindGraphAuthKey(
      "https://mg.example.com/",
      "13800000000",
    );
    expect(key).toBe("https://mg.example.com|13800000000");
  });
});

describe("mindmate api auth headers", () => {
  it("builds bearer headers with account and client label", () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    const headers = globalThis.MindGraphMindMate.buildAuthHeaders("13800000000", "tok", "req-1");
    expect(headers.Authorization).toBe("Bearer tok");
    expect(headers["X-MG-Account"]).toBe("13800000000");
    expect(headers["X-MG-Client"]).toMatch(/extension$/);
  });

  it("builds conversation route query suffix for MindBot rows", () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    const suffix = globalThis.MindGraphMindMate.conversationRouteQuerySuffix({
      difyUser: "mindbot_5_staff42",
      server: 2,
      mindbotConfigId: 9,
    });
    expect(suffix).toContain("dify_user=mindbot_5_staff42");
    expect(suffix).toContain("server=2");
    expect(suffix).toContain("mindbot_config_id=9");
  });

  it("maps Dify API messages to panel bubbles", () => {
    loadModule("mindmate-compose.js", "MindGraphMindMate");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    const composed = globalThis.MindGraphMindMate.buildFirstMessageWithPageContext(
      (key, subs) => {
        if (key === "mindmatePageContextIntro") {
          return "INTRO";
        }
        if (key === "mindmatePageContextRouting") {
          return "ROUTING";
        }
        if (key === "mindmatePageContextGuidance") {
          return "GUIDANCE";
        }
        if (key === "mindmatePageContextMaterialHeader") {
          return "**[Reference material: page body]**";
        }
        if (key === "mindmatePageContextMeta") {
          return `META:${subs[0]}:${subs[1]}:${subs[2]}`;
        }
        if (key === "mindmatePageContextQuestion") {
          return `**User question (classify intent and answer from this line):** ${subs[0]}`;
        }
        if (key === "mindmatePageContextSource_page_markdown") {
          return "generic-extract";
        }
        return key;
      },
      "Explain this lesson",
      {
        title: "Lesson A",
        url: "https://example.com/lesson",
        markdown: "## Section\n\nBody text",
      },
    );
    const rows = globalThis.MindGraphMindMate.panelMessagesFromApi([
      { id: "m1", query: composed, answer: "Hello" },
    ]);
    expect(rows).toHaveLength(2);
    expect(rows[0].role).toBe("user");
    expect(rows[0].text).toBe("Explain this lesson");
    expect(rows[1].role).toBe("assistant");
  });

  it("maps 401 from auth/me to login expired", async () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("mindmate-sse.js", "MindGraphMindMate");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
      if (String(url).endsWith("/api/auth/me")) {
        expect(init?.credentials).toBe("omit");
        return { ok: false, status: 401 };
      }
      throw new Error("unexpected fetch");
    };
    try {
      const result = await globalThis.MindGraphMindMate.verifyAuth({
        baseUrl: "https://example.com",
        account: "13800000000",
        token: "tok",
        requestId: "req-1",
      });
      expect(result).toEqual({ ok: false, error: "errMindMateLoginExpired" });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
