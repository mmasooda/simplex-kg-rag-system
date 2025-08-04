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
    VALID_NODE_LABELS = [
        "Product", "License", "Panel", "Module", "Feature",
        "Detector", "Base", "Annunciator", "PowerSupply", 
        "Battery", "Circuit", "Accessory", "Specification"
    ]
    VALID_RELATIONSHIPS = [
        "COMPATIBLE_WITH", "REQUIRES_LICENSE", "PART_OF", "SUPPORTS",
        "HAS_BASE", "HAS_MODULE", "ALTERNATIVE_TO", "REQUIRES_POWER_SUPPLY", 
        "USES_BATTERY", "POWERED_BY", "REQUIRES_MODULE", "HAS_SPECIFICATION"
    ]
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _get_entity_description(self, label: str) -> str:
        """Get description for entity type to help LLM understand what to extract"""
        descriptions = {
            "Product": "general fire alarm products and equipment",
            "License": "software licenses or compliance certifications",
            "Panel": "fire alarm control panels and main units",
            "Module": "expansion modules, interface cards, and internal components",
            "Feature": "software features or system capabilities",
            "Detector": "smoke detectors, heat detectors, and sensing devices",
            "Base": "detector bases, mounting hardware, and sounder bases",
            "Annunciator": "display panels, LED indicators, and user interfaces",
            "PowerSupply": "power supplies, transformers, and electrical units",
            "Battery": "backup batteries and power storage devices",
            "Circuit": "wiring circuits, loops, and electrical connections",
            "Accessory": "mounting brackets, tools, and auxiliary components",
            "Specification": "technical standards, compliance requirements, and performance specs"
        }
        return descriptions.get(label, "system components")
    
    def _get_relationship_description(self, rel_type: str) -> str:
        """Get description for relationship type to help LLM understand what to look for"""
        descriptions = {
            "COMPATIBLE_WITH": "Products that can work together or are interoperable",
            "REQUIRES_LICENSE": "Products that need specific software licenses or certifications",
            "PART_OF": "Components that are part of larger systems or assemblies",
            "SUPPORTS": "Products that enable or support specific features or capabilities",
            "HAS_BASE": "Detectors that require or use specific mounting bases",
            "HAS_MODULE": "Panels or systems that include or require specific modules",
            "ALTERNATIVE_TO": "Products that can substitute for or replace other products",
            "REQUIRES_POWER_SUPPLY": "Components that need specific power supplies",
            "USES_BATTERY": "Devices that use specific types of backup batteries",
            "POWERED_BY": "Devices that receive power from other components",
            "REQUIRES_MODULE": "Systems that need specific modules for operation",
            "HAS_SPECIFICATION": "Products with specific technical specifications or standards"
        }
        return descriptions.get(rel_type, "related components")
        
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
        
        # Limit text length for API
        text_to_analyze = text[:2000]
        
        prompt = f"""You are an expert knowledge extraction specialist for fire alarm and security systems. Your task is to identify and extract structured entities from technical documentation.

ENTITY TYPES TO EXTRACT:
{chr(10).join([f"• {label}: For {self._get_entity_description(label)}" for label in self.VALID_NODE_LABELS])}

EXTRACTION GUIDELINES:
1. Extract only entities explicitly mentioned in the text
2. Prioritize SKU codes, model numbers, and part numbers when available
3. Include technical specifications (voltage, current, capacity, etc.)
4. Capture compatibility and requirement information
5. Note any regulatory compliance or standards mentioned

REQUIRED PROPERTIES FOR EACH ENTITY:
- sku: Product/model number (if available)
- name: Full product name or description
- type: Specific category or variant
- description: Key technical details or purpose
- manufacturer: Brand name (if mentioned)

Format your response as a valid JSON array:
[
  {{
    "label": "Detector",
    "properties": {{
      "sku": "4098-9714",
      "name": "TrueAlarm Photoelectric Smoke Detector",
      "type": "photoelectric",
      "description": "Commercial grade smoke detector with enhanced sensitivity",
      "manufacturer": "Simplex"
    }},
    "source_text": "The exact text phrase where this entity was identified"
  }}
]

TEXT TO ANALYZE:
{text_to_analyze}

RESPOND WITH JSON ONLY:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
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
        """Extract relationships between identified entities using focused relationship discovery"""
        
        if len(entities) < 2:
            return []
        
        # Limit text length for API
        text_to_analyze = text[:3000]  # Longer text for relationship context
        
        # Create entity summary for the LLM
        entity_summary = []
        for i, entity in enumerate(entities):
            entity_summary.append(f"Entity {i+1}: {entity.label} - {entity.properties.get('name', 'Unknown')} (SKU: {entity.properties.get('sku', 'N/A')})")
        
        prompt = f"""You are an expert in fire alarm system relationships and dependencies. Analyze the text to identify explicit relationships between the entities found.

