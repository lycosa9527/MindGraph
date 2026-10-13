import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const extensionRoot = path.resolve(__dirname, "..");

/**
 * @param {string} relPath
 */
function loadUmd(relPath) {
  const code = fs.readFileSync(path.join(extensionRoot, relPath), "utf8");
  const fn = new Function(code);
  fn();
}

/**
 * Minimal one-page PDF whose text layer is a single Helvetica string.
 * @param {string} message
 * @returns {Uint8Array}
 */
function buildTextPdf(message) {
  const stream = `BT /F1 24 Tf 40 80 Td (${message}) Tj ET`;
  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
      + "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    `4 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`,
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
  ];
  let body = "%PDF-1.4\n";
  const offsets = [0];
  for (const object of objects) {
    offsets.push(body.length);
    body += object;
  }
  const xrefAt = body.length;
  let xref = "xref\n0 6\n0000000000 65535 f \n";
  for (let index = 1; index <= 5; index += 1) {
    xref += `${String(offsets[index]).padStart(10, "0")} 00000 n \n`;
  }
  const trailer = `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`;
  return new TextEncoder().encode(body + xref + trailer);
}

describe("packaged pdf.js", () => {
  it("extracts text without eval or a remote worker", async () => {
    loadUmd("vendor/pdfjs/pdf.worker.min.js");
    loadUmd("vendor/pdfjs/pdf.min.js");
    const pdfjsLib = globalThis.pdfjsLib;
    expect(typeof pdfjsLib.getDocument).toBe("function");
    expect(globalThis.pdfjsWorker && globalThis.pdfjsWorker.WorkerMessageHandler).toBeTruthy();

    const task = pdfjsLib.getDocument({
      data: buildTextPdf("Hello MindGraph"),
      isEvalSupported: false,
    });
    const pdf = await task.promise;
    const page = await pdf.getPage(1);
    const content = await page.getTextContent();
    const text = content.items.map((item) => item.str || "").join("");
    await pdf.destroy();
    expect(text).toBe("Hello MindGraph");
  });
});
