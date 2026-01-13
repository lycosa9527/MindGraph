# Hybrid Search Optimization: Parallel Execution & Deduplication

## Overview

This document explains how to optimize MindGraph's hybrid search to match Dify's approach by implementing:
1. **Parallel Execution**: Run vector and keyword searches simultaneously
2. **Deduplication**: Remove duplicate chunks before reranking

## Current Implementation (Sequential)

**MindGraph's Current Flow**:
```python
# Sequential execution - SLOW
vector_ids = self.vector_search(...)      # Wait for this to complete
keyword_results = self.keyword_search(...)  # Then wait for this
# Combine results...
```

**Problem**: If vector search takes 200ms and keyword search takes 150ms, total time = 350ms

## Dify's Approach (Parallel)

**Dify's Flow**:
```python
# Parallel execution - FAST
with ThreadPoolExecutor(max_workers=2) as executor:
    futures = []
    futures.append(executor.submit(vector_search, ...))
    futures.append(executor.submit(keyword_search, ...))
    # Wait for both to complete
    for future in as_completed(futures):
        results.extend(future.result())
```

**Benefit**: If vector search takes 200ms and keyword search takes 150ms, total time = max(200ms, 150ms) = 200ms (saves 150ms!)

## Why Deduplication is Needed

When doing hybrid search, the same chunk can appear in both results:

**Example**:
- Query: "Python programming"
- Vector search returns: [chunk_1, chunk_2, chunk_3]
- Keyword search returns: [chunk_2, chunk_4, chunk_5]

**Without deduplication**: chunk_2 appears twice, gets double-weighted, and wastes rerank API calls

**With deduplication**: [chunk_1, chunk_2, chunk_3, chunk_4, chunk_5] - each chunk appears once

## Dify's Deduplication Logic

Dify deduplicates based on:
1. **For Dify documents**: Use `metadata["doc_id"]` as unique key, keep highest score
2. **For other documents**: Use `(provider, page_content)` as unique key, keep first occurrence

**Key Points**:
- Preserves order of first appearance
- For duplicates with scores, keeps the one with higher score
- O(n) time complexity using dictionary

## Implementation Plan

### Step 1: Add Parallel Execution

**Location**: `services/rag_service.py:hybrid_search()`

**Changes**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def hybrid_search(self, ...):
    # Run both searches in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(self.vector_search, db, user_id, query, top_k * 2)
        keyword_future = executor.submit(
            lambda: self.keyword_search.keyword_search(db, user_id, query, top_k * 2)
        )
        
        # Wait for both to complete
        vector_ids = vector_future.result()
        keyword_results = keyword_future.result()
    
    # Rest of the logic...
```

### Step 2: Add Deduplication

**Location**: `services/rag_service.py` (new method)

**Implementation**:
```python
def _deduplicate_chunks(
    self, 
    chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Deduplicate chunks by chunk_id, keeping highest score.
    
    Args:
        chunks: List of chunk dicts with 'id' and 'score' keys
        
    Returns:
        Deduplicated list preserving first-seen order
    """
    if not chunks:
        return chunks
    
    seen = {}  # chunk_id -> chunk dict
    order = []  # Preserve order
    
    for chunk in chunks:
        chunk_id = chunk.get("id") or chunk.get("chunk_id")
        if not chunk_id:
            continue
            
        if chunk_id not in seen:
            seen[chunk_id] = chunk
            order.append(chunk_id)
        else:
            # Keep the one with higher score
            old_score = seen[chunk_id].get("score", 0.0)
            new_score = chunk.get("score", 0.0)
            if new_score > old_score:
                seen[chunk_id] = chunk
    
    return [seen[chunk_id] for chunk_id in order]
```

### Step 3: Update Hybrid Search Flow

**New Flow**:
```python
def hybrid_search(self, ...):
    # 1. Run searches in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(...)
        keyword_future = executor.submit(...)
        vector_ids = vector_future.result()
        keyword_results = keyword_future.result()
    
    # 2. Combine results with scores
    combined_chunks = []
    # Add vector results with scores
    for i, chunk_id in enumerate(vector_ids):
        combined_chunks.append({
            "id": chunk_id,
            "score": 1.0 - (i / max(len(vector_ids), 1)),
            "source": "vector"
        })
    # Add keyword results with scores
    for result in keyword_results:
        combined_chunks.append({
            "id": result["chunk_id"],
            "score": result["score"],
            "source": "keyword"
        })
    
    # 3. Deduplicate before combining scores
    deduplicated = self._deduplicate_chunks(combined_chunks)
    
    # 4. Recalculate combined scores with weights
    final_scores = {}
    for chunk in deduplicated:
        chunk_id = chunk["id"]
        if chunk["source"] == "vector":
            final_scores[chunk_id] = final_scores.get(chunk_id, 0.0) + weights["vector"] * chunk["score"]
        else:
            final_scores[chunk_id] = final_scores.get(chunk_id, 0.0) + weights["keyword"] * chunk["score"]
    
    # 5. Sort and return top K
    sorted_chunks = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_id for chunk_id, _ in sorted_chunks[:top_k]]
```

### Step 4: Update retrieve_context() to Deduplicate Before Reranking

**Location**: `services/rag_service.py:retrieve_context()`

**Changes**:
```python
def retrieve_context(self, ...):
    # Get chunk IDs from search
    chunk_ids = self.hybrid_search(...)  # Already deduplicated
    
    # Lookup chunks
    chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()
    
    # Extract texts
    texts = [chunk.text for chunk in chunks]
    
    # Deduplicate texts (in case same chunk appears multiple times)
    # This shouldn't happen after hybrid_search deduplication, but safety check
    seen_texts = {}
    unique_texts = []
    for chunk in chunks:
        if chunk.text not in seen_texts:
            seen_texts[chunk.text] = chunk.id
            unique_texts.append(chunk.text)
    
    # Apply reranking
    if self.use_rerank_model and len(unique_texts) > 1:
        reranked = self.rerank_client.rerank(...)
        return [item["document"] for item in reranked]
    
    return unique_texts[:top_k]
```

## Performance Benefits

**Before (Sequential)**:
- Vector search: 200ms
- Keyword search: 150ms
- **Total: 350ms**

**After (Parallel)**:
- Vector search: 200ms (parallel)
- Keyword search: 150ms (parallel)
- **Total: 200ms (saves 150ms = 43% faster)**

**With Deduplication**:
- Prevents double-processing same chunks
- Reduces rerank API calls (cost savings)
- More accurate scoring (no double-weighting)

## Testing

1. **Performance Test**: Measure time before/after parallel execution
2. **Deduplication Test**: Verify chunks appear only once
3. **Score Test**: Verify scores are correct after deduplication
4. **Integration Test**: Verify end-to-end retrieval still works

## Configuration

Add optional config to control parallel execution:
```python
# config/settings.py
RETRIEVAL_PARALLEL_WORKERS = int(os.getenv("RETRIEVAL_PARALLEL_WORKERS", "2"))
```

## Notes

- ThreadPoolExecutor is thread-safe and works well for I/O-bound operations (DB queries, API calls)
- Deduplication should happen BEFORE reranking to avoid wasting API calls
- Preserve order of first appearance for consistent results
- Keep highest score when duplicates found (better relevance)
