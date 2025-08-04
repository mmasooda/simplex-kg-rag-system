"""
Lightweight scoring filter and reranker for retrieval results
Uses simple text similarity metrics as approximation for embeddings
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
import math

logger = logging.getLogger(__name__)

class LightweightScoringFilter:
    """
    Lightweight scoring and filtering system using text similarity metrics
    Approximates embedding-based reranking without heavy dependencies
    """
    
    def __init__(self, min_relevance_score: float = 0.3):
        self.min_relevance_score = min_relevance_score
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Fire alarm domain keywords for relevance scoring
        self.fire_alarm_keywords = {
            'products': ['detector', 'panel', 'alarm', 'smoke', 'heat', 'fire', 'simplex', 'module', 'base'],
            'technical': ['sku', 'model', 'voltage', 'current', 'capacity', 'loop', 'channel', 'zone'],
            'specifications': ['compatible', 'requires', 'supports', 'operating', 'installation', 'wiring'],
            'relationships': ['with', 'to', 'for', 'in', 'on', 'by', 'from', 'using']
        }
    
    def score_and_filter_results(self, query: str, retrieval_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score retrieval results and filter by relevance to query
        
        Args:
            query: User query text
            retrieval_results: List of retrieval results with data
            
        Returns:
            Filtered and scored results sorted by relevance
        """
        scored_results = []
        
        # Preprocess query
        query_processed = self._preprocess_text(query)
        query_keywords = self._extract_keywords(query_processed)
        
        for result in retrieval_results:
            try:
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(query_processed, query_keywords, result)
                
                if relevance_score >= self.min_relevance_score:
                    result_with_score = result.copy()
                    result_with_score['relevance_score'] = relevance_score
                    scored_results.append(result_with_score)
                    
            except Exception as e:
                self.logger.warning(f"Error scoring result: {e}")
                continue
        
        # Sort by combined score (relevance + original confidence)
        scored_results.sort(key=lambda x: (
            x.get('relevance_score', 0) * 0.6 + 
            x.get('metadata', {}).get('confidence', 0.5) * 0.4
        ), reverse=True)
        
        self.logger.info(f"Filtered {len(scored_results)} from {len(retrieval_results)} results")
        return scored_results
    
    def _calculate_relevance_score(self, query: str, query_keywords: List[str], result: Dict[str, Any]) -> float:
        """Calculate relevance score between query and result"""
        
        # Extract text content from result
        result_text = self._extract_text_from_result(result)
        if not result_text:
            return 0.0
        
        result_processed = self._preprocess_text(result_text)
        result_keywords = self._extract_keywords(result_processed)
        
        # Calculate multiple similarity metrics
        cosine_sim = self._cosine_similarity(query_keywords, result_keywords)
        jaccard_sim = self._jaccard_similarity(set(query_keywords), set(result_keywords))
        domain_relevance = self._domain_relevance_score(result_text)
        semantic_sim = self._semantic_similarity(query, result_processed)
        
        # Weighted combination
        final_score = (
            cosine_sim * 0.35 +
            jaccard_sim * 0.25 + 
            domain_relevance * 0.25 +
            semantic_sim * 0.15
        )
        
        return min(final_score, 1.0)
    
    def _extract_text_from_result(self, result: Dict[str, Any]) -> str:
        """Extract all text content from a result"""
        text_parts = []
        
        # Extract from data field
        data = result.get('data', [])
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # Extract key fields
                    for key, value in item.items():
                        if isinstance(value, str) and len(value) > 2:
                            text_parts.append(f"{key}: {value}")
                elif isinstance(item, str):
                    text_parts.append(item)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 2:
                    text_parts.append(f"{key}: {value}")
        
        # Extract from metadata
        metadata = result.get('metadata', {})
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if isinstance(value, str) and len(value) > 2:
                    text_parts.append(f"{key}: {value}")
        
        return ' '.join(text_parts)
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for similarity calculation"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^a-zA-Z0-9\s-]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from preprocessed text"""
        # Split into words
        words = text.split()
        
        # Filter out short words and common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
        
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return keywords
    
    def _cosine_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """Calculate cosine similarity between keyword lists"""
        if not keywords1 or not keywords2:
            return 0.0
        
        # Create frequency vectors
        all_keywords = set(keywords1 + keywords2)
        vector1 = [keywords1.count(kw) for kw in all_keywords]
        vector2 = [keywords2.count(kw) for kw in all_keywords]
        
        # Calculate cosine similarity
        dot_product = sum(v1 * v2 for v1, v2 in zip(vector1, vector2))
        magnitude1 = math.sqrt(sum(v1 * v1 for v1 in vector1))
        magnitude2 = math.sqrt(sum(v2 * v2 for v2 in vector2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets"""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _domain_relevance_score(self, text: str) -> float:
        """Calculate domain relevance score based on fire alarm keywords"""
        text_lower = text.lower()
        total_score = 0.0
        total_weight = 0.0
        
        for category, keywords in self.fire_alarm_keywords.items():
            category_weight = {
                'products': 0.4,
                'technical': 0.3,
                'specifications': 0.2,
                'relationships': 0.1
            }.get(category, 0.1)
            
            matches = sum(1 for kw in keywords if kw in text_lower)
            category_score = min(matches / len(keywords), 1.0)
            
            total_score += category_score * category_weight
            total_weight += category_weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _semantic_similarity(self, query: str, result_text: str) -> float:
        """Simple semantic similarity using common phrases and patterns"""
        query_lower = query.lower()
        result_lower = result_text.lower()
        
        # Look for common fire alarm patterns
        patterns = [
            r'smoke\s+detector', r'heat\s+detector', r'fire\s+alarm', r'control\s+panel',
            r'detector\s+base', r'sounder\s+base', r'manual\s+station', r'pull\s+station',
            r'notification\s+appliance', r'speaker\s+strobe', r'horn\s+strobe',
            r'power\s+supply', r'battery\s+backup', r'loop\s+powered',
            r'addressable\s+device', r'conventional\s+detector', r'analog\s+detector'
        ]
        
        query_patterns = sum(1 for pattern in patterns if re.search(pattern, query_lower))
        result_patterns = sum(1 for pattern in patterns if re.search(pattern, result_lower))
        
        if query_patterns == 0:
            return 0.5  # Neutral score if no patterns in query
        
        pattern_overlap = min(result_patterns / query_patterns, 1.0)
        
        # Boost score if result contains query terms
        query_terms = set(query_lower.split())
        result_terms = set(result_lower.split())
        term_overlap = len(query_terms.intersection(result_terms)) / len(query_terms) if query_terms else 0
        
        return (pattern_overlap * 0.6 + term_overlap * 0.4)

class RetrievalResultsCache:
    """
    Simple caching mechanism for retrieval results to reduce redundant processing
    """
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.access_count = {}
        self.max_size = max_size
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached results for query hash"""
        if query_hash in self.cache:
            self.access_count[query_hash] = self.access_count.get(query_hash, 0) + 1
            self.logger.debug(f"Cache hit for query hash {query_hash[:8]}")
            return self.cache[query_hash]
        return None
    
    def put(self, query_hash: str, results: List[Dict[str, Any]]):
        """Cache results for query hash"""
        # Implement LRU eviction if cache is full
        if len(self.cache) >= self.max_size:
            # Remove least recently used item
            lru_key = min(self.access_count.keys(), key=lambda k: self.access_count[k])
            del self.cache[lru_key]
            del self.access_count[lru_key]
            self.logger.debug(f"Evicted LRU item {lru_key[:8]} from cache")
        
        self.cache[query_hash] = results
        self.access_count[query_hash] = 1
        self.logger.debug(f"Cached results for query hash {query_hash[:8]}")
    
    def clear(self):
        """Clear all cached results"""
        self.cache.clear()
        self.access_count.clear()
        self.logger.info("Cleared retrieval results cache")