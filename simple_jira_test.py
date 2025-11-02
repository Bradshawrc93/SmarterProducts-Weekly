#!/usr/bin/env python3
"""
Simple Jira connection test without complex dependencies
"""
import os
import sys
from datetime import datetime, timedelta

# Simple configuration loading
def load_config():
    """Load configuration from config.env file"""
    config = {}
    
    # Try to find config file
    config_files = ['config.env', '.env', '.env.local']
    config_file = None
    
    for file in config_files:
        if os.path.exists(file):
            config_file = file
            break
    
    if not config_file:
        print("❌ No configuration file found. Please run: python setup_local_config.py")
        return None
    
    print(f"📄 Loading configuration from: {config_file}")
    
    # Read the config file
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    
    return config

def test_jira_basic():
    """Test basic Jira connection using requests"""
    try:
        import requests
        from requests.auth import HTTPBasicAuth
        import json
    except ImportError:
        print("❌ Missing required packages. Please install: pip install requests")
        return False
    
    config = load_config()
    if not config:
        return False
    
    # Get required config values
    jira_base_url = config.get('JIRA_BASE_URL')
    jira_email = config.get('JIRA_EMAIL') 
    jira_token = config.get('JIRA_API_TOKEN')
    jira_boards = config.get('JIRA_BOARDS', '').split(',')
    
    if not all([jira_base_url, jira_email, jira_token]):
        print("❌ Missing required Jira configuration:")
        print("   - JIRA_BASE_URL")
        print("   - JIRA_EMAIL") 
        print("   - JIRA_API_TOKEN")
        return False
    
    print("🔍 Testing Jira Connection")
    print("=" * 50)
    print(f"🌐 Jira URL: {jira_base_url}")
    print(f"📧 Email: {jira_email}")
    print(f"📋 Boards: {jira_boards}")
    print()
    
    # Test basic connection
    try:
        auth = HTTPBasicAuth(jira_email, jira_token)
        headers = {'Accept': 'application/json'}
        
        # Test connection with a simple API call
        response = requests.get(
            f"{jira_base_url}/rest/api/3/myself",
            auth=auth,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ Successfully connected to Jira!")
            print(f"👤 Logged in as: {user_info.get('displayName', 'Unknown')}")
            print(f"📧 Account email: {user_info.get('emailAddress', 'Unknown')}")
        else:
            print(f"❌ Jira connection failed: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    print()
    
    # Test each board
    for i, board_key in enumerate(jira_boards, 1):
        board_key = board_key.strip()
        if not board_key:
            continue
            
        print(f"🔍 Testing Board {i}: {board_key}")
        print("-" * 30)
        
        try:
            # Get recent issues from this board/project
            days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            jql = f'project = {board_key} AND updated >= "{days_ago}" ORDER BY updated DESC'
            
            response = requests.post(
                f"{jira_base_url}/rest/api/3/search/jql",
                auth=auth,
                headers={**headers, 'Content-Type': 'application/json'},
                json={
                    'jql': jql,
                    'maxResults': 10,
                    'fields': ['summary', 'status', 'assignee', 'priority', 'updated', 'created']
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                total = data.get('total', 0)
                
                print(f"   📊 Found {total} issues in the last 30 days")
                
                if total == 0:
                    print("   ℹ️  No recent issues (expected for new boards)")
                else:
                    print("   📝 Recent issues:")
                    for issue in issues[:5]:
                        fields = issue['fields']
                        assignee = fields.get('assignee', {})
                        assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
                        
                        print(f"      • {issue['key']}: {fields['summary'][:50]}...")
                        print(f"        Status: {fields['status']['name']} | Assignee: {assignee_name}")
                
                print("   ✅ Board accessible")
                
            else:
                print(f"   ❌ Failed to access board: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except Exception as board_error:
            print(f"   ❌ Error accessing board: {board_error}")
        
        print()
    
    print("🎉 Jira connection test completed!")
    return True

if __name__ == "__main__":
    print("🚀 Simple Jira Connection Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = test_jira_basic()
    
    if success:
        print("✅ Test PASSED - Jira connection is working!")
    else:
        print("❌ Test FAILED - Please check your configuration")
    
    sys.exit(0 if success else 1)
