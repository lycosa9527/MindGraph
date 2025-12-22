# Diagram Type Field Mapping Table

This table shows the field mappings between what `prompt_to_diagram` agent returns vs what each renderer expects.

| Diagram Type | Prompt Returns | Renderer Expects | Normalization Status | Notes |
|--------------|----------------|------------------|---------------------|-------|
| **bubble_map** | `topic`, `attributes` | `topic`, `attributes` | ✅ OK | No normalization needed |
| **circle_map** | `topic`, `context` | `topic`, `context` | ✅ OK | Normalized: `contexts` → `context` |
| **double_bubble_map** | `left`, `right`, `similarities`, `left_differences`, `right_differences` | `left`, `right`, `similarities`, `left_differences`, `right_differences` | ✅ OK | Normalized: `left_topic` → `left`, `right_topic` → `right` |
| **brace_map** | `topic`, `parts` | `whole`, `parts` | ✅ FIXED | Normalized: `topic` → `whole` |
| **bridge_map** | `relating_factor`, `analogies` | `relating_factor`, `analogies` | ✅ OK | No normalization needed |
| **tree_map** | `topic`, `children` | `topic`, `children` | ✅ OK | Normalized: `categories` → `children` (with structure transformation) |
| **flow_map** | `title`, `steps`, `substeps` | `title`, `steps`, `substeps` | ✅ OK | No normalization needed |
| **multi_flow_map** | `event`, `causes`, `effects` | `event`, `causes`, `effects` | ✅ OK | No normalization needed |
| **mind_map** | `topic`, `children` | `topic`, `children`, `_layout` | ✅ HANDLED | Requires `_layout` enhancement (already implemented) |
| **concept_map** | `topic`, `concepts`, `relationships` | `topic`, `concepts`, `relationships` | ✅ OK | No normalization needed |

## Field Details

### bubble_map
- **Main field**: `topic` (string)
- **Array field**: `attributes` (array of strings)

### circle_map
- **Main field**: `topic` (string)
- **Array field**: `context` (array of strings) - normalized from `contexts` if present

### double_bubble_map
- **Main fields**: `left` (string), `right` (string) - normalized from `left_topic`/`right_topic` if present
- **Array fields**: `similarities`, `left_differences`, `right_differences` (arrays of strings)

### brace_map
- **Main field**: `whole` (string) - normalized from `topic` if present
- **Array field**: `parts` (array of objects with `name` and optional `subparts`)

### bridge_map
- **Main field**: `relating_factor` (string, usually "as")
- **Array field**: `analogies` (array of objects with `left`, `right`, `id`)

### tree_map
- **Main field**: `topic` (string)
- **Array field**: `children` (array of objects with `id`, `label`, `children`) - normalized from `categories` if present

### flow_map
- **Main field**: `title` (string)
- **Array fields**: `steps` (array of strings), `substeps` (array of objects with `step` and `substeps`)

### multi_flow_map
- **Main field**: `event` (string)
- **Array fields**: `causes`, `effects` (arrays of strings)

### mind_map
- **Main field**: `topic` (string)
- **Array field**: `children` (array of objects with `id`, `label`, `children`)
- **Layout field**: `_layout` (object with `positions`, `connections`) - **REQUIRED** but not returned by prompt_to_diagram, must be enhanced

### concept_map
- **Main field**: `topic` (string)
- **Array fields**: `concepts` (array of strings), `relationships` (array of objects with `from`, `to`, `label`)

