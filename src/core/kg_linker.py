"""
KG-Linker Module: Multi-task prompting with OpenAI API
Performs entity extraction, path identification, Cypher generation, and draft answering
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class KGLinkerOutput:
    """Output from the KG-Linker module"""
    entities: List[Dict[str, Any]]
    paths: List[List[str]]
    cypher_query: str
    draft_answer: str
    raw_response: str

class KGLinker:
    """
    The cognitive core of BYOKG-RAG
    Interfaces with OpenAI to perform multi-task analysis
    """
    
    def __init__(self, openai_client: OpenAI, graph_schema: Dict[str, Any]):
        self.client = openai_client
        self.graph_schema = graph_schema
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_query(self, user_query: str, context: str = "") -> KGLinkerOutput:
        """
        Process user query through multi-task prompting
        
        Args:
            user_query: The user's natural language question
            context: Previous context from iterations
            
        Returns:
            KGLinkerOutput with extracted information
        """
        prompt = self._build_prompt(user_query, context)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            self.logger.debug(f"Raw LLM response: {response_text}")
            
            # Parse the structured response
            output = self._parse_response(response_text)
            output.raw_response = response_text
            
            return output
            
        except Exception as e:
            self.logger.error(f"Error in KG-Linker: {str(e)}")
            # Return empty output on error
            return KGLinkerOutput(
                entities=[],
                paths=[],
                cypher_query="",
                draft_answer="Unable to process query due to an error.",
                raw_response=""
            )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM"""
        return """You are a knowledge graph expert specializing in fire alarm systems.
Your task is to analyze user queries and extract structured information for graph-based retrieval.

You must always respond with the following sections:
1. ENTITIES: Extract relevant entities mentioned or implied in the query
2. PATHS: Identify potential graph traversal paths
3. CYPHER: Generate a Cypher query to retrieve relevant information
4. DRAFT_ANSWER: Provide a preliminary answer based on your understanding

Use the provided graph schema to ensure your outputs are valid."""
    
    def _build_prompt(self, user_query: str, context: str) -> str:
        """Build the complete prompt for the LLM"""
        
        schema_info = self._format_schema_info()
        
        prompt = f"""Graph Schema Information:
{schema_info}

Previous Context:
{context if context else "No previous context."}

User Query: {user_query}

Please analyze this query and provide:

<ENTITIES>
List all entities (nodes) that are relevant to answering this query.
Format: entity_type:identifier
Example: Product:4007ES, License:LIC-001
</ENTITIES>

<PATHS>
List potential paths through the graph that could help answer this query.
Format: Each path on a new line using -> notation
Example: Product->COMPATIBLE_WITH->Product
</PATHS>

<CYPHER>
Generate a Cypher query to retrieve relevant information.
The query should be valid Neo4j Cypher syntax.
</CYPHER>

<DRAFT_ANSWER>
Based on the query and your understanding of fire alarm systems, provide a draft answer.
This will be refined with actual graph data in subsequent iterations.
</DRAFT_ANSWER>"""

        return prompt
    
    def _format_schema_info(self) -> str:
        """Format graph schema information for the prompt"""
        schema_lines = []
        
        # Node types
        schema_lines.append("Node Types:")
        for node_type, properties in self.graph_schema.get('nodes', {}).items():
            props_str = ", ".join(properties)
            schema_lines.append(f"  - {node_type}: {props_str}")
        
        # Relationship types
        schema_lines.append("\nRelationship Types:")
        for rel_type, info in self.graph_schema.get('relationships', {}).items():
            schema_lines.append(f"  - {rel_type}: {info.get('description', '')}")
        
        return "\n".join(schema_lines)
    
    def _parse_response(self, response_text: str) -> KGLinkerOutput:
        """Parse the structured response from the LLM"""
        
        # Extract sections using regex
        entities = self._extract_section(response_text, "ENTITIES")
        paths = self._extract_section(response_text, "PATHS")
        cypher = self._extract_section(response_text, "CYPHER")
        draft_answer = self._extract_section(response_text, "DRAFT_ANSWER")
        
        # Parse entities
        parsed_entities = []
        if entities:
            for line in entities.strip().split('\n'):
                if ':' in line and line.strip():
                    parts = line.strip().split(':', 1)
                    if len(parts) == 2:
                        parsed_entities.append({
                            'type': parts[0].strip(),
                            'identifier': parts[1].strip()
                        })
        
        # Parse paths
        parsed_paths = []
        if paths:
            for line in paths.strip().split('\n'):
                if '->' in line and line.strip():
                    path_nodes = [n.strip() for n in line.split('->')]
                    parsed_paths.append(path_nodes)
        
        # Clean Cypher query
        cleaned_cypher = cypher.strip() if cypher else ""
        
        return KGLinkerOutput(
            entities=parsed_entities,
            paths=parsed_paths,
            cypher_query=cleaned_cypher,
            draft_answer=draft_answer.strip() if draft_answer else "",
            raw_response=""
        )
    
    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a section from the response text"""
        pattern = f"<{section_name}>(.*?)</{section_name}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

class GraphSchemaLoader:
    """
    Loads and manages the graph schema definition
    """
    
    @staticmethod
    def get_default_schema() -> Dict[str, Any]:
        """Get the default Simplex graph schema with expanded fire alarm domain entities"""
        return {
            "nodes": {
                "Product": ["sku", "name", "description", "type", "manufacturer"],
                "License": ["license_sku", "name", "description", "duration"],
                "Panel": ["sku", "name", "device_capacity", "loop_capacity"],
                "Module": ["sku", "name", "type", "channels"],
                "Feature": ["name", "description", "category"],
                "Detector": ["sku", "name", "type", "sensitivity", "operating_voltage"],
                "Base": ["sku", "name", "type", "compatibility", "sounder_capability"],
                "Annunciator": ["sku", "name", "type", "display_type", "zones"],
                "PowerSupply": ["sku", "name", "voltage", "current_rating", "backup_capability"],
                "Battery": ["sku", "name", "voltage", "amp_hours", "type"],
                "Circuit": ["name", "type", "max_devices", "wire_requirements"],
                "Accessory": ["sku", "name", "type", "compatibility"],
                "Specification": ["name", "type", "value", "unit", "standard"]
            },
            "relationships": {
                "COMPATIBLE_WITH": {
                    "description": "Indicates two products can work together",
                    "properties": ["notes", "verified_date", "weight"]
                },
                "REQUIRES_LICENSE": {
                    "description": "Product requires a specific license",
                    "properties": ["quantity", "mandatory", "weight"]
                },
                "PART_OF": {
                    "description": "Component is part of a larger system",
                    "properties": ["role", "quantity", "weight"]
                },
                "SUPPORTS": {
                    "description": "Product supports a specific feature",
                    "properties": ["version", "limitations", "weight"]
                },
                "HAS_BASE": {
                    "description": "Detector requires or uses a specific base",
                    "properties": ["required", "notes", "weight"]
                },
                "HAS_MODULE": {
                    "description": "Panel or system includes a specific module",
                    "properties": ["slot", "quantity", "weight"]
                },
                "ALTERNATIVE_TO": {
                    "description": "Product can be used as an alternative to another",
                    "properties": ["notes", "limitations", "weight"]
                },
                "REQUIRES_POWER_SUPPLY": {
                    "description": "Component requires specific power supply",
                    "properties": ["voltage", "current", "weight"]
                },
                "USES_BATTERY": {
                    "description": "Device uses specific battery for backup",
                    "properties": ["backup_hours", "quantity", "weight"]
                },
                "POWERED_BY": {
                    "description": "Device is powered by another component",
                    "properties": ["voltage", "current_draw", "weight"]
                },
                "REQUIRES_MODULE": {
                    "description": "System requires specific module for operation",
                    "properties": ["function", "mandatory", "weight"]
                },
                "HAS_SPECIFICATION": {
                    "description": "Product has specific technical specifications",
                    "properties": ["category", "compliance", "weight"]
                }
            }
        }