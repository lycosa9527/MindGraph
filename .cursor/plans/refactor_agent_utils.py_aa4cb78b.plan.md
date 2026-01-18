---
name: Refactor agent_utils.py
overview: Complete business/logic/code review and refactoring of agent_utils.py to split into focused modules, remove duplication, eliminate unused code, and improve maintainability while maintaining backward compatibility.
todos: []
---

# Complete Review and Refactoring Plan for agent_utils.py

## Business/Logic/Code Review Findings

### Current State Analysis

**File Statistics:**

- Total lines: 1,245 (exceeds 600-800 line guideline)
- Functions: 15+ functions with mixed responsibilities
- External usage: Only `extract_json_from_response` is used externally (14+ files)
- Unused code: Several functions (`extract_topics_with_agent`, `generate_characteristics_with_agent`, `detect_language`, `validate_agent_output`) are not used externally

**Key Issues Identified:**

1. **Multiple Responsibilities Violation**

   - JSON parsing/repair (~450 lines)
   - Topic extraction (~200 lines) - DUPLICATED in `topic_extraction.py`
   - Characteristics generation (~300 lines)
   - Language detection (~50 lines) - NOT USED externally
   - Validation (~50 lines) - NOT USED externally

2. **Code Quality Issues**

   - Functions too long: `extract_json_from_response` (~220 lines), `_extract_partial_json` (~200 lines), `_repair_json_structure` (~150 lines)
   - Hardcoded fallback data: `generate_characteristics_fallback()` contains 200+ lines of hardcoded dictionaries
   - Tight coupling: JSON repair logic is specific to mind maps/tree maps
   - Code duplication: Topic extraction logic exists in both `agent_utils.py` and `topic_extraction.py`

3. **Architecture Issues**

   - No clear separation of concerns
   - Helper functions (`_clean_json_string`, `_remove_js_comments_safely`, `_escape_chinese_quotes_in_strings`) are tightly coupled to JSON extraction
   - Unused public functions create API confusion
   - Hardcoded business logic (car brands, animals, fruits) should be configurable

4. **Business Logic Concerns**

   - Fallback characteristics are hardcoded for specific topics (photosynthesis, D3, car brands, etc.)
   - Topic extraction fallback logic includes hardcoded car brand list
   - Language detection is simplistic (character counting)

## Refactoring Strategy

### Phase 1: Create New Module Structure

Split `agent_utils.py` into focused modules:

```
agents/core/
├── json_parser.py          (~450 lines) - JSON extraction & repair
│   ├── extract_json_from_response() - PUBLIC API
│   ├── _extract_partial_json()
│   ├── _repair_json_structure()
│   ├── _clean_json_string()
│   ├── _remove_js_comments_safely()
│   └── _escape_chinese_quotes_in_strings()
│
├── characteristics.py      (~350 lines) - Characteristics generation
│   ├── generate_characteristics_with_agent() - PUBLIC API
│   ├── parse_characteristics_result()
│   └── generate_characteristics_fallback()
│
├── topic_extraction_utils.py (~150 lines) - Topic extraction utilities
│   ├── parse_topic_extraction_result()
│   └── extract_topics_from_prompt()
│
└── agent_utils.py          (~50 lines) - Backward compatibility wrapper
    └── Re-exports all public APIs
```

### Phase 2: Code Improvements

1. **Extract JSON Parser Module** (`json_parser.py`)

   - Move all JSON-related functions
   - Create `JSONParser` class to encapsulate state
   - Break down large functions into smaller, testable units
   - Improve error handling and logging

2. **Extract Characteristics Module** (`characteristics.py`)

   - Move characteristics generation functions
   - Extract hardcoded fallback data to configuration file or constants module
   - Improve YAML parsing error handling
   - Add validation for characteristics structure

3. **Consolidate Topic Extraction** (`topic_extraction_utils.py`)

   - Move topic extraction utilities from `agent_utils.py`
   - Consider merging with existing `topic_extraction.py` or clearly separate concerns
   - Remove duplicate logic

4. **Remove Unused Code**

   - Remove `detect_language()` (not used, exists elsewhere)
   - Remove `validate_agent_output()` (not used externally)
   - Consider deprecating `extract_topics_with_agent()` and `generate_characteristics_with_agent()` if truly unused

5. **Improve Backward Compatibility** (`agent_utils.py`)

   - Create wrapper module that re-exports all public APIs
   - Add deprecation warnings for functions that should use new modules
   - Maintain existing import paths

### Phase 3: Specific Code Improvements

1. **JSON Parser Improvements**

   - Extract JSON extraction logic into smaller functions
   - Improve error messages with context
   - Add type hints for all internal functions
   - Reduce complexity of `_repair_json_structure()` by splitting repair patterns

2. **Characteristics Module Improvements**

   - Move fallback data to `config/characteristics_fallbacks.py` or `data/characteristics_fallbacks.py`
   - Add configuration for fallback data
   - Improve YAML parsing with better error recovery
   - Add validation for characteristics structure

3. **Topic Extraction Improvements**

   - Consolidate with existing `topic_extraction.py` logic
   - Remove hardcoded car brand list (make configurable)
   - Improve fallback logic

## Implementation Steps

### Step 1: Create JSON Parser Module

- Create `agents/core/json_parser.py`
- Move JSON-related functions from `agent_utils.py`
- Refactor large functions into smaller units
- Add comprehensive docstrings
- Maintain exact function signatures for `extract_json_from_response()`

### Step 2: Create Characteristics Module  

- Create `agents/core/characteristics.py`
- Move characteristics functions
- Extract fallback data to separate file
- Improve error handling

### Step 3: Create Topic Extraction Utils Module

- Create `agents/core/topic_extraction_utils.py`
- Move topic extraction utilities
- Consider integration with existing `topic_extraction.py`

### Step 4: Update Backward Compatibility Wrapper

- Update `agent_utils.py` to re-export from new modules
- Add deprecation comments for internal-only functions
- Ensure all existing imports continue to work

### Step 5: Update Dependent Files

- Update imports in 14+ files that use `extract_json_from_response`
- Test all affected agents
- Verify no breaking changes

### Step 6: Remove Unused Code

- Remove unused functions or mark as deprecated
- Clean up imports

## Files to Modify

**New Files:**

- `agents/core/json_parser.py` - JSON parsing and repair
- `agents/core/characteristics.py` - Characteristics generation
- `agents/core/topic_extraction_utils.py` - Topic extraction utilities
- `config/characteristics_fallbacks.py` or `data/characteristics_fallbacks.py` - Fallback data

**Modified Files:**

- `agents/core/agent_utils.py` - Converted to compatibility wrapper
- 14+ agent files - Update imports (if needed for clarity, but backward compatible)

**Files to Review:**

- `agents/core/topic_extraction.py` - Check for duplication/consolidation opportunities

## Testing Strategy

1. **Unit Tests**

   - Test JSON parser with various malformed JSON inputs
   - Test characteristics generation and parsing
   - Test topic extraction utilities

2. **Integration Tests**

   - Test all agents that use `extract_json_from_response`
   - Verify backward compatibility
   - Test error handling paths

3. **Regression Tests**

   - Ensure all existing functionality works
   - Verify no performance degradation

## Success Criteria

- Each module under 600 lines
- No breaking changes to external APIs
- Improved code organization and maintainability
- Reduced code duplication
- Better separation of concerns
- All tests passing