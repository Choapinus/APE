# Long-Term Memory Implementation Specification

## Overview

This document provides detailed technical specifications for implementing vector-based long-term memory in the APE project. The implementation follows the existing architectural patterns and integrates seamlessly with the current MCP-based system.

## Core Classes and Interfaces

### 1. VectorMemory Class

```python
# File: ape/core/vector_memory.py

from __future__ import annotations
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from dataclasses import dataclass
from datetime import datetime

from ape.core.memory import AgentMemory
from ape.settings import settings
from ape.db_pool import get_db

@dataclass
class MemoryItem:
    """Represents a single memory chunk with metadata."""
    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    chunk_type: str = "conversation"
    session_id: Optional[str] = None
    relevance_score: float = 0.0

class EmbeddingBackend(ABC):
    """Abstract interface for embedding generation."""
    
    @abstractmethod
    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension."""
        pass

class VectorMemory(AgentMemory):
    """Long-term semantic memory using vector embeddings."""
    
    def __init__(
        self, 
        embedding_backend: EmbeddingBackend,
        index_path: str,
        session_id: Optional[str] = None,
        max_chunks: int = 10000
    ):
        self.embedding_backend = embedding_backend
        self.index_path = Path(index_path)
        self.session_id = session_id
        self.max_chunks = max_chunks
        self._index = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize FAISS index and database tables."""
        if self._initialized:
            return
            
        # Ensure directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database tables
        await self._init_db_tables()
        
        # Initialize FAISS index
        await self._init_faiss_index()
        
        self._initialized = True
    
    async def add(self, message: Dict[str, str]) -> None:
        """Add message to vector memory."""
        content = message.get("content", "")
        if not content.strip():
            return
            
        memory_item = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            metadata={
                "role": message.get("role", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            },
            session_id=self.session_id,
            chunk_type="conversation"
        )
        
        await self.append(memory_item)
    
    async def append(self, memory_item: MemoryItem) -> str:
        """Store memory item with embedding."""
        if not self._initialized:
            await self.initialize()
        
        # Generate embedding
        embedding = await self.embedding_backend.embed_text(memory_item.content)
        memory_item.embedding = embedding
        
        # Store in database
        async with get_db() as conn:
            await conn.execute("""
                INSERT INTO memory_chunks 
                (id, session_id, content, embedding, metadata, chunk_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_item.id,
                memory_item.session_id,
                memory_item.content,
                embedding.tobytes(),  # Store as binary
                json.dumps(memory_item.metadata),
                memory_item.chunk_type,
                memory_item.timestamp or datetime.utcnow()
            ))
            await conn.commit()
        
        # Add to FAISS index
        await self._add_to_index(memory_item.id, embedding)
        
        return memory_item.id
    
    async def search(self, query: str, k: int = 5, filters: Optional[Dict] = None) -> List[MemoryItem]:
        """Semantic search for similar memories."""
        if not self._initialized:
            await self.initialize()
        
        # Generate query embedding
        query_embedding = await self.embedding_backend.embed_text(query)
        
        # Search FAISS index
        similar_ids = await self._search_index(query_embedding, k * 2)  # Get more for filtering
        
        # Retrieve full items from database
        items = await self._get_items_by_ids(similar_ids)
        
        # Apply filters
        if filters:
            items = [item for item in items if self._matches_filters(item, filters)]
        
        # Calculate relevance scores and sort
        for item in items:
            if item.embedding is not None:
                item.relevance_score = float(np.dot(query_embedding, item.embedding))
        
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return items[:k]
    
    async def summarize(self, text: str) -> str:
        """Generate summary and store in vector memory."""
        # For now, delegate to existing summarization
        # TODO: Integrate with MCP summarize_text tool
        return text[:200] + "..." if len(text) > 200 else text
    
    async def prune(self) -> None:
        """Remove old or irrelevant memories."""
        # TODO: Implement importance-based pruning
        pass
    
    async def force_summarize(self) -> None:
        """Force summarization of current session."""
        if not self.session_id:
            return
        
        # Get recent conversations for this session
        async with get_db() as conn:
            cursor = await conn.execute("""
                SELECT content FROM history 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 50
            """, (self.session_id,))
            rows = await cursor.fetchall()
        
        if not rows:
            return
        
        # Combine content and create summary
        combined_content = "\n".join([row[0] for row in rows])
        summary = await self.summarize(combined_content)
        
        # Store summary as a memory chunk
        summary_item = MemoryItem(
            id=str(uuid.uuid4()),
            content=summary,
            metadata={"type": "session_summary", "messages_count": len(rows)},
            session_id=self.session_id,
            chunk_type="summary"
        )
        
        await self.append(summary_item)
    
    def tokens(self) -> int:
        """Return estimated token count (for compatibility)."""
        # TODO: Implement based on stored chunks
        return 0
    
    # Private methods
    async def _init_db_tables(self) -> None:
        """Initialize database tables for vector memory."""
        async with get_db() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    metadata JSON,
                    chunk_type TEXT DEFAULT 'conversation',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    relevance_score REAL DEFAULT 0.0
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_session 
                ON memory_chunks(session_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type 
                ON memory_chunks(chunk_type)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_timestamp 
                ON memory_chunks(timestamp)
            """)
            
            await conn.commit()
    
    async def _init_faiss_index(self) -> None:
        """Initialize or load FAISS index."""
        try:
            import faiss
        except ImportError:
            raise RuntimeError("FAISS is required for vector memory. Install with: pip install faiss-cpu")
        
        dimension = self.embedding_backend.get_dimension()
        
        if self.index_path.exists():
            # Load existing index
            self._index = faiss.read_index(str(self.index_path))
        else:
            # Create new index
            self._index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            self._save_index()
    
    async def _add_to_index(self, item_id: str, embedding: np.ndarray) -> None:
        """Add embedding to FAISS index."""
        if self._index is None:
            return
        
        # Normalize for cosine similarity
        embedding = embedding / np.linalg.norm(embedding)
        
        # Add to index
        self._index.add(embedding.reshape(1, -1))
        
        # Save index periodically
        if self._index.ntotal % 100 == 0:
            await self._save_index()
    
    async def _search_index(self, query_embedding: np.ndarray, k: int) -> List[str]:
        """Search FAISS index for similar vectors."""
        if self._index is None or self._index.ntotal == 0:
            return []
        
        # Normalize query
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Search
        scores, indices = self._index.search(query_embedding.reshape(1, -1), min(k, self._index.ntotal))
        
        # Get item IDs (need to maintain mapping)
        # TODO: Implement ID mapping for FAISS indices
        return [str(i) for i in indices[0] if i >= 0]
    
    async def _save_index(self) -> None:
        """Save FAISS index to disk."""
        if self._index is not None:
            import faiss
            faiss.write_index(self._index, str(self.index_path))
    
    async def _get_items_by_ids(self, item_ids: List[str]) -> List[MemoryItem]:
        """Retrieve memory items by IDs."""
        if not item_ids:
            return []
        
        placeholders = ",".join(["?" for _ in item_ids])
        async with get_db() as conn:
            cursor = await conn.execute(f"""
                SELECT id, session_id, content, embedding, metadata, chunk_type, timestamp
                FROM memory_chunks 
                WHERE id IN ({placeholders})
            """, item_ids)
            rows = await cursor.fetchall()
        
        items = []
        for row in rows:
            embedding_bytes = row[3]
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32) if embedding_bytes else None
            
            items.append(MemoryItem(
                id=row[0],
                session_id=row[1],
                content=row[2],
                embedding=embedding,
                metadata=json.loads(row[4]) if row[4] else {},
                chunk_type=row[5],
                timestamp=datetime.fromisoformat(row[6]) if row[6] else None
            ))
        
        return items
    
    def _matches_filters(self, item: MemoryItem, filters: Dict) -> bool:
        """Check if memory item matches filters."""
        for key, value in filters.items():
            if key == "session_id" and item.session_id != value:
                return False
            elif key == "chunk_type" and item.chunk_type != value:
                return False
            elif key in item.metadata and item.metadata[key] != value:
                return False
        return True
```

