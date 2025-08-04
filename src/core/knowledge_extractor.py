"""
Knowledge Extractor: Extracts structured knowledge from text using LLM
Specifically designed for Simplex fire alarm product documentation
"""

import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
import json
import re

logger = logging.getLogger(__name__)

class KnowledgeExtractor:
    """
    Extracts structured knowledge from text content using OpenAI GPT models
    Focuses on Simplex fire alarm products, specifications, and relationships
    """
    
    def __init__(self, openai_client: OpenAI):
        self.openai_client = openai_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def extract_knowledge(self, content: str, source_file: str) -> Dict[str, Any]:
        """
        Extract structured knowledge from document content
        
        Args:
            content: Raw text content from document
            source_file: Source file name for reference
            
        Returns:
            Dictionary with extracted knowledge
        """
        self.logger.info(f"Extracting knowledge from {source_file}")
        
        if not content or len(content.strip()) < 100:
            self.logger.warning(f"Content too short for meaningful extraction: {source_file}")
            return {"entities": [], "relationships": [], "specifications": []}
        
        try:
            # Extract entities first
            entities = self._extract_entities(content, source_file)
            
            # Extract specifications and technical details
            specifications = self._extract_specifications(content, source_file)
            
            # Extract relationships between entities
            relationships = self._extract_relationships(content, entities, source_file)
            
            result = {
                "entities": entities,
                "relationships": relationships,
                "specifications": specifications,
                "source_file": source_file,
                "content_length": len(content)
            }
            
            self.logger.info(f"Extracted from {source_file}: "
                           f"{len(entities)} entities, {len(relationships)} relationships, "
                           f"{len(specifications)} specifications")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting knowledge from {source_file}: {e}")
            return {"entities": [], "relationships": [], "specifications": [], "error": str(e)}
    
    def _extract_entities(self, content: str, source_file: str) -> List[Dict[str, Any]]:
        """Extract product entities from content"""
        
        prompt = f"""
You are an expert in fire alarm systems, specifically Simplex products. 

Analyze the following document content and extract all Simplex fire alarm products mentioned.

For each product, identify:
1. Product SKU/Model Number (e.g., 4100ES, 4090-9001)
2. Product Name/Description
3. Product Type (Panel, Module, Device, etc.)
4. Key specifications and features
5. Applications and use cases

Document Content:
{content[:4000]}...

Return ONLY a JSON array of products in this exact format:
[
  {{
    "sku": "exact_sku_or_model",
    "name": "product name",
    "type": "Panel|Module|Device",
    "category": "specific category",
    "description": "detailed description",
    "specifications": "key technical specs",
    "applications": "use cases and applications",
    "manufacturer": "Simplex"
  }}
]

Focus on actual Simplex products with real SKUs. Ignore generic references.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a fire alarm systems expert. Extract only factual product information in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            entities = self._parse_json_response(response_text)
            
            # Validate entities
            validated_entities = []
            for entity in entities:
                if isinstance(entity, dict) and entity.get('sku') and entity.get('name'):
                    entity['source'] = source_file
                    validated_entities.append(entity)
            
            return validated_entities
            
        except Exception as e:
            self.logger.error(f"Error extracting entities from {source_file}: {e}")
            return []
    
    def _extract_specifications(self, content: str, source_file: str) -> List[Dict[str, Any]]:
        """Extract technical specifications from content"""
        
        prompt = f"""
You are a fire alarm systems expert. Extract technical specifications, ratings, and performance data from this document.

Look for:
1. Electrical specifications (voltage, current, power)
2. Physical specifications (dimensions, weight, mounting)
3. Performance ratings (capacity, range, sensitivity)
4. Certifications and standards (UL, FM, NFPA)
5. Environmental ratings (temperature, humidity)
6. Communication protocols and interfaces

Document Content:
{content[:4000]}...

Return ONLY a JSON array of specifications:
[
  {{
    "specification_type": "electrical|physical|performance|certification|environmental|communication",
    "parameter": "parameter name",
    "value": "specification value",
    "unit": "unit of measurement",
    "product_sku": "related product SKU if applicable",
    "notes": "additional context"
  }}
]
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert. Extract precise specifications in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content
            specifications = self._parse_json_response(response_text)
            
            # Add source information
            for spec in specifications:
                if isinstance(spec, dict):
                    spec['source'] = source_file
            
            return specifications if isinstance(specifications, list) else []
            
        except Exception as e:
            self.logger.error(f"Error extracting specifications from {source_file}: {e}")
            return []
    
    def _extract_relationships(self, content: str, entities: List[Dict], source_file: str) -> List[Dict[str, Any]]:
        """Extract relationships between products"""
        
        if len(entities) < 2:
            return []
        
        entity_list = ", ".join([f"{e['sku']} ({e['name']})" for e in entities[:10]])
        
        prompt = f"""
You are a fire alarm systems expert. Analyze the relationships between these Simplex products found in the document:

Products found: {entity_list}

Document Content:
{content[:3000]}...

Identify relationships such as:
1. COMPATIBLE_WITH - products that work together
2. REQUIRES - one product needs another to function
3. HAS_MODULE - panels that support specific modules
4. ALTERNATIVE_TO - products that can substitute for each other
5. PART_OF - components that are part of a larger system

Return ONLY a JSON array of relationships:
[
  {{
    "source_sku": "source product SKU",
    "target_sku": "target product SKU", 
    "relationship_type": "COMPATIBLE_WITH|REQUIRES|HAS_MODULE|ALTERNATIVE_TO|PART_OF",
    "description": "description of the relationship",
    "technical_notes": "technical details about the relationship"
  }}
]

Only include relationships explicitly mentioned or strongly implied in the document.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a systems integration expert. Extract only documented relationships in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content
            relationships = self._parse_json_response(response_text)
            
            # Add source information and validate
            validated_relationships = []
            entity_skus = {e['sku'] for e in entities}
            
            for rel in relationships:
                if (isinstance(rel, dict) and 
                    rel.get('source_sku') in entity_skus and 
                    rel.get('target_sku') in entity_skus):
                    rel['source'] = source_file
                    validated_relationships.append(rel)
            
            return validated_relationships
            
        except Exception as e:
            self.logger.error(f"Error extracting relationships from {source_file}: {e}")
            return []
    
    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON block
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_text)
            
            # Try to find array directly
            array_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if array_match:
                return json.loads(array_match.group())
            
            # Try parsing the whole response
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            self.logger.debug(f"Response text: {response_text[:500]}")
            return []
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
            return []