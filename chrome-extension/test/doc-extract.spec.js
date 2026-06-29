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

  it("matches smartedu host", () => {
    loadModule("doc-extract/hosts.js");
    const entry = globalThis.MindGraphDocExtract.matchHost(
      "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=abc",
    );
    expect(entry.id).toBe("smartedu");
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
  it("extracts four assets from shared fixture", () => {
    loadModule("doc-extract/smartedu/models.js");
    loadModule("doc-extract/smartedu/metadata.js");
    const fixturePath = path.join(
      repoRoot,
      "tests/fixtures/doc-extract/smartedu/class_activity_b45c766e.json",
    );
    const detailJson = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
    const assets = globalThis.MindGraphDocExtract.extractAssetsFromDetailJson(detailJson);
    expect(assets).toHaveLength(4);
    expect(assets.map((a) => a.alias).sort()).toEqual([
      "coursewares",
      "learning_task",
      "lesson_plandesign",
      "micro_lesson_video",
    ]);
    const video = assets.find((a) => a.alias === "micro_lesson_video");
    expect(video.localKind).toBe("m3u8");
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
});
