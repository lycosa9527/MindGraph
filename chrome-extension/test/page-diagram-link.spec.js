import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

/**
 * @returns {typeof globalThis.MindGraphPageDiagramLink}
 */
function loadStore() {
  const abs = path.resolve(repoRoot, "chrome-extension/page-diagram-link.js");
  const code = fs.readFileSync(abs, "utf8");
  const fn = new Function(
    "globalThis",
    "self",
    `${code}\nreturn globalThis.MindGraphPageDiagramLink;`,
  );
  return fn(globalThis, globalThis);
}

describe("last generated diagram", () => {
  const store = loadStore();

  it("keeps one page and ignores the hash", () => {
    const saved = store.rememberLastDiagram(
      "https://basic.smartedu.cn/lesson?id=1#p2",
      "diagram-1",
      "local",
    );
    expect(saved).toEqual({
      pageUrl: "https://basic.smartedu.cn/lesson?id=1",
      diagramId: "diagram-1",
      presetId: "local",
    });
    expect(store.lookupLastDiagram(saved, "https://basic.smartedu.cn/lesson?id=1#other")).toEqual({
      diagramId: "diagram-1",
      presetId: "local",
    });
  });

  it("returns nothing for a different page", () => {
    const saved = store.rememberLastDiagram("https://example.com/a", "diagram-a", "test");
    expect(store.lookupLastDiagram(saved, "https://example.com/b")).toBeNull();
    expect(store.rememberLastDiagram("https://example.com/a", "  ", "test")).toBeNull();
    expect(store.pageDiagramKey("not a url")).toBe("");
  });
});
