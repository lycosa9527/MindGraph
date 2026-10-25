import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const scriptPath = path.resolve(repoRoot, "chrome-extension/presence-mark.js");
const ATTR = "data-mindgraph-extension";
const EVENT = "mindgraph-extension-installed";

/**
 * @param {{ readyState?: string, root?: object | null }} [options]
 */
function createDocument(options = {}) {
  const listeners = new Map();
  const doc = {
    readyState: options.readyState ?? "complete",
    documentElement: options.root === undefined ? createRoot() : options.root,
    addEventListener(type, fn) {
      const list = listeners.get(type) ?? [];
      list.push(fn);
      listeners.set(type, list);
    },
    dispatchEvent(event) {
      const list = listeners.get(event.type) ?? [];
      for (const fn of list) {
        fn(event);
      }
      return true;
    },
    fire(type) {
      const list = listeners.get(type) ?? [];
      for (const fn of list) {
        fn({ type });
      }
    },
  };
  return doc;
}

function createRoot() {
  const attrs = new Map();
  return {
    getAttribute(name) {
      return attrs.has(name) ? attrs.get(name) : null;
    },
    setAttribute(name, value) {
      attrs.set(name, String(value));
    },
  };
}

function withDocument(doc, fn) {
  const previous = globalThis.document;
  globalThis.document = doc;
  try {
    fn();
  } finally {
    globalThis.document = previous;
  }
}

function runMarker(doc) {
  const code = fs.readFileSync(scriptPath, "utf8");
  const run = new Function(code);
  withDocument(doc, () => {
    run();
  });
}

describe("MindGraph presence marker", () => {
  it("sets the page attribute and announces it", () => {
    const doc = createDocument();
    const seen = [];
    doc.addEventListener(EVENT, () => {
      seen.push(doc.documentElement.getAttribute(ATTR));
    });
    runMarker(doc);
    expect(doc.documentElement.getAttribute(ATTR)).toBe("1");
    expect(seen).toEqual(["1"]);
  });

  it("does not announce twice when the marker is already present", () => {
    const root = createRoot();
    root.setAttribute(ATTR, "1");
    const doc = createDocument({ root });
    let announced = 0;
    doc.addEventListener(EVENT, () => {
      announced += 1;
    });
    runMarker(doc);
    expect(announced).toBe(0);
  });

  it("waits for the document element when the script starts early", () => {
    const root = createRoot();
    const doc = createDocument({ readyState: "loading", root: null });
    const code = fs.readFileSync(scriptPath, "utf8");
    const run = new Function(code);
    withDocument(doc, () => {
      run();
      expect(doc.documentElement).toBeNull();
      doc.documentElement = root;
      doc.fire("DOMContentLoaded");
    });
    expect(root.getAttribute(ATTR)).toBe("1");
  });

  it("is registered at document start on MindGraph hosts", () => {
    const manifest = JSON.parse(
      fs.readFileSync(path.resolve(repoRoot, "chrome-extension/manifest.json"), "utf8"),
    );
    const entry = manifest.content_scripts.find((item) => item.js.includes("presence-mark.js"));
    expect(entry.run_at).toBe("document_start");
    expect(entry.matches).toEqual([
      "https://mg.mindspringedu.com/*",
      "https://www.mindspringedu.com/*",
      "https://test.mindspringedu.com/*",
      "http://localhost:9527/*",
      "http://127.0.0.1:9527/*",
    ]);
    const mindgraphHosts = manifest.host_permissions.filter(
      (pattern) =>
        pattern.includes("mindspringedu.com") ||
        pattern.includes("localhost:9527") ||
        pattern.includes("127.0.0.1:9527"),
    );
    for (const pattern of mindgraphHosts) {
      expect(entry.matches).toContain(pattern);
    }
  });

  it("uses the same marker names as the web app", () => {
    const web = fs.readFileSync(
      path.resolve(repoRoot, "frontend/src/composables/browserPluginPresence.ts"),
      "utf8",
    );
    const script = fs.readFileSync(scriptPath, "utf8");
    expect(web).toContain(`'${ATTR}'`);
    expect(web).toContain(`'${EVENT}'`);
    expect(script).toContain(`"${ATTR}"`);
    expect(script).toContain(`"${EVENT}"`);
  });
});
