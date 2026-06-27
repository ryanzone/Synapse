import math
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

class MemoryService:
    """Vector database as the agent's primary cognitive memory."""
    
    def __init__(self, qdrant_url: str = "http://localhost:6333",
                 collection: str = "synapse_memory"):
        self.client = QdrantClient(url=qdrant_url)
        self.collection = collection
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._ensure_collection()
    
    def _ensure_collection(self):
        if self.client.collection_exists(self.collection):
            return

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
            ),
        )
    
    def _embed(self, text: str) -> List[float]:
        return self.embedder.encode(text, normalize_embeddings=True).tolist()
    
    def _decay(self, importance: float, timestamp: str, rate: float = 0.01) -> float:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds() / 86400
        return max(0.05, importance * math.exp(-rate * days))
    
    def store(self, text: str, category: str, task_id: str,
              importance: float = 0.5, confidence: float = 0.8,
              related: List[str] = None, workflow_name: str = None,
              metadata: Dict = None) -> str:
        vector = self._embed(text)
        
        # Semantic deduplication
        dupes = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(key="category", match=models.MatchValue(value=category)),
                    models.FieldCondition(key="task_id", match=models.MatchValue(value=task_id)),
                ]
            ),
            limit=1,
            score_threshold=0.95
        )
        if dupes:
            new_imp = min(1.0, dupes[0].payload["importance"] + 0.05)
            self.client.set_payload(self.collection, [dupes[0].id], {"importance": new_imp})
            return dupes[0].id
        
        point_id = str(uuid.uuid4())
        payload = {
            "text": text,
            "category": category,
            "importance": importance,
            "confidence": confidence,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "related_memories": related or [],
            "workflow_name": workflow_name,
            "metadata": metadata or {},
        }
        self.client.upsert(self.collection, points=[
            models.PointStruct(id=point_id, vector=vector, payload=payload)
        ])
        return point_id
    
    def retrieve(self, query: str, categories: List[str] = None,
                 task_id: str = None, top_k: int = 10) -> List[Dict[str, Any]]:
        vector = self._embed(query)
        must_filters = []
        if categories:
            must_filters.append(models.FieldCondition(key="category", match=models.MatchAny(any=categories)))
        if task_id:
            must_filters.append(models.FieldCondition(key="task_id", match=models.MatchValue(value=task_id)))
        
        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=models.Filter(must=must_filters) if must_filters else None,
            limit=top_k * 3,
            score_threshold=0.25
        )
        
        ranked = []
        for res in results:
            decayed = self._decay(res.payload["importance"], res.payload["timestamp"])
            score = (res.score * 0.5) + (decayed * 0.3) + (res.payload["confidence"] * 0.2)
            ranked.append({**res.payload, "id": res.id, "retrieval_score": round(score, 4)})
        
        ranked.sort(key=lambda x: x["retrieval_score"], reverse=True)
        return ranked[:top_k]
    
    def link(self, source_id: str, target_id: str):
        for pid in [source_id, target_id]:
            pts = self.client.retrieve(self.collection, [pid], with_payload=True)
            if not pts:
                continue
            rel = pts[0].payload.get("related_memories", [])
            other = target_id if pid == source_id else source_id
            if other not in rel:
                rel.append(other)
                self.client.set_payload(
    collection_name=self.collection,
    payload={"related_memories": rel},
    points=[pid],
)