IDENTIFIED ENTITIES:
{chr(10).join(entity_summary)}

RELATIONSHIP TYPES TO LOOK FOR:
{chr(10).join([f"• {rel}: {self._get_relationship_description(rel)}" for rel in self.VALID_RELATIONSHIPS])}

RELATIONSHIP DISCOVERY GUIDELINES:
1. Only identify relationships explicitly stated or clearly implied in the text
2. Focus on technical dependencies (requires, uses, compatible with)
3. Look for installation relationships (has base, has module)
4. Identify alternative or substitute products
5. Note power and connectivity requirements
6. Extract compliance and specification relationships

For each relationship found, provide:
- Source entity (by number from list above)
- Target entity (by number from list above)  
- Relationship type (from valid types listed)
- Supporting evidence from the text
- Confidence level (0.5 for inferred, 1.0 for explicit)

Format as JSON array:
[
  {{
    "source_entity": 1,
    "target_entity": 2,
    "type": "HAS_BASE",
    "properties": {{
      "evidence": "The exact text that indicates this relationship",
      "weight": 1.0,
      "required": true
    }},
    "confidence": 1.0
  }}
]

TEXT TO ANALYZE:
{text_to_analyze}

RESPOND WITH JSON ONLY:"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a relationship extraction expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            response_text = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                relationships_data = json.loads(json_match.group())
                
                relationships = []
                for rel_data in relationships_data:
                    try:
                        source_idx = rel_data['source_entity'] - 1  # Convert to 0-based index
                        target_idx = rel_data['target_entity'] - 1
                        
                        if 0 <= source_idx < len(entities) and 0 <= target_idx < len(entities):
                            # Add weight based on confidence: 1.0 for explicit (confidence >= 0.9), 0.5 for inferred
                            confidence = rel_data.get('confidence', 0.8)
                            weight = 1.0 if confidence >= 0.9 else 0.5
                            
                            properties = rel_data.get('properties', {})
                            properties['weight'] = weight
                            
                            relationship = Relationship(
                                source=entities[source_idx],
                                target=entities[target_idx],
                                type=rel_data['type'],
                                properties=properties,
                                confidence=confidence
                            )
                            relationships.append(relationship)
                    except (KeyError, IndexError, ValueError) as e:
                        self.logger.warning(f"Skipping invalid relationship data: {e}")
                        continue
                
                self.logger.info(f"Extracted {len(relationships)} relationships")
                return relationships
            else:
                self.logger.warning("No valid JSON found in relationship extraction response")
                return []
                
        except Exception as e:
            self.logger.error(f"Error extracting relationships: {str(e)}")
            return []
    
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
                model="gpt-4o",
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
                    # Add weight based on confidence: 1.0 for explicit (confidence >= 0.9), 0.5 for inferred
                    confidence = rel_data.get('confidence', 1.0)
                    weight = 1.0 if confidence >= 0.9 else 0.5
                    
                    properties = rel_data.get('properties', {})
                    properties['weight'] = weight
                    
                    return Relationship(
                        source_entity=source,
                        target_entity=target,
                        relationship_type=rel_data['relationship_type'],
                        properties=properties,
                        source_text=rel_data.get('source_text', ''),
                        confidence=confidence
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