#!/usr/bin/env python3
"""
Monitor the iterative KG building progress
"""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import json
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

def get_kg_stats():
    """Get current knowledge graph statistics"""
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    with driver.session() as session:
        # Node counts
        node_result = session.run("""
            MATCH (n) 
            RETURN labels(n)[0] as type, count(n) as count 
            ORDER BY count DESC
        """)
        nodes = {row['type']: row['count'] for row in node_result}
        
        # Relationship counts
        rel_result = session.run("""
            MATCH ()-[r]->() 
            RETURN type(r) as type, count(r) as count 
            ORDER BY count DESC
        """)
        relationships = {row['type']: row['count'] for row in rel_result}
        
        # Sample entities with enrichment
        enriched = session.run("""
            MATCH (n)
            WHERE EXISTS(n.enriched_description)
            RETURN count(n) as enriched_count
        """).single()['enriched_count']
        
    return {
        'timestamp': datetime.now().isoformat(),
        'nodes': nodes,
        'relationships': relationships,
        'total_nodes': sum(nodes.values()),
        'total_relationships': sum(relationships.values()),
        'enriched_entities': enriched
    }

def monitor_for_duration(duration_minutes=60):
    """Monitor progress for specified duration"""
    end_time = time.time() + (duration_minutes * 60)
    progress_log = []
    
    print(f"=== MONITORING KG BUILDING FOR {duration_minutes} MINUTES ===")
    print(f"Started at: {datetime.now()}")
    
    while time.time() < end_time:
        try:
            stats = get_kg_stats()
            progress_log.append(stats)
            
            print(f"\n[{stats['timestamp']}]")
            print(f"Total Nodes: {stats['total_nodes']}")
            print(f"Total Relationships: {stats['total_relationships']}")
            print(f"Enriched Entities: {stats['enriched_entities']}")
            
            print("Node Types:")
            for node_type, count in stats['nodes'].items():
                print(f"  {node_type}: {count}")
            
            print("Relationship Types:")
            for rel_type, count in stats['relationships'].items():
                print(f"  {rel_type}: {count}")
            
            # Save progress
            with open('monitoring_progress.json', 'w') as f:
                json.dump(progress_log, f, indent=2)
            
            # Wait 2 minutes between checks
            time.sleep(120)
            
        except Exception as e:
            print(f"Error monitoring: {e}")
            time.sleep(60)
    
    print(f"\n=== MONITORING COMPLETED ===")
    print(f"Final stats saved to monitoring_progress.json")
    
    # Create summary report
    if progress_log:
        initial = progress_log[0]
        final = progress_log[-1]
        
        summary = {
            'monitoring_duration_minutes': duration_minutes,
            'initial_state': initial,
            'final_state': final,
            'growth': {
                'nodes': final['total_nodes'] - initial['total_nodes'],
                'relationships': final['total_relationships'] - initial['total_relationships'],
                'enriched': final['enriched_entities'] - initial['enriched_entities']
            }
        }
        
        with open('kg_growth_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nGrowth Summary:")
        print(f"Nodes: {initial['total_nodes']} → {final['total_nodes']} (+{summary['growth']['nodes']})")
        print(f"Relationships: {initial['total_relationships']} → {final['total_relationships']} (+{summary['growth']['relationships']})")
        print(f"Enriched: {initial['enriched_entities']} → {final['enriched_entities']} (+{summary['growth']['enriched']})")

if __name__ == "__main__":
    monitor_for_duration(60)  # Monitor for 1 hour