### 2. Embedding Backend Implementations

```python
# File: ape/core/embeddings.py

from typing import Optional
import numpy as np
from abc import ABC, abstractmethod

class MiniLMEmbedding(EmbeddingBackend):
    """MiniLM-L6 embedding implementation."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    async def embed_text(self, text: str) -> np.ndarray:
        if self._model is None:
            await self._load_model()
        
        # Run in thread pool to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self._model.encode, text)
        return np.array(embedding, dtype=np.float32)
    
    def get_dimension(self) -> int:
        return 384  # MiniLM-L6 dimension
    
    async def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError("sentence-transformers required. Install with: pip install sentence-transformers")
        
        self._model = SentenceTransformer(self.model_name)

class OllamaEmbedding(EmbeddingBackend):
    """Ollama-based embedding implementation."""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
    
    async def embed_text(self, text: str) -> np.ndarray:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama required. Install with: pip install ollama")
        
        # Use Ollama client for embedding
        client = ollama.AsyncClient(host=self.base_url)
        response = await client.embeddings(model=self.model_name, prompt=text)
        return np.array(response['embedding'], dtype=np.float32)
    
    def get_dimension(self) -> int:
        # TODO: Query model for actual dimension
        return 768  # Common dimension for many models
```

### 3. Hybrid Memory Manager

