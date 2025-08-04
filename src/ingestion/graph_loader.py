"""
Neo4j Graph Schema and Bulk Loading Module
Handles creation of graph schema and loading extracted knowledge
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
import pandas as pd

logger = logging.getLogger(__name__)

class GraphSchemaManager:
    """
    Manages Neo4j graph schema and constraints
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_schema(self):
        """Create graph schema with constraints and indexes"""
        
        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT product_sku IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE",
            "CREATE CONSTRAINT license_sku IF NOT EXISTS FOR (l:License) REQUIRE l.license_sku IS UNIQUE",
            "CREATE CONSTRAINT panel_sku IF NOT EXISTS FOR (p:Panel) REQUIRE p.sku IS UNIQUE",
            
            # Indexes for performance
            "CREATE INDEX product_name IF NOT EXISTS FOR (p:Product) ON (p.name)",
            "CREATE INDEX product_type IF NOT EXISTS FOR (p:Product) ON (p.type)",
            "CREATE INDEX license_name IF NOT EXISTS FOR (l:License) ON (l.name)",
            "CREATE INDEX panel_capacity IF NOT EXISTS FOR (p:Panel) ON (p.device_capacity)"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    self.logger.info(f"Created constraint/index: {constraint[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Constraint might already exist: {e}")
    
    def clear_graph(self):
        """Clear all nodes and relationships from the graph"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            self.logger.info("Cleared all nodes and relationships from graph")

class Neo4jBulkLoader:
    """
    Handles bulk loading of data into Neo4j
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def load_entities(self, entities: List[Dict[str, Any]]):
        """Load entities into Neo4j using batch operations"""
        
        # Group entities by label
        entities_by_label = {}
        for entity in entities:
            label = entity['label']
            if label not in entities_by_label:
                entities_by_label[label] = []
            entities_by_label[label].append(entity)
        
        # Load each group
        for label, entity_group in entities_by_label.items():
            self._load_entity_batch(label, entity_group)
    
    def _load_entity_batch(self, label: str, entities: List[Dict[str, Any]]):
        """Load a batch of entities with the same label"""
        
        if not entities:
            return
        
        # Prepare batch data
        batch_data = []
        for entity in entities:
            props = entity['properties'].copy()
            props['_source_text'] = entity.get('source_text', '')[:500]  # Limit text length
            batch_data.append(props)
        
        # Create Cypher query based on label
        if label == "Product":
            query = f"""
            UNWIND $batch AS props
            MERGE (n:{label} {{sku: props.sku}})
            SET n += props
            """
        elif label == "License":
            query = f"""
            UNWIND $batch AS props
            MERGE (n:{label} {{license_sku: props.license_sku}})
            SET n += props
            """
        else:
            # Generic merge on name
            query = f"""
            UNWIND $batch AS props
            MERGE (n:{label} {{name: props.name}})
            SET n += props
            """
        
        with self.driver.session() as session:
            result = session.run(query, batch=batch_data)
            summary = result.consume()
            self.logger.info(f"Loaded {summary.counters.nodes_created} new {label} nodes, "
                           f"updated {summary.counters.properties_set} properties")
    
    def load_relationships(self, relationships: List[Dict[str, Any]]):
        """Load relationships into Neo4j"""
        
        # Group relationships by type
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel['type']
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append(rel)
        
        # Load each group
        for rel_type, rel_group in rels_by_type.items():
            self._load_relationship_batch(rel_type, rel_group)
    
    def _load_relationship_batch(self, rel_type: str, relationships: List[Dict[str, Any]]):
        """Load a batch of relationships with the same type"""
        
        if not relationships:
            return
        
        # Prepare batch data
        batch_data = []
        for rel in relationships:
            source = rel['source']
            target = rel['target']
            
            # Determine match keys
            source_key = 'sku' if source['label'] in ['Product', 'Panel'] else 'license_sku' if source['label'] == 'License' else 'name'
            target_key = 'sku' if target['label'] in ['Product', 'Panel'] else 'license_sku' if target['label'] == 'License' else 'name'
            
            batch_data.append({
                'source_label': source['label'],
                'source_key': source_key,
                'source_value': source['properties'].get(source_key, source['properties'].get('name', '')),
                'target_label': target['label'],
                'target_key': target_key,
                'target_value': target['properties'].get(target_key, target['properties'].get('name', '')),
                'properties': rel.get('properties', {})
            })
        
        # Create relationships
        query = f"""
        UNWIND $batch AS rel
        MATCH (source) WHERE labels(source) = [rel.source_label] AND source[rel.source_key] = rel.source_value
        MATCH (target) WHERE labels(target) = [rel.target_label] AND target[rel.target_key] = rel.target_value
        MERGE (source)-[r:{rel_type}]->(target)
        SET r += rel.properties
        """
        
        with self.driver.session() as session:
            result = session.run(query, batch=batch_data)
            summary = result.consume()
            self.logger.info(f"Created {summary.counters.relationships_created} {rel_type} relationships")

class CSVExporter:
    """
    Exports extracted knowledge to CSV format for neo4j-admin import
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def export_to_csv(self, knowledge_data: List[Dict[str, Any]]):
        """Export knowledge data to CSV files for bulk import"""
        
        # Collect all entities and relationships
        all_entities = []
        all_relationships = []
        
        for doc_data in knowledge_data:
            all_entities.extend(doc_data.get('entities', []))
            all_relationships.extend(doc_data.get('relationships', []))
        
        # Export entities by type
        self._export_entities(all_entities)
        
        # Export relationships by type
        self._export_relationships(all_relationships)
        
        self.logger.info(f"Exported {len(all_entities)} entities and {len(all_relationships)} relationships to CSV")
    
    def _export_entities(self, entities: List[Dict[str, Any]]):
        """Export entities to CSV files"""
        
        # Group by label
        entities_by_label = {}
        for entity in entities:
            label = entity['label']
            if label not in entities_by_label:
                entities_by_label[label] = []
            entities_by_label[label].append(entity)
        
        # Export each type
        for label, entity_list in entities_by_label.items():
            # Prepare data
            rows = []
            for entity in entity_list:
                row = entity['properties'].copy()
                row['_label'] = label
                rows.append(row)
            
            # Write to CSV
            if rows:
                df = pd.DataFrame(rows)
                csv_file = self.output_dir / f"{label.lower()}_nodes.csv"
                df.to_csv(csv_file, index=False)
                self.logger.info(f"Exported {len(rows)} {label} nodes to {csv_file}")
    
    def _export_relationships(self, relationships: List[Dict[str, Any]]):
        """Export relationships to CSV files"""
        
        # Group by type
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel['type']
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append(rel)
        
        # Export each type
        for rel_type, rel_list in rels_by_type.items():
            rows = []
            for rel in rel_list:
                source = rel['source']
                target = rel['target']
                
                # Determine identifiers
                source_id = source['properties'].get('sku') or source['properties'].get('license_sku') or source['properties'].get('name', '')
                target_id = target['properties'].get('sku') or target['properties'].get('license_sku') or target['properties'].get('name', '')
                
                row = {
                    '_source_id': source_id,
                    '_source_label': source['label'],
                    '_target_id': target_id,
                    '_target_label': target['label'],
                    '_type': rel_type
                }
                row.update(rel.get('properties', {}))
                rows.append(row)
            
            # Write to CSV
            if rows:
                df = pd.DataFrame(rows)
                csv_file = self.output_dir / f"{rel_type.lower()}_relationships.csv"
                df.to_csv(csv_file, index=False)
                self.logger.info(f"Exported {len(rows)} {rel_type} relationships to {csv_file}")