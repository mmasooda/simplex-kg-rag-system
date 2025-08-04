"""
LLM Response Caching System
Reduces latency and costs by caching repeated LLM prompts
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class CachedResponse:
    """Represents a cached LLM response"""
    response: str
    timestamp: float
    model: str  
    tokens_used: int
    metadata: Dict[str, Any]

class LLMCache:
    """
    File-based LLM response cache with TTL and size management
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24, max_cache_size_mb: int = 100):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Track cache stats
        self.stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0,
            'evictions': 0
        }
        
        # Clean expired entries on initialization
        self._cleanup_expired()
    
    def get_response(self, prompt: str, model: str, **kwargs) -> Optional[CachedResponse]:
        """
        Get cached response for prompt if available and not expired
        
        Args:
            prompt: The LLM prompt
            model: Model name used
            **kwargs: Additional parameters that affect the response
            
        Returns:
            Cached response if available, None otherwise
        """
        cache_key = self._generate_cache_key(prompt, model, kwargs)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                cached_response = CachedResponse(**cached_data)
                
                # Check if cache entry is still valid
                if time.time() - cached_response.timestamp < self.ttl_seconds:
                    self.stats['hits'] += 1
                    self.logger.debug(f"Cache hit for key {cache_key[:8]}")
                    return cached_response
                else:
                    # Remove expired entry
                    cache_file.unlink()
                    self.logger.debug(f"Removed expired cache entry {cache_key[:8]}")
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            self.logger.warning(f"Error reading cache entry {cache_key[:8]}: {e}")
            return None
    
    def save_response(self, prompt: str, model: str, response: str, tokens_used: int = 0, **kwargs):
        """
        Save LLM response to cache
        
        Args:
            prompt: The LLM prompt
            model: Model name used
            response: The LLM response
            tokens_used: Number of tokens used
            **kwargs: Additional parameters that affected the response
        """
        try:
            cache_key = self._generate_cache_key(prompt, model, kwargs)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            cached_response = CachedResponse(
                response=response,
                timestamp=time.time(),
                model=model,
                tokens_used=tokens_used,
                metadata=kwargs
            )
            
            with open(cache_file, 'w') as f:
                json.dump(asdict(cached_response), f, indent=2)
            
            self.stats['saves'] += 1
            self.logger.debug(f"Cached response for key {cache_key[:8]}")
            
            # Check cache size and cleanup if needed
            self._manage_cache_size()
            
        except Exception as e:
            self.logger.error(f"Error saving cache entry: {e}")
    
    def _generate_cache_key(self, prompt: str, model: str, params: Dict[str, Any]) -> str:
        """Generate unique cache key for prompt and parameters"""
        # Create a deterministic hash of prompt, model, and relevant parameters
        cache_input = {
            'prompt': prompt.strip(),
            'model': model,
            'temperature': params.get('temperature', 0.0),
            'max_tokens': params.get('max_tokens', 1000),
            'top_p': params.get('top_p', 1.0)
        }
        
        cache_string = json.dumps(cache_input, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()
    
    def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_count = 0
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                if current_time - cached_data['timestamp'] > self.ttl_seconds:
                    cache_file.unlink()
                    expired_count += 1
                    
            except Exception as e:
                self.logger.warning(f"Error checking cache file {cache_file.name}: {e}")
                # Remove corrupted cache files
                try:
                    cache_file.unlink()
                    expired_count += 1
                except:
                    pass
        
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired cache entries")
    
    def _manage_cache_size(self):
        """Manage cache size by removing oldest entries if needed"""
        try:
            # Calculate total cache size
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
            
            if total_size > self.max_cache_size_bytes:
                # Get all cache files sorted by modification time (oldest first)
                cache_files = sorted(
                    self.cache_dir.glob("*.json"),
                    key=lambda f: f.stat().st_mtime
                )
                
                # Remove oldest files until under size limit
                removed_count = 0
                for cache_file in cache_files:
                    if total_size <= self.max_cache_size_bytes:
                        break
                    
                    try:
                        file_size = cache_file.stat().st_size
                        cache_file.unlink()
                        total_size -= file_size
                        removed_count += 1
                        self.stats['evictions'] += 1
                    except Exception as e:
                        self.logger.warning(f"Error removing cache file {cache_file.name}: {e}")
                
                if removed_count > 0:
                    self.logger.info(f"Evicted {removed_count} cache entries to manage size")
                    
        except Exception as e:
            self.logger.error(f"Error managing cache size: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            'cache_size_mb': self._get_cache_size_mb()
        }
    
    def _get_cache_size_mb(self) -> float:
        """Get current cache size in MB"""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
            return total_size / (1024 * 1024)
        except:
            return 0.0
    
    def clear_cache(self):
        """Clear all cache entries"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            
            self.stats = {
                'hits': 0,
                'misses': 0, 
                'saves': 0,
                'evictions': 0
            }
            
            self.logger.info("Cleared all cache entries")
            
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")

class CachedOpenAIClient:
    """
    Wrapper around OpenAI client that adds caching
    """
    
    def __init__(self, openai_client, cache_dir: Path, enable_cache: bool = True):
        self.client = openai_client
        self.cache = LLMCache(cache_dir) if enable_cache else None
        self.enable_cache = enable_cache
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def chat_completions_create(self, **kwargs):
        """
        Create chat completion with caching
        """
        # Extract key parameters for caching
        messages = kwargs.get('messages', [])
        model = kwargs.get('model', 'gpt-4o')
        temperature = kwargs.get('temperature', 0.1)
        max_tokens = kwargs.get('max_tokens', 1000)
        
        # Create prompt string from messages
        prompt = self._messages_to_prompt(messages)
        
        # Check cache first
        if self.cache:
            cached_response = self.cache.get_response(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if cached_response:
                # Return mock response object with cached content
                return self._create_mock_response(cached_response.response)
        
        # Make actual API call
        try:
            response = self.client.chat.completions.create(**kwargs)
            response_text = response.choices[0].message.content
            
            # Cache the response
            if self.cache:
                tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
                self.cache.save_response(
                    prompt=prompt,
                    model=model,
                    response=response_text,
                    tokens_used=tokens_used,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in cached OpenAI call: {e}")
            raise
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to a single prompt string for caching"""
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_parts.append(f"{role}: {content}")
        return '\n'.join(prompt_parts)
    
    def _create_mock_response(self, cached_content: str):
        """Create a mock response object with cached content"""
        class MockChoice:
            def __init__(self, content):
                self.message = MockMessage(content)
        
        class MockMessage:
            def __init__(self, content):
                self.content = content
        
        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]
        
        return MockResponse(cached_content)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats() if self.cache else {}
    
    def clear_cache(self):
        """Clear cache"""
        if self.cache:
            self.cache.clear_cache()