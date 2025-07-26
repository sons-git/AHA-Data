import traceback
from qdrant_client.conversions import common_types as types

def rrf(points: list[types.QueryResponse] = None, n_points: int = None, payload: list[str] = None, k: int = 60) -> str:
        """
        Perform Reciprocal Rank Fusion (RRF) on dense and sparse Qdrant search results
        and return a combined context string from the top-ranked documents.
        
        Args:
            points: List containing [dense_results, sparse_results]
            n_points: Number of top documents to include in final context
            payload: List of payload keys to extract
            k: RRF parameter (default 60)
    
        Returns:
            Combined context string from top-ranked documents
        """
        try:
            dense_results = points[0].points
            sparse_results = points[1].points
            
            # Create score maps directly without intermediate sets
            dense_scores = {str(r.id): r.score for r in dense_results}
            sparse_scores = {str(r.id): r.score for r in sparse_results}
            
            # Get all unique doc IDs in one pass
            all_doc_ids = dense_scores.keys() | sparse_scores.keys()
            
            # Build document lookup only for docs we have
            doc_lookup = {}
            for result in dense_results:
                doc_lookup[str(result.id)] = result
            for result in sparse_results:
                doc_lookup[str(result.id)] = result
            
            # Calculate RRF scores directly without ranx overhead
            rrf_scores = {}
            
            # Create sorted rank lists once
            dense_ranked = sorted(dense_scores.items(), key=lambda x: x[1], reverse=True)
            sparse_ranked = sorted(sparse_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Create rank mappings
            dense_ranks = {doc_id: rank + 1 for rank, (doc_id, _) in enumerate(dense_ranked)}
            sparse_ranks = {doc_id: rank + 1 for rank, (doc_id, _) in enumerate(sparse_ranked)}
            
            # Calculate RRF scores
            for doc_id in all_doc_ids:
                dense_rank = dense_ranks.get(doc_id, len(dense_results) + 1)
                sparse_rank = sparse_ranks.get(doc_id, len(sparse_results) + 1)
                
                rrf_scores[doc_id] = (1 / (k + dense_rank)) + (1 / (k + sparse_rank))
            
            # Get top N documents efficiently
            if n_points and n_points < len(rrf_scores):
                import heapq
                top_items = heapq.nlargest(n_points, rrf_scores.items(), key=lambda x: x[1])
                top_doc_ids = [doc_id for doc_id, _ in top_items]
            else:
                top_doc_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:n_points]
            
            # Build context with list comprehension and join
            context_chunks = []
            for idx, doc_id in enumerate(top_doc_ids):
                doc = doc_lookup[doc_id]
                payload_content = [f"Context {idx}: {doc.payload.get(key, '')}" for key in payload]
                context_chunks.append("\n".join(payload_content))
            
            return "\n\n------------------------------------------------------------------\n\n".join(context_chunks)
            
        except Exception as e:
            print("[RRF Exception Traceback]")
            traceback.print_exc()
            return f"[RRF Error] {e}"