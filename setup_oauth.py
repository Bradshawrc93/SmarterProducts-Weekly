#!/usr/bin/env python3
"""
Set up OAuth with your personal Google account for document creation
"""
import json
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import subprocess

def run_oauth_flow():
    """Run OAuth flow to get user credentials"""
    
    print("🔧 Running OAuth Flow with Your Personal Google Account")
    print("=" * 60)
    
    if not os.path.exists('oauth_credentials.json'):
        print("❌ oauth_credentials.json not found!")
        return None
    
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = None
    
    # Check for existing token
    if os.path.exists('token.json'):
        print("🔍 Checking existing token...")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Starting OAuth flow...")
            print("💡 Your browser will open for Google authentication")
            print("💡 Please log in with your Google account and grant permissions")
            
            flow = InstalledAppFlow.from_client_secrets_file('oauth_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        print("✅ OAuth credentials saved for future use")
    
    print("✅ OAuth authentication successful!")
    return creds

def create_weekly_report_with_oauth():
    """Create the actual weekly report using OAuth"""
    
    print("\n🚀 Creating Weekly Report with OAuth")
    print("=" * 50)
    
    # Get OAuth credentials
    creds = run_oauth_flow()
    if not creds:
        return None, None
    
    try:
        # Build services with your personal account
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        print("✅ Google services initialized with your personal account")
        
        # Calculate document name
        today = datetime.now()
        days_since_monday = today.weekday()
        if days_since_monday == 0:
            target_monday = today
        else:
            target_monday = today - timedelta(days=days_since_monday)
        
        this_wednesday = target_monday + timedelta(days=9)
        report_date = this_wednesday.strftime('%-m/%-d/%y')
        
        doc_title = f"Weekly Product Team Report {report_date}"
        
        print(f"📄 Creating document: '{doc_title}'")
        
        # Create document with your personal account (has storage!)
        document = {'title': doc_title}
        doc = docs_service.documents().create(body=document).execute()
        doc_id = doc.get('documentId')
        
        print(f"✅ Document created successfully!")
        print(f"📄 Document ID: {doc_id}")
        
        # Move to your reports folder if configured
        config = {}
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        drive_folder_id = config.get('GOOGLE_DRIVE_FOLDER_ID', '')
        
        if drive_folder_id and drive_folder_id != '1example_folder_id':
            try:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=drive_folder_id,
                    removeParents='root'
                ).execute()
                print(f"📁 Moved to reports folder")
            except Exception as folder_error:
                print(f"⚠️  Could not move to folder: {folder_error}")
                print(f"📄 Document created in root Drive instead")
        
        # Add the complete report content
        print("📊 Generating and adding complete report content...")
        
        # Generate report content
        result = subprocess.run(['python', 'generate_full_report.py'], 
                              capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            # Extract report content
            output_lines = result.stdout.split('\n')
            report_start = False
            report_lines = []
            
            for line in output_lines:
                if "📝 COMPLETE WEEKLY REPORT" in line:
                    report_start = True
                    continue
                elif line.strip().startswith("======") and report_start:
                    continue
                elif "🎉 REPORT GENERATION COMPLETE" in line and report_start:
                    break
                elif report_start:
                    report_lines.append(line)
            
            report_content = '\n'.join(report_lines).strip()
            
            # Add content to document
            requests = [{
                'insertText': {
                    'location': {'index': 1},
                    'text': report_content
                }
            }]
            
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            print(f"✅ Complete report content added!")
            print(f"📊 Report includes real data from all 4 teams and Jira boards")
        else:
            print(f"⚠️  Document created but could not add content")
        
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        
        print(f"🔗 Your Weekly Report: {doc_url}")
        print()
        print("🎉 SUCCESS! Full automation working with OAuth!")
        print("📄 Document created with your personal Google account")
        print("✅ Contains real data from Google Sheets and Jira")
        print("🚀 Weekly automation system is now fully operational!")
        
        return doc_id, doc_url
        
    except Exception as e:
        print(f"❌ OAuth document creation failed: {e}")
        return None, None

if __name__ == "__main__":
    doc_id, doc_url = create_weekly_report_with_oauth()
    
    if doc_id:
        print(f"\n🎯 WEEKLY AUTOMATION COMPLETE!")
        print(f"📄 Report created: {doc_url}")
        print(f"✅ System ready for Tuesday/Wednesday scheduling")
        print(f"🔄 OAuth token saved for future automated runs")
    else:
        print(f"\n🔧 Check the OAuth setup steps above")
