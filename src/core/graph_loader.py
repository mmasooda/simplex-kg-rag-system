"""
Graph Loader: Loads extracted knowledge into Neo4j knowledge graph
Handles Simplex fire alarm product data with proper relationships
"""

import logging
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase, Driver
import time

logger = logging.getLogger(__name__)

class GraphLoader:
    """
    Loads extracted knowledge into Neo4j knowledge graph
    Creates nodes and relationships for Simplex fire alarm products
    """
    
    def __init__(self, neo4j_driver: Driver):
        self.driver = neo4j_driver
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize constraints and indexes
        self._setup_graph_constraints()
    
    def _setup_graph_constraints(self):
        """Setup graph constraints and indexes for better performance"""
        constraints = [
            "CREATE CONSTRAINT simplex_product_sku_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE",
            "CREATE CONSTRAINT simplex_panel_sku_unique IF NOT EXISTS FOR (p:Panel) REQUIRE p.sku IS UNIQUE", 
            "CREATE CONSTRAINT simplex_module_sku_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.sku IS UNIQUE",
            "CREATE CONSTRAINT simplex_device_sku_unique IF NOT EXISTS FOR (d:Device) REQUIRE d.sku IS UNIQUE",
            "CREATE INDEX product_name_index IF NOT EXISTS FOR (p:Product) ON (p.name)",
            "CREATE INDEX product_type_index IF NOT EXISTS FOR (p:Product) ON (p.type)"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    self.logger.debug(f"Applied constraint: {constraint}")
                except Exception as e:
                    self.logger.debug(f"Constraint may already exist: {e}")
    
    def load_knowledge(self, knowledge_data: Dict[str, Any], source_file: str) -> int:
        """
        Load extracted knowledge into the graph
        
        Args:
            knowledge_data: Dictionary with entities, relationships, specifications
            source_file: Source file for tracking
            
        Returns:
            Number of nodes created
        """
        self.logger.info(f"Loading knowledge from {source_file} into graph")
        
        nodes_created = 0
        
        try:
            with self.driver.session() as session:
                # Load entities as nodes
                nodes_created += self._load_entities(session, knowledge_data.get('entities', []), source_file)
                
                # Load specifications as properties or separate nodes
                self._load_specifications(session, knowledge_data.get('specifications', []), source_file)
                
                # Load relationships
                self._load_relationships(session, knowledge_data.get('relationships', []), source_file)
                
                self.logger.info(f"Successfully loaded knowledge from {source_file}: {nodes_created} nodes created")
                
        except Exception as e:
            self.logger.error(f"Error loading knowledge from {source_file}: {e}")
        
        return nodes_created
    
    def _load_entities(self, session, entities: List[Dict], source_file: str) -> int:
        """Load product entities as nodes"""
        nodes_created = 0
        
        for entity in entities:
            try:
                if not entity.get('sku') or not entity.get('name'):
                    self.logger.warning(f"Skipping entity with missing SKU or name: {entity}")
                    continue
                
                # Determine node labels based on product type
                labels = self._get_node_labels(entity.get('type', 'Product'))
                
                # Prepare node properties
                properties = {
                    'sku': entity['sku'],
                    'name': entity['name'],
                    'type': entity.get('type', 'Product'),
                    'category': entity.get('category', ''),
                    'description': entity.get('description', ''),
                    'specifications': entity.get('specifications', ''),
                    'applications': entity.get('applications', ''),
                    'manufacturer': entity.get('manufacturer', 'Simplex'),
                    'source_file': source_file,
                    'created_timestamp': int(time.time())
                }
                
                # Remove empty properties
                properties = {k: v for k, v in properties.items() if v}
                
                # Create or update node
                labels_str = ':'.join(labels)
                query = f"""
                    MERGE (p:{labels_str} {{sku: $sku}})
                    SET p += $properties
                    RETURN p
                """
                
                result = session.run(query, sku=entity['sku'], properties=properties)
                
                if result.single():
                    nodes_created += 1
                    self.logger.debug(f"Created/updated node: {entity['sku']} - {entity['name']}")
                
            except Exception as e:
                self.logger.error(f"Error creating node for entity {entity.get('sku', 'unknown')}: {e}")
        
        return nodes_created
    
    def _load_specifications(self, session, specifications: List[Dict], source_file: str):
        """Load technical specifications"""
        for spec in specifications:
            try:
                if not spec.get('parameter'):
                    continue
                
                # If specification is linked to a specific product, add it as property
                if spec.get('product_sku'):
                    param_name = f"spec_{spec['parameter'].lower().replace(' ', '_')}"
                    query = f"""
                        MATCH (p:Product {{sku: $product_sku}})
                        SET p.{param_name} = $value
                    """
                    
                    session.run(query, 
                               product_sku=spec['product_sku'],
                               value=spec.get('value', ''))
                
                # Also create specification nodes for complex specs
                if spec.get('specification_type') and spec.get('value'):
                    spec_properties = {
                        'type': spec['specification_type'],
                        'parameter': spec['parameter'],
                        'value': spec.get('value', ''),
                        'unit': spec.get('unit', ''),
                        'notes': spec.get('notes', ''),
                        'source_file': source_file
                    }
                    
                    # Remove empty properties
                    spec_properties = {k: v for k, v in spec_properties.items() if v}
                    
                    query = """
                        CREATE (s:Specification $properties)
                    """
                    
                    session.run(query, properties=spec_properties)
                    
                    # Link to product if specified
                    if spec.get('product_sku'):
                        link_query = """
                            MATCH (p:Product {sku: $product_sku})
                            MATCH (s:Specification {parameter: $parameter, value: $value})
                            WHERE s.source_file = $source_file
                            MERGE (p)-[:HAS_SPECIFICATION]->(s)
                        """
                        
                        session.run(link_query,
                                   product_sku=spec['product_sku'],
                                   parameter=spec['parameter'],
                                   value=spec['value'],
                                   source_file=source_file)
                
            except Exception as e:
                self.logger.error(f"Error loading specification {spec.get('parameter', 'unknown')}: {e}")
    
    def _load_relationships(self, session, relationships: List[Dict], source_file: str):
        """Load relationships between products"""
        for rel in relationships:
            try:
                if not all([rel.get('source_sku'), rel.get('target_sku'), rel.get('relationship_type')]):
                    self.logger.warning(f"Skipping incomplete relationship: {rel}")
                    continue
                
                # Prepare relationship properties
                rel_properties = {
                    'description': rel.get('description', ''),
                    'technical_notes': rel.get('technical_notes', ''),
                    'source_file': source_file,
                    'created_timestamp': int(time.time())
                }
                
                # Remove empty properties
                rel_properties = {k: v for k, v in rel_properties.items() if v}
                
                # Create relationship
                rel_type = rel['relationship_type'].upper()
                query = f"""
                    MATCH (source:Product {{sku: $source_sku}})
                    MATCH (target:Product {{sku: $target_sku}})
                    MERGE (source)-[r:{rel_type}]->(target)
                    SET r += $properties
                    RETURN r
                """
                
                result = session.run(query,
                                   source_sku=rel['source_sku'],
                                   target_sku=rel['target_sku'],
                                   properties=rel_properties)
                
                if result.single():
                    self.logger.debug(f"Created relationship: {rel['source_sku']} -{rel_type}-> {rel['target_sku']}")
                
            except Exception as e:
                self.logger.error(f"Error creating relationship {rel.get('relationship_type', 'unknown')}: {e}")
    
    def _get_node_labels(self, product_type: str) -> List[str]:
        """Determine node labels based on product type"""
        base_labels = ['Product']
        
        # Map product types to specific labels
        type_mapping = {
            'Panel': ['Panel'],
            'Module': ['Module'], 
            'Device': ['Device'],
            'Control Panel': ['Panel'],
            'Interface Module': ['Module'],
            'I/O Module': ['Module'],
            'Control Module': ['Module'],
            'Smoke Detector': ['Device'],
            'Heat Detector': ['Device'],
            'Manual Station': ['Device'],
            'Notification Device': ['Device'],
            'Voice Notification Device': ['Device']
        }
        
        if product_type in type_mapping:
            return base_labels + type_mapping[product_type]
        
        return base_labels
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get current graph statistics"""
        try:
            with self.driver.session() as session:
                # Count nodes by label
                node_counts = {}
                result = session.run("""
                    MATCH (n)
                    RETURN labels(n) as labels, count(n) as count
                """)
                
                for record in result:
                    labels = record['labels']
                    count = record['count']
                    key = ':'.join(sorted(labels))
                    node_counts[key] = count
                
                # Count relationships by type
                rel_counts = {}
                result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as rel_type, count(r) as count
                """)
                
                for record in result:
                    rel_counts[record['rel_type']] = record['count']
                
                # Get total counts
                total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()['count']
                total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                
                return {
                    'total_nodes': total_nodes,
                    'total_relationships': total_rels,
                    'nodes_by_label': node_counts,
                    'relationships_by_type': rel_counts
                }
                
        except Exception as e:
            self.logger.error(f"Error getting graph statistics: {e}")
            return {}
    
    def clear_source_data(self, source_file: str) -> int:
        """Clear all data from a specific source file"""
        try:
            with self.driver.session() as session:
                # Count nodes to be deleted
                count_result = session.run("""
                    MATCH (n {source_file: $source_file})
                    RETURN count(n) as count
                """, source_file=source_file)
                
                nodes_to_delete = count_result.single()['count']
                
                # Delete nodes and their relationships
                session.run("""
                    MATCH (n {source_file: $source_file})
                    DETACH DELETE n
                """, source_file=source_file)
                
                self.logger.info(f"Cleared {nodes_to_delete} nodes from {source_file}")
                return nodes_to_delete
                
        except Exception as e:
            self.logger.error(f"Error clearing data from {source_file}: {e}")
            return 0