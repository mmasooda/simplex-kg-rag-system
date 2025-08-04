"""
LLM-Powered Knowledge Extraction Module
Uses OpenAI API to extract entities and relationships from documents
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from openai import OpenAI
import re

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """Represents an extracted entity"""
    label: str
    properties: Dict[str, Any]
    source_text: str
    confidence: float = 1.0
    
@dataclass
class Relationship:
    """Represents an extracted relationship"""
    source_entity: Entity
    target_entity: Entity
    relationship_type: str
    properties: Dict[str, Any]
    source_text: str
    confidence: float = 1.0

class KnowledgeExtractor:
    """
    LLM-powered knowledge extraction using prompt chaining
    """
    
    # Define the graph schema
    VALID_NODE_LABELS = ["Product", "License", "Panel", "Module", "Feature"]
    VALID_RELATIONSHIPS = ["COMPATIBLE_WITH", "REQUIRES_LICENSE", "PART_OF", "SUPPORTS"]
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def extract_knowledge(self, text_chunk: str) -> Tuple[List[Entity], List[Relationship]]:
        """
        Extract entities and relationships from a text chunk using prompt chaining
        
        Args:
            text_chunk: Text to extract knowledge from
            
        Returns:
            Tuple of (entities, relationships)
        """
        # Step 1: Entity Identification
        entities = self._extract_entities(text_chunk)
        
        # Step 2: Relationship Extraction
        relationships = self._extract_relationships(text_chunk, entities)
        
        return entities, relationships
    
    def _extract_entities(self, text: str) -> List[Entity]:
        """Extract entities using LLM"""
        
        prompt = f"""You are a knowledge extraction expert specializing in fire alarm systems.
        
Extract entities from the following text. Only identify entities that match these types:
{', '.join(self.VALID_NODE_LABELS)}

For each entity found, provide:
1. The entity type (from the list above)
2. Key properties (e.g., sku, name, description)
3. The exact text snippet where you found this entity

Format your response as a JSON array of objects with this structure:
{{
    "label": "Product",
    "properties": {{
        "sku": "ABC123",
        "name": "Product Name",
        "description": "Brief description"
    }},
    "source_text": "The exact text where this was found"
}}

Text to analyze:
{text[:2000]}  # Limit text length for API

Response:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a knowledge extraction expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                entities_data = json.loads(json_match.group())
                
                entities = []
                for entity_data in entities_data:
                    entity = Entity(
                        label=entity_data['label'],
                        properties=entity_data['properties'],
                        source_text=entity_data.get('source_text', ''),
                        confidence=entity_data.get('confidence', 1.0)
                    )
                    entities.append(entity)
                
                self.logger.info(f"Extracted {len(entities)} entities")
                return entities
            else:
                self.logger.warning("No valid JSON found in LLM response")
                return []
                
        except Exception as e:
            self.logger.error(f"Error extracting entities: {str(e)}")
            return []
    
    def _extract_relationships(self, text: str, entities: List[Entity]) -> List[Relationship]:
        """Extract relationships between identified entities"""
        
        if len(entities) < 2:
            return []
        
        # Create entity pairs to check
        entity_pairs = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                entity_pairs.append((entities[i], entities[j]))
        
        relationships = []
        
        # Check each pair for relationships
        for source, target in entity_pairs[:10]:  # Limit to avoid too many API calls
            relationship = self._check_relationship(text, source, target)
            if relationship:
                relationships.append(relationship)
        
        self.logger.info(f"Extracted {len(relationships)} relationships")
        return relationships
    
    def _check_relationship(self, text: str, source: Entity, target: Entity) -> Optional[Relationship]:
        """Check if a relationship exists between two entities"""
        
        prompt = f"""Analyze if there is a relationship between these two entities based on the text.

Valid relationship types: {', '.join(self.VALID_RELATIONSHIPS)}

Entity 1: {source.label} - {source.properties.get('name', source.properties.get('sku', ''))}
Entity 2: {target.label} - {target.properties.get('name', target.properties.get('sku', ''))}

Text context:
{text[:1500]}

If a relationship exists, respond with JSON:
{{
    "relationship_type": "COMPATIBLE_WITH",
    "properties": {{"notes": "any relevant notes"}},
    "source_text": "The text that indicates this relationship",
    "confidence": 0.95
}}

If no relationship exists, respond with: {{"relationship_type": null}}

Response:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a relationship extraction expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                rel_data = json.loads(json_match.group())
                
                if rel_data.get('relationship_type'):
                    return Relationship(
                        source_entity=source,
                        target_entity=target,
                        relationship_type=rel_data['relationship_type'],
                        properties=rel_data.get('properties', {}),
                        source_text=rel_data.get('source_text', ''),
                        confidence=rel_data.get('confidence', 1.0)
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking relationship: {str(e)}")
            return None

class DocumentProcessor:
    """
    Processes extracted documents to build knowledge graph data
    """
    
    def __init__(self, knowledge_extractor: KnowledgeExtractor):
        self.extractor = knowledge_extractor
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single document to extract knowledge
        
        Args:
            doc_data: Document data from PDF parser
            
        Returns:
            Dictionary with entities and relationships
        """
        text_content = doc_data.get('text_content', '')
        
        # Split text into chunks for processing
        chunks = self._split_text_into_chunks(text_content, chunk_size=2000)
        
        all_entities = []
        all_relationships = []
        
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            
            entities, relationships = self.extractor.extract_knowledge(chunk)
            
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        
        # Deduplicate entities
        unique_entities = self._deduplicate_entities(all_entities)
        
        return {
            "filename": doc_data.get('filename', ''),
            "entities": [asdict(e) for e in unique_entities],
            "relationships": [self._relationship_to_dict(r) for r in all_relationships],
            "metadata": {
                "chunks_processed": len(chunks),
                "total_entities": len(unique_entities),
                "total_relationships": len(all_relationships)
            }
        }
    
    def _split_text_into_chunks(self, text: str, chunk_size: int = 2000) -> List[str]:
        """Split text into chunks for processing"""
        words = text.split()
        chunks = []
        
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities based on SKU or name"""
        seen = set()
        unique = []
        
        for entity in entities:
            # Create a unique key
            key = (
                entity.label,
                entity.properties.get('sku') or entity.properties.get('name', '')
            )
            
            if key not in seen and key[1]:  # Ensure we have a valid identifier
                seen.add(key)
                unique.append(entity)
        
        return unique
    
    def _relationship_to_dict(self, rel: Relationship) -> Dict[str, Any]:
        """Convert relationship to dictionary"""
        return {
            "source": {
                "label": rel.source_entity.label,
                "properties": rel.source_entity.properties
            },
            "target": {
                "label": rel.target_entity.label,
                "properties": rel.target_entity.properties
            },
            "type": rel.relationship_type,
            "properties": rel.properties,
            "source_text": rel.source_text,
            "confidence": rel.confidence
        }