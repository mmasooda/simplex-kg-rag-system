#!/usr/bin/env python3
"""
Create sample knowledge graph data for demonstration
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import os
import json
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_knowledge_graph():
    """Create sample knowledge graph with Simplex products"""
    
    # Sample products with detailed specifications
    products = [
        {
            "sku": "4100ES",
            "name": "Simplex 4100ES Fire Alarm Control Panel",
            "description": "Advanced fire alarm control panel with 636 addressable points, supports voice evacuation, built-in networking capabilities, suitable for large commercial buildings",
            "type": "Control Panel",
            "manufacturer": "Simplex",
            "capacity": "636 points",
            "features": "Voice evacuation, networking, LCD display"
        },
        {
            "sku": "4090-9001",
            "name": "TrueAlarm Photoelectric Smoke Detector",
            "description": "Intelligent addressable photoelectric smoke detector with advanced algorithms, suitable for office environments, compatible with 4100ES panel",
            "type": "Smoke Detector",
            "manufacturer": "Simplex",
            "technology": "Photoelectric",
            "application": "Office, commercial"
        },
        {
            "sku": "4098-9714",
            "name": "Addressable Manual Pull Station",
            "description": "Single action addressable manual pull station with LED indicator, weatherproof design, direct connection to 4100ES",
            "type": "Manual Pull Station",  
            "manufacturer": "Simplex",
            "features": "LED indicator, single action"
        },
        {
            "sku": "4906-9356",
            "name": "Multi-Candela Horn Strobe",
            "description": "Wall mount horn strobe notification appliance with multiple candela settings (15/30/75/95 cd), 24VDC operation",
            "type": "Notification Device",
            "manufacturer": "Simplex",
            "candela_options": "15/30/75/95 cd",
            "voltage": "24VDC"
        },
        {
            "sku": "4090-9788",
            "name": "Fixed Temperature Heat Detector",
            "description": "Fixed temperature heat detector 135°F activation, suitable for storage areas and kitchens, addressable technology",
            "type": "Heat Detector",
            "manufacturer": "Simplex",
            "activation_temp": "135°F",
            "technology": "Fixed temperature"
        },
        {
            "sku": "4020-9101",
            "name": "Simplex IDNet Interface Module",
            "description": "Interface module for connecting conventional devices to IDNet addressable system, supports 4100ES integration",
            "type": "Interface Module",
            "manufacturer": "Simplex",
            "compatibility": "4100ES, IDNet"
        }
    ]
    
    # Sample licenses
    licenses = [
        {
            "license_sku": "LIC-4100ES-BASIC",
            "name": "4100ES Basic License",
            "description": "Basic software license for 4100ES panel",
            "duration": "Perpetual"
        },
        {
            "license_sku": "LIC-4100ES-VOICE",
            "name": "4100ES Voice License", 
            "description": "Voice evacuation license for 4100ES panel",
            "duration": "Perpetual"
        }
    ]
    
    # Sample relationships with detailed technical specifications
    relationships = [
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "Product", "sku": "4090-9001"},
            "type": "COMPATIBLE_WITH",
            "properties": {"notes": "Direct IDNet addressable connection, up to 636 devices per panel", "verified": True, "connection_type": "IDNet addressable"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "Product", "sku": "4098-9714"},
            "type": "COMPATIBLE_WITH", 
            "properties": {"notes": "Addressable manual station with LED feedback", "verified": True, "connection_type": "IDNet addressable"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "Product", "sku": "4906-9356"},
            "type": "COMPATIBLE_WITH",
            "properties": {"notes": "NAC circuit connection, 24VDC operation", "verified": True, "connection_type": "NAC circuit"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "Product", "sku": "4090-9788"},
            "type": "COMPATIBLE_WITH",
            "properties": {"notes": "Heat detector for mechanical rooms and kitchens", "verified": True, "connection_type": "IDNet addressable"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "Product", "sku": "4020-9101"},
            "type": "COMPATIBLE_WITH",
            "properties": {"notes": "Interface module for conventional device integration", "verified": True, "connection_type": "IDNet interface"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "License", "license_sku": "LIC-4100ES-BASIC"},
            "type": "REQUIRES_LICENSE",
            "properties": {"quantity": 1, "mandatory": True, "purpose": "Basic panel operation"}
        },
        {
            "source": {"label": "Product", "sku": "4100ES"},
            "target": {"label": "License", "license_sku": "LIC-4100ES-VOICE"},
            "type": "REQUIRES_LICENSE",
            "properties": {"quantity": 1, "mandatory": False, "purpose": "Voice evacuation features"}
        },
        {
            "source": {"label": "Product", "sku": "4090-9001"},
            "target": {"label": "Product", "sku": "4090-9788"},
            "type": "COMPATIBLE_WITH",
            "properties": {"notes": "Both detectors can be used in same zone for dual sensing", "verified": True, "application": "Dual detection"}
        }
    ]
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    try:
        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing data")
            
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT product_sku IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE",
                "CREATE CONSTRAINT license_sku IF NOT EXISTS FOR (l:License) REQUIRE l.license_sku IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except:
                    pass  # Constraint might already exist
            
            # Create products
            for product in products:
                session.run("""
                    CREATE (p:Product {
                        sku: $sku,
                        name: $name,
                        description: $description,
                        type: $type,
                        manufacturer: $manufacturer
                    })
                """, **product)
            
            logger.info(f"Created {len(products)} products")
            
            # Create licenses
            for license in licenses:
                session.run("""
                    CREATE (l:License {
                        license_sku: $license_sku,
                        name: $name,
                        description: $description,
                        duration: $duration
                    })
                """, **license)
            
            logger.info(f"Created {len(licenses)} licenses")
            
            # Create relationships
            for rel in relationships:
                source = rel['source']
                target = rel['target']
                rel_type = rel['type']
                props = rel['properties']
                
                if source['label'] == 'Product' and target['label'] == 'Product':
                    query = f"""
                        MATCH (s:Product {{sku: $source_id}})
                        MATCH (t:Product {{sku: $target_id}})
                        CREATE (s)-[r:{rel_type}]->(t)
                        SET r += $props
                    """
                    session.run(query, 
                               source_id=source['sku'], 
                               target_id=target['sku'],
                               props=props)
                
                elif source['label'] == 'Product' and target['label'] == 'License':
                    query = f"""
                        MATCH (s:Product {{sku: $source_id}})
                        MATCH (t:License {{license_sku: $target_id}})
                        CREATE (s)-[r:{rel_type}]->(t)
                        SET r += $props
                    """
                    session.run(query,
                               source_id=source['sku'],
                               target_id=target['license_sku'], 
                               props=props)
            
            logger.info(f"Created {len(relationships)} relationships")
            
            # Verify the data
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
            for record in result:
                logger.info(f"{record['label']}: {record['count']} nodes")
            
            result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count")
            for record in result:
                logger.info(f"{record['rel_type']}: {record['count']} relationships")
            
            logger.info("Sample knowledge graph created successfully!")
    
    finally:
        driver.close()

if __name__ == "__main__":
    create_sample_knowledge_graph()