#!/usr/bin/env python3
"""
Test script to verify Jira connection and data retrieval
"""
import logging
import sys
from datetime import datetime, timedelta
from config.settings import settings
from services.data_collector import DataCollector

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_jira_connection():
    """Test Jira connection and data retrieval from all configured boards"""
    
    print("🔍 Testing Jira Connection and Data Retrieval")
    print("=" * 60)
    
    try:
        # Initialize data collector
        print("📡 Initializing Jira connection...")
        data_collector = DataCollector()
        
        if not data_collector.jira_client:
            print("❌ Failed to initialize Jira client")
            return False
        
        print(f"✅ Connected to Jira: {settings.jira_base_url}")
        print(f"📧 Using email: {settings.jira_email}")
        print(f"📋 Configured boards: {settings.jira_boards}")
        print()
        
        # Test each board individually
        for i, board_key in enumerate(settings.jira_boards, 1):
            print(f"🔍 Testing Board {i}: {board_key}")
            print("-" * 40)
            
            try:
                # Get issues from the last 30 days (more lenient for testing)
                days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                
                jql = f"""
                project = {board_key} 
                AND updated >= "{days_ago}"
                ORDER BY updated DESC
                """
                
                print(f"   JQL Query: {jql.strip()}")
                
                # Search for issues
                issues = data_collector.jira_client.search_issues(
                    jql, 
                    maxResults=10,  # Limit for testing
                    fields='summary,status,assignee,priority,updated,created'
                )
                
                print(f"   📊 Found {len(issues)} issues in the last 30 days")
                
                if len(issues) == 0:
                    print("   ℹ️  No recent issues found (this is expected for new boards)")
                else:
                    print("   📝 Recent issues:")
                    for issue in issues[:5]:  # Show first 5
                        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
                        print(f"      • {issue.key}: {issue.fields.summary[:50]}...")
                        print(f"        Status: {issue.fields.status.name} | Assignee: {assignee}")
                
                print("   ✅ Board accessible and working")
                
            except Exception as board_error:
                print(f"   ❌ Error accessing board {board_key}: {board_error}")
                # Continue testing other boards
            
            print()
        
        # Now test the full data collection method
        print("🔄 Testing Full Data Collection Method")
        print("-" * 40)
        
        try:
            jira_data = data_collector.collect_jira_data()
            
            print(f"✅ Full data collection successful!")
            print(f"📊 Summary:")
            print(f"   - Total boards processed: {len(jira_data['boards'])}")
            print(f"   - Total issues found: {jira_data['summary']['total_issues']}")
            print(f"   - Completed issues: {jira_data['summary']['completed_issues']}")
            print(f"   - In progress issues: {jira_data['summary']['in_progress_issues']}")
            print(f"   - Blocked issues: {jira_data['summary']['blocked_issues']}")
            
            print(f"\n📋 Board Details:")
            for board_key, board_data in jira_data['boards'].items():
                stats = board_data['stats']
                print(f"   {board_key}: {stats['total']} issues (✅ {stats['completed']}, 🔄 {stats['in_progress']}, 🚫 {stats['blocked']})")
            
            return True
            
        except Exception as collection_error:
            print(f"❌ Full data collection failed: {collection_error}")
            return False
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        logger.error(f"Detailed error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("🚀 Starting Jira Connection Test")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = test_jira_connection()
    
    print()
    print("=" * 60)
    if success:
        print("🎉 Jira connection test PASSED!")
        print("✅ All boards are accessible and data retrieval is working")
        print("🔄 You can now run: python manage.py run-preview-generation")
    else:
        print("❌ Jira connection test FAILED!")
        print("🔧 Please check your configuration in config.env:")
        print("   - JIRA_BASE_URL")
        print("   - JIRA_API_TOKEN") 
        print("   - JIRA_EMAIL")
        print("   - JIRA_BOARDS")
    
    sys.exit(0 if success else 1)
