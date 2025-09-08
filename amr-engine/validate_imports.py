#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick validation script to check for import errors.
Run this before building Docker to catch issues early.
"""

import sys
import traceback
import os

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_imports():
    """Test critical imports that might fail."""
    errors = []
    
    try:
        print("Testing core FastAPI imports...")
        import fastapi
        import uvicorn
        import pydantic
        print("[OK] FastAPI imports successful")
    except ImportError as e:
        errors.append(f"FastAPI imports failed: {e}")
    
    try:
        print("Testing AMR engine imports...")
        from amr_engine.main import create_app
        from amr_engine.core.classifier import Classifier
        from amr_engine.core.schemas import ClassificationInput
        print("[OK] AMR engine imports successful")
    except ImportError as e:
        errors.append(f"AMR engine imports failed: {e}")
        traceback.print_exc()
    
    try:
        print("Testing new auth imports...")
        from amr_engine.core.auth import AuthenticationService
        print("[OK] Auth imports successful")
    except ImportError as e:
        errors.append(f"Auth imports failed: {e}")
        traceback.print_exc()
    
    try:
        print("Testing cryptography imports...")
        import cryptography
        import jwt
        print("[OK] Cryptography imports successful")
    except ImportError as e:
        errors.append(f"Cryptography imports failed: {e}")
        print("[WARNING] Note: You may need to install: pip install cryptography PyJWT python-jose[cryptography]")
    
    try:
        print("Testing app creation...")
        app = create_app()
        print("[OK] App creation successful")
    except Exception as e:
        errors.append(f"App creation failed: {e}")
        traceback.print_exc()
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n[SUCCESS] All imports and app creation successful!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)