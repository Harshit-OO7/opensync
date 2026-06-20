"""
Migrate local Qdrant embeddings to Qdrant Cloud.
Run this once to move all repo embeddings to production.
"""

import sys
sys.path.insert(0, ".")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# ── Local Qdrant ──────────────────────────────────────────
local = QdrantClient(host="localhost", port=6333)

# ── Qdrant Cloud ──────────────────────────────────────────
CLOUD_URL = input("Enter your Qdrant Cloud URL (https://xxx.qdrant.io): ").strip()
CLOUD_API_KEY = input("Enter your Qdrant Cloud API key: ").strip()

cloud = QdrantClient(url=CLOUD_URL, api_key=CLOUD_API_KEY)

COLLECTION = "repositories"

# ── Create collection in cloud if needed ──────────────────
existing = cloud.get_collections().collections
if COLLECTION not in [c.name for c in existing]:
    cloud.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    print(f"Created collection: {COLLECTION}")

# ── Fetch all points from local ───────────────────────────
print("Fetching points from local Qdrant...")
points, offset = [], None

while True:
    result, next_offset = local.scroll(
        collection_name=COLLECTION,
        limit=100,
        offset=offset,
        with_vectors=True,
        with_payload=True,
    )
    points.extend(result)
    if next_offset is None:
        break
    offset = next_offset

print(f"Found {len(points)} points locally")

# ── Upload to cloud ───────────────────────────────────────
if points:
    cloud_points = [
        PointStruct(id=p.id, vector=p.vector, payload=p.payload)
        for p in points
    ]
    cloud.upsert(collection_name=COLLECTION, points=cloud_points)
    print(f"Uploaded {len(cloud_points)} points to Qdrant Cloud")
else:
    print("No points found locally — run run_indexer.py first")

print("Migration complete!")