#!/usr/bin/env python3
"""
Comprehensive Jira test that retrieves actual board information and sample data
"""
import os
import sys
from datetime import datetime, timedelta
import json

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

def test_jira_comprehensive():
    """Comprehensive Jira test with detailed board information"""
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
        print("❌ Missing required Jira configuration")
        return False
    
    print("🔍 Comprehensive Jira Data Retrieval Test")
    print("=" * 60)
    print(f"🌐 Jira URL: {jira_base_url}")
    print(f"📧 Email: {jira_email}")
    print(f"📋 Boards: {jira_boards}")
    print()
    
    auth = HTTPBasicAuth(jira_email, jira_token)
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    
    # Test connection first
    try:
        response = requests.get(
            f"{jira_base_url}/rest/api/3/myself",
            auth=auth,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ Connected as: {user_info.get('displayName', 'Unknown')}")
        else:
            print(f"❌ Connection failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    print()
    
    # Get detailed information for each board
    for i, board_key in enumerate(jira_boards, 1):
        board_key = board_key.strip()
        if not board_key:
            continue
            
        print(f"📋 BOARD {i}: {board_key}")
        print("=" * 50)
        
        try:
            # 1. Get project information
            print("🔍 Getting project information...")
            project_response = requests.get(
                f"{jira_base_url}/rest/api/3/project/{board_key}",
                auth=auth,
                headers=headers,
                timeout=10
            )
            
            if project_response.status_code == 200:
                project_info = project_response.json()
                print(f"   📝 Project Name: {project_info.get('name', 'Unknown')}")
                print(f"   🔑 Project Key: {project_info.get('key', 'Unknown')}")
                print(f"   📖 Description: {project_info.get('description', 'No description')[:100]}...")
                print(f"   👤 Lead: {project_info.get('lead', {}).get('displayName', 'Unknown')}")
                
                # Get project type and category
                project_type = project_info.get('projectTypeKey', 'Unknown')
                print(f"   🏷️  Type: {project_type}")
                
            else:
                print(f"   ⚠️  Could not get project details: HTTP {project_response.status_code}")
            
            print()
            
            # 2. Get ALL issues from this project (not just recent ones)
            print("🔍 Getting all issues from project...")
            
            # First, get a count of all issues
            count_response = requests.post(
                f"{jira_base_url}/rest/api/3/search/jql",
                auth=auth,
                headers=headers,
                json={
                    'jql': f'project = {board_key}',
                    'maxResults': 0  # Just get the count
                },
                timeout=10
            )
            
            total_issues = 0
            if count_response.status_code == 200:
                count_data = count_response.json()
                total_issues = count_data.get('total', 0)
                print(f"   📊 Total issues in project: {total_issues}")
            
            # Now get actual issues (limit to 20 for display)
            issues_response = requests.post(
                f"{jira_base_url}/rest/api/3/search/jql",
                auth=auth,
                headers=headers,
                json={
                    'jql': f'project = {board_key} ORDER BY created DESC',
                    'maxResults': 20,
                    'fields': ['summary', 'status', 'assignee', 'priority', 'updated', 'created', 'issuetype', 'reporter']
                },
                timeout=10
            )
            
            if issues_response.status_code == 200:
                issues_data = issues_response.json()
                issues = issues_data.get('issues', [])
                
                if len(issues) == 0:
                    print("   📝 No issues found in this project")
                    
                    # Let's try to create a sample issue for testing
                    print("   🔧 Creating a sample issue for testing...")
                    
                    sample_issue = {
                        "fields": {
                            "project": {"key": board_key},
                            "summary": f"Sample Weekly Report Test Issue - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                            "description": {
                                "type": "doc",
                                "version": 1,
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "This is a sample issue created by the SmarterProducts Weekly automation system for testing data retrieval. You can safely delete this issue after testing."
                                            }
                                        ]
                                    }
                                ]
                            },
                            "issuetype": {"name": "Task"}  # Most common issue type
                        }
                    }
                    
                    create_response = requests.post(
                        f"{jira_base_url}/rest/api/3/issue",
                        auth=auth,
                        headers=headers,
                        json=sample_issue,
                        timeout=10
                    )
                    
                    if create_response.status_code == 201:
                        created_issue = create_response.json()
                        issue_key = created_issue.get('key')
                        print(f"   ✅ Created sample issue: {issue_key}")
                        print(f"   🔗 View at: {jira_base_url}/browse/{issue_key}")
                        
                        # Now retrieve it to show we can access it
                        print("   🔄 Retrieving the created issue...")
                        
                        retrieve_response = requests.post(
                            f"{jira_base_url}/rest/api/3/search/jql",
                            auth=auth,
                            headers=headers,
                            json={
                                'jql': f'project = {board_key} ORDER BY created DESC',
                                'maxResults': 5,
                                'fields': ['summary', 'status', 'assignee', 'priority', 'updated', 'created', 'issuetype', 'reporter']
                            },
                            timeout=10
                        )
                        
                        if retrieve_response.status_code == 200:
                            retrieve_data = retrieve_response.json()
                            retrieved_issues = retrieve_data.get('issues', [])
                            
                            print(f"   📋 Retrieved {len(retrieved_issues)} issues:")
                            for issue in retrieved_issues[:3]:  # Show first 3
                                fields = issue['fields']
                                assignee = fields.get('assignee')
                                assignee_name = assignee.get('displayName') if assignee else 'Unassigned'
                                reporter = fields.get('reporter', {})
                                reporter_name = reporter.get('displayName', 'Unknown')
                                
                                print(f"      🎫 {issue['key']}: {fields['summary']}")
                                print(f"         Status: {fields['status']['name']}")
                                print(f"         Type: {fields['issuetype']['name']}")
                                print(f"         Assignee: {assignee_name}")
                                print(f"         Reporter: {reporter_name}")
                                print(f"         Created: {fields['created'][:10]}")
                                print()
                    
                    else:
                        print(f"   ⚠️  Could not create sample issue: HTTP {create_response.status_code}")
                        print(f"   Response: {create_response.text[:200]}...")
                
                else:
                    print(f"   📋 Found {len(issues)} existing issues:")
                    for issue in issues[:5]:  # Show first 5
                        fields = issue['fields']
                        assignee = fields.get('assignee')
                        assignee_name = assignee.get('displayName') if assignee else 'Unassigned'
                        reporter = fields.get('reporter', {})
                        reporter_name = reporter.get('displayName', 'Unknown')
                        
                        print(f"      🎫 {issue['key']}: {fields['summary']}")
                        print(f"         Status: {fields['status']['name']}")
                        print(f"         Type: {fields['issuetype']['name']}")
                        print(f"         Assignee: {assignee_name}")
                        print(f"         Reporter: {reporter_name}")
                        print(f"         Created: {fields['created'][:10]}")
                        print()
            
            else:
                print(f"   ❌ Failed to get issues: HTTP {issues_response.status_code}")
                print(f"   Response: {issues_response.text[:200]}...")
            
            # 3. Get issue types available in this project
            print("🔍 Getting available issue types...")
            
            issuetypes_response = requests.get(
                f"{jira_base_url}/rest/api/3/project/{board_key}/statuses",
                auth=auth,
                headers=headers,
                timeout=10
            )
            
            if issuetypes_response.status_code == 200:
                issuetypes_data = issuetypes_response.json()
                print(f"   🏷️  Available issue types:")
                for issuetype in issuetypes_data[:5]:  # Show first 5
                    print(f"      • {issuetype.get('name', 'Unknown')}")
            
            print()
            print("-" * 50)
            print()
                
        except Exception as board_error:
            print(f"   ❌ Error processing board {board_key}: {board_error}")
            print()
    
    print("🎉 Comprehensive Jira test completed!")
    return True

if __name__ == "__main__":
    print("🚀 Comprehensive Jira Data Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = test_jira_comprehensive()
    
    if success:
        print("✅ Test PASSED - Jira integration is fully working!")
        print("🔄 You can now run the full weekly report generation!")
    else:
        print("❌ Test FAILED - Please check your configuration")
    
    sys.exit(0 if success else 1)
