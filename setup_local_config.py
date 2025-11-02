#!/usr/bin/env python3
"""
Local Configuration Setup Script
This script helps you create a local configuration file safely
"""
import os
import shutil

def setup_local_config():
    """Copy the example config to a local config file"""
    
    example_file = "config.env.example"
    local_file = "config.env"
    
    if not os.path.exists(example_file):
        print(f"❌ {example_file} not found!")
        return False
    
    if os.path.exists(local_file):
        response = input(f"⚠️  {local_file} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return False
    
    # Copy the example file
    shutil.copy2(example_file, local_file)
    
    print(f"✅ Created {local_file}")
    print(f"📝 Please edit {local_file} with your actual credentials")
    print(f"🔒 This file is already in .gitignore and will NOT be committed to GitHub")
    print()
    print("Next steps:")
    print("1. Edit config.env with your actual API keys and configuration")
    print("2. Run: python manage.py test-connections")
    print("3. Run: python manage.py run-preview-generation (for testing)")
    
    return True

if __name__ == "__main__":
    setup_local_config()
