declare module '@data/prompt_language_registry.json' {
  export interface PromptLanguageRegistryEntry {
    code: string
    englishName: string
    nativeLabel: string
    search: string[]
  }
  const value: PromptLanguageRegistryEntry[]
  export default value
}
