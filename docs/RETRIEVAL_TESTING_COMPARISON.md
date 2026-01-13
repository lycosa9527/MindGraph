# Retrieval Testing Comparison: MindGraph vs Dify

## ✅ Yes, MindGraph Has Retrieval Testing!

Both MindGraph and Dify have retrieval testing features. Here's a detailed comparison:

## Feature Comparison

| Feature | MindGraph | Dify | Notes |
|---------|-----------|------|-------|
| **API Endpoint** | ✅ `/api/knowledge-space/retrieval-test` | ✅ `/datasets/<id>/hit-testing` | Both have endpoints |
| **Frontend UI** | ✅ `RetrievalTest.vue` component | ✅ Built-in UI | Both have UI |
| **Test Methods** | ✅ semantic, keyword, hybrid | ✅ semantic, hybrid, keyword, full-text | Similar |
| **Timing Metrics** | ✅ embedding_ms, search_ms, rerank_ms, total_ms | ⚠️ Basic timing | MindGraph has more detailed metrics |
| **Stats** | ✅ chunks_searched, before_rerank, after_rerank | ⚠️ Basic stats | MindGraph has better stats |
| **Score Display** | ✅ Shows scores with color coding | ✅ Shows scores | Both display scores |
| **Query Recording** | ❌ Not recorded | ✅ Records in `DatasetQuery` table | Dify tracks queries for analytics |
| **Metadata Filtering** | ❌ Not supported in test | ✅ Supports metadata filtering | Dify more advanced |
| **Image Queries** | ❌ Text only | ✅ Supports `attachment_ids` | Dify supports multimodal |
| **External KB** | ❌ Not supported | ✅ External knowledge base testing | Dify more comprehensive |
| **Child Chunks** | ❌ Not displayed | ✅ Shows hierarchical child chunks | Dify shows more detail |
| **Reranking Modes** | ✅ Uses new reranking_mode config | ✅ Configurable reranking_mode | Both support modes |

## MindGraph's Retrieval Testing

### API Endpoint

```python
POST /api/knowledge-space/retrieval-test

Request:
{
    "query": "test query",
    "method": "hybrid",  # semantic, keyword, hybrid
    "top_k": 5,
    "score_threshold": 0.0
}

Response:
{
    "query": "test query",
    "method": "hybrid",
    "results": [
        {
            "chunk_id": 1,
            "text": "chunk content...",
            "score": 0.85,
            "document_id": 1,
            "document_name": "document.pdf",
            "chunk_index": 0,
            "start_char": 0,
            "end_char": 500,
            "metadata": {}
        }
    ],
    "timing": {
        "total_ms": 250.5,
        "embedding_ms": 120.3,
        "search_ms": 80.2,
        "rerank_ms": 50.0
    },
    "stats": {
        "total_chunks_searched": 10,
        "chunks_before_rerank": 8,
        "chunks_after_rerank": 5,
        "chunks_filtered_by_threshold": 3
    }
}
```

### Features

✅ **Detailed Timing Metrics**:
- Embedding generation time
- Search execution time
- Reranking time
- Total time

✅ **Comprehensive Stats**:
- Total chunks searched
- Chunks before/after reranking
- Filtered by threshold

✅ **Frontend UI**:
- Form for query input
- Method selection (semantic/keyword/hybrid)
- Top K and score threshold configuration
- Results table with color-coded scores
- Timing display

## Dify's Hit Testing

### API Endpoint

```python
POST /datasets/<dataset_id>/hit-testing

Request:
{
    "query": "test query",
    "retrieval_model": {
        "search_method": "hybrid_search",
        "reranking_enable": true,
        "reranking_mode": "reranking_model",
        "top_k": 4,
        "score_threshold_enabled": true,
        "score_threshold": 0.5,
        "weights": {...},
        "metadata_filtering_conditions": {...}
    },
    "attachment_ids": ["image_id"]  # Optional
}

Response:
{
    "query": {"content": "test query"},
    "records": [
        {
            "segment": {
                "id": "segment_id",
                "content": "segment content...",
                "document": {...},
                "score": 0.85,
                ...
            },
            "child_chunks": [
                {"id": "chunk_id", "content": "...", "score": 0.9}
            ],
            "files": [...]
        }
    ]
}
```

### Features

✅ **Query Recording**: Records queries in `DatasetQuery` table for analytics
✅ **Metadata Filtering**: Supports filtering by metadata conditions
✅ **Multimodal**: Supports image queries via `attachment_ids`
✅ **External KB**: Can test external knowledge bases
✅ **Hierarchical**: Shows child chunks within segments
✅ **Configurable**: Full retrieval model configuration

## Key Differences

### MindGraph Advantages

1. **Better Timing Metrics**: More detailed breakdown (embedding, search, rerank)
2. **Better Stats**: Shows chunks before/after reranking, filtered counts
3. **Simpler UI**: Cleaner, more focused interface
4. **Color-Coded Scores**: Visual score indicators (green/yellow/gray)

### Dify Advantages

1. **Query Analytics**: Records queries for tracking and analysis
2. **Metadata Filtering**: Can filter by document metadata in tests
3. **Multimodal**: Supports image queries
4. **External KB**: Can test external knowledge bases
5. **Hierarchical Display**: Shows child chunks within segments
6. **More Configurable**: Full retrieval model configuration

## Recommendations

### For MindGraph

1. ✅ **Keep current implementation** - It's good!
2. ⚠️ **Add query recording** (optional) - For analytics
3. ⚠️ **Add metadata filtering** (optional) - For advanced testing
4. ⚠️ **Update to use new reranking_mode** - Already done ✅

### Current Status

✅ **Retrieval testing exists and works well**
✅ **Updated to use new reranking_mode** (Dify's approach)
✅ **Good timing metrics and stats**
✅ **Functional frontend UI**

## Summary

**Yes, MindGraph has retrieval testing just like Dify!**

- ✅ Both have API endpoints
- ✅ Both have frontend UI
- ✅ Both support multiple search methods
- ✅ Both show results with scores

**MindGraph's advantages**:
- More detailed timing metrics
- Better stats display
- Simpler, cleaner UI

**Dify's advantages**:
- Query recording/analytics
- Metadata filtering
- Multimodal support
- External KB testing

**Conclusion**: MindGraph's retrieval testing is **good and functional**. Dify has more advanced features, but MindGraph's implementation is solid for most use cases.
