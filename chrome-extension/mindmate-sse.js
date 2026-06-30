/**
 * Buffered SSE line reader for MindMate streams (same pattern as web app).
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};

  /**
   * @param {ReadableStreamDefaultReader<Uint8Array>} reader
   * @param {(payload: Record<string, unknown>) => boolean | void} onData
   * @param {AbortSignal | null | undefined} signal
   * @returns {Promise<void>}
   */
  async function consumeSseDataLines(reader, onData, signal) {
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        if (signal && signal.aborted) {
          break;
        }
        const chunk = await reader.read();
        if (chunk.done) {
          break;
        }
        buffer += decoder.decode(chunk.value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) {
            continue;
          }
          try {
            const payload = JSON.parse(line.slice(6));
            const stop = onData(payload);
            if (stop === false) {
              return;
            }
          } catch {
            /* skip malformed JSON */
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  MindGraphMindMate.consumeSseDataLines = consumeSseDataLines;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
