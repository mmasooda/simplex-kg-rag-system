#!/usr/bin/env python3
"""
Enhanced Simplex Product Knowledge Graph Creator
Implements comprehensive schema with Panel, Module, Device nodes and proper relationships
Based on user specifications for Simplex fire alarm products
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

def create_enhanced_simplex_kg():
    """Create comprehensive Simplex Product Knowledge Graph"""
    
    # PANEL NODES - Fire Alarm Control Panels
    panels = [
        {
            "sku": "4100ES",
            "name": "Simplex 4100ES Fire Alarm Control Panel", 
            "type": "Panel",
            "category": "Control Panel",
            "manufacturer": "Simplex",
            "description": "Advanced fire alarm control panel with 636 addressable points, supports voice evacuation, built-in networking capabilities, suitable for large commercial buildings",
            "capacity": "636 points",
            "features": "Voice evacuation, networking, LCD display, IDNet addressable",
            "power_requirements": "120/240 VAC, 50/60 Hz",
            "applications": "Large commercial buildings, hospitals, universities",
            "certifications": "UL 864 UUKL, FM Approved"
        },
        {
            "sku": "4010ES", 
            "name": "Simplex 4010ES Fire Alarm Control Panel",
            "type": "Panel",
            "category": "Control Panel", 
            "manufacturer": "Simplex",
            "description": "Mid-range fire alarm control panel with 318 addressable points, networking capability, ideal for medium commercial buildings",
            "capacity": "318 points",
            "features": "Networking, LCD display, IDNet addressable",
            "power_requirements": "120/240 VAC, 50/60 Hz", 
            "applications": "Medium commercial buildings, schools, retail",
            "certifications": "UL 864 UUKL, FM Approved"
        },
        {
            "sku": "4007ES",
            "name": "Simplex 4007ES Fire Alarm Control Panel",
            "type": "Panel", 
            "category": "Control Panel",
            "manufacturer": "Simplex",
            "description": "Compact fire alarm control panel with 159 addressable points, ideal for smaller installations",
            "capacity": "159 points",
            "features": "LCD display, IDNet addressable",
            "power_requirements": "120 VAC, 50/60 Hz",
            "applications": "Small commercial buildings, offices, restaurants", 
            "certifications": "UL 864 UUKL, FM Approved"
        }
    ]
    
    # MODULE NODES - Interface and Control Modules
    modules = [
        {
            "sku": "4020-9101",
            "name": "IDNet Interface Module",
            "type": "Module",
            "category": "Interface Module",
            "manufacturer": "Simplex", 
            "description": "Interface module for connecting conventional devices to IDNet addressable system, supports 4100ES integration",
            "input_types": "Contact closure, voltage supervision",
            "output_types": "Relay contact",
            "wiring": "2-wire IDNet addressable",
            "compatibility": "4100ES, 4010ES, 4007ES",
            "applications": "Converting conventional devices to addressable"
        },
        {
            "sku": "4090-9003",
            "name": "Dual Input/Output Module", 
            "type": "Module",
            "category": "I/O Module",
            "manufacturer": "Simplex",
            "description": "Dual input/output module with supervised inputs and form-C relay outputs",
            "input_types": "Two supervised inputs",
            "output_types": "Two form-C relay outputs", 
            "wiring": "2-wire IDNet addressable",
            "compatibility": "4100ES, 4010ES, 4007ES",
            "applications": "Door control, equipment supervision, auxiliary functions"
        },
        {
            "sku": "4100-9004",
            "name": "Control Relay Module",
            "type": "Module",
            "category": "Control Module", 
            "manufacturer": "Simplex",
            "description": "Four form-C relay outputs for controlling building systems",
            "input_types": "None",
            "output_types": "Four form-C relay outputs (10A @ 30VDC, 10A @ 250VAC)",
            "wiring": "2-wire IDNet addressable",
            "compatibility": "4100ES, 4010ES, 4007ES",
            "applications": "HVAC control, elevator recall, door release"
        }
    ]
    
    # DEVICE NODES - Detection and Notification Devices  
    devices = [
        {
            "sku": "4090-9001", 
            "name": "TrueAlarm Photoelectric Smoke Detector",
            "type": "Device",
            "category": "Smoke Detector",
            "manufacturer": "Simplex",
            "description": "Intelligent addressable photoelectric smoke detector with advanced algorithms, suitable for office environments",
            "detection_principle": "Photoelectric", 
            "sensitivity": "Drift compensation with automatic testing",
            "wiring": "2-wire IDNet addressable",
            "base_required": "4098-9792 Detector Base",
            "applications": "Offices, corridors, common areas",
            "certifications": "UL 268, FM Approved"
        },
        {
            "sku": "4090-9788",
            "name": "Fixed Temperature Heat Detector", 
            "type": "Device",
            "category": "Heat Detector",
            "manufacturer": "Simplex",
            "description": "Fixed temperature heat detector 135°F activation, suitable for storage areas and kitchens",
            "detection_principle": "Fixed temperature", 
            "activation_temp": "135°F (57°C)",
            "wiring": "2-wire IDNet addressable",
            "base_required": "4098-9792 Detector Base",
            "applications": "Storage rooms, kitchens, mechanical rooms",
            "certifications": "UL 521, FM Approved"
        },
        {
            "sku": "4098-9714",
            "name": "Addressable Manual Pull Station", 
            "type": "Device",
            "category": "Manual Station",
            "manufacturer": "Simplex",
            "description": "Single action addressable manual pull station with LED indicator, weatherproof design",
            "operation": "Single action pull",
            "indication": "LED status indicator",
            "wiring": "2-wire IDNet addressable", 
            "mounting": "Single gang box",
            "applications": "Exit routes, corridors, stairwells",
            "certifications": "UL 38, FM Approved"
        },
        {
            "sku": "4906-9356",
            "name": "Multi-Candela Horn Strobe",
            "type": "Device", 
            "category": "Notification Device",
            "manufacturer": "Simplex",
            "description": "Wall mount horn strobe notification appliance with multiple candela settings",
            "candela_options": "15/30/75/95 cd",
            "sound_output": "90 dBA at 10 feet",
            "voltage": "24VDC", 
            "wiring": "NAC circuit",
            "mounting": "Wall mount",
            "applications": "General notification, corridors, rooms",
            "certifications": "UL 1971, FM Approved"
        },
        {
            "sku": "4906-9001",
            "name": "High-Power Speaker Strobe",
            "type": "Device",
            "category": "Voice Notification Device", 
            "manufacturer": "Simplex",
            "description": "High-power speaker strobe for voice evacuation systems with selectable candela",
            "candela_options": "15/30/75/110 cd",
            "sound_output": "Voice messages and tones", 
            "voltage": "25VRMS/70VRMS",
            "wiring": "Speaker circuit + strobe circuit",
            "mounting": "Wall mount",
            "applications": "Voice evacuation systems, large areas",
            "certifications": "UL 1480, UL 1971, FM Approved"
        }
    ]
    
    # COMPREHENSIVE RELATIONSHIPS
    relationships = [
        # PANEL-MODULE COMPATIBILITY
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Module", "sku": "4020-9101"}, 
            "relationship": "HAS_MODULE",
            "properties": {
                "max_modules": 636,
                "connection_type": "IDNet addressable",
                "power_supplied": True,
                "supervision": "Continuous",
                "notes": "Up to 636 addressable modules supported"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Module", "sku": "4090-9003"},
            "relationship": "HAS_MODULE", 
            "properties": {
                "max_modules": 636,
                "connection_type": "IDNet addressable", 
                "power_supplied": True,
                "supervision": "Continuous",
                "notes": "Dual I/O modules for system control"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4010ES"},
            "target": {"type": "Module", "sku": "4020-9101"},
            "relationship": "HAS_MODULE",
            "properties": {
                "max_modules": 318,
                "connection_type": "IDNet addressable",
                "power_supplied": True, 
                "supervision": "Continuous",
                "notes": "Mid-range panel supports up to 318 devices"
            }
        },
        
        # PANEL-DEVICE COMPATIBILITY 
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4090-9001"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "connection_type": "IDNet addressable",
                "max_devices": 636,
                "power_supplied": True,
                "polling_rate": "10 seconds",
                "drift_compensation": True,
                "notes": "Direct IDNet connection with automatic drift compensation"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4090-9788"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "connection_type": "IDNet addressable",
                "max_devices": 636,
                "power_supplied": True,
                "polling_rate": "10 seconds", 
                "notes": "Heat detectors for harsh environments"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4098-9714"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "connection_type": "IDNet addressable",
                "max_devices": 636,
                "power_supplied": True,
                "led_control": True,
                "notes": "Manual stations with LED feedback control"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4906-9356"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "connection_type": "NAC circuit",
                "max_devices": "Per NAC rating",
                "power_supplied": True,
                "synchronization": True,
                "notes": "Horn strobes connected via NAC circuits"
            }
        },
        
        # MODULE-DEVICE RELATIONSHIPS
        {
            "source": {"type": "Module", "sku": "4020-9101"},
            "target": {"type": "Device", "sku": "4090-9001"},
            "relationship": "REQUIRES",
            "properties": {
                "purpose": "Conventional device interface",
                "supervision": "End-of-line resistor",
                "notes": "Interface module required for conventional smoke detectors"
            }
        },
        
        # ALTERNATIVE PRODUCT RELATIONSHIPS
        {
            "source": {"type": "Panel", "sku": "4010ES"},
            "target": {"type": "Panel", "sku": "4100ES"},
            "relationship": "ALTERNATIVE_TO",
            "properties": {
                "upgrade_path": True,
                "capacity_difference": "318 vs 636 points",
                "feature_differences": "4100ES has voice evacuation capability",
                "notes": "4100ES is the high-capacity alternative to 4010ES"
            }
        },
        {
            "source": {"type": "Device", "sku": "4090-9788"},
            "target": {"type": "Device", "sku": "4090-9001"},
            "relationship": "ALTERNATIVE_TO", 
            "properties": {
                "application_difference": "Heat vs smoke detection",
                "environment_suitability": "Heat detector for harsh environments",
                "notes": "Heat detectors alternative for areas unsuitable for smoke detection"
            }
        },
        
        # DEVICE COMPATIBILITY (SAME SYSTEM)
        {
            "source": {"type": "Device", "sku": "4090-9001"},
            "target": {"type": "Device", "sku": "4090-9788"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "same_zone": True,
                "dual_detection": True,
                "notes": "Can be used together in same zone for enhanced protection"
            }
        }
    ]
    
    # Connect to Neo4j and create the knowledge graph
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    try:
        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing knowledge graph data")
            
            # Create constraints for better performance
            constraints = [
                "CREATE CONSTRAINT simplex_panel_sku IF NOT EXISTS FOR (p:Panel) REQUIRE p.sku IS UNIQUE",
                "CREATE CONSTRAINT simplex_module_sku IF NOT EXISTS FOR (m:Module) REQUIRE m.sku IS UNIQUE", 
                "CREATE CONSTRAINT simplex_device_sku IF NOT EXISTS FOR (d:Device) REQUIRE d.sku IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint may already exist: {e}")
            
            # Create Panel nodes
            logger.info("Creating Panel nodes...")
            for panel in panels:
                session.run("""
                    CREATE (p:Panel {
                        sku: $sku,
                        name: $name,
                        type: $type,
                        category: $category,
                        manufacturer: $manufacturer,
                        description: $description,
                        capacity: $capacity, 
                        features: $features,
                        power_requirements: $power_requirements,
                        applications: $applications,
                        certifications: $certifications
                    })
                """, **panel)
            
            logger.info(f"Created {len(panels)} Panel nodes")
            
            # Create Module nodes
            logger.info("Creating Module nodes...")
            for module in modules:
                # Handle optional fields
                module_props = {k: v for k, v in module.items() if v is not None}
                
                # Build dynamic query based on available properties
                prop_str = ", ".join([f"{k}: ${k}" for k in module_props.keys()])
                query = f"""
                    CREATE (m:Module {{
                        {prop_str}
                    }})
                """
                session.run(query, **module_props)
            
            logger.info(f"Created {len(modules)} Module nodes")
            
            # Create Device nodes
            logger.info("Creating Device nodes...")
            for device in devices:
                # Handle optional fields
                device_props = {k: v for k, v in device.items() if v is not None}
                
                # Build dynamic query based on available properties
                prop_str = ", ".join([f"{k}: ${k}" for k in device_props.keys()])
                query = f"""
                    CREATE (d:Device {{
                        {prop_str}
                    }})
                """
                session.run(query, **device_props)
            
            logger.info(f"Created {len(devices)} Device nodes")
            
            # Create relationships
            logger.info("Creating relationships...")
            for rel in relationships:
                source = rel['source']
                target = rel['target'] 
                rel_type = rel['relationship']
                props = rel['properties']
                
                # Dynamic relationship creation based on node types
                query = f"""
                    MATCH (s:{source['type']} {{sku: $source_sku}})
                    MATCH (t:{target['type']} {{sku: $target_sku}})
                    CREATE (s)-[r:{rel_type}]->(t)
                    SET r += $props
                """
                
                session.run(query,
                           source_sku=source['sku'],
                           target_sku=target['sku'],
                           props=props)
            
            logger.info(f"Created {len(relationships)} relationships")
            
            # Verify the knowledge graph
            logger.info("\n=== KNOWLEDGE GRAPH VERIFICATION ===")
            
            # Count nodes by type
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as node_type, count(n) as count
                ORDER BY count DESC
            """)
            
            for record in result:
                logger.info(f"{record['node_type']}: {record['count']} nodes")
            
            # Count relationships by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)
            
            logger.info("\nRelationship types:")
            for record in result:
                logger.info(f"{record['rel_type']}: {record['count']} relationships")
            
            # Sample queries to verify functionality
            logger.info("\n=== SAMPLE VERIFICATION QUERIES ===")
            
            # Find all devices compatible with 4100ES
            result = session.run("""
                MATCH (p:Panel {sku: '4100ES'})-[:COMPATIBLE_WITH]->(d:Device)
                RETURN d.name as device_name, d.sku as device_sku
                ORDER BY d.name
            """)
            
            logger.info("\nDevices compatible with 4100ES Panel:")
            for record in result:
                logger.info(f"  - {record['device_name']} ({record['device_sku']})")
            
            # Find all modules that work with 4100ES
            result = session.run("""
                MATCH (p:Panel {sku: '4100ES'})-[:HAS_MODULE]->(m:Module)
                RETURN m.name as module_name, m.sku as module_sku
                ORDER BY m.name
            """)
            
            logger.info("\nModules compatible with 4100ES Panel:")
            for record in result:
                logger.info(f"  - {record['module_name']} ({record['module_sku']})")
            
            logger.info("\n🎉 Enhanced Simplex Product Knowledge Graph created successfully!")
            logger.info("Graph includes:")
            logger.info("  • Panel nodes (Control Panels)")
            logger.info("  • Module nodes (Interface/Control Modules)")  
            logger.info("  • Device nodes (Detection/Notification)")
            logger.info("  • Comprehensive relationships (COMPATIBLE_WITH, HAS_MODULE, REQUIRES, ALTERNATIVE_TO)")
            logger.info("  • Detailed technical specifications and compatibility data")
    
    finally:
        driver.close()

if __name__ == "__main__":
    create_enhanced_simplex_kg()