```python
# File: ape/core/hybrid_memory.py

from typing import Optional, Dict, List
from ape.core.memory import AgentMemory, WindowMemory
from ape.core.vector_memory import VectorMemory, MemoryItem

class HybridMemory(AgentMemory):
    """Combines short-term WindowMemory with long-term VectorMemory."""
    
    def __init__(
        self,
        window_memory: WindowMemory,
        vector_memory: VectorMemory,
        context_injection_limit: int = 3
    ):
        self.window_memory = window_memory
        self.vector_memory = vector_memory
        self.context_injection_limit = context_injection_limit
    
    async def add(self, message: Dict[str, str]) -> None:
        """Add message to both memories."""
        self.window_memory.add(message)
        await self.vector_memory.add(message)
    
    async def prune(self) -> None:
        """Prune window memory and transfer summaries to vector memory."""
        # First, let window memory do its pruning (creates summaries)
        await self.window_memory.prune()
        
        # If window memory created a summary, store it in vector memory
        if hasattr(self.window_memory, 'summary') and self.window_memory.summary:
            summary_item = MemoryItem(
                id=str(uuid.uuid4()),
                content=self.window_memory.summary,
                metadata={"type": "window_summary"},
                session_id=self.window_memory.session_id,
                chunk_type="summary"
            )
            await self.vector_memory.append(summary_item)
    
    async def get_enhanced_context(self, current_query: Optional[str] = None) -> str:
        """Get context enhanced with relevant long-term memories."""
        context_parts = []
        
        # Add window memory summary
        window_context = self.window_memory.latest_context()
        if window_context and window_context != "(no summary yet)":
            context_parts.append(f"Recent Summary: {window_context}")
        
        # Add relevant long-term memories if we have a query
        if current_query:
            try:
                relevant_memories = await self.vector_memory.search(
                    current_query, 
                    k=self.context_injection_limit
                )
                
                if relevant_memories:
                    memory_texts = []
                    for memory in relevant_memories:
                        relevance = f"({memory.relevance_score:.2f})" if memory.relevance_score > 0 else ""
                        memory_texts.append(f"- {memory.content[:200]}... {relevance}")
                    
                    context_parts.append(
                        f"Relevant Past Context:\n" + "\n".join(memory_texts)
                    )
            except Exception as e:
                # Graceful degradation if vector memory fails
                logger.warning(f"Vector memory search failed: {e}")
        
        return "\n\n".join(context_parts) if context_parts else "(no enhanced context)"
    
    async def summarize(self, text: str) -> str:
        """Delegate summarization to window memory."""
        return await self.window_memory.summarize(text)
    
    async def force_summarize(self) -> None:
        """Force summarization in both memories."""
        await self.window_memory.force_summarize()
        await self.vector_memory.force_summarize()
    
    def tokens(self) -> int:
        """Return window memory token count (vector memory is separate)."""
        return self.window_memory.tokens()
```

## MCP Tool Integration

### Memory Tools

```python
# File: ape/mcp/memory_tools.py

from ape.mcp.plugin import tool
from ape.core.vector_memory import VectorMemory, MemoryItem
from ape.core.embeddings import MiniLMEmbedding
from ape.settings import settings
import json

# Global vector memory instance (singleton pattern)
_vector_memory = None

async def get_vector_memory() -> VectorMemory:
    """Get or create global vector memory instance."""
    global _vector_memory
    if _vector_memory is None:
        embedding_backend = MiniLMEmbedding()
        _vector_memory = VectorMemory(
            embedding_backend=embedding_backend,
            index_path=f"{settings.SESSION_DB_PATH}.faiss"
        )
        await _vector_memory.initialize()
    return _vector_memory

@tool(
    name="memory_append",
    description="Store important information in long-term vector memory for future retrieval",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The content to store in memory"
            },
            "type": {
                "type": "string", 
                "description": "Type of memory (conversation, reflection, summary, etc.)",
                "default": "manual"
            },
            "metadata": {
                "type": "object",
                "description": "Additional metadata for the memory",
                "default": {}
            }
        },
        "required": ["content"]
    }
)
async def memory_append(content: str, type: str = "manual", metadata: dict = None) -> str:
    """Store content in vector memory."""
    try:
        vector_memory = await get_vector_memory()
        
        memory_item = MemoryItem(
            id=str(uuid.uuid4()),
            content=content,
            metadata=metadata or {},
            chunk_type=type
        )
        
        item_id = await vector_memory.append(memory_item)
        
        return json.dumps({
            "status": "success",
            "message": f"Stored memory with ID: {item_id}",
            "memory_id": item_id
        })
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to store memory: {str(e)}"
        })

@tool(
    name="memory_search", 
    description="Search long-term memory for relevant information",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for finding relevant memories"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            },
            "filters": {
                "type": "object", 
                "description": "Filters to apply (e.g., {\"chunk_type\": \"summary\"})",
                "default": {}
            }
        },
        "required": ["query"]
    }
)
async def memory_search(query: str, limit: int = 5, filters: dict = None) -> str:
    """Search vector memory for relevant content."""
    try:
        vector_memory = await get_vector_memory()
        
        results = await vector_memory.search(query, k=limit, filters=filters or {})
        
        if not results:
            return json.dumps({
                "status": "success",
                "message": "No relevant memories found",
                "results": []
            })
        
        formatted_results = []
        for memory in results:
            formatted_results.append({
                "id": memory.id,
                "content": memory.content,
                "relevance_score": memory.relevance_score,
                "type": memory.chunk_type,
                "timestamp": memory.timestamp.isoformat() if memory.timestamp else None,
                "metadata": memory.metadata
            })
        
        return json.dumps({
            "status": "success", 
            "message": f"Found {len(results)} relevant memories",
            "results": formatted_results
        })
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Memory search failed: {str(e)}"
        })
```

## Resource Integration

```python
# File: ape/resources/adapters/memory.py

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.mcp.memory_tools import get_vector_memory
import json
from urllib.parse import parse_qs

@register
class MemoryResourceAdapter(ResourceAdapter):
    """Memory search resource adapter."""
    
    uri_patterns = ["memory://*"]
    
    catalog = [
        ResourceMeta(
            uri="memory://search",
            name="Memory Search",
            description="Search long-term vector memory for relevant information",
            type_="text"
        )
    ]
    
    async def read(self, uri: str, **query) -> tuple[str, str]:
        """Handle memory resource requests."""
        
        if not uri.startswith("memory://search"):
            raise ValueError(f"Unsupported memory URI: {uri}")
        
        # Parse query parameters
        query_text = query.get("q", [""])[0] if isinstance(query.get("q"), list) else query.get("q", "")
        limit = int(query.get("limit", ["5"])[0] if isinstance(query.get("limit"), list) else query.get("limit", 5))
        
        if not query_text:
            return "application/json", json.dumps({
                "error": "Query parameter 'q' is required",
                "example": "memory://search?q=user preferences&limit=5"
            })
        
        try:
            vector_memory = await get_vector_memory()
            results = await vector_memory.search(query_text, k=limit)
            
            response = {
                "query": query_text,
                "results": [
                    {
                        "content": memory.content,
                        "relevance": memory.relevance_score,
                        "type": memory.chunk_type,
                        "timestamp": memory.timestamp.isoformat() if memory.timestamp else None
                    }
                    for memory in results
                ]
            }
            
            return "application/json", json.dumps(response, indent=2)
            
        except Exception as e:
            return "application/json", json.dumps({
                "error": f"Memory search failed: {str(e)}"
            })
```

## Settings Integration

```python
# File: ape/settings.py (additions)

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Vector Memory Settings
    VECTOR_MEMORY_ENABLED: bool = Field(True, description="Enable vector memory functionality")
    EMBEDDING_MODEL: str = Field("all-MiniLM-L6-v2", description="Embedding model for vector memory")
    EMBEDDING_BACKEND: str = Field("minilm", description="Embedding backend (minilm, ollama)")
    VECTOR_INDEX_PATH: str = Field("ape/vector_memory.faiss", description="Path to FAISS vector index")
    MEMORY_MAX_CHUNKS: int = Field(10000, description="Maximum number of memory chunks to store")
    MEMORY_SEARCH_LIMIT: int = Field(20, description="Maximum results for memory search")
    
    # Memory Context Injection
    MEMORY_CONTEXT_INJECTION: bool = Field(True, description="Inject relevant memories into context")
    MEMORY_CONTEXT_LIMIT: int = Field(3, description="Maximum memories to inject into context")
```

## Testing Strategy

### Unit Tests

```python
# File: tests/unit/test_vector_memory.py

import pytest
import numpy as np
from unittest.mock import AsyncMock, Mock
from ape.core.vector_memory import VectorMemory, MemoryItem
from ape.core.embeddings import MiniLMEmbedding

class MockEmbeddingBackend:
    def __init__(self, dimension=384):
        self.dimension = dimension
    
    async def embed_text(self, text: str) -> np.ndarray:
        # Return deterministic embedding for testing
        return np.random.rand(self.dimension).astype(np.float32)
    
    def get_dimension(self) -> int:
        return self.dimension

@pytest.mark.asyncio
async def test_vector_memory_initialization():
    """Test VectorMemory initialization."""
    backend = MockEmbeddingBackend()
    memory = VectorMemory(backend, "/tmp/test_index.faiss")
    
    await memory.initialize()
    assert memory._initialized is True

@pytest.mark.asyncio 
async def test_memory_append_and_search():
    """Test adding and searching memories."""
    backend = MockEmbeddingBackend()
    memory = VectorMemory(backend, "/tmp/test_index.faiss")
    await memory.initialize()
    
    # Add test memory
    item = MemoryItem(
        id="test-1",
        content="This is a test memory about Python programming",
        chunk_type="test"
    )
    
    item_id = await memory.append(item)
    assert item_id == "test-1"
    
    # Search for similar content
    results = await memory.search("Python programming", k=1)
    assert len(results) > 0
    assert results[0].content == item.content

@pytest.mark.asyncio
async def test_memory_tools():
    """Test MCP memory tools."""
    from ape.mcp.memory_tools import memory_append, memory_search
    
    # Test memory append
    result = await memory_append("Test knowledge about AI", "test")
    assert "success" in result
    
    # Test memory search
    result = await memory_search("AI knowledge", limit=1)
    assert "success" in result
```

## Migration Plan

### Phase 1: Core Implementation (Week 1-2)
1. Implement VectorMemory class with FAISS integration
2. Create embedding backend abstractions (MiniLM)
3. Add database schema for memory chunks
4. Basic unit tests

### Phase 2: MCP Integration (Week 2-3)
1. Implement memory_append and memory_search tools
2. Create memory resource adapter
3. Integration with existing MCP server
4. CLI commands for memory inspection

### Phase 3: Hybrid Memory (Week 3-4)
1. Implement HybridMemory class
2. Integrate with AgentCore
3. Context injection functionality
4. Comprehensive testing

### Phase 4: Advanced Features (Week 4+)
1. Multiple embedding backends (Ollama)
2. Memory quality management
3. Cross-session memory sharing
4. Performance optimization

## Performance Considerations

### Memory Usage
- FAISS index: ~4KB per 1000 memories (384-dim embeddings)
- SQLite storage: ~1KB per memory chunk
- Embedding model: ~100MB (MiniLM-L6)

### Latency Targets
- Memory append: <100ms
- Memory search: <200ms
- Context injection: <50ms

### Scaling Strategy
- Hierarchical FAISS indexing for >100K memories
- Periodic index rebuilding
- Memory importance scoring for pruning

This specification provides a comprehensive foundation for implementing long-term memory in APE while maintaining compatibility with the existing architecture and following established patterns.