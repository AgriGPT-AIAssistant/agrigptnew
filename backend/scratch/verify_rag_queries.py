import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag_pipeline import RAGPipeline

def test_rag_queries():
    print("Initializing RAG Pipeline...")
    pipeline = RAGPipeline()
    pipeline.initialize()
    
    test_queries = [
        "Rice",
        "Cotton",
        "Tomato",
        "Maize",
        "Wheat",
        "Sugarcane",
        "Paddy disease",
        "Weather query",
        "Fertilizer query",
        "Pest query"
    ]
    
    print("\nRunning RAG verification queries...\n")
    for q in test_queries:
        print(f"==================================================")
        print(f"QUERY: {q}")
        print(f"==================================================")
        result = pipeline.query(q)
        print(f"Retrieved: {result['n_final']} documents.")
        print(f"Context snippet:\n{result['context'][:300]}...\n")
        print("Sources:")
        for src in result['sources']:
            print(f" - {src['document']} | {src['section']} | Score: {src['reranker_score']}")
        print(f"==================================================\n")

if __name__ == "__main__":
    test_rag_queries()
