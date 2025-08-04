"""
Enhanced KG-Linker with YAML-based prompts and iterative refinement
Implements rule-based extraction and LLM-assisted processing
"""

import logging
import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class EntityExtractionResult:
    """Result from entity extraction process"""
    panels: List[Dict[str, Any]]
    devices: List[Dict[str, Any]]
    bases: List[Dict[str, Any]]
    circuits: List[Dict[str, Any]]
    specifications: List[Dict[str, Any]]
    confidence: float

@dataclass
class KGLinkerResult:
    """Enhanced result from KG-Linker processing"""
    entities: EntityExtractionResult
    paths: List[Dict[str, Any]]
    cypher_queries: List[Dict[str, Any]]
    rule_based_extractions: Dict[str, Any]
    llm_extractions: Dict[str, Any]
    iteration_data: Dict[str, Any]

class EnhancedKGLinker:
    """
    Enhanced KG-Linker with YAML prompts and iterative processing
    Combines rule-based extraction with LLM-assisted analysis
    """
    
    def __init__(self, openai_client: OpenAI, graph_schema: Dict[str, Any]):
        self.openai_client = openai_client
        self.graph_schema = graph_schema
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load YAML prompt templates
        self.prompts = self._load_prompt_templates()
        
        # Rule-based extraction patterns
        self.extraction_rules = self._initialize_extraction_rules()
    
    def _load_prompt_templates(self) -> Dict[str, Any]:
        """Load YAML prompt templates"""
        prompts = {}
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        try:
            # Load entity extraction prompts
            with open(prompts_dir / "entity_extraction.yaml", 'r') as f:
                prompts['entity_extraction'] = yaml.safe_load(f)
            
            # Load answer generation prompts  
            with open(prompts_dir / "answer_generation.yaml", 'r') as f:
                prompts['answer_generation'] = yaml.safe_load(f)
                
            self.logger.info("Successfully loaded YAML prompt templates")
            return prompts
            
        except Exception as e:
            self.logger.error(f"Error loading prompt templates: {e}")
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """Fallback default prompts if YAML loading fails"""
        return {
            'entity_extraction': {
                'entity_extraction': {
                    'system_prompt': 'You are a fire alarm systems expert.',
                    'extraction_prompt': 'Extract fire alarm entities from: {query}'
                }
            }
        }
    
    def _initialize_extraction_rules(self) -> Dict[str, Any]:
        """Initialize rule-based extraction patterns"""
        return {
            'panel_capacity_rules': {
                # Rule: Calculate required panel capacity based on device counts
                'pattern': r'(\d+)\s*(smoke|heat|manual|detector|device|point)',
                'capacity_mapping': {
                    'up_to_159': '4007ES',
                    'up_to_318': '4010ES', 
                    'up_to_636': '4100ES'
                }
            },
            'detector_base_rules': {
                # Rule: Every detector needs a base
                'smoke_detector_bases': {
                    'standard_base': '4098-9792',
                    'relay_base': '4098-9793',
                    'weatherproof_base': '4098-9795'
                },
                'heat_detector_bases': {
                    'standard_base': '4098-9792',
                    'high_temp_base': '4098-9794',
                    'weatherproof_base': '4098-9795'
                }
            },
            'internal_module_rules': {
                # Rule: Panels require internal modules
                '4100ES': {
                    'required': ['4100-1431', '4100-1432', '4100-1433', '4100-1434'],
                    'voice_required': '4100-1435',
                    'network_required': '4100-1436'
                },
                '4010ES': {
                    'required': ['4010-1431', '4010-1432', '4010-1433', '4010-1434']
                },
                '4007ES': {
                    'required': ['4007-1431', '4007-1432', '4007-1433', '4007-1434']
                }
            },
            'circuit_calculation_rules': {
                # Rule: Calculate NAC and speaker circuits
                'nac_circuit_capacity': 3.0,  # Amps per circuit
                'speaker_circuit_capacity': 2.0,  # Amps per circuit
                'device_current_draw': {
                    'horn_strobe': 0.135,  # Amps
                    'speaker_1w': 0.042,   # Amps at 1 watt
                    'speaker_2w': 0.083    # Amps at 2 watts
                }
            }
        }
    
    def process_query(self, user_query: str, context: str = "", iteration: int = 1) -> KGLinkerResult:
        """
        Process user query with enhanced KG-Linker
        
        Args:
            user_query: User's fire alarm system query
            context: Previous iteration context
            iteration: Current iteration number
            
        Returns:
            KGLinkerResult with extracted entities and relationships
        """
        self.logger.info(f"Enhanced KG-Linker processing iteration {iteration}")
        
        # Step 1: Rule-based extraction
        rule_based_results = self._apply_rule_based_extraction(user_query)
        
        # Step 2: LLM-assisted entity extraction
        llm_entities = self._extract_entities_with_llm(user_query, context, iteration)
        
        # Step 3: Combine rule-based and LLM results
        combined_entities = self._combine_extractions(rule_based_results, llm_entities)
        
        # Step 4: Generate relationship paths
        relationship_paths = self._identify_relationship_paths(combined_entities, user_query)
        
        # Step 5: Generate Cypher queries
        cypher_queries = self._generate_cypher_queries(combined_entities, relationship_paths)
        
        # Step 6: Create iteration metadata
        iteration_data = {
            'iteration_number': iteration,
            'rule_based_entities': len(rule_based_results.get('entities', [])),
            'llm_entities': len(llm_entities.devices + llm_entities.panels + llm_entities.bases),
            'total_paths': len(relationship_paths),
            'cypher_queries': len(cypher_queries)
        }
        
        return KGLinkerResult(
            entities=combined_entities,
            paths=relationship_paths,
            cypher_queries=cypher_queries,
            rule_based_extractions=rule_based_results,
            llm_extractions=llm_entities.__dict__,
            iteration_data=iteration_data
        )
    
    def _apply_rule_based_extraction(self, user_query: str) -> Dict[str, Any]:
        """Apply rule-based extraction patterns"""
        self.logger.info("Applying rule-based extraction")
        
        results = {
            'entities': [],
            'panel_recommendations': [],
            'detector_base_requirements': [],
            'internal_modules': [],
            'circuit_calculations': []
        }
        
        # Extract device quantities using patterns
        device_pattern = r'(\d+)\s*(smoke\s*detector|heat\s*detector|manual\s*station|speaker|strobe)'
        device_matches = re.findall(device_pattern, user_query.lower())
        
        total_addressable_points = 0
        
        for quantity, device_type in device_matches:
            quantity = int(quantity)
            total_addressable_points += quantity
            
            # Create entity
            entity = {
                'type': device_type.replace(' ', '_'),
                'quantity': quantity,
                'extraction_method': 'rule_based'
            }
            results['entities'].append(entity)
            
            # Apply detector-base rules
            if 'smoke' in device_type or 'heat' in device_type:
                base_requirement = {
                    'detector_type': device_type,
                    'detector_quantity': quantity,
                    'required_base': '4098-9792',  # Standard base
                    'base_quantity': quantity,
                    'rule': 'Every detector requires a mounting base'
                }
                results['detector_base_requirements'].append(base_requirement)
        
        # Apply panel capacity rules
        if total_addressable_points > 0:
            if total_addressable_points <= 159:
                recommended_panel = '4007ES'
            elif total_addressable_points <= 318:
                recommended_panel = '4010ES'
            else:
                recommended_panel = '4100ES'
            
            panel_rec = {
                'recommended_panel': recommended_panel,
                'total_points_needed': total_addressable_points,
                'capacity_utilization': f"{total_addressable_points}/{self._get_panel_capacity(recommended_panel)}",
                'rule': 'Panel capacity must exceed total addressable points'
            }
            results['panel_recommendations'].append(panel_rec)
            
            # Apply internal module rules
            if recommended_panel in self.extraction_rules['internal_module_rules']:
                module_rules = self.extraction_rules['internal_module_rules'][recommended_panel]
                for module_sku in module_rules.get('required', []):
                    results['internal_modules'].append({
                        'module_sku': module_sku,
                        'panel_sku': recommended_panel,
                        'required': True,
                        'rule': 'Panel requires internal modules for operation'
                    })
        
        # Apply circuit calculation rules
        speaker_pattern = r'(\d+)\s*speaker'
        speaker_matches = re.findall(speaker_pattern, user_query.lower())
        
        for quantity_str in speaker_matches:
            quantity = int(quantity_str)
            # Calculate speaker circuits needed
            circuits_needed = self._calculate_speaker_circuits(quantity, 1)  # Assume 1 watt
            results['circuit_calculations'].append({
                'circuit_type': 'speaker',
                'devices': quantity,
                'circuits_needed': circuits_needed,
                'rule': 'Speaker circuit capacity limitations'
            })
        
        self.logger.info(f"Rule-based extraction found {len(results['entities'])} entities")
        return results
    
    def _extract_entities_with_llm(self, user_query: str, context: str, iteration: int) -> EntityExtractionResult:
        """Extract entities using LLM with YAML prompts"""
        self.logger.info(f"LLM entity extraction - iteration {iteration}")
        
        try:
            # Get prompts from YAML
            entity_prompts = self.prompts['entity_extraction']['entity_extraction']
            system_prompt = entity_prompts['system_prompt']
            extraction_prompt = entity_prompts['extraction_prompt'].format(
                query=user_query,
                context=context,
                iteration=iteration
            )
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            entities_data = self._parse_json_response(response_text)
            
            return EntityExtractionResult(
                panels=entities_data.get('panels', []),
                devices=entities_data.get('devices', []),
                bases=entities_data.get('bases', []),
                circuits=entities_data.get('circuits', []),
                specifications=entities_data.get('specifications', []),
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"LLM entity extraction failed: {e}")
            return EntityExtractionResult([], [], [], [], [], 0.0)
    
    def _combine_extractions(self, rule_based: Dict, llm_results: EntityExtractionResult) -> EntityExtractionResult:
        """Combine rule-based and LLM extractions intelligently"""
        self.logger.info("Combining rule-based and LLM extractions")
        
        # Start with LLM results as base
        combined = EntityExtractionResult(
            panels=llm_results.panels.copy(),
            devices=llm_results.devices.copy(), 
            bases=llm_results.bases.copy(),
            circuits=llm_results.circuits.copy(),
            specifications=llm_results.specifications.copy(),
            confidence=0.9  # Higher confidence for combined results
        )
        
        # Enhance with rule-based findings
        for panel_rec in rule_based.get('panel_recommendations', []):
            # Check if LLM missed the panel recommendation
            panel_found = any(p.get('suggested_sku') == panel_rec['recommended_panel'] 
                            for p in combined.panels)
            
            if not panel_found:
                combined.panels.append({
                    'entity': 'panel_requirement',
                    'capacity_needed': panel_rec['total_points_needed'],
                    'suggested_sku': panel_rec['recommended_panel'],
                    'source': 'rule_based_enhancement'
                })
        
        # Ensure detector-base relationships from rules
        for base_req in rule_based.get('detector_base_requirements', []):
            # Add base requirements that LLM might have missed
            bases_for_detector = [b for b in combined.bases 
                                if b.get('required_for') == base_req['detector_type']]
            
            if not bases_for_detector:
                combined.bases.append({
                    'entity': 'detector_base',
                    'quantity': base_req['base_quantity'],
                    'base_type': 'standard',
                    'required_for': base_req['detector_type'],
                    'source': 'rule_based_enhancement'
                })
        
        self.logger.info(f"Combined extraction: {len(combined.panels)} panels, "
                        f"{len(combined.devices)} devices, {len(combined.bases)} bases")
        
        return combined
    
    def _identify_relationship_paths(self, entities: EntityExtractionResult, user_query: str) -> List[Dict[str, Any]]:
        """Identify critical relationship paths between entities"""
        paths = []
        
        # Critical path: Panel capacity analysis
        for panel in entities.panels:
            total_devices = sum(d.get('quantity', 0) for d in entities.devices)
            paths.append({
                'path_type': 'panel_capacity_analysis',
                'source': f"total_devices_{total_devices}",
                'target': panel.get('suggested_sku', 'unknown'),
                'relationship': 'REQUIRES_CAPACITY',
                'analysis': f"Panel must support {total_devices} addressable points"
            })
        
        # Critical path: Detector-base dependencies
        for device in entities.devices:
            if device.get('category') in ['smoke_detector', 'heat_detector']:
                paths.append({
                    'path_type': 'detector_base_dependency',
                    'source': device.get('entity', 'detector'),
                    'target': 'detector_base',
                    'relationship': 'REQUIRES_BASE',
                    'mandatory': True,
                    'quantity_relationship': '1:1'
                })
        
        # Circuit design paths
        for circuit in entities.circuits:
            paths.append({
                'path_type': 'circuit_design',
                'source': circuit.get('type', 'circuit'),
                'target': 'notification_devices',
                'relationship': 'POWERS',
                'specifications': circuit.get('specifications', '')
            })
        
        return paths
    
    def _generate_cypher_queries(self, entities: EntityExtractionResult, paths: List[Dict]) -> List[Dict[str, Any]]:
        """Generate Cypher queries based on entities and paths"""
        queries = []
        
        # Query 1: Find compatible panel for capacity
        for panel in entities.panels:
            capacity_needed = panel.get('capacity_needed', 0)
            # Convert to integer if it's a string
            if isinstance(capacity_needed, str):
                try:
                    capacity_needed = int(capacity_needed)
                except (ValueError, TypeError):
                    capacity_needed = 0
            if capacity_needed > 0:
                queries.append({
                    'purpose': 'find_compatible_panel',
                    'cypher': '''
                        MATCH (p:Panel)
                        WHERE toInteger(split(p.capacity, ' ')[0]) >= $capacity_needed
                        RETURN p.sku, p.name, p.capacity, p.voice_capability
                        ORDER BY toInteger(split(p.capacity, ' ')[0])
                    ''',
                    'parameters': {'capacity_needed': capacity_needed}
                })
        
        # Query 2: Find detector-base relationships
        if entities.devices:
            queries.append({
                'purpose': 'detector_base_requirements',
                'cypher': '''
                    MATCH (d:Device)-[r:REQUIRES_BASE|COMPATIBLE_WITH_BASE]->(b:Base)
                    WHERE d.category IN ['Smoke Detector', 'Heat Detector']
                    RETURN d.sku, d.name, type(r) as relationship, b.sku, b.name
                    ORDER BY d.sku
                ''',
                'parameters': {}
            })
        
        # Query 3: Find internal modules for selected panel
        for panel in entities.panels:
            panel_sku = panel.get('suggested_sku')
            if panel_sku:
                queries.append({
                    'purpose': 'panel_internal_modules',
                    'cypher': '''
                        MATCH (p:Panel {sku: $panel_sku})-[:HAS_INTERNAL_MODULE]->(im:InternalModule)
                        RETURN p.sku, im.sku, im.name, im.required
                        ORDER BY im.required DESC, im.sku
                    ''',
                    'parameters': {'panel_sku': panel_sku}
                })
        
        # Query 4: Complete system compatibility
        queries.append({
            'purpose': 'complete_system_compatibility',
            'cypher': '''
                MATCH (p:Panel)-[:COMPATIBLE_WITH]->(d:Device),
                      (d)-[:REQUIRES_BASE]->(b:Base)
                OPTIONAL MATCH (p)-[:HAS_INTERNAL_MODULE]->(im:InternalModule)
                WHERE im.required = true OR im IS NULL
                WITH p, d, b, collect(im.sku) as internal_modules
                RETURN p.sku as panel, d.sku as device, b.sku as base, internal_modules
                ORDER BY p.sku, d.sku
            ''',
            'parameters': {}
        })
        
        return queries
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON block
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_text)
            
            # Try to find JSON structure
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {}
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}
    
    def _get_panel_capacity(self, panel_sku: str) -> int:
        """Get panel capacity by SKU"""
        capacities = {
            '4007ES': 159,
            '4010ES': 318,
            '4100ES': 636
        }
        return capacities.get(panel_sku, 636)
    
    def _calculate_speaker_circuits(self, speaker_count: int, wattage: int) -> int:
        """Calculate number of speaker circuits needed"""
        current_per_speaker = self.extraction_rules['circuit_calculation_rules']['device_current_draw'].get(f'speaker_{wattage}w', 0.042)
        total_current = speaker_count * current_per_speaker
        circuit_capacity = self.extraction_rules['circuit_calculation_rules']['speaker_circuit_capacity']
        return int(total_current / circuit_capacity) + (1 if total_current % circuit_capacity > 0 else 0)