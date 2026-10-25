/**
 * Tell a MindGraph page that this extension is installed.
 * The attribute lives on the shared DOM. A window flag would stay in the
 * isolated content-script world and the page would never see it.
 * Keep the names in sync with frontend/src/composables/browserPluginPresence.ts.
 */
(function () {
  "use strict";

  const ATTR = "data-mindgraph-extension";
  const EVENT = "mindgraph-extension-installed";

  function mark() {
    const root = document.documentElement;
    if (!root) {
      return false;
    }
    if (root.getAttribute(ATTR) === "1") {
      return true;
    }
    root.setAttribute(ATTR, "1");
    document.dispatchEvent(new CustomEvent(EVENT));
    return true;
  }

  if (!mark() && document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mark, { once: true });
  }
})();
