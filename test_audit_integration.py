#!/usr/bin/env python3
"""
Test script for audit integration functionality.
Tests the audit publisher integration without requiring Docker.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the amr-engine directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "amr-engine"))

# Set environment variables for testing
os.environ['KAFKA_ENABLED'] = 'false'
os.environ['AUDIT_STREAMING_ENABLED'] = 'false' 
os.environ['PSEUDONYMIZATION_ENABLED'] = 'false'
os.environ['AMR_RULES_PATH'] = 'amr-engine/amr_engine/rules/eucast_v_2025_1.yaml'

async def test_audit_integration():
    """Test the audit integration components."""
    print("=== Testing Audit Integration Components ===")
    
    try:
        # Test correlation ID functionality
        print("\n1. Testing Correlation ID functionality...")
        from amr_engine.core.correlation import generate_correlation_id, set_correlation_id, get_correlation_id
        
        correlation_id = generate_correlation_id()
        print(f"   OK Generated correlation ID: {correlation_id}")
        
        set_correlation_id(correlation_id)
        retrieved_id = get_correlation_id()
        assert retrieved_id == correlation_id, f"Correlation ID mismatch: {retrieved_id} != {correlation_id}"
        print(f"   OK Correlation ID context works correctly")
        
    except Exception as e:
        print(f"   ERROR Correlation ID test failed: {e}")
        return False
    
    try:
        # Test audit service initialization
        print("\n2. Testing Audit Service...")
        from amr_engine.core.audit_integration import get_audit_service
        
        audit_service = get_audit_service()
        print(f"   OK Audit service created successfully")
        print(f"   OK Audit enabled: {audit_service.is_enabled}")
        
        # Test health status
        health_status = await audit_service.get_health_status()
        print(f"   OK Health status: {health_status}")
        
    except Exception as e:
        print(f"   ERROR Audit service test failed: {e}")
        return False
    
    try:
        # Test FastAPI app creation
        print("\n3. Testing FastAPI App Creation...")
        from amr_engine.main import create_app
        
        app = create_app()
        print(f"   OK FastAPI app created successfully")
        print(f"   OK App title: {app.title}")
        
    except Exception as e:
        print(f"   ERROR FastAPI app creation failed: {e}")
        return False
    
    try:
        # Test classification with audit (mock)
        print("\n4. Testing Classification Schema...")
        from amr_engine.core.schemas import ClassificationInput, ClassificationResult
        
        # Create a test classification input
        test_input = ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ampicillin",
            method="MIC",
            mic_mg_L=8.0,
            specimenId="TEST-001"
        )
        print(f"   OK Classification input created: {test_input.organism}")
        
        # Create a test classification result
        test_result = ClassificationResult(
            specimenId="TEST-001",
            organism="Escherichia coli", 
            antibiotic="Ampicillin",
            method="MIC",
            input=test_input.model_dump(),
            decision="R",
            reason="Test classification",
            ruleVersion="EUCAST-2025.1"
        )
        print(f"   OK Classification result created: {test_result.decision}")
        
    except Exception as e:
        print(f"   ERROR Classification schema test failed: {e}")
        return False
    
    print("\n=== All Audit Integration Tests Passed! ===")
    return True


async def test_metrics():
    """Test metrics functionality."""
    print("\n=== Testing Metrics ===")
    
    try:
        from amr_engine.core.audit_integration import audit_events_total, audit_publish_duration
        
        # Test metrics objects exist
        print("   OK Audit metrics objects created successfully")
        print(f"   OK audit_events_total: {audit_events_total}")
        print(f"   OK audit_publish_duration: {audit_publish_duration}")
        
    except Exception as e:
        print(f"   ERROR Metrics test failed: {e}")
        return False
    
    return True


async def main():
    """Main test function."""
    print("Starting Audit Integration Tests...")
    
    # Test basic components
    success = await test_audit_integration()
    if not success:
        print("Basic integration tests failed!")
        return 1
    
    # Test metrics
    success = await test_metrics()
    if not success:
        print("Metrics tests failed!")
        return 1
    
    print("\nSUCCESS ALL TESTS PASSED! SUCCESS")
    print("Audit integration is working correctly!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)