#!/usr/bin/env python3
"""
NOUS Setup Collections
----------------------
Opretter alle Qdrant collections der mangler.
Kør efter Qdrant genstart eller ved nye wing-installationer.

Brug:
    python3 nous-setup-collections.py
"""
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
VECTOR_DIM = 768  # nomic-embed-text

ALL_COLLECTIONS = [
    "boernesag_secret",
    "fbf_data_private", 
    "jura_private",
    "dans_profil_private",
    "familie_private",
    "nous_projekt_swarm",
    "swarm_public",
]


def main():
    print("=" * 60)
    print("  NOUS: Opretter Qdrant collections")
    print("=" * 60 + "\n")
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    for name in ALL_COLLECTIONS:
        try:
            client.get_collection(name)
            print(f"  ✓ {name:30} findes allerede")
        except Exception:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
            )
            print(f"  → {name:30} OPPRETTET")
    
    print("\n" + "=" * 60)
    print("  Alle collections klar")
    print("=" * 60)


if __name__ == "__main__":
    main()
