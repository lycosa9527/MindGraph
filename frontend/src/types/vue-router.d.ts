import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** vue-i18n key for `document.title` (see `meta.pageTitle.*`). */
    titleKey?: string
    /** Auth layout: hide brand + language toggle; use browser-detected locale on the page. */
    authLayoutMinimal?: boolean
  }
}
