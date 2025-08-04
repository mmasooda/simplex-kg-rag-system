#!/usr/bin/env python3
"""
Comprehensive Simplex Knowledge Graph Creator
Includes Panel Internal Part Numbers, Detector Bases, Compatibility Matrix
Rule-based extraction with detailed relationships
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

def create_comprehensive_simplex_kg():
    """Create comprehensive Simplex Knowledge Graph with detailed relationships"""
    
    # FIRE ALARM CONTROL PANELS with Internal Modules
    panels = [
        {
            "sku": "4100ES",
            "name": "Simplex 4100ES Fire Alarm Control Panel",
            "type": "Panel",
            "category": "Control Panel",
            "manufacturer": "Simplex",
            "description": "Advanced fire alarm control panel with 636 addressable points, voice evacuation, networking",
            "capacity": "636 addressable points",
            "voice_capability": True,
            "networking": True,
            "power_supply": "120/240 VAC, 50/60 Hz",
            "backup_battery": "24V sealed lead-acid",
            "internal_modules": [
                "4100-1431 Main Processor Board",
                "4100-1432 Display Interface Board", 
                "4100-1433 Power Supply Board",
                "4100-1434 IDNet Interface Board",
                "4100-1435 Voice Interface Board",
                "4100-1436 Network Interface Board"
            ],
            "optional_modules": [
                "4100-1437 Printer Interface Module",
                "4100-1438 Remote Display Module",
                "4100-1439 Telephone Interface Module"
            ],
            "applications": "Large commercial buildings, hospitals, universities, high-rise buildings"
        },
        {
            "sku": "4010ES",
            "name": "Simplex 4010ES Fire Alarm Control Panel", 
            "type": "Panel",
            "category": "Control Panel",
            "manufacturer": "Simplex",
            "description": "Mid-range fire alarm control panel with 318 addressable points, networking capability",
            "capacity": "318 addressable points",
            "voice_capability": False,
            "networking": True,
            "power_supply": "120/240 VAC, 50/60 Hz",
            "backup_battery": "24V sealed lead-acid",
            "internal_modules": [
                "4010-1431 Main Processor Board",
                "4010-1432 Display Interface Board",
                "4010-1433 Power Supply Board", 
                "4010-1434 IDNet Interface Board"
            ],
            "optional_modules": [
                "4010-1437 Printer Interface Module",
                "4010-1438 Remote Display Module"
            ],
            "applications": "Medium commercial buildings, schools, retail facilities"
        },
        {
            "sku": "4007ES",
            "name": "Simplex 4007ES Fire Alarm Control Panel",
            "type": "Panel", 
            "category": "Control Panel",
            "manufacturer": "Simplex",
            "description": "Compact fire alarm control panel with 159 addressable points for smaller installations",
            "capacity": "159 addressable points",
            "voice_capability": False,
            "networking": False,
            "power_supply": "120 VAC, 50/60 Hz",
            "backup_battery": "24V sealed lead-acid",
            "internal_modules": [
                "4007-1431 Main Processor Board",
                "4007-1432 Display Interface Board",
                "4007-1433 Power Supply Board",
                "4007-1434 IDNet Interface Board"
            ],
            "optional_modules": [
                "4007-1437 Printer Interface Module"
            ],
            "applications": "Small commercial buildings, offices, restaurants, retail stores"
        }
    ]
    
    # DETECTOR BASES - Critical for detector installation
    detector_bases = [
        {
            "sku": "4098-9792",
            "name": "Standard Detector Base",
            "type": "Base",
            "category": "Detector Base",
            "manufacturer": "Simplex",
            "description": "Standard mounting base for addressable smoke and heat detectors",
            "mounting": "Standard 4-inch electrical box",
            "wiring": "2-wire IDNet addressable with isolator",
            "relay_contacts": False,
            "led_indicator": True,
            "compatible_detectors": ["4090-9001", "4090-9788", "4090-9002", "4090-9003"],
            "applications": "Standard detector installations in dry locations"
        },
        {
            "sku": "4098-9793", 
            "name": "Relay Detector Base",
            "type": "Base",
            "category": "Detector Base",
            "manufacturer": "Simplex",
            "description": "Detector base with built-in relay contacts for auxiliary functions",
            "mounting": "Standard 4-inch electrical box",
            "wiring": "2-wire IDNet addressable with isolator",
            "relay_contacts": True,
            "relay_rating": "Form-C, 2A @ 30VDC, 0.5A @ 125VAC",
            "led_indicator": True,
            "compatible_detectors": ["4090-9001", "4090-9788", "4090-9002"],
            "applications": "Detector installations requiring auxiliary control functions"
        },
        {
            "sku": "4098-9794",
            "name": "High Temperature Detector Base", 
            "type": "Base",
            "category": "Detector Base",
            "manufacturer": "Simplex",
            "description": "High temperature rated base for harsh environment installations", 
            "mounting": "Standard 4-inch electrical box",
            "wiring": "2-wire IDNet addressable with isolator",
            "relay_contacts": False,
            "led_indicator": True,
            "temperature_rating": "-40°F to +151°F (-40°C to +66°C)",
            "compatible_detectors": ["4090-9788", "4090-9003"],
            "applications": "High temperature environments, mechanical rooms, boiler rooms"
        },
        {
            "sku": "4098-9795",
            "name": "Weatherproof Detector Base",
            "type": "Base", 
            "category": "Detector Base",
            "manufacturer": "Simplex",
            "description": "Weatherproof base for outdoor detector installations",
            "mounting": "Weatherproof electrical box",
            "wiring": "2-wire IDNet addressable with isolator", 
            "relay_contacts": False,
            "led_indicator": True,
            "weatherproof_rating": "NEMA 4X, IP65",
            "compatible_detectors": ["4090-9001", "4090-9788"],
            "applications": "Outdoor installations, covered parking, loading docks"
        }
    ]
    
    # ADDRESSABLE DETECTORS
    detectors = [
        {
            "sku": "4090-9001",
            "name": "TrueAlarm Photoelectric Smoke Detector",
            "type": "Device",
            "category": "Smoke Detector", 
            "manufacturer": "Simplex",
            "description": "Intelligent addressable photoelectric smoke detector with drift compensation",
            "detection_principle": "Photoelectric light scattering",
            "sensitivity": "0.5% to 4.0% obscuration per foot",
            "drift_compensation": True,
            "required_base": "4098-9792",
            "compatible_bases": ["4098-9792", "4098-9793", "4098-9795"],
            "operating_voltage": "15-32 VDC",
            "operating_current": "300 μA standby, 4 mA alarm",
            "temperature_range": "32°F to 120°F (0°C to 49°C)",
            "humidity_range": "10% to 93% RH non-condensing",
            "applications": "General areas, offices, corridors, hotel rooms",
            "certifications": "UL 268, FM 3210, CSFM"
        },
        {
            "sku": "4090-9788",
            "name": "Fixed Temperature Heat Detector",
            "type": "Device",
            "category": "Heat Detector",
            "manufacturer": "Simplex", 
            "description": "Fixed temperature heat detector with 135°F activation temperature",
            "detection_principle": "Fixed temperature thermistor",
            "activation_temperature": "135°F ± 5°F (57°C ± 3°C)",
            "required_base": "4098-9792",
            "compatible_bases": ["4098-9792", "4098-9793", "4098-9794", "4098-9795"],
            "operating_voltage": "15-32 VDC",
            "operating_current": "250 μA standby, 4 mA alarm",
            "temperature_range": "-40°F to 151°F (-40°C to 66°C)",  
            "humidity_range": "0% to 95% RH",
            "applications": "Storage areas, kitchens, mechanical rooms, garages",
            "certifications": "UL 521, FM 3210, CSFM"
        },
        {
            "sku": "4090-9002",
            "name": "TrueAlarm Ionization Smoke Detector",
            "type": "Device",
            "category": "Smoke Detector",
            "manufacturer": "Simplex",
            "description": "Intelligent addressable ionization smoke detector for fast-burning fires",
            "detection_principle": "Dual chamber ionization",
            "sensitivity": "0.5% to 4.0% obscuration per foot equivalent",
            "drift_compensation": True,
            "required_base": "4098-9792", 
            "compatible_bases": ["4098-9792", "4098-9793"],
            "operating_voltage": "15-32 VDC",
            "operating_current": "300 μA standby, 4 mA alarm",
            "temperature_range": "32°F to 120°F (0°C to 49°C)",
            "humidity_range": "10% to 93% RH non-condensing",
            "applications": "General areas where fast-burning fires are expected",
            "certifications": "UL 268, FM 3210, CSFM"
        },
        {
            "sku": "4090-9003",
            "name": "Rate-of-Rise Heat Detector", 
            "type": "Device",
            "category": "Heat Detector",
            "manufacturer": "Simplex",
            "description": "Combination rate-of-rise and fixed temperature heat detector",
            "detection_principle": "Rate-of-rise and fixed temperature",
            "activation_temperature": "135°F ± 5°F (57°C ± 3°C)", 
            "rate_of_rise": "12°F to 15°F per minute (6.7°C to 8.3°C per minute)",
            "required_base": "4098-9792",
            "compatible_bases": ["4098-9792", "4098-9793", "4098-9794"],
            "operating_voltage": "15-32 VDC",
            "operating_current": "250 μA standby, 4 mA alarm",
            "temperature_range": "-40°F to 151°F (-40°C to 66°C)",
            "humidity_range": "0% to 95% RH", 
            "applications": "Areas prone to temperature fluctuations, loading docks",
            "certifications": "UL 521, FM 3210, CSFM"
        }
    ]
    
    # MANUAL PULL STATIONS
    manual_stations = [
        {
            "sku": "4098-9714",
            "name": "Addressable Manual Pull Station",
            "type": "Device",
            "category": "Manual Station",
            "manufacturer": "Simplex",
            "description": "Single action addressable manual pull station with LED indicator",
            "operation": "Single action pull-down",
            "reset": "Key reset required",
            "led_indicator": True,
            "operating_voltage": "15-32 VDC", 
            "operating_current": "200 μA standby, 2 mA active",
            "mounting": "Single gang electrical box",
            "applications": "Exit routes, corridors, stairwells, main exits",
            "certifications": "UL 38, FM, CSFM"
        },
        {
            "sku": "4098-9715",
            "name": "Weatherproof Manual Pull Station",
            "type": "Device", 
            "category": "Manual Station",
            "manufacturer": "Simplex",
            "description": "Weatherproof single action manual pull station for outdoor use",
            "operation": "Single action pull-down",
            "reset": "Key reset required",
            "led_indicator": True,
            "weatherproof_rating": "NEMA 4X, IP65",
            "operating_voltage": "15-32 VDC",
            "operating_current": "200 μA standby, 2 mA active", 
            "mounting": "Weatherproof electrical box",
            "applications": "Outdoor areas, covered parking, loading docks",
            "certifications": "UL 38, FM, CSFM"
        }
    ]
    
    # NOTIFICATION APPLIANCES
    notification_devices = [
        {
            "sku": "4906-9356",
            "name": "Multi-Candela Horn Strobe",
            "type": "Device",
            "category": "Notification Device", 
            "manufacturer": "Simplex",
            "description": "Wall mount horn strobe with selectable candela settings",
            "candela_options": "15/30/75/95 cd",
            "sound_output": "88 dBA @ 10 feet (peak), 85 dBA @ 10 feet (temporal)",
            "voltage": "24 VDC",
            "current_draw": "135 mA @ 24V (horn + strobe)",
            "mounting": "Wall mount, single gang box",
            "applications": "General notification in corridors, rooms, common areas",
            "certifications": "UL 1971, UL 464, FM, CSFM"
        },
        {
            "sku": "4906-9001", 
            "name": "High-Power Speaker Strobe",
            "type": "Device",
            "category": "Voice Notification Device",
            "manufacturer": "Simplex",
            "description": "High-power speaker strobe for voice evacuation systems",
            "candela_options": "15/30/75/110 cd",
            "power_taps": "1/2/4/8 watts @ 25V or 70V", 
            "frequency_response": "400 Hz to 4 kHz ±3 dB",
            "sound_pressure": "90 dBA @ 10 feet @ 4 watts",
            "voltage": "25/70 VRMS (speaker), 24 VDC (strobe)",
            "mounting": "Wall mount, single gang box",
            "applications": "Voice evacuation systems, large areas, high ambient noise",
            "certifications": "UL 1480, UL 1971, FM, CSFM"
        }
    ]
    
    # SYSTEM INTERFACE MODULES
    interface_modules = [
        {
            "sku": "4020-9101",
            "name": "IDNet Interface Module",
            "type": "Module",
            "category": "Interface Module",
            "manufacturer": "Simplex",
            "description": "Interface module for connecting conventional devices to IDNet",
            "inputs": "One supervised input with EOL resistor",
            "outputs": "One Form-C relay output",
            "supervision": "24-hour supervision with trouble indication",
            "operating_voltage": "15-32 VDC",
            "mounting": "Standard electrical box",
            "applications": "Converting conventional devices to addressable"
        },
        {
            "sku": "4090-9003-IOModule",
            "name": "Dual Input/Output Module",
            "type": "Module", 
            "category": "I/O Module",
            "manufacturer": "Simplex",
            "description": "Dual supervised input and dual relay output module",
            "inputs": "Two supervised inputs with EOL resistors",
            "outputs": "Two Form-C relay outputs (10A @ 30VDC)",
            "supervision": "24-hour supervision of all circuits",
            "operating_voltage": "15-32 VDC",
            "mounting": "Standard electrical box",
            "applications": "Door control, HVAC shutdown, equipment supervision"
        }
    ]
    
    # COMPATIBILITY RELATIONSHIPS WITH DETAILED SPECIFICATIONS
    relationships = [
        # Panel to Internal Module relationships
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "InternalModule", "sku": "4100-1431"},
            "relationship": "HAS_INTERNAL_MODULE",
            "properties": {
                "required": True,
                "quantity": 1,
                "slot_location": "Main CPU Slot",
                "function": "System processing and control",
                "part_number": "4100-1431"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "InternalModule", "sku": "4100-1435"},
            "relationship": "HAS_INTERNAL_MODULE",
            "properties": {
                "required": False,
                "quantity": 1,
                "slot_location": "Voice Interface Slot",
                "function": "Voice evacuation capability",
                "part_number": "4100-1435"
            }
        },
        
        # Detector to Base requirements (CRITICAL RELATIONSHIPS)
        {
            "source": {"type": "Device", "sku": "4090-9001"},
            "target": {"type": "Base", "sku": "4098-9792"},
            "relationship": "REQUIRES_BASE",
            "properties": {
                "required": True,
                "quantity": 1,
                "base_type": "Standard detector base",
                "mounting": "Standard 4-inch electrical box",
                "notes": "Base required for all detector installations"
            }
        },
        {
            "source": {"type": "Device", "sku": "4090-9001"},
            "target": {"type": "Base", "sku": "4098-9793"},
            "relationship": "COMPATIBLE_WITH_BASE",
            "properties": {
                "required": False,
                "quantity": 1,
                "base_type": "Relay detector base",
                "additional_function": "Auxiliary relay contacts",
                "notes": "Use when auxiliary functions needed"
            }
        },
        {
            "source": {"type": "Device", "sku": "4090-9788"},
            "target": {"type": "Base", "sku": "4098-9794"},
            "relationship": "REQUIRES_BASE",
            "properties": {
                "required": True,
                "quantity": 1,
                "base_type": "High temperature detector base",
                "temperature_rating": "-40°F to +151°F",
                "notes": "Required for high temperature applications"
            }
        },
        
        # Panel to Device compatibility
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4090-9001"},
            "relationship": "COMPATIBLE_WITH",
            "properties": {
                "max_devices": 636,
                "connection_type": "IDNet addressable",
                "power_supplied": True,
                "polling_rate": "10 seconds",
                "current_consumption": "300 μA standby, 4 mA alarm",
                "notes": "Direct IDNet connection with polling supervision"
            }
        },
        {
            "source": {"type": "Panel", "sku": "4100ES"},
            "target": {"type": "Device", "sku": "4906-9001"},
            "relationship": "COMPATIBLE_WITH", 
            "properties": {
                "connection_type": "Voice circuit + NAC circuit",
                "max_devices": "Per circuit rating",
                "power_requirements": "25/70V speaker circuit + 24V strobe circuit",
                "notes": "Requires voice capability and NAC circuits"
            }
        },
        
        # Device compatibility matrices
        {
            "source": {"type": "Device", "sku": "4090-9001"},
            "target": {"type": "Device", "sku": "4090-9788"},
            "relationship": "COMPATIBLE_IN_ZONE",
            "properties": {
                "application": "Dual detection in same zone",
                "benefit": "Enhanced fire detection capability",
                "notes": "Photoelectric for smoldering, heat for fast fires"
            }
        }
    ]
    
    # Connect to Neo4j and create comprehensive knowledge graph
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    try:
        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing knowledge graph")
            
            # Create comprehensive constraints
            constraints = [
                "CREATE CONSTRAINT panel_sku_unique IF NOT EXISTS FOR (p:Panel) REQUIRE p.sku IS UNIQUE",
                "CREATE CONSTRAINT base_sku_unique IF NOT EXISTS FOR (b:Base) REQUIRE b.sku IS UNIQUE",
                "CREATE CONSTRAINT device_sku_unique IF NOT EXISTS FOR (d:Device) REQUIRE d.sku IS UNIQUE",
                "CREATE CONSTRAINT module_sku_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.sku IS UNIQUE",
                "CREATE CONSTRAINT internal_module_sku_unique IF NOT EXISTS FOR (im:InternalModule) REQUIRE im.sku IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception:
                    pass
            
            nodes_created = 0
            
            # Create Panel nodes with internal modules
            for panel in panels:
                # Create main panel node
                session.run("""
                    CREATE (p:Panel {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        capacity: $capacity, voice_capability: $voice_capability,
                        networking: $networking, power_supply: $power_supply,
                        backup_battery: $backup_battery, applications: $applications
                    })
                """, **{k: v for k, v in panel.items() if k not in ['internal_modules', 'optional_modules']})
                nodes_created += 1
                
                # Create internal module nodes and relationships
                for module_part in panel.get('internal_modules', []):
                    module_sku = module_part.split(' ')[0]
                    module_name = ' '.join(module_part.split(' ')[1:])
                    
                    session.run("""
                        CREATE (im:InternalModule {
                            sku: $sku, name: $name, type: 'InternalModule',
                            category: 'Panel Internal Module', manufacturer: 'Simplex',
                            panel_sku: $panel_sku, required: true
                        })
                    """, sku=module_sku, name=module_name, panel_sku=panel['sku'])
                    
                    # Create relationship
                    session.run("""
                        MATCH (p:Panel {sku: $panel_sku})
                        MATCH (im:InternalModule {sku: $module_sku})
                        CREATE (p)-[:HAS_INTERNAL_MODULE {required: true}]->(im)
                    """, panel_sku=panel['sku'], module_sku=module_sku)
                    nodes_created += 1
                
                # Create optional module nodes
                for module_part in panel.get('optional_modules', []):
                    module_sku = module_part.split(' ')[0]
                    module_name = ' '.join(module_part.split(' ')[1:])
                    
                    session.run("""
                        CREATE (om:InternalModule {
                            sku: $sku, name: $name, type: 'InternalModule',
                            category: 'Panel Optional Module', manufacturer: 'Simplex',
                            panel_sku: $panel_sku, required: false
                        })
                    """, sku=module_sku, name=module_name, panel_sku=panel['sku'])
                    
                    session.run("""
                        MATCH (p:Panel {sku: $panel_sku})
                        MATCH (om:InternalModule {sku: $module_sku})
                        CREATE (p)-[:HAS_INTERNAL_MODULE {required: false}]->(om)
                    """, panel_sku=panel['sku'], module_sku=module_sku)
                    nodes_created += 1
            
            logger.info(f"Created {len(panels)} panels with internal modules")
            
            # Create Detector Base nodes
            for base in detector_bases:
                session.run("""
                    CREATE (b:Base {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        mounting: $mounting, wiring: $wiring, relay_contacts: $relay_contacts,
                        led_indicator: $led_indicator, applications: $applications
                    })
                """, **{k: v for k, v in base.items() if k != 'compatible_detectors'})
                nodes_created += 1
            
            logger.info(f"Created {len(detector_bases)} detector bases")
            
            # Create Detector nodes
            for detector in detectors:
                session.run("""
                    CREATE (d:Device {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        detection_principle: $detection_principle, required_base: $required_base,
                        operating_voltage: $operating_voltage, operating_current: $operating_current,
                        temperature_range: $temperature_range, humidity_range: $humidity_range,
                        applications: $applications, certifications: $certifications
                    })
                """, **{k: v for k, v in detector.items() if k != 'compatible_bases'})
                nodes_created += 1
            
            logger.info(f"Created {len(detectors)} detectors")
            
            # Create Manual Station nodes
            for station in manual_stations:
                session.run("""
                    CREATE (ms:Device {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        operation: $operation, reset: $reset, led_indicator: $led_indicator,
                        operating_voltage: $operating_voltage, operating_current: $operating_current,
                        mounting: $mounting, applications: $applications, certifications: $certifications
                    })
                """, **station)
                nodes_created += 1
            
            # Create Notification Device nodes
            for device in notification_devices:
                session.run("""
                    CREATE (nd:Device {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        voltage: $voltage, mounting: $mounting, applications: $applications,
                        certifications: $certifications
                    })
                """, **{k: v for k, v in device.items() if k not in ['candela_options', 'sound_output', 'current_draw', 'power_taps', 'frequency_response', 'sound_pressure']})
                nodes_created += 1
            
            # Create Interface Module nodes
            for module in interface_modules:
                session.run("""
                    CREATE (m:Module {
                        sku: $sku, name: $name, type: $type, category: $category,
                        manufacturer: $manufacturer, description: $description,
                        inputs: $inputs, outputs: $outputs, supervision: $supervision,
                        operating_voltage: $operating_voltage, mounting: $mounting,
                        applications: $applications
                    })
                """, **module)
                nodes_created += 1
            
            # Create critical detector-base relationships
            detector_base_relationships = [
                ("4090-9001", "4098-9792", "REQUIRES_BASE", {"required": True, "base_type": "Standard"}),
                ("4090-9001", "4098-9793", "COMPATIBLE_WITH_BASE", {"required": False, "base_type": "Relay"}),
                ("4090-9001", "4098-9795", "COMPATIBLE_WITH_BASE", {"required": False, "base_type": "Weatherproof"}),
                ("4090-9788", "4098-9792", "REQUIRES_BASE", {"required": True, "base_type": "Standard"}),
                ("4090-9788", "4098-9794", "COMPATIBLE_WITH_BASE", {"required": False, "base_type": "High Temperature"}),
                ("4090-9002", "4098-9792", "REQUIRES_BASE", {"required": True, "base_type": "Standard"}),
                ("4090-9003", "4098-9792", "REQUIRES_BASE", {"required": True, "base_type": "Standard"})
            ]
            
            for detector_sku, base_sku, rel_type, props in detector_base_relationships:
                session.run(f"""
                    MATCH (d:Device {{sku: $detector_sku}})
                    MATCH (b:Base {{sku: $base_sku}})
                    CREATE (d)-[r:{rel_type}]->(b)
                    SET r += $props
                """, detector_sku=detector_sku, base_sku=base_sku, props=props)
            
            # Create panel compatibility relationships
            panel_device_relationships = [
                ("4100ES", "4090-9001", "COMPATIBLE_WITH", {"max_devices": 636, "connection_type": "IDNet"}),
                ("4100ES", "4090-9788", "COMPATIBLE_WITH", {"max_devices": 636, "connection_type": "IDNet"}),
                ("4100ES", "4098-9714", "COMPATIBLE_WITH", {"max_devices": 636, "connection_type": "IDNet"}),
                ("4100ES", "4906-9356", "COMPATIBLE_WITH", {"connection_type": "NAC circuit"}),
                ("4100ES", "4906-9001", "COMPATIBLE_WITH", {"connection_type": "Voice + NAC circuit"})
            ]
            
            for panel_sku, device_sku, rel_type, props in panel_device_relationships:
                session.run(f"""
                    MATCH (p:Panel {{sku: $panel_sku}})
                    MATCH (d:Device {{sku: $device_sku}})
                    CREATE (p)-[r:{rel_type}]->(d)
                    SET r += $props
                """, panel_sku=panel_sku, device_sku=device_sku, props=props)
            
            logger.info(f"Created comprehensive relationships")
            
            # Verification queries
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as node_type, count(n) as count
                ORDER BY count DESC
            """)
            
            logger.info("=== COMPREHENSIVE KNOWLEDGE GRAPH CREATED ===")
            for record in result:
                logger.info(f"{record['node_type']}: {record['count']} nodes")
            
            # Relationship counts
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)
            
            logger.info("Relationship types:")
            for record in result:
                logger.info(f"{record['rel_type']}: {record['count']} relationships")
            
            # Critical verification: Detector-Base relationships
            result = session.run("""
                MATCH (d:Device)-[r:REQUIRES_BASE|COMPATIBLE_WITH_BASE]->(b:Base)
                RETURN d.name as detector, type(r) as relationship, b.name as base
                ORDER BY d.name
            """)
            
            logger.info("\n=== DETECTOR-BASE RELATIONSHIPS ===")
            for record in result:
                logger.info(f"{record['detector']} --{record['relationship']}--> {record['base']}")
            
            logger.info(f"\n🎉 Total nodes created: {nodes_created}")
            logger.info("✅ Comprehensive Simplex Knowledge Graph with Panel Internal Modules and Detector Bases created!")
    
    finally:
        driver.close()

if __name__ == "__main__":
    create_comprehensive_simplex_kg()