---
name: vue-best-practices
description: Vue 3 development best practices covering TypeScript configuration, component typing, Composition API patterns, tooling troubleshooting, and testing. Use when working with Vue 3 components, TypeScript in Vue files, vue-tsc errors, Volar issues, or Composition API patterns.
---

# Vue 3 Best Practices

## TypeScript Configuration

### Component Props Extraction

When extracting props types from components, use `ExtractPropTypes`:

```typescript
import type { ExtractPropTypes } from 'vue'

const props = defineProps({
  title: String,
  count: { type: Number, required: true }
})

type Props = ExtractPropTypes<typeof props>
```

### Generic Component Props

For generic components, use `PropType` with proper typing:

```typescript
import type { PropType } from 'vue'

defineProps({
  items: {
    type: Array as PropType<Item[]>,
    required: true
  }
})
```

### vue-tsc strictTemplates

When `vue-tsc` reports template errors with `strictTemplates: true`, ensure:

1. Props are properly typed in `defineProps`
2. Event handlers match emit signatures
3. Template refs are typed correctly

For template refs:
```typescript
const inputRef = ref<InstanceType<typeof ElInput> | null>(null)
```

### Volar 3.0 Breaking Changes

Volar 3.0 requires explicit generic type parameters for some component types:

```typescript
// Before (may not work in Volar 3.0)
const component = defineComponent({...})

// After
const component = defineComponent<Props, Emits>({...})
```

### @vue-ignore Directive

Use `@vue-ignore` sparingly. Prefer fixing the underlying type issue:

```vue
<!-- Only when absolutely necessary -->
<!-- @vue-ignore -->
<component :is="dynamicComponent" />
```

## Composition API Patterns

### Composable Return Types

Always explicitly type composable return values:

```typescript
export function useDragConstraints() {
  const constraints = ref<DragConstraints>({...})
  
  return {
    constraints: readonly(constraints),
    setDiagramType: (type: DiagramType) => {...}
  }
}
```

### Reactive State Management

Use `readonly()` when exposing refs from composables to prevent external mutation:

```typescript
const state = ref({ count: 0 })

return {
  state: readonly(state), // Prevents external mutation
  increment: () => state.value.count++
}
```

### Computed with Type Inference

Let TypeScript infer computed types when possible:

```typescript
const constraints = computed<DragConstraints>(() => {
  // TypeScript infers return type
  return { minX: 0, maxX: 100 }
})
```

### Watch Patterns

Type watch callbacks properly:

```typescript
watch(
  () => props.diagramType,
  (newType: DiagramType | undefined) => {
    // Handle change
  }
)
```

## Component Patterns

### DefineComponent with Generics

For components with complex prop types:

```typescript
import type { DefineComponent } from 'vue'

type ComponentProps = {
  items: Item[]
  onSelect: (item: Item) => void
}

const MyComponent: DefineComponent<ComponentProps> = defineComponent({
  props: {
    items: { type: Array as PropType<Item[]>, required: true }
  },
  emits: ['select'],
  setup(props, { emit }) {
    // TypeScript knows props and emit types
  }
})
```

### Template Refs Typing

Type template refs based on component type:

```typescript
// For Element Plus components
const inputRef = ref<InstanceType<typeof ElInput> | null>(null)

// For custom components
const childRef = ref<InstanceType<typeof MyComponent> | null>(null)

// For DOM elements
const divRef = ref<HTMLDivElement | null>(null)
```

### Emit Type Safety

Define emit types explicitly:

```typescript
const emit = defineEmits<{
  (e: 'update', value: string): void
  (e: 'delete', id: number): void
}>()
```

## Tooling Configuration

### vueCompilerOptions

Configure `vueCompilerOptions` in `tsconfig.json` for better type checking:

```json
{
  "compilerOptions": {
    "vueCompilerOptions": {
      "target": 3,
      "experimentalCompatMode": 2
    }
  }
}
```

### Path Aliases

Use path aliases consistently. Configure in both `tsconfig.json` and `vite.config.ts`:

```typescript
// tsconfig.json
{
  "paths": {
    "@/*": ["src/*"]
  }
}

// vite.config.ts
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src')
  }
}
```

## Pinia Store Patterns

### Store Type Safety

Type Pinia stores properly:

```typescript
import { defineStore } from 'pinia'

export const useMyStore = defineStore('myStore', () => {
  const state = ref<StateType>({...})
  
  const getters = {
    computedValue: computed(() => state.value.something)
  }
  
  function action() {
    // Actions
  }
  
  return { state, ...getters, action }
})
```

### Store Mocking in Tests

Mock Pinia stores in tests:

```typescript
import { setActivePinia, createPinia } from 'pinia'

beforeEach(() => {
  setActivePinia(createPinia())
})
```

## VueUse Integration

### Type-Safe Composables

When using VueUse composables, ensure proper typing:

```typescript
import { useMouse } from '@vueuse/core'

const { x, y } = useMouse() // Types are inferred
```

## Testing Patterns

### Component Testing Setup

For component tests with TypeScript:

```typescript
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

describe('MyComponent', () => {
  it('renders correctly', () => {
    const wrapper = mount(MyComponent, {
      props: {
        title: 'Test'
      }
    })
    expect(wrapper.text()).toContain('Test')
  })
})
```

## Common Pitfalls

### Reactive Object Mutation

Avoid direct mutation of reactive objects. Use proper reactivity:

```typescript
// Bad
const state = reactive({ count: 0 })
state.count = 1 // Direct mutation

// Good
const state = ref({ count: 0 })
state.value = { count: 1 } // Replace entire object
// Or
state.value.count = 1 // If structure allows
```

### Template Ref Timing

Template refs are only available after component mount:

```typescript
onMounted(() => {
  // Safe to access template refs here
  if (inputRef.value) {
    inputRef.value.focus()
  }
})
```

### Watch Deep Objects

Use `deep: true` for watching nested objects:

```typescript
watch(
  () => props.config,
  (newConfig) => {
    // Handle change
  },
  { deep: true }
)
```

## Performance Optimization

### Computed Caching

Computed properties are cached. Use them for derived state:

```typescript
// Good - cached
const filteredItems = computed(() => 
  items.value.filter(item => item.active)
)

// Avoid - recalculates on every access
const filteredItems = () => 
  items.value.filter(item => item.active)
```

### v-memo for Lists

Use `v-memo` for expensive list rendering:

```vue
<div v-for="item in items" v-memo="[item.id, item.status]">
  <!-- Expensive rendering -->
</div>
```

## Error Handling

### Async Component Loading

Handle errors in async components:

```typescript
const AsyncComponent = defineAsyncComponent({
  loader: () => import('./MyComponent.vue'),
  errorComponent: ErrorComponent,
  loadingComponent: LoadingComponent,
  delay: 200,
  timeout: 3000
})
```

## Best Practices Summary

1. **Always type props, emits, and composable returns**
2. **Use `readonly()` when exposing refs from composables**
3. **Type template refs based on component type**
4. **Configure `vueCompilerOptions` for better type checking**
5. **Use computed for derived state, not functions**
6. **Handle template ref timing with `onMounted`**
7. **Use `deep: true` for watching nested objects**
8. **Type Pinia stores properly**
9. **Use path aliases consistently**
10. **Avoid direct mutation of reactive objects**
