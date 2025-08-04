#!/usr/bin/env python3
"""
Test script to verify the Simplex KG-RAG system components
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
import boto3

# Load environment
load_dotenv()

def test_neo4j():
    """Test Neo4j connection"""
    print("Testing Neo4j connection...")
    try:
        driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j Connected!' as message")
            message = result.single()['message']
            print(f"✅ Neo4j: {message}")
            
            # Create test schema
            session.run("CREATE CONSTRAINT product_sku IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE")
            print("✅ Neo4j: Schema constraints created")
            
        driver.close()
        return True
    except Exception as e:
        print(f"❌ Neo4j Error: {str(e)}")
        return False

def test_openai():
    """Test OpenAI connection"""
    print("\nTesting OpenAI connection...")
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Simple test
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'OpenAI Connected!'"}],
            max_tokens=20
        )
        
        message = response.choices[0].message.content
        print(f"✅ OpenAI: {message}")
        return True
    except Exception as e:
        print(f"❌ OpenAI Error: {str(e)}")
        return False

def test_s3():
    """Test S3 connection"""
    print("\nTesting S3 connection...")
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # List buckets
        response = s3_client.list_buckets()
        bucket_names = [b['Name'] for b in response['Buckets']]
        
        if os.getenv('AWS_BUCKET_NAME') in bucket_names:
            print(f"✅ S3: Connected to bucket '{os.getenv('AWS_BUCKET_NAME')}'")
            
            # List objects in bucket
            objects = s3_client.list_objects_v2(Bucket=os.getenv('AWS_BUCKET_NAME'), MaxKeys=5)
            if 'Contents' in objects:
                print(f"   Found {len(objects['Contents'])} objects in bucket")
            else:
                print("   Bucket is empty")
            
            return True
        else:
            print(f"❌ S3: Bucket '{os.getenv('AWS_BUCKET_NAME')}' not found")
            return False
            
    except Exception as e:
        print(f"❌ S3 Error: {str(e)}")
        return False

def test_core_modules():
    """Test core BYOKG-RAG modules"""
    print("\nTesting core modules...")
    try:
        from src.core.kg_linker import KGLinker, GraphSchemaLoader
        from src.core.graph_retriever import GraphRetriever
        from src.core.orchestrator import BYOKGRAGPipeline
        
        print("✅ Core modules imported successfully")
        
        # Test schema loader
        schema = GraphSchemaLoader.get_default_schema()
        print(f"✅ Graph schema loaded with {len(schema['nodes'])} node types and {len(schema['relationships'])} relationship types")
        
        return True
    except Exception as e:
        print(f"❌ Core modules error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Simplex KG-RAG System Test")
    print("=" * 50)
    
    results = {
        "Neo4j": test_neo4j(),
        "OpenAI": test_openai(),
        "S3": test_s3(),
        "Core Modules": test_core_modules()
    }
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    
    all_passed = True
    for component, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{component}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("1. Run ingestion: python scripts/run_ingestion.py")
        print("2. Start API: python scripts/run_api.py")
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")

if __name__ == "__main__":
    main()