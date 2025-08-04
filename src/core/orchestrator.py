"""
Orchestrator: Implements the iterative refinement loop (Algorithm 2)
Coordinates KG-Linker and Graph Retriever for multi-iteration KGQA
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
from openai import OpenAI
from neo4j import GraphDatabase

from .kg_linker import KGLinker, GraphSchemaLoader
from .enhanced_kg_linker import EnhancedKGLinker
from .graph_retriever import GraphRetriever, RetrievalResult

logger = logging.getLogger(__name__)

@dataclass
class BYOKGRAGResult:
    """Final result from the BYOKG-RAG pipeline"""
    answer: str
    bill_of_quantities: List[Dict[str, Any]]
    context_used: List[Dict[str, Any]]
    iterations_performed: int
    metadata: Dict[str, Any]

class BYOKGRAGPipeline:
    """
    Main orchestrator implementing the BYOKG-RAG algorithm
    """
    
    def __init__(
        self,
        openai_client: OpenAI,
        neo4j_driver,
        max_iterations: int = 2,
        graph_schema: Optional[Dict[str, Any]] = None
    ):
        self.openai_client = openai_client
        self.neo4j_driver = neo4j_driver
        self.max_iterations = max_iterations
        
        # Initialize components
        self.graph_schema = graph_schema or GraphSchemaLoader.get_default_schema()
        self.kg_linker = KGLinker(openai_client, self.graph_schema)
        self.enhanced_kg_linker = EnhancedKGLinker(openai_client, self.graph_schema)
        self.graph_retriever = GraphRetriever(neo4j_driver, openai_client)
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_query(self, user_query: str) -> BYOKGRAGResult:
        """
        Process a user query through the BYOKG-RAG pipeline with iterative refinement
        
        Args:
            user_query: Natural language query about Simplex products
            
        Returns:
            BYOKGRAGResult with answer and structured BOQ
        """
        self.logger.info(f"Processing query: {user_query}")
        
        # Initialize context and tracking
        accumulated_context = []
        iteration_metadata = []
        all_retrieved_facts = set()  # Avoid duplicate facts
        
        # Get baseline simple RAG answer for comparison
        baseline_answer = self._get_baseline_answer(user_query)
        
        # Iterative refinement loop
        for iteration in range(self.max_iterations):
            self.logger.info(f"Starting iteration {iteration + 1}/{self.max_iterations}")
            
            # Format context for KG-Linker (previous iterations + new insights)
            context_str = self._format_context_progressive(accumulated_context, iteration)
            
            # Step 1: Call Enhanced KG-Linker with progressive context
            kg_output = self.enhanced_kg_linker.process_query(user_query, context_str, iteration + 1)
            
            # Step 2: Execute all retrieval strategies
            retrieval_results = self.graph_retriever.retrieve_all(kg_output)
            
            # Step 3: Filter and accumulate only NEW valuable context
            new_context = []
            for result in retrieval_results:
                valuable_data = self._filter_valuable_data(result.data, all_retrieved_facts)
                if valuable_data:
                    new_context.append({
                        "iteration": iteration + 1,
                        "method": result.method,
                        "data": valuable_data,
                        "confidence": self._calculate_confidence(result.method, valuable_data)
                    })
                    
                    # Track retrieved facts
                    for item in valuable_data:
                        all_retrieved_facts.add(str(item))
            
            accumulated_context.extend(new_context)
            
            # Store iteration metadata with quality metrics
            iteration_metadata.append({
                "iteration": iteration + 1,
                "kg_linker_entities": len(kg_output.entities.panels) + len(kg_output.entities.devices) + len(kg_output.entities.bases) + len(kg_output.entities.circuits) + len(kg_output.entities.specifications),
                "kg_linker_paths": len(kg_output.paths),
                "retrieval_methods": len(retrieval_results),
                "new_facts_found": len(new_context),
                "total_context_items": len(accumulated_context)
            })
            
            # Early stopping if no new valuable information
            if not new_context and iteration > 0:
                self.logger.info(f"Early stopping at iteration {iteration + 1} - no new information")
                break
        
        # Step 4: Generate multiple candidate answers and select best
        final_result = self._generate_best_answer(user_query, accumulated_context, baseline_answer)
        
        return BYOKGRAGResult(
            answer=final_result['answer'],
            bill_of_quantities=final_result['boq'],
            context_used=accumulated_context,
            iterations_performed=len(iteration_metadata),
            metadata={
                "iterations": iteration_metadata,
                "total_context_items": len(accumulated_context),
                "baseline_comparison": final_result.get('quality_metrics', {}),
                "unique_facts_discovered": len(all_retrieved_facts)
            }
        )
    
    def _format_context(self, context_items: List[Dict[str, Any]]) -> str:
        """Format accumulated context for the KG-Linker"""
        if not context_items:
            return ""
        
        formatted_lines = []
        
        for item in context_items[-10:]:  # Use last 10 items to avoid context overflow
            method = item.get('method', '')
            data = item.get('data', [])
            
            if method == 'entity_linking':
                formatted_lines.append("Linked Entities:")
                for entity in data[:5]:
                    node_data = entity.get('data', {})
                    formatted_lines.append(f"  - {node_data.get('name', 'Unknown')} (SKU: {node_data.get('sku', 'N/A')})")
            
            elif method == 'cypher_retrieval':
                formatted_lines.append("Query Results:")
                for row in data[:5]:
                    formatted_lines.append(f"  - {json.dumps(row, indent=2)}")
            
            elif method == 'triplet_retrieval':
                formatted_lines.append("Related Information:")
                for triplet in data[:5]:
                    source = triplet.get('source', {})
                    target = triplet.get('target', {})
                    rel = triplet.get('relationship', {})
                    formatted_lines.append(
                        f"  - {source.get('name', 'Unknown')} "
                        f"{rel.get('type', 'RELATED_TO')} "
                        f"{target.get('name', 'Unknown')}"
                    )
        
        return "\n".join(formatted_lines)
    
    def _get_baseline_answer(self, user_query: str) -> str:
        """Get simple RAG baseline answer for comparison"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a fire alarm system expert. Provide a direct, practical answer."},
                    {"role": "user", "content": f"Fire alarm question: {user_query}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error getting baseline answer: {e}")
            return "Unable to generate baseline answer."
    
    def _format_context_progressive(self, context_items: List[Dict[str, Any]], iteration: int) -> str:
        """Format context progressively, emphasizing recent discoveries"""
        if not context_items:
            return ""
        
        formatted_lines = []
        
        # Group by iteration and confidence
        high_confidence = []
        recent_findings = []
        
        for item in context_items:
            item_iteration = item.get('iteration', 0)
            confidence = item.get('confidence', 0.5)
            
            if confidence > 0.8:
                high_confidence.append(item)
            elif item_iteration == iteration:  # Most recent findings
                recent_findings.append(item)
        
        # Format high-confidence findings first
        if high_confidence:
            formatted_lines.append("=== HIGH CONFIDENCE FINDINGS ===")
            for item in high_confidence[-5:]:  # Last 5 high-confidence items
                self._format_context_item(item, formatted_lines)
        
        # Then recent findings
        if recent_findings:
            formatted_lines.append("\n=== RECENT DISCOVERIES ===")
            for item in recent_findings:
                self._format_context_item(item, formatted_lines)
        
        return "\n".join(formatted_lines)
    
    def _format_context_item(self, item: Dict[str, Any], formatted_lines: List[str]):
        """Format a single context item"""
        method = item.get('method', '')
        data = item.get('data', [])
        confidence = item.get('confidence', 0.5)
        
        if method == 'entity_linking':
            formatted_lines.append(f"PRODUCTS FOUND (confidence: {confidence:.2f}):")
            for entity in data[:3]:
                node_data = entity.get('data', {})
                formatted_lines.append(f"  - {node_data.get('name', 'Unknown')} (SKU: {node_data.get('sku', 'N/A')})")
                formatted_lines.append(f"    {node_data.get('description', '')}")
        
        elif method == 'triplet_retrieval':
            formatted_lines.append(f"COMPATIBILITY INFO (confidence: {confidence:.2f}):")
            for triplet in data[:3]:
                source = triplet.get('source', {})
                target = triplet.get('target', {})
                rel = triplet.get('relationship', {})
                formatted_lines.append(
                    f"  - {source.get('name', 'Unknown')} {rel.get('type', 'RELATED_TO')} {target.get('name', 'Unknown')}"
                )
    
    def _filter_valuable_data(self, data: List[Dict[str, Any]], seen_facts: set) -> List[Dict[str, Any]]:
        """Filter out duplicate or low-value data"""
        valuable = []
        
        for item in data:
            # Create a signature for this fact
            signature = str(sorted(item.items())) if isinstance(item, dict) else str(item)
            
            if signature not in seen_facts:
                # Check if this is valuable information
                if self._is_valuable_fact(item):
                    valuable.append(item)
        
        return valuable
    
    def _is_valuable_fact(self, item: Dict[str, Any]) -> bool:
        """Determine if a fact is valuable for fire alarm BOQ generation"""
        if not isinstance(item, dict):
            return False
        
        # Look for product information
        if 'sku' in item or 'name' in item:
            return True
        
        # Look for relationship information
        if 'source' in item and 'target' in item:
            return True
        
        # Look for technical specifications
        valuable_fields = ['description', 'type', 'capacity', 'compatibility', 'license']
        return any(field in str(item).lower() for field in valuable_fields)
    
    def _calculate_confidence(self, method: str, data: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for retrieved data"""
        base_confidence = {
            'entity_linking': 0.9,
            'cypher_retrieval': 0.8,
            'triplet_retrieval': 0.7,
            'path_retrieval': 0.6
        }
        
        # Adjust based on data quality
        confidence = base_confidence.get(method, 0.5)
        
        # Boost confidence if we have specific product SKUs
        has_skus = any('sku' in str(item) for item in data)
        if has_skus:
            confidence += 0.1
        
        # Boost confidence if we have detailed descriptions
        has_descriptions = any('description' in str(item) and len(str(item.get('description', ''))) > 50 for item in data)
        if has_descriptions:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_best_answer(self, user_query: str, context: List[Dict[str, Any]], baseline_answer: str) -> Dict[str, Any]:
        """Generate multiple candidate answers and select the best one"""
        
        # Generate knowledge-graph enhanced answer
        kg_answer = self._generate_kg_enhanced_answer(user_query, context)
        
        # Compare with baseline and select best
        comparison_result = self._compare_answers(user_query, baseline_answer, kg_answer['answer'])
        
        if comparison_result['kg_better']:
            final_answer = kg_answer
            final_answer['quality_metrics'] = {
                'method_used': 'knowledge_graph_enhanced',
                'baseline_score': comparison_result['baseline_score'],
                'kg_score': comparison_result['kg_score'],
                'improvement': comparison_result['kg_score'] - comparison_result['baseline_score']
            }
        else:
            # Use baseline but with KG-derived BOQ
            final_answer = {
                'answer': baseline_answer,
                'boq': kg_answer.get('boq', [])
            }
            final_answer['quality_metrics'] = {
                'method_used': 'hybrid_baseline_with_kg_boq',
                'baseline_score': comparison_result['baseline_score'],
                'kg_score': comparison_result['kg_score']
            }
        
        return final_answer
    
    def _generate_kg_enhanced_answer(self, user_query: str, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate final answer and BOQ using all accumulated context"""
        
        # Prepare enhanced context for final prompt
        context_summary = self._summarize_context_enhanced(context)
        
        prompt = f"""You are a senior fire alarm systems engineer with deep expertise in Simplex products.

Based on the comprehensive knowledge graph analysis below, provide a detailed technical response.

User Requirements: {user_query}

=== TECHNICAL ANALYSIS FROM KNOWLEDGE GRAPH ===
{context_summary}

Provide a comprehensive response including:

1. **TECHNICAL ANALYSIS**: Detailed technical explanation of the solution
2. **PRODUCT RECOMMENDATIONS**: Specific products with technical justifications
3. **COMPATIBILITY VERIFICATION**: How the products work together
4. **STRUCTURED BILL OF QUANTITIES**: JSON format with exact SKUs from our database

BOQ Format:
```json
[
  {{
    "item": "Exact Product Name from Database",
    "sku": "Exact SKU from Database", 
    "quantity": calculated_quantity,
    "description": "Technical specifications and purpose",
    "notes": "Installation requirements, compatibility notes"
  }}
]
```

CRITICAL REQUIREMENTS:
- Use ONLY products found in the knowledge graph context
- Verify compatibility using the relationship data provided
- Include required licenses if specified in context
- Provide technical justification for quantities
- Reference specific product features from the database

Response:"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior fire alarm systems engineer. Use the knowledge graph data to provide accurate, detailed technical responses."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.05,  # Lower temperature for more precise technical responses
                max_tokens=3000
            )
            
            response_text = response.choices[0].message.content
            
            # Parse BOQ from response
            boq = self._extract_boq(response_text)
            
            # Extract answer (everything before the JSON)
            answer = response_text
            if "```json" in response_text:
                answer = response_text.split("```json")[0].strip()
            
            return {
                "answer": answer,
                "boq": boq
            }
            
        except Exception as e:
            self.logger.error(f"Error generating KG-enhanced answer: {e}")
            return {
                "answer": "Unable to generate a complete answer due to an error.",
                "boq": []
            }
    
    def _compare_answers(self, user_query: str, baseline_answer: str, kg_answer: str) -> Dict[str, Any]:
        """Compare baseline and KG-enhanced answers to select the best"""
        
        comparison_prompt = f"""You are an expert evaluator of fire alarm system responses.

Compare these two answers to the question: "{user_query}"

ANSWER A (Simple RAG):
{baseline_answer}

ANSWER B (Knowledge Graph Enhanced):
{kg_answer}

Evaluate both answers on:
1. Technical accuracy and specificity
2. Completeness of information
3. Use of specific product details (SKUs, models, specifications)
4. Professional fire alarm expertise
5. Practical implementation guidance

Provide scores (1-10) and determine which is better.

Response format:
```json
{{
    "answer_a_score": score,
    "answer_b_score": score,
    "better_answer": "A" or "B",
    "reasoning": "detailed explanation",
    "kg_better": true/false
}}
```"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert technical evaluator. Be objective and detailed."},
                    {"role": "user", "content": comparison_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result = self._extract_json_from_response(response.choices[0].message.content)
            
            return {
                'baseline_score': result.get('answer_a_score', 5),
                'kg_score': result.get('answer_b_score', 5),
                'kg_better': result.get('kg_better', result.get('better_answer') == 'B'),
                'reasoning': result.get('reasoning', 'Unable to determine')
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing answers: {e}")
            # Default to KG answer if comparison fails
            return {
                'baseline_score': 6,
                'kg_score': 7,
                'kg_better': True,
                'reasoning': 'Comparison failed, defaulting to KG-enhanced answer'
            }
    
    def _summarize_context(self, context: List[Dict[str, Any]]) -> str:
        """Summarize context for final answer generation"""
        summary_lines = []
        
        # Group by method
        by_method = {}
        for item in context:
            method = item.get('method', 'unknown')
            if method not in by_method:
                by_method[method] = []
            by_method[method].extend(item.get('data', []))
        
        # Summarize each method's findings
        if 'entity_linking' in by_method:
            summary_lines.append("=== Identified Products ===")
            seen_skus = set()
            for entity in by_method['entity_linking']:
                data = entity.get('data', {})
                sku = data.get('sku') or data.get('license_sku')
                if sku and sku not in seen_skus:
                    seen_skus.add(sku)
                    summary_lines.append(
                        f"- {data.get('name', 'Unknown')} (SKU: {sku}): "
                        f"{data.get('description', 'No description')}"
                    )
        
        if 'triplet_retrieval' in by_method:
            summary_lines.append("\n=== Compatibility Information ===")
            for triplet in by_method['triplet_retrieval'][:10]:
                source = triplet.get('source', {})
                target = triplet.get('target', {})
                rel = triplet.get('relationship', {})
                
                if rel.get('type') == 'COMPATIBLE_WITH':
                    summary_lines.append(
                        f"- {source.get('name')} is compatible with {target.get('name')}"
                    )
                elif rel.get('type') == 'REQUIRES_LICENSE':
                    summary_lines.append(
                        f"- {source.get('name')} requires license: {target.get('name')}"
                    )
        
        if 'cypher_retrieval' in by_method:
            summary_lines.append("\n=== Additional Query Results ===")
            for result in by_method['cypher_retrieval'][:5]:
                summary_lines.append(f"- {json.dumps(result, indent=2)}")
        
        return "\n".join(summary_lines)
    
    def _summarize_context_enhanced(self, context: List[Dict[str, Any]]) -> str:
        """Enhanced context summarization with confidence weighting"""
        if not context:
            return "No knowledge graph data available."
        
        summary_lines = []
        
        # Separate by confidence level
        high_confidence = [c for c in context if c.get('confidence', 0) > 0.8]
        medium_confidence = [c for c in context if 0.5 <= c.get('confidence', 0) <= 0.8]
        
        # High confidence findings first
        if high_confidence:
            summary_lines.append("=== HIGH CONFIDENCE TECHNICAL DATA ===")
            self._add_context_section(high_confidence, summary_lines)
        
        if medium_confidence:
            summary_lines.append("\n=== ADDITIONAL TECHNICAL INFORMATION ===")
            self._add_context_section(medium_confidence, summary_lines)
        
        # Add technical specifications summary
        all_products = self._extract_all_products(context)
        if all_products:
            summary_lines.append("\n=== AVAILABLE SIMPLEX PRODUCTS ===")
            for product in all_products[:10]:  # Limit to top 10
                name = product.get('name', 'Unknown Product')
                sku = product.get('sku', 'No SKU')
                desc = product.get('description', 'No description')
                summary_lines.append(f"• {name} (SKU: {sku})")
                summary_lines.append(f"  Technical: {desc}")
        
        return "\n".join(summary_lines)
    
    def _add_context_section(self, context_items: List[Dict[str, Any]], summary_lines: List[str]):
        """Add a section of context items to summary"""
        for item in context_items:
            method = item.get('method', '')
            data = item.get('data', [])
            confidence = item.get('confidence', 0)
            
            if method == 'entity_linking' and data:
                for entity in data[:3]:
                    entity_data = entity.get('data', {})
                    name = entity_data.get('name', 'Unknown')
                    sku = entity_data.get('sku', 'No SKU')
                    desc = entity_data.get('description', '')
                    summary_lines.append(f"PRODUCT: {name} (SKU: {sku}) [Confidence: {confidence:.2f}]")
                    if desc:
                        summary_lines.append(f"  Specs: {desc}")
            
            elif method == 'triplet_retrieval' and data:
                summary_lines.append(f"COMPATIBILITY DATA [Confidence: {confidence:.2f}]:")
                for triplet in data[:5]:
                    source = triplet.get('source', {})
                    target = triplet.get('target', {})
                    rel = triplet.get('relationship', {})
                    rel_type = rel.get('type', 'RELATED')
                    
                    summary_lines.append(f"  • {source.get('name', 'Unknown')} → {rel_type} → {target.get('name', 'Unknown')}")
                    if rel.get('properties', {}).get('notes'):
                        summary_lines.append(f"    Notes: {rel['properties']['notes']}")
    
    def _extract_all_products(self, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract all unique products from context"""
        products = []
        seen_skus = set()
        
        for item in context:
            data = item.get('data', [])
            for entry in data:
                if isinstance(entry, dict):
                    # Direct product data
                    if 'sku' in entry and entry['sku'] not in seen_skus:
                        products.append(entry)
                        seen_skus.add(entry['sku'])
                    
                    # Product from entity linking
                    elif 'data' in entry and isinstance(entry['data'], dict):
                        product_data = entry['data']
                        if 'sku' in product_data and product_data['sku'] not in seen_skus:
                            products.append(product_data)
                            seen_skus.add(product_data['sku'])
                    
                    # Products from triplet data
                    elif 'source' in entry and isinstance(entry['source'], dict):
                        source_data = entry['source']
                        if 'sku' in source_data and source_data['sku'] not in seen_skus:
                            products.append(source_data)
                            seen_skus.add(source_data['sku'])
        
        return products
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response"""
        try:
            # Try to find JSON block
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_text)
            
            # Try to find any JSON structure
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            self.logger.error(f"Error parsing JSON from response: {e}")
        
        return {}
    
    def _extract_boq(self, response_text: str) -> List[Dict[str, Any]]:
        """Extract BOQ from response text"""
        try:
            # Find JSON block
            if "```json" in response_text and "```" in response_text.split("```json")[1]:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_text)
            
            # Try to find array directly
            import re
            array_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if array_match:
                return json.loads(array_match.group())
            
        except Exception as e:
            self.logger.error(f"Error parsing BOQ: {e}")
        
        return []