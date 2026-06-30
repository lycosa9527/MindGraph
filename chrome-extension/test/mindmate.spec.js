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
      if (key === "mindmatePageContextMeta") {
        return `META:${subs[0]}:${subs[1]}`;
      }
      if (key === "mindmatePageContextQuestion") {
        return `Q:${subs[0]}`;
      }
      return key;
    };
    const msg = globalThis.MindGraphMindMate.buildFirstMessageWithPageContext(t, "Explain this lesson", {
      title: "Lesson A",
      url: "https://example.com/lesson",
      markdown: "## Section\n\nBody text",
    });
    expect(msg).toContain("INTRO");
    expect(msg).toContain("META:Lesson A:https://example.com/lesson");
    expect(msg).toContain("## Section");
    expect(msg).toContain("Q:Explain this lesson");
    expect(msg.length).toBeLessThanOrEqual(5000);
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

  it("maps 401 from auth/me to login expired", async () => {
    loadModule("shared-mindgraph.js", "MindGraphShared");
    loadModule("mindmate-sse.js", "MindGraphMindMate");
    loadModule("mindmate-api.js", "MindGraphMindMate");
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      if (String(url).endsWith("/api/auth/me")) {
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
