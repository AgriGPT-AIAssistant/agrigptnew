import asyncio
import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag_pipeline import RAGPipeline
from app.core.config import settings

def main():
    print("Testing RAG Pipeline...")
    pipeline = RAGPipeline()
    pipeline.initialize()
    
    query = "What is the best fertilizer for cotton?"
    print(f"\nQuerying RAG for: '{query}'")
    result = pipeline.query(query)
    print("\nRAG Result Keys:", list(result.keys()))
    print("Number of documents retrieved:", result["n_final"])
    print("\nFirst 400 characters of context:\n", result["context"][:400])
    print("\nSources:\n", result["sources"])

if __name__ == "__main__":
    main()
