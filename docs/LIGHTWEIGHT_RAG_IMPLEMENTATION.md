# Lightweight RAG System Implementation Guide

**Goal**: Implement a simple, file-based RAG system for MindGraph - no Redis, no servers, just like SQLite!

---

## Table of Contents

1. [Lightweight RAG Options](#lightweight-rag-options)
2. [Recommended: ChromaDB](#recommended-chromadb)
3. [Alternative: LanceDB](#alternative-lancedb)
4. [Alternative: DuckDB + VSS](#alternative-duckdb--vss)
5. [Implementation Guide](#implementation-guide)
6. [Educational Content Setup](#educational-content-setup)
7. [Integration with Voice Agent](#integration-with-voice-agent)

---

## Lightweight RAG Options

### Comparison Table

| Solution | Storage | Size | Complexity | Performance | Best For |
|----------|---------|------|------------|-------------|----------|
| **ChromaDB** | SQLite | ~5MB | ⭐ Easy | Good | Prototypes, small projects |
| **LanceDB** | File-based | ~10MB | ⭐⭐ Medium | Excellent | Production-ready small projects |
| **DuckDB+VSS** | File-based | ~30MB | ⭐⭐⭐ Advanced | Excellent | SQL lovers |
| **FAISS+SQLite** | Hybrid | ~20MB | ⭐⭐ Medium | Good | Need FAISS features |
| **txtai** | SQLite | ~15MB | ⭐ Easy | Good | All-in-one solution |

### Why Not These?

❌ **Pinecone/Weaviate/Qdrant** - Require servers, overkill for small projects  
❌ **Milvus** - Heavy, complex setup  
❌ **Redis** - Requires Redis server  
❌ **Elasticsearch** - Heavy infrastructure  

---

## Recommended: ChromaDB + Qwen Embeddings

**ChromaDB** is the "SQLite of vector databases" - perfect for your needs!

### Why ChromaDB + Qwen?

✅ **File-based** - Everything stored in local files  
✅ **No server required** - Just `pip install chromadb`  
✅ **SQLite backend** - Uses SQLite under the hood  
✅ **Python native** - Easy to use  
✅ **Qwen embeddings** - Superior quality for Chinese + multilingual content  
✅ **Affordable** - 0.0005元/1K tokens (~$0.00007) + 1M tokens free  
✅ **Metadata filtering** - Query by grade, subject, etc.  
✅ **Persistent** - Survives restarts  
✅ **Fast enough** - Good for thousands of documents  

### Installation

```bash
pip install chromadb openai
```

**Note**: We use OpenAI SDK for Qwen's OpenAI-compatible API. ChromaDB works seamlessly with it!

### Basic Usage with Qwen Embeddings

```python
import chromadb
from chromadb.utils import embedding_functions

# Create Qwen embedding function
qwen_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key="your-qwen-api-key",  # Or from os.getenv("DASHSCOPE_API_KEY")
    api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model_name="text-embedding-v4"
)

# Create client (saves to disk)
client = chromadb.PersistentClient(path="./chroma_db")

# Create collection with Qwen embeddings
collection = client.get_or_create_collection(
    name="educational_content",
    embedding_function=qwen_ef,
    metadata={"description": "K12 educational materials"}
)

# Add documents (embeddings generated via Qwen API)
collection.add(
    documents=[
        "光合作用是植物将光能转化为化学能的过程。",  # Chinese support!
        "Photosynthesis is the process by which plants convert light energy.",
        "细胞分裂产生两个相同的子细胞。"
    ],
    metadatas=[
        {"subject": "biology", "grade": 7, "topic": "photosynthesis"},
        {"subject": "biology", "grade": 8, "topic": "cell_division"},
        {"subject": "biology", "grade": 7, "topic": "photosynthesis"}
    ],
    ids=["doc1", "doc2", "doc3"]
)

# Query (works in Chinese and English!)
results = collection.query(
    query_texts=["植物如何制造能量？"],  # Chinese query
    n_results=3
)

print(results['documents'][0])  # Top result
```

### Qwen Embedding Benefits

**Why Qwen text-embedding-v4 is excellent for MindGraph**:

1. **Superior Chinese Support** - Trained on massive Chinese corpus
2. **100+ Languages** - Including Japanese, Korean, German, French, etc.
3. **Free Quota** - 1M tokens free (enough for 30K-50K documents)
4. **Affordable** - Only ¥0.0005/1K tokens (~$0.00007) after free tier
5. **High Quality** - MTEB score: 71.58, CMTEB score: 71.99 (top-tier)
6. **Flexible Dimensions** - Choose from 64 to 2048 dimensions
7. **Fast** - Batch processing support, optimized for speed

### Cost Example

```python
# For 10,000 K12 educational documents (~500 words each = ~700 tokens):
total_tokens = 10,000 × 700 = 7,000,000 tokens

# One-time embedding cost:
free_tokens = 1,000,000  # Free quota
paid_tokens = 6,000,000  # Remaining
cost = 6,000 × ¥0.0005 = ¥3 (~$0.42 USD)

# Ongoing query cost (per 1000 queries):
query_tokens = 1,000 × 50 = 50,000 tokens
query_cost = 50 × ¥0.0005 = ¥0.025 (~$0.003 USD)

# Total: ~¥3 to embed 10K docs + ¥0.025 per 1000 queries
# Extremely affordable for high quality!
```

### File Structure

```
your_project/
├── data/
│   └── rag/                    # ChromaDB storage (like SQLite)
│       ├── chroma.sqlite3      # Metadata storage
│       └── index/              # Vector indexes (Qwen embeddings)
├── services/
│   └── lightweight_rag.py      # RAG implementation
├── scripts/
│   └── setup_rag.py           # Populate content
├── .env                        # API keys
└── requirements.txt
```

**Total size**: ~5-50MB depending on content (similar to SQLite!)

---

## ChromaDB Implementation for MindGraph

### Complete RAG System with Qwen Embeddings

```python
"""
Lightweight RAG System for MindGraph
Uses ChromaDB + Qwen Embeddings for superior Chinese/multilingual support

@author lycosa9527
@made_by MindSpring Team
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger('RAG')


class LightweightRAGSystem:
    """
    Simple, file-based RAG system using ChromaDB + Qwen Embeddings.
    Perfect for educational projects with Chinese/multilingual content.
    
    Features:
    - No server required
    - SQLite-based storage
    - Qwen text-embedding-v4 (best quality)
    - Supports 100+ languages including Chinese
    - Metadata filtering (grade, subject, etc.)
    - Persistent across restarts
    - Affordable: 0.0005元/1K tokens + 1M free
    """
    
    def __init__(
        self, 
        data_dir: str = "./data/rag",
        api_key: Optional[str] = None,
        use_local_embeddings: bool = False
    ):
        """
        Initialize RAG system.
        
        Args:
            data_dir: Directory to store database files (default: ./data/rag)
            api_key: Qwen API key (or set DASHSCOPE_API_KEY env var)
            use_local_embeddings: If True, use free local embeddings instead of Qwen
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.data_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Choose embedding function
        if use_local_embeddings:
            # Option 1: Local sentence-transformers (free, no API)
            logger.info("Using local embeddings (sentence-transformers)")
            self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        else:
            # Option 2: Qwen embeddings (better quality, small cost)
            logger.info("Using Qwen text-embedding-v4 (API-based)")
            api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY required for Qwen embeddings")
            
            self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model_name="text-embedding-v4",
                # dimensions=1024  # Can customize: 2048, 1536, 1024 (default), 768, 512, 256
            )
        
        # Create collections
        self.educational_collection = self._get_or_create_collection(
            "educational_content",
            "K12 educational materials, concepts, and explanations"
        )
        
        self.diagram_examples_collection = self._get_or_create_collection(
            "diagram_examples",
            "Successful diagram examples for reference"
        )
        
        logger.info(f"RAG system initialized at: {self.data_dir}")
        logger.info(f"Educational docs: {self.educational_collection.count()}")
        logger.info(f"Diagram examples: {self.diagram_examples_collection.count()}")
    
    def _get_or_create_collection(
        self,
        name: str,
        description: str
    ) -> chromadb.Collection:
        """Get or create a collection"""
        
        return self.client.get_or_create_collection(
            name=name,
            metadata={"description": description},
            embedding_function=self.embedding_function
        )
    
    # ===== ADD CONTENT =====
    
    def add_educational_content(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None
    ) -> None:
        """
        Add educational content to RAG system.
        
        Args:
            documents: List of text documents
            metadatas: List of metadata dicts (must include: subject, grade, topic)
            ids: Optional list of document IDs (auto-generated if not provided)
        
        Example:
            rag.add_educational_content(
                documents=["Photosynthesis is..."],
                metadatas=[{"subject": "biology", "grade": 7, "topic": "photosynthesis"}]
            )
        """
        
        if ids is None:
            # Auto-generate IDs
            start_id = self.educational_collection.count()
            ids = [f"edu_{start_id + i}" for i in range(len(documents))]
        
        self.educational_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(documents)} educational documents")
    
    def add_diagram_example(
        self,
        diagram_data: Dict,
        success_metrics: Dict,
        description: str
    ) -> str:
        """
        Add a successful diagram as an example.
        
        Args:
            diagram_data: Full diagram data
            success_metrics: Metrics like completion_score, accuracy, etc.
            description: Text description of the diagram
        
        Returns:
            Document ID
        """
        
        # Create searchable text from diagram
        searchable_text = self._diagram_to_text(diagram_data, description)
        
        doc_id = f"diagram_{diagram_data.get('type', 'unknown')}_{len(self.diagram_examples_collection.get()['ids'])}"
        
        self.diagram_examples_collection.add(
            documents=[searchable_text],
            metadatas=[{
                "diagram_type": diagram_data.get('type'),
                "center_topic": diagram_data.get('center', {}).get('text', 'unknown'),
                "node_count": len(diagram_data.get('children', [])),
                "success_score": success_metrics.get('score', 0),
                "grade": diagram_data.get('grade_level', 'unknown'),
                "subject": diagram_data.get('subject', 'unknown')
            }],
            ids=[doc_id]
        )
        
        logger.info(f"Added diagram example: {doc_id}")
        return doc_id
    
    def _diagram_to_text(self, diagram_data: Dict, description: str) -> str:
        """Convert diagram to searchable text"""
        
        parts = [
            f"Diagram Type: {diagram_data.get('type')}",
            f"Center: {diagram_data.get('center', {}).get('text', 'unknown')}",
            f"Description: {description}",
            "Nodes:"
        ]
        
        for node in diagram_data.get('children', [])[:10]:  # First 10 nodes
            if isinstance(node, dict):
                parts.append(f"- {node.get('text', node.get('label', str(node)))}")
            else:
                parts.append(f"- {node}")
        
        return "\n".join(parts)
    
    # ===== QUERY =====
    
    def query_educational_content(
        self,
        query: str,
        n_results: int = 5,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query educational content with optional filtering.
        
        Args:
            query: Search query
            n_results: Number of results to return
            grade: Filter by grade level (optional)
            subject: Filter by subject (optional)
            topic: Filter by topic (optional)
        
        Returns:
            {
                'documents': [[doc1, doc2, ...]],
                'metadatas': [[meta1, meta2, ...]],
                'distances': [[dist1, dist2, ...]],
                'ids': [[id1, id2, ...]]
            }
        """
        
        # Build where clause for filtering
        where = {}
        if grade is not None:
            where['grade'] = grade
        if subject is not None:
            where['subject'] = subject
        if topic is not None:
            where['topic'] = topic
        
        results = self.educational_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None
        )
        
        logger.debug(f"Query: '{query[:50]}...' | Results: {len(results['ids'][0])}")
        
        return results
    
    def find_similar_diagrams(
        self,
        query: str,
        diagram_type: Optional[str] = None,
        n_results: int = 3
    ) -> Dict[str, Any]:
        """
        Find similar diagram examples.
        
        Args:
            query: Description of what you're looking for
            diagram_type: Filter by diagram type (optional)
            n_results: Number of examples to return
        
        Returns:
            Similar diagram examples with metadata
        """
        
        where = {}
        if diagram_type:
            where['diagram_type'] = diagram_type
        
        results = self.diagram_examples_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None
        )
        
        return results
    
    # ===== UTILITIES =====
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        
        return {
            'educational_docs': self.educational_collection.count(),
            'diagram_examples': self.diagram_examples_collection.count(),
            'storage_path': str(self.data_dir),
            'collections': [
                'educational_content',
                'diagram_examples'
            ]
        }
    
    def reset(self, confirm: bool = False) -> None:
        """
        Reset RAG system (delete all data).
        Requires confirmation.
        """
        
        if not confirm:
            logger.warning("Reset requires confirm=True")
            return
        
        self.client.reset()
        logger.warning("RAG system reset - all data deleted")
    
    def backup(self, backup_path: str) -> None:
        """
        Backup RAG database.
        Simply copy the directory!
        """
        
        import shutil
        backup_path = Path(backup_path)
        
        if backup_path.exists():
            logger.warning(f"Backup path exists: {backup_path}")
            return
        
        shutil.copytree(self.data_dir, backup_path)
        logger.info(f"RAG backed up to: {backup_path}")


# ===== GLOBAL INSTANCE =====

# Initialize global RAG system
rag_system = LightweightRAGSystem(data_dir="./data/rag")
```

---

## PDF Processing for Educational Content

### Why PDF Processing Matters

**Your educational files are in PDF format!** We need to:
1. Extract text from PDFs
2. Clean and chunk the text
3. Embed via Qwen API
4. Store in ChromaDB

### PDF Library Setup

```bash
# Install PDF processing library (fastest and best)
pip install pymupdf

# Optional: For OCR (scanned PDFs with images)
pip install pytesseract pillow
```

### PDF Text Extraction

```python
"""
PDF Processing Utilities for MindGraph RAG System
Handles text extraction, chunking, and metadata extraction

@author lycosa9527
@made_by MindSpring Team
"""

import fitz  # PyMuPDF
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger('PDF_PROCESSOR')


class PDFProcessor:
    """
    Process PDF files for RAG ingestion.
    
    Features:
    - Fast text extraction (PyMuPDF)
    - Smart chunking by sections
    - Metadata extraction
    - OCR support (optional)
    - Batch processing
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize PDF processor.
        
        Args:
            chunk_size: Words per chunk (default: 500)
            chunk_overlap: Words to overlap between chunks (default: 50)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract all text from PDF.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted text as string
        """
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            logger.info(f"Extracting text from {pdf_path} ({len(doc)} pages)")
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += page_text
                
                if (page_num + 1) % 10 == 0:
                    logger.debug(f"Processed {page_num + 1}/{len(doc)} pages")
            
            doc.close()
            
            # Clean text
            text = self._clean_text(text)
            
            logger.info(f"✓ Extracted {len(text)} characters from {pdf_path}")
            return text
        
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove page numbers (common pattern)
        text = re.sub(r'\n\d+\n', '\n', text)
        # Strip
        text = text.strip()
        return text
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text
        
        Returns:
            List of text chunks
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk = ' '.join(words[i:i + self.chunk_size])
            
            # Skip very short chunks (end of document)
            if len(chunk.split()) > 50:
                chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
    
    def chunk_by_sections(self, text: str) -> List[Dict]:
        """
        Chunk text by natural sections (chapters, topics).
        Better for educational content!
        
        Returns:
            List of dicts with 'text' and 'section_info'
        """
        chunks = []
        
        # Split by common section headers
        # Patterns: "Chapter 1", "第一章", "1. Topic", "Section 1.1"
        sections = re.split(
            r'(?:Chapter|章节|第.*章|Section|§)\s*[\d一二三四五六七八九十]+',
            text
        )
        
        for i, section in enumerate(sections):
            section = section.strip()
            
            if len(section.split()) > 100:  # Skip tiny sections
                # Further chunk if too large
                if len(section.split()) > self.chunk_size:
                    sub_chunks = self.chunk_text(section)
                    for j, sub_chunk in enumerate(sub_chunks):
                        chunks.append({
                            'text': sub_chunk,
                            'section_number': i,
                            'sub_chunk': j,
                            'type': 'section_chunk'
                        })
                else:
                    chunks.append({
                        'text': section,
                        'section_number': i,
                        'type': 'section'
                    })
        
        logger.info(f"Created {len(chunks)} section-based chunks")
        return chunks
    
    def extract_metadata(self, pdf_path: str) -> Dict:
        """
        Extract PDF metadata.
        
        Returns:
            Dict with title, author, pages, etc.
        """
        try:
            doc = fitz.open(pdf_path)
            
            metadata = {
                'filename': Path(pdf_path).name,
                'filepath': pdf_path,
                'title': doc.metadata.get('title', Path(pdf_path).stem),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'creator': doc.metadata.get('creator', ''),
                'pages': len(doc),
                'file_size_mb': Path(pdf_path).stat().st_size / (1024 * 1024)
            }
            
            doc.close()
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to extract metadata from {pdf_path}: {e}")
            return {'filename': Path(pdf_path).name, 'filepath': pdf_path}
    
    def process_pdf_to_chunks(
        self,
        pdf_path: str,
        use_sections: bool = True
    ) -> Tuple[List[str], Dict]:
        """
        Complete pipeline: PDF → Text → Chunks.
        
        Args:
            pdf_path: Path to PDF
            use_sections: If True, chunk by sections (recommended)
        
        Returns:
            (chunks, metadata)
        """
        # Extract text
        text = self.extract_text(pdf_path)
        
        # Extract metadata
        metadata = self.extract_metadata(pdf_path)
        
        # Chunk
        if use_sections:
            chunk_dicts = self.chunk_by_sections(text)
            chunks = [c['text'] for c in chunk_dicts]
            # Add section info to metadata
            metadata['section_info'] = [
                {k: v for k, v in c.items() if k != 'text'}
                for c in chunk_dicts
            ]
        else:
            chunks = self.chunk_text(text)
        
        logger.info(f"✓ Processed {pdf_path}: {len(chunks)} chunks, {metadata['pages']} pages")
        
        return chunks, metadata


# Global instance
pdf_processor = PDFProcessor(chunk_size=500, chunk_overlap=50)
```

### Batch PDF Processing

```python
"""
Batch process multiple PDFs into RAG system
"""

from pathlib import Path
from typing import List
import logging

logger = logging.getLogger('PDF_BATCH')


def process_pdf_directory(
    pdf_dir: str,
    rag_system,
    grade_mapping: Dict[str, int] = None,
    subject_mapping: Dict[str, str] = None
) -> int:
    """
    Process all PDFs in a directory.
    
    Args:
        pdf_dir: Directory containing PDFs
        rag_system: LightweightRAGSystem instance
        grade_mapping: Map filename pattern → grade level
        subject_mapping: Map filename pattern → subject
    
    Returns:
        Total chunks added
    """
    
    pdf_dir = Path(pdf_dir)
    pdf_files = list(pdf_dir.glob("**/*.pdf"))
    
    logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    total_chunks = 0
    
    for pdf_path in pdf_files:
        try:
            logger.info(f"Processing {pdf_path.name}...")
            
            # Extract chunks and metadata
            chunks, pdf_metadata = pdf_processor.process_pdf_to_chunks(str(pdf_path))
            
            # Determine grade and subject from filename
            grade = _infer_grade(pdf_path.name, grade_mapping)
            subject = _infer_subject(pdf_path.name, subject_mapping)
            
            # Build metadata for each chunk
            chunk_ids = [f"{pdf_path.stem}_chunk_{i}" for i in range(len(chunks))]
            chunk_metadatas = [
                {
                    'source': pdf_metadata['filename'],
                    'source_path': pdf_metadata['filepath'],
                    'pages': pdf_metadata['pages'],
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'grade': grade,
                    'subject': subject,
                    'source_type': 'pdf',
                    'title': pdf_metadata.get('title', pdf_path.stem)
                }
                for i in range(len(chunks))
            ]
            
            # Add to RAG
            rag_system.add_educational_content(
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )
            
            total_chunks += len(chunks)
            logger.info(f"✓ Added {len(chunks)} chunks from {pdf_path.name}")
        
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            continue
    
    logger.info(f"✓ Total: {total_chunks} chunks from {len(pdf_files)} PDFs")
    return total_chunks


def _infer_grade(filename: str, mapping: Dict = None) -> int:
    """Infer grade level from filename"""
    
    if mapping:
        for pattern, grade in mapping.items():
            if pattern in filename.lower():
                return grade
    
    # Try to extract grade from filename
    # Patterns: "grade7", "7年级", "G7", etc.
    import re
    
    patterns = [
        r'grade[\s_-]?(\d+)',
        r'(\d+)年级',
        r'g(\d+)',
        r'七年级|初一' # Chinese grades
    ]
    
    grade_map = {
        '七年级': 7, '初一': 7,
        '八年级': 8, '初二': 8,
        '九年级': 9, '初三': 9
    }
    
    for pattern in patterns:
        match = re.search(pattern, filename.lower())
        if match:
            if match.group(0) in grade_map:
                return grade_map[match.group(0)]
            try:
                return int(match.group(1))
            except:
                pass
    
    return 0  # Unknown grade


def _infer_subject(filename: str, mapping: Dict = None) -> str:
    """Infer subject from filename"""
    
    if mapping:
        for pattern, subject in mapping.items():
            if pattern in filename.lower():
                return subject
    
    # Common subjects
    subjects = {
        'biology': ['biology', '生物'],
        'physics': ['physics', '物理'],
        'chemistry': ['chemistry', '化学'],
        'math': ['math', 'mathematics', '数学'],
        'english': ['english', '英语'],
        'chinese': ['chinese', '语文'],
        'history': ['history', '历史'],
        'geography': ['geography', '地理']
    }
    
    filename_lower = filename.lower()
    for subject, keywords in subjects.items():
        for keyword in keywords:
            if keyword in filename_lower:
                return subject
    
    return 'unknown'
```

---

## Educational Content Setup

### Populate with K12 Content from PDFs

```python
"""
Script to populate RAG system with educational PDF content.
Processes PDF textbooks and adds to ChromaDB with Qwen embeddings.

Run once to seed the database.
"""

import asyncio
from services.lightweight_rag import rag_system
from services.pdf_processor import pdf_processor, process_pdf_directory
import logging

logger = logging.getLogger(__name__)


async def populate_educational_content_from_pdfs():
    """
    Populate RAG from PDF files.
    Recommended: Organize PDFs by grade and subject
    
    Directory structure:
    textbooks/
    ├── grade7/
    │   ├── biology_grade7.pdf
    │   ├── physics_grade7.pdf
    │   └── chemistry_grade7.pdf
    ├── grade8/
    │   └── ...
    └── grade9/
        └── ...
    """
    
    # Process PDF directory
    logger.info("Processing PDFs from textbooks directory...")
    
    # Method 1: Batch process all PDFs in directory
    total_chunks = process_pdf_directory(
        pdf_dir="./data/textbooks",
        rag_system=rag_system,
        grade_mapping={
            'grade7': 7,
            'grade8': 8,
            'grade9': 9,
            '七年级': 7,
            '八年级': 8,
            '九年级': 9
        },
        subject_mapping={
            'biology': 'biology',
            'physics': 'physics',
            'chemistry': 'chemistry',
            '生物': 'biology',
            '物理': 'physics',
            '化学': 'chemistry'
        }
    )
    
    logger.info(f"✓ Processed {total_chunks} chunks from PDF files")
    
    # Method 2: Process individual PDFs with custom metadata
    await process_individual_pdfs()
    
    # Print statistics
    stats = rag_system.get_stats()
    logger.info(f"RAG System Stats: {stats}")


async def process_individual_pdfs():
    """
    Process specific PDFs with custom metadata.
    Use this when you need fine-grained control.
    """
    
    pdfs_to_process = [
        {
            'path': './data/textbooks/biology_grade7.pdf',
            'metadata': {
                'subject': 'biology',
                'grade': 7,
                'title': 'Grade 7 Biology Textbook',
                'topic': 'life_science',
                'publisher': 'Education Press',
                'year': 2024
            }
        },
        {
            'path': './data/textbooks/physics_grade8.pdf',
            'metadata': {
                'subject': 'physics',
                'grade': 8,
                'title': 'Grade 8 Physics Textbook',
                'topic': 'mechanics',
                'publisher': 'Science Press',
                'year': 2024
            }
        }
    ]
    
    for pdf_info in pdfs_to_process:
        try:
            # Extract chunks
            chunks, pdf_metadata = pdf_processor.process_pdf_to_chunks(
                pdf_info['path'],
                use_sections=True  # Chunk by chapters/sections
            )
            
            # Build metadata for each chunk
            chunk_ids = [f"{pdf_info['metadata']['subject']}_{pdf_info['metadata']['grade']}_chunk_{i}" 
                        for i in range(len(chunks))]
            
            chunk_metadatas = [
                {
                    **pdf_info['metadata'],
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'source_type': 'pdf',
                    'pages': pdf_metadata['pages']
                }
                for i in range(len(chunks))
            ]
            
            # Add to RAG
            rag_system.add_educational_content(
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )
            
            logger.info(f"✓ Added {len(chunks)} chunks from {pdf_info['path']}")
        
        except Exception as e:
            logger.error(f"Failed to process {pdf_info['path']}: {e}")


async def populate_educational_content():
    """
    Populate RAG with K12 educational content.
    
    Sources:
    - Science concepts
    - Math concepts
    - Social studies
    - Language arts
    """
    
    # Biology concepts (Grade 6-8)
    biology_docs = [
        # Photosynthesis
        {
            "text": "Photosynthesis is the process by which plants use sunlight, water, and carbon dioxide to create oxygen and energy in the form of sugar (glucose). It occurs in the chloroplasts of plant cells.",
            "metadata": {"subject": "biology", "grade": 7, "topic": "photosynthesis", "concept": "process"}
        },
        {
            "text": "Chlorophyll is the green pigment in plants that absorbs light energy for photosynthesis. It is located in the chloroplasts and gives plants their green color.",
            "metadata": {"subject": "biology", "grade": 7, "topic": "photosynthesis", "concept": "chlorophyll"}
        },
        {
            "text": "The equation for photosynthesis is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2. This means carbon dioxide and water are converted into glucose and oxygen.",
            "metadata": {"subject": "biology", "grade": 8, "topic": "photosynthesis", "concept": "equation"}
        },
        
        # Cell Biology
        {
            "text": "Mitosis is the process of cell division that results in two identical daughter cells. It has four main phases: prophase, metaphase, anaphase, and telophase.",
            "metadata": {"subject": "biology", "grade": 8, "topic": "cell_division", "concept": "mitosis"}
        },
        {
            "text": "The cell membrane is a protective barrier that controls what enters and exits the cell. It is selectively permeable, meaning it only allows certain substances to pass through.",
            "metadata": {"subject": "biology", "grade": 6, "topic": "cell_structure", "concept": "membrane"}
        },
        
        # Ecosystems
        {
            "text": "A food chain shows how energy flows from one organism to another. It starts with producers (plants), moves to primary consumers (herbivores), then to secondary consumers (carnivores).",
            "metadata": {"subject": "biology", "grade": 6, "topic": "ecosystems", "concept": "food_chain"}
        },
        {
            "text": "Decomposers like bacteria and fungi break down dead organisms and return nutrients to the soil. They play a crucial role in nutrient cycling.",
            "metadata": {"subject": "biology", "grade": 6, "topic": "ecosystems", "concept": "decomposers"}
        }
    ]
    
    # Earth Science (Grade 6-8)
    earth_science_docs = [
        {
            "text": "The water cycle describes how water moves through Earth's systems. It includes evaporation, condensation, precipitation, and collection. Water constantly cycles between the atmosphere, land, and oceans.",
            "metadata": {"subject": "earth_science", "grade": 6, "topic": "water_cycle", "concept": "process"}
        },
        {
            "text": "Evaporation is when water changes from liquid to gas (water vapor). It happens when the sun heats water in oceans, lakes, and rivers.",
            "metadata": {"subject": "earth_science", "grade": 6, "topic": "water_cycle", "concept": "evaporation"}
        },
        {
            "text": "Plate tectonics is the theory that Earth's crust is divided into large plates that move slowly over the mantle. This movement causes earthquakes, volcanoes, and mountain formation.",
            "metadata": {"subject": "earth_science", "grade": 7, "topic": "geology", "concept": "plate_tectonics"}
        },
        {
            "text": "Climate change refers to long-term changes in Earth's climate patterns. It is primarily caused by increased greenhouse gases from human activities, leading to global warming.",
            "metadata": {"subject": "earth_science", "grade": 8, "topic": "climate", "concept": "climate_change"}
        }
    ]
    
    # Physics concepts (Grade 6-8)
    physics_docs = [
        {
            "text": "Force is a push or pull that can change an object's motion. It is measured in Newtons (N). Forces can cause objects to speed up, slow down, or change direction.",
            "metadata": {"subject": "physics", "grade": 6, "topic": "forces", "concept": "force"}
        },
        {
            "text": "Friction is a force that opposes motion between two surfaces in contact. It can be helpful (allowing us to walk) or problematic (slowing down machines).",
            "metadata": {"subject": "physics", "grade": 6, "topic": "forces", "concept": "friction"}
        },
        {
            "text": "Energy is the ability to do work. It exists in many forms: kinetic (motion), potential (stored), thermal (heat), chemical, electrical, and more. Energy can be transformed from one form to another.",
            "metadata": {"subject": "physics", "grade": 7, "topic": "energy", "concept": "energy_basics"}
        },
        {
            "text": "Newton's First Law states that an object at rest stays at rest, and an object in motion stays in motion, unless acted upon by an external force. This is also called the law of inertia.",
            "metadata": {"subject": "physics", "grade": 8, "topic": "forces", "concept": "newtons_laws"}
        }
    ]
    
    # Chemistry concepts (Grade 7-8)
    chemistry_docs = [
        {
            "text": "An atom is the smallest unit of matter that retains the properties of an element. It consists of a nucleus (protons and neutrons) and electrons orbiting around it.",
            "metadata": {"subject": "chemistry", "grade": 7, "topic": "atoms", "concept": "atom_structure"}
        },
        {
            "text": "A chemical reaction occurs when substances interact to form new substances with different properties. Signs of a chemical reaction include color change, temperature change, gas production, or precipitate formation.",
            "metadata": {"subject": "chemistry", "grade": 8, "topic": "reactions", "concept": "chemical_reactions"}
        },
        {
            "text": "The periodic table organizes elements by atomic number and properties. Elements in the same column (group) have similar chemical properties.",
            "metadata": {"subject": "chemistry", "grade": 8, "topic": "periodic_table", "concept": "organization"}
        }
    ]
    
    # Combine all documents
    all_docs = biology_docs + earth_science_docs + physics_docs + chemistry_docs
    
    # Add to RAG system
    documents = [doc["text"] for doc in all_docs]
    metadatas = [doc["metadata"] for doc in all_docs]
    
    rag_system.add_educational_content(
        documents=documents,
        metadatas=metadatas
    )
    
    logger.info(f"✓ Added {len(all_docs)} educational documents to RAG")
    
    # Add thinking map best practices
    thinking_map_docs = [
        {
            "text": "Circle Maps are used to define concepts and explore what you already know. The center contains the topic, and the surrounding circles contain observations, facts, and characteristics.",
            "metadata": {"subject": "thinking_maps", "grade": 0, "topic": "circle_map", "concept": "purpose"}
        },
        {
            "text": "Bubble Maps are used to describe qualities and attributes using adjectives. The center contains the object or topic being described, and bubbles contain descriptive words.",
            "metadata": {"subject": "thinking_maps", "grade": 0, "topic": "bubble_map", "concept": "purpose"}
        },
        {
            "text": "Flow Maps show sequences, processes, and procedures. They help visualize the steps in a process and understand cause-and-effect relationships over time.",
            "metadata": {"subject": "thinking_maps", "grade": 0, "topic": "flow_map", "concept": "purpose"}
        },
        {
            "text": "Double Bubble Maps are used to compare and contrast two things. Shared similarities go in the middle overlapping bubbles, while differences go in the outer bubbles.",
            "metadata": {"subject": "thinking_maps", "grade": 0, "topic": "double_bubble_map", "concept": "purpose"}
        }
    ]
    
    documents = [doc["text"] for doc in thinking_map_docs]
    metadatas = [doc["metadata"] for doc in thinking_map_docs]
    
    rag_system.add_educational_content(
        documents=documents,
        metadatas=metadatas
    )
    
    logger.info(f"✓ Added {len(thinking_map_docs)} thinking map documents to RAG")
    
    # Print statistics
    stats = rag_system.get_stats()
    logger.info(f"RAG System Stats: {stats}")


if __name__ == "__main__":
    # Option 1: Populate from PDFs (recommended - your use case!)
    asyncio.run(populate_educational_content_from_pdfs())
    
    # Option 2: Populate from text strings (if you have extracted text)
    # asyncio.run(populate_educational_content())
```

### Directory Structure for PDFs

```
MindGraph/
├── data/
│   ├── textbooks/           # Put your PDF files here!
│   │   ├── grade7/
│   │   │   ├── biology_grade7_textbook.pdf
│   │   │   ├── physics_grade7_textbook.pdf
│   │   │   └── chemistry_grade7_textbook.pdf
│   │   ├── grade8/
│   │   │   ├── biology_grade8_textbook.pdf
│   │   │   └── ...
│   │   └── grade9/
│   │       └── ...
│   │
│   └── rag/                 # ChromaDB storage (auto-created)
│       ├── chroma.sqlite3
│       └── index/
│
├── services/
│   ├── lightweight_rag.py   # RAG system
│   └── pdf_processor.py     # PDF processing
│
└── scripts/
    └── setup_rag.py         # Populate from PDFs
```

### Run the Setup Script

```bash
# First time setup - process PDFs
python scripts/setup_rag.py

# Output:
# Processing PDFs from textbooks directory...
# Extracting text from biology_grade7_textbook.pdf (156 pages)
# ✓ Extracted 245,832 characters from biology_grade7_textbook.pdf
# Created 125 section-based chunks
# ✓ Added 125 chunks from biology_grade7_textbook.pdf
# Processing physics_grade7_textbook.pdf...
# ...
# ✓ Total: 487 chunks from 5 PDFs
# RAG System Stats: {'educational_docs': 487, 'diagram_examples': 0, ...}
```

---

## Integration with Voice Agent

### RAG Query Tool

```python
"""
RAG Query Tool for Voice Agent
Allows voice agent to access educational knowledge base
"""

from services.lightweight_rag import rag_system


class RAGQueryTool:
    """
    Tool for querying educational knowledge base.
    Voice agent can use this to get accurate information.
    """
    
    name = "rag_query"
    description = "Query the educational knowledge base for concepts, definitions, and explanations"
    
    parameters = {
        "query": "string - what to search for",
        "grade": "int (optional) - filter by grade level",
        "subject": "string (optional) - filter by subject (biology, physics, etc.)",
        "n_results": "int - number of results (default: 3)"
    }
    
    async def execute(
        self,
        query: str,
        grade: int = None,
        subject: str = None,
        n_results: int = 3
    ) -> dict:
        """
        Query RAG system.
        
        Returns:
        {
            'success': True,
            'results': [
                {
                    'content': 'Photosynthesis is...',
                    'metadata': {'subject': 'biology', 'grade': 7, ...},
                    'relevance': 0.85
                }
            ],
            'summary': 'Found 3 relevant documents about photosynthesis'
        }
        """
        
        try:
            # Query RAG
            results = rag_system.query_educational_content(
                query=query,
                n_results=n_results,
                grade=grade,
                subject=subject
            )
            
            # Format results
            formatted_results = []
            if results['ids'][0]:  # Has results
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'relevance': 1 - results['distances'][0][i],  # Convert distance to similarity
                        'id': results['ids'][0][i]
                    })
            
            # Generate summary
            summary = f"Found {len(formatted_results)} relevant document{'s' if len(formatted_results) != 1 else ''}"
            if subject:
                summary += f" in {subject}"
            if grade:
                summary += f" for grade {grade}"
            
            return {
                'success': True,
                'results': formatted_results,
                'summary': summary,
                'query': query
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
```

### Voice Agent Usage Example

```python
# In Brain Agent's tool list
tools = [
    RAGQueryTool(),
    WebSearchTool(),
    DiagramAddNodesTool(),
    # ... other tools
]

# Example conversation:
# User: "What is photosynthesis?"

# Brain Agent ReAct loop:
# REASON: "User asking about a science concept. Should check knowledge base first."
# ACT: rag_query(query="photosynthesis", subject="biology")
# OBSERVE: Got definition from knowledge base
# ACT: final_answer

# Omni speaks: "According to our knowledge base, photosynthesis is the process 
# by which plants use sunlight, water, and carbon dioxide to create oxygen and 
# energy in the form of sugar..."
```

---

## Alternative: LanceDB

### If You Want Better Performance

**LanceDB** is like ChromaDB but faster for larger datasets.

```bash
pip install lancedb
```

```python
import lancedb

# Create database (file-based, like SQLite)
db = lancedb.connect("./data/lancedb")

# Create table
table = db.create_table(
    "educational_content",
    data=[
        {
            "text": "Photosynthesis is...",
            "metadata": {"subject": "biology", "grade": 7}
        }
    ]
)

# Query
results = table.search("How do plants make energy?").limit(5).to_list()
```

**Pros**:
- Faster than ChromaDB
- Better for production
- Still file-based

**Cons**:
- Slightly more complex
- Larger file size

---

## Alternative: DuckDB + VSS Extension

### For SQL Lovers

If you prefer SQL interface:

```bash
pip install duckdb duckdb-vss
```

```python
import duckdb

# Create database
conn = duckdb.connect('./data/educational.duckdb')

# Install VSS extension
conn.execute("INSTALL vss;")
conn.execute("LOAD vss;")

# Create table with vector column
conn.execute("""
    CREATE TABLE educational_content (
        id INTEGER PRIMARY KEY,
        text VARCHAR,
        subject VARCHAR,
        grade INTEGER,
        embedding FLOAT[384]  -- Vector column
    );
""")

# Add vector index
conn.execute("""
    CREATE INDEX idx_embedding ON educational_content 
    USING HNSW (embedding);
""")

# Query using SQL!
results = conn.execute("""
    SELECT text, subject, grade,
           array_cosine_similarity(embedding, ?) as similarity
    FROM educational_content
    ORDER BY similarity DESC
    LIMIT 5;
""", [query_embedding]).fetchall()
```

---

## Performance Comparison

### Benchmark (10,000 documents)

| Operation | ChromaDB | LanceDB | DuckDB+VSS |
|-----------|----------|---------|------------|
| **Insert 1K docs** | ~2s | ~1s | ~3s |
| **Query (single)** | ~50ms | ~20ms | ~30ms |
| **Query (batch)** | ~200ms | ~80ms | ~150ms |
| **Storage size** | ~100MB | ~120MB | ~80MB |
| **Memory usage** | Low | Low | Very Low |

**Recommendation**: Start with **ChromaDB**, upgrade to **LanceDB** if needed.

---

## File Structure

### What It Looks Like

```
MindGraph/
├── data/
│   ├── rag/                    # ChromaDB storage (like SQLite)
│   │   ├── chroma.sqlite3      # Metadata (~2MB)
│   │   └── index/              # Vector indexes (~50MB)
│   │       ├── id_to_uuid/
│   │       └── hnsw/
│   └── backups/                # Optional backups
│       └── rag_backup_20250122/
├── services/
│   └── lightweight_rag.py      # RAG implementation
├── scripts/
│   └── setup_rag.py           # Populate with content
└── requirements.txt
```

**Total size for 1000 documents**: ~50-100MB (similar to small SQLite database!)

---

## Advantages Over Server-Based Solutions

### ChromaDB vs Redis/Pinecone/Qdrant

| Feature | ChromaDB | Redis/Pinecone/Qdrant |
|---------|----------|------------------------|
| **Setup** | `pip install` | Install server, configure, manage |
| **Deployment** | Include files | Need separate service |
| **Cost** | Free | $0-100+/month |
| **Backup** | Copy directory | Complex backup procedures |
| **Local dev** | Works offline | Need server running |
| **Portability** | Very easy | Need infrastructure |
| **Complexity** | ⭐ Simple | ⭐⭐⭐ Complex |

---

## Best Practices for PDF-Based RAG

### 1. PDF Organization

```
Recommended structure:
textbooks/
├── grade7/
│   ├── subject_grade7.pdf
│   └── ...
├── grade8/
└── grade9/

Benefits:
- Easy to process by grade
- Clear subject identification
- Simple filename patterns
```

### 2. Chunking Strategy

```python
# For textbooks: Use section-based chunking (recommended)
chunks, metadata = pdf_processor.process_pdf_to_chunks(
    pdf_path,
    use_sections=True  # Chunks by chapters/sections
)

# Benefits:
# - Natural boundaries (chapters, topics)
# - Better retrieval accuracy
# - Preserves context

# For reference materials: Use fixed-size chunking
pdf_processor.chunk_size = 500  # Adjust size
chunks = pdf_processor.chunk_text(text)
```

### 3. Metadata Enrichment

```python
# Always include rich metadata for better filtering
metadata = {
    'source': 'biology_textbook.pdf',
    'subject': 'biology',
    'grade': 7,
    'chapter': 'Photosynthesis',
    'topic': 'plant_biology',
    'publisher': 'Education Press',
    'year': 2024,
    'language': 'zh',  # Chinese
    'verified': True,  # Quality checked
    'difficulty': 'medium'
}
```

### 4. Regular Backups

```python
# Backup RAG database weekly
rag_system.backup(f"./data/backups/rag_backup_{datetime.now().strftime('%Y%m%d')}")
```

### 5. Incremental Updates

```python
# Don't reprocess all PDFs each time
# Track processed files
def get_processed_files() -> set:
    """Get list of already processed PDFs"""
    # Query existing documents
    existing = rag_system.educational_collection.get()
    processed = set(meta['source'] for meta in existing['metadatas'])
    return processed

# Only process new PDFs
processed = get_processed_files()
new_pdfs = [p for p in all_pdfs if p.name not in processed]
```

### 2. Metadata Strategy

```python
# Always include useful metadata
metadata = {
    "subject": "biology",      # For filtering
    "grade": 7,                # For grade-appropriate content
    "topic": "photosynthesis", # For topic clustering
    "difficulty": "medium",    # For personalization
    "source": "textbook",      # For citation
    "verified": True           # For quality control
}
```

### 3. Chunking Strategy

```python
# Don't add huge documents, chunk them
def chunk_document(text: str, chunk_size: int = 500) -> List[str]:
    """Split long documents into chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks
```

### 6. Quality Control for PDFs

```python
def validate_pdf_extraction(pdf_path: str, extracted_text: str) -> bool:
    """Validate PDF extraction quality"""
    
    # Check 1: Minimum text length
    if len(extracted_text) < 1000:
        logger.warning(f"{pdf_path}: Too little text extracted (possible scan?)")
        return False
    
    # Check 2: Reasonable word count
    words = extracted_text.split()
    if len(words) < 100:
        logger.warning(f"{pdf_path}: Too few words")
        return False
    
    # Check 3: Not all gibberish
    alpha_ratio = sum(c.isalpha() for c in extracted_text) / len(extracted_text)
    if alpha_ratio < 0.5:
        logger.warning(f"{pdf_path}: Too many non-alphabetic characters")
        return False
    
    return True

# Use OCR for scanned PDFs
if not validate_pdf_extraction(pdf_path, text):
    logger.info(f"Using OCR for {pdf_path}")
    text = extract_text_with_ocr(pdf_path)  # Implement OCR fallback
```

### 7. Processing Large PDFs

```python
# For very large textbooks (500+ pages)
def process_large_pdf(pdf_path: str, page_batch_size: int = 50):
    """Process large PDF in batches"""
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    for batch_start in range(0, total_pages, page_batch_size):
        batch_end = min(batch_start + page_batch_size, total_pages)
        
        # Extract text from page batch
        batch_text = ""
        for page_num in range(batch_start, batch_end):
            batch_text += doc[page_num].get_text()
        
        # Chunk and add
        chunks = pdf_processor.chunk_text(batch_text)
        
        chunk_ids = [f"{Path(pdf_path).stem}_p{batch_start}-{batch_end}_c{i}" 
                    for i in range(len(chunks))]
        
        rag_system.add_educational_content(
            documents=chunks,
            metadatas=[{'source': pdf_path, 'page_range': f"{batch_start}-{batch_end}"}] * len(chunks),
            ids=chunk_ids
        )
        
        logger.info(f"Processed pages {batch_start}-{batch_end}/{total_pages}")
    
    doc.close()
```

---

## Summary

### Recommendation: ChromaDB + Qwen + PDF Processing

For your MindGraph project with **PDF textbooks**, this stack is perfect:

✅ **ChromaDB** - SQLite-like simplicity (file-based, no servers)  
✅ **Qwen text-embedding-v4** - Best for Chinese + multilingual  
✅ **PyMuPDF** - Fast PDF text extraction  
✅ **Affordable** - 1M tokens free + cheap after  
✅ **Smart chunking** - By chapters/sections for better retrieval  
✅ **Rich metadata** - Grade, subject, chapter, page filtering  
✅ **Persistent storage** - Survives restarts  
✅ **100+ languages** - Works with your Chinese + English content  

### Quick Start with PDFs

```bash
# 1. Install dependencies
pip install chromadb openai pymupdf

# 2. Set API key
export DASHSCOPE_API_KEY="your-api-key"

# 3. Organize PDFs
mkdir -p data/textbooks/grade7
# Copy your PDF files here

# 4. Run setup script
python scripts/setup_rag.py

# Output:
# Processing PDFs...
# ✓ Extracted text from biology_grade7.pdf (234 pages)
# ✓ Created 156 chunks
# ✓ Added to RAG system
# Total: 487 chunks from 5 PDFs

# 5. Query (works with Chinese and English!)
from services.lightweight_rag import rag_system

results = rag_system.query_educational_content(
    query="什么是光合作用？",
    grade=7,
    subject="biology"
)

print(results['documents'][0])  # Top relevant chunk from textbook
print(results['metadatas'][0])  # Metadata: source PDF, page, chapter

# Done! ✓
```

### File Processing Summary

```
Your PDFs (textbooks/)
    ↓
PyMuPDF Extraction (fast, accurate)
    ↓
Smart Chunking (by chapters/sections)
    ↓
Qwen Embeddings (API call, high quality)
    ↓
ChromaDB Storage (local, persistent)
    ↓
Query & Retrieve (grade/subject filtering)
    ↓
Voice Agent / ThinkGuide (natural answers)
```

**Cost for 10 textbooks (~3000 pages total)**:
- Text extraction: FREE (local)
- Embeddings: First 1M tokens FREE, then ~¥3 (~$0.42)
- Storage: FREE (local files)
- **Total: < $1 for entire textbook library!**

---

## Next Steps

1. ✅ Install ChromaDB
2. ✅ Copy implementation code
3. ✅ Run setup script to populate content
4. ✅ Integrate with voice agent
5. ✅ Test queries
6. ✅ Add more educational content over time

**It's that simple!** No Redis, no servers, no complexity - just like SQLite! 🎯

