"""
Graph Retriever Toolkit: Multi-strategy retrieval from Neo4j
Implements entity linking, path retrieval, Cypher execution, and triplet retrieval
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
import json
from neo4j import GraphDatabase
import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    """Result from a retrieval operation"""
    method: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class GraphRetriever:
    """
    Multi-strategy graph retrieval system
    """
    
    def __init__(self, neo4j_driver, openai_client: Optional[OpenAI] = None):
        self.driver = neo4j_driver
        self.openai_client = openai_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize entity linker
        self.entity_linker = EntityLinker(neo4j_driver)
    
    def retrieve_all(self, kg_linker_output) -> List[RetrievalResult]:
        """
        Execute all retrieval strategies based on KG-Linker output
        
        Args:
            kg_linker_output: Output from KG-Linker module
            
        Returns:
            List of retrieval results from different strategies
        """
        results = []
        
        # 1. Entity Linking
        if kg_linker_output.entities:
            linked_entities = self.entity_linker.link_entities(kg_linker_output.entities)
            if linked_entities:
                results.append(RetrievalResult(
                    method="entity_linking",
                    data=linked_entities,
                    metadata={"entity_count": len(linked_entities)}
                ))
        
        # 2. Path Retrieval
        if kg_linker_output.paths:
            path_results = self._retrieve_paths(kg_linker_output.paths, linked_entities if kg_linker_output.entities else [])
            if path_results:
                results.append(RetrievalResult(
                    method="path_retrieval",
                    data=path_results,
                    metadata={"path_count": len(path_results)}
                ))
        
        # 3. Cypher Retrieval
        if kg_linker_output.cypher_query:
            cypher_results = self._execute_cypher(kg_linker_output.cypher_query)
            if cypher_results:
                results.append(RetrievalResult(
                    method="cypher_retrieval",
                    data=cypher_results,
                    metadata={"query": kg_linker_output.cypher_query}
                ))
        
        # 4. Triplet Retrieval (safety net)
        if linked_entities:
            triplet_results = self._retrieve_triplets(linked_entities)
            if triplet_results:
                results.append(RetrievalResult(
                    method="triplet_retrieval",
                    data=triplet_results,
                    metadata={"triplet_count": len(triplet_results)}
                ))
        
        return results
    
    def _retrieve_paths(self, paths: List[List[str]], linked_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Retrieve data following specified paths"""
        results = []
        
        # Get starting nodes from linked entities
        start_nodes = {e['data']['sku'] if 'sku' in e['data'] else e['data'].get('name', ''): e for e in linked_entities}
        
        with self.driver.session() as session:
            for path in paths[:5]:  # Limit to avoid too many queries
                if len(path) < 2:
                    continue
                
                # Build dynamic Cypher query for path
                query = self._build_path_query(path)
                
                try:
                    result = session.run(query)
                    for record in result:
                        results.append({
                            "path": path,
                            "data": dict(record)
                        })
                except Exception as e:
                    self.logger.warning(f"Path query failed: {e}")
        
        return results
    
    def _build_path_query(self, path: List[str]) -> str:
        """Build a Cypher query for a path pattern"""
        # Simple implementation - matches path pattern
        query_parts = []
        
        for i, node in enumerate(path):
            if i == 0:
                query_parts.append(f"(n0:{node})")
            elif i % 2 == 0:  # Node
                prev_idx = i // 2
                query_parts.append(f"-[r{prev_idx}]-(n{i//2}:{node})")
        
        query = "MATCH " + "".join(query_parts)
        query += " RETURN * LIMIT 50"
        
        return query
    
    def _execute_cypher(self, cypher_query: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query safely"""
        results = []
        
        # Basic query validation
        forbidden_keywords = ['DELETE', 'REMOVE', 'SET', 'CREATE', 'MERGE', 'DETACH']
        query_upper = cypher_query.upper()
        
        for keyword in forbidden_keywords:
            if keyword in query_upper:
                self.logger.warning(f"Forbidden keyword '{keyword}' in query, skipping")
                return results
        
        try:
            with self.driver.session() as session:
                # Add LIMIT if not present
                if 'LIMIT' not in query_upper:
                    cypher_query += ' LIMIT 100'
                
                result = session.run(cypher_query)
                
                for record in result:
                    # Convert Neo4j objects to plain dictionaries
                    row_dict = {}
                    for key, value in record.items():
                        if hasattr(value, '_properties'):  # Neo4j Node/Relationship
                            row_dict[key] = dict(value)
                        else:
                            row_dict[key] = value
                    results.append(row_dict)
                    
        except Exception as e:
            self.logger.error(f"Cypher execution failed: {e}")
        
        return results
    
    def _retrieve_triplets(self, linked_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Retrieve triplets (relationships) connected to linked entities"""
        triplets = []
        
        with self.driver.session() as session:
            for entity in linked_entities[:10]:  # Limit to avoid too many queries
                entity_id = entity['data'].get('sku') or entity['data'].get('license_sku') or entity['data'].get('name')
                
                if not entity_id:
                    continue
                
                # Query for all relationships of this entity
                query = """
                MATCH (n)-[r]-(m)
                WHERE (n.sku = $id OR n.license_sku = $id OR n.name = $id)
                RETURN n, type(r) as rel_type, r, m
                LIMIT 20
                """
                
                result = session.run(query, id=entity_id)
                
                for record in result:
                    triplets.append({
                        "source": dict(record['n']),
                        "relationship": {
                            "type": record['rel_type'],
                            "properties": dict(record['r'])
                        },
                        "target": dict(record['m'])
                    })
        
        return triplets

class EntityLinker:
    """
    Links ambiguous entity mentions to concrete graph nodes
    """
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def link_entities(self, entities: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Link entity mentions to actual nodes in the graph
        
        Args:
            entities: List of entity mentions from KG-Linker
            
        Returns:
            List of linked entities with their graph data
        """
        linked = []
        
        with self.driver.session() as session:
            for entity in entities:
                entity_type = entity.get('type', '')
                identifier = entity.get('identifier', '')
                
                if not entity_type or not identifier:
                    continue
                
                # Try exact match first
                exact_match = self._exact_match(session, entity_type, identifier)
                if exact_match:
                    linked.append({
                        "mention": entity,
                        "data": exact_match,
                        "match_type": "exact"
                    })
                    continue
                
                # Try fuzzy match
                fuzzy_matches = self._fuzzy_match(session, entity_type, identifier)
                if fuzzy_matches:
                    # Take best match
                    linked.append({
                        "mention": entity,
                        "data": fuzzy_matches[0]['node'],
                        "match_type": "fuzzy",
                        "score": fuzzy_matches[0]['score']
                    })
        
        self.logger.info(f"Linked {len(linked)} out of {len(entities)} entities")
        return linked
    
    def _exact_match(self, session, entity_type: str, identifier: str) -> Optional[Dict[str, Any]]:
        """Try exact matching on common properties"""
        
        # Build query based on entity type
        if entity_type in ['Product', 'Panel']:
            query = f"""
            MATCH (n:{entity_type})
            WHERE n.sku = $identifier OR n.name = $identifier
            RETURN n LIMIT 1
            """
        elif entity_type == 'License':
            query = f"""
            MATCH (n:{entity_type})
            WHERE n.license_sku = $identifier OR n.name = $identifier
            RETURN n LIMIT 1
            """
        else:
            query = f"""
            MATCH (n:{entity_type})
            WHERE n.name = $identifier
            RETURN n LIMIT 1
            """
        
        result = session.run(query, identifier=identifier)
        record = result.single()
        
        if record:
            return dict(record['n'])
        return None
    
    def _fuzzy_match(self, session, entity_type: str, identifier: str) -> List[Dict[str, Any]]:
        """Fuzzy matching using string similarity"""
        
        # Get all nodes of the specified type
        query = f"MATCH (n:{entity_type}) RETURN n LIMIT 100"
        result = session.run(query)
        
        matches = []
        identifier_lower = identifier.lower()
        
        for record in result:
            node = dict(record['n'])
            
            # Calculate similarity score
            score = 0.0
            
            # Check different properties
            for prop in ['sku', 'license_sku', 'name']:
                if prop in node and node[prop]:
                    prop_value = str(node[prop]).lower()
                    
                    # Exact match
                    if prop_value == identifier_lower:
                        score = 1.0
                        break
                    
                    # Contains match
                    if identifier_lower in prop_value or prop_value in identifier_lower:
                        score = max(score, 0.8)
                    
                    # Partial match
                    common_chars = len(set(identifier_lower) & set(prop_value))
                    score = max(score, common_chars / max(len(identifier_lower), len(prop_value)))
            
            if score > 0.5:  # Threshold
                matches.append({
                    "node": node,
                    "score": score
                })
        
        # Sort by score
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return matches[:5]  # Return top 5 matches