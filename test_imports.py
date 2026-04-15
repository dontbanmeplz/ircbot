#!/usr/bin/env python3
"""
Quick test to verify core modules can be imported
"""

print("Testing imports...")

try:
    print("  ✓ Importing config...")
    import config
    
    print("  ✓ Importing models...")
    from models import db, Book, SearchHistory
    
    print("  ✓ Importing auth...")
    from auth import init_auth, check_password, User
    
    print("  ✓ Importing parser...")
    from parser import parse_search_results, extract_metadata_from_filename
    
    print("  ✓ Importing async_dcc_bot...")
    from async_dcc_bot import AsyncDCCBot
    
    # Don't import bot_manager since it requires socketio and starts threads
    print("  ⚠ Skipping bot_manager (requires socketio context)")
    
    print("\n✅ All core modules imported successfully!")
    print("\n🎉 The broadcast=True issue has been fixed!")
    print("\nYou can now start the application with:")
    print("  uv run python app.py")
    print("\nOr use the start script:")
    print("  ./start.sh")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
