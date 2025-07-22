#!/usr/bin/env python3
"""
Standalone Content Scheduler Runner

This script runs only the content scheduler without the FastAPI application.
Useful for running the scheduler independently or for testing.

Usage:
    python run_scheduler.py
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from app.scheduler import main

if __name__ == "__main__":
    print("🚀 Starting Standalone Content Scheduler...")
    print("⏰ This will run the scheduler without the FastAPI application")
    print("🛑 Press Ctrl+C to stop")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Scheduler error: {str(e)}")
        sys.exit(1) 