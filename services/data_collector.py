"""
Data Collection Service - Jira and Google Sheets Integration
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import gspread
from jira import JIRA
from google.oauth2.service_account import Credentials
from config.settings import settings

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects data from Jira boards and Google Sheets"""
    
    def __init__(self):
        self.jira_client = None
        self.sheets_client = None
        self._setup_clients()
    
    def _setup_clients(self):
        """Initialize Jira and Google Sheets clients"""
        try:
            # Setup Jira client
            self.jira_client = JIRA(
                server=settings.jira_base_url,
                basic_auth=(settings.jira_email, settings.jira_api_token)
            )
            logger.info("Jira client initialized successfully")
            
            # Setup Google Sheets client
            credentials = Credentials.from_service_account_info(
                settings.google_credentials,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.sheets_client = gspread.authorize(credentials)
            logger.info("Google Sheets client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise
    
    def collect_jira_data(self, boards: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Collect data from specified Jira boards
        
        Args:
            boards: List of board IDs/keys. If None, uses settings.jira_boards
            
        Returns:
            Dictionary containing Jira data organized by board
        """
        if boards is None:
            boards = settings.jira_boards
        
        logger.info(f"Collecting Jira data from boards: {boards}")
        
        jira_data = {
            "boards": {},
            "summary": {
                "total_issues": 0,
                "completed_issues": 0,
                "in_progress_issues": 0,
                "blocked_issues": 0
            },
            "collection_timestamp": datetime.now().isoformat()
        }
        
        try:
            for board_key in boards:
                logger.info(f"Processing board: {board_key}")
                
                # Get issues from the last week
                week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                
                # JQL query to get recent issues
                jql = f"""
                project = {board_key} 
                AND updated >= "{week_ago}"
                ORDER BY updated DESC
                """
                
                issues = self.jira_client.search_issues(
                    jql, 
                    maxResults=100,
                    fields='summary,status,assignee,priority,updated,created'
                )
                
                board_data = {
                    "issues": [],
                    "stats": {
                        "total": len(issues),
                        "completed": 0,
                        "in_progress": 0,
                        "blocked": 0
                    }
                }
                
                for issue in issues:
                    issue_data = {
                        "key": issue.key,
                        "summary": issue.fields.summary,
                        "status": issue.fields.status.name,
                        "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                        "priority": issue.fields.priority.name if issue.fields.priority else "None",
                        "updated": issue.fields.updated,
                        "created": issue.fields.created
                    }
                    
                    board_data["issues"].append(issue_data)
                    
                    # Update stats
                    status_lower = issue.fields.status.name.lower()
                    if any(word in status_lower for word in ['done', 'completed', 'closed', 'resolved']):
                        board_data["stats"]["completed"] += 1
                        jira_data["summary"]["completed_issues"] += 1
                    elif any(word in status_lower for word in ['progress', 'development', 'review']):
                        board_data["stats"]["in_progress"] += 1
                        jira_data["summary"]["in_progress_issues"] += 1
                    elif any(word in status_lower for word in ['blocked', 'impediment']):
                        board_data["stats"]["blocked"] += 1
                        jira_data["summary"]["blocked_issues"] += 1
                
                jira_data["boards"][board_key] = board_data
                jira_data["summary"]["total_issues"] += len(issues)
                
                logger.info(f"Collected {len(issues)} issues from {board_key}")
        
        except Exception as e:
            logger.error(f"Error collecting Jira data: {e}")
            raise
        
        return jira_data
    
    def _detect_relevant_tabs(self, spreadsheet) -> List[str]:
        """
        Automatically detect relevant tabs based on content and naming patterns
        
        Args:
            spreadsheet: Google Sheets spreadsheet object
            
        Returns:
            List of relevant tab names
        """
        try:
            all_worksheets = spreadsheet.worksheets()
            relevant_tabs = []
            
            # Keywords that indicate relevant data
            relevant_keywords = [
                'metrics', 'kpi', 'data', 'weekly', 'monthly', 'report', 
                'dashboard', 'summary', 'stats', 'performance', 'issues',
                'tasks', 'progress', 'status', 'tracking'
            ]
            
            # Skip common irrelevant tabs
            skip_keywords = [
                'template', 'example', 'backup', 'archive', 'old', 'test'
            ]
            
            for worksheet in all_worksheets:
                tab_name = worksheet.title.lower()
                
                # Skip if contains skip keywords
                if any(skip_word in tab_name for skip_word in skip_keywords):
                    logger.info(f"Skipping tab '{worksheet.title}' (contains skip keyword)")
                    continue
                
                # Include if contains relevant keywords
                if any(keyword in tab_name for keyword in relevant_keywords):
                    relevant_tabs.append(worksheet.title)
                    logger.info(f"Including tab '{worksheet.title}' (contains relevant keyword)")
                    continue
                
                # Check if tab has substantial data (more than just headers)
                try:
                    # Get first few rows to check for data
                    sample_data = worksheet.get_all_values()
                    if len(sample_data) > 2:  # More than just headers
                        relevant_tabs.append(worksheet.title)
                        logger.info(f"Including tab '{worksheet.title}' (has substantial data: {len(sample_data)} rows)")
                    else:
                        logger.info(f"Skipping tab '{worksheet.title}' (insufficient data: {len(sample_data)} rows)")
                except Exception as e:
                    logger.warning(f"Could not analyze tab '{worksheet.title}': {e}")
            
            # If no tabs found with keywords, include all non-empty tabs
            if not relevant_tabs:
                logger.info("No keyword-matched tabs found, including all non-empty tabs")
                for worksheet in all_worksheets:
                    try:
                        sample_data = worksheet.get_all_values()
                        if len(sample_data) > 1:  # At least headers + 1 row
                            relevant_tabs.append(worksheet.title)
                    except Exception:
                        continue
            
            logger.info(f"Detected relevant tabs: {relevant_tabs}")
            return relevant_tabs
            
        except Exception as e:
            logger.error(f"Error detecting relevant tabs: {e}")
            # Fallback: return all worksheet names
            try:
                return [ws.title for ws in spreadsheet.worksheets()]
            except:
                return []

    def collect_sheets_data(self, sheet_ids: Optional[List[str]] = None, tab_strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect data from multiple Google Sheets with automatic or manual tab detection
        
        Args:
            sheet_ids: List of Google Sheets IDs. If None, uses settings.google_sheets_ids
            tab_strategy: "auto" for automatic detection or "manual" for specified tabs
            
        Returns:
            Dictionary containing sheets data organized by sheet and tab
        """
        if sheet_ids is None:
            sheet_ids = settings.google_sheets_ids
        if tab_strategy is None:
            tab_strategy = settings.google_sheets_tab_strategy
        
        logger.info(f"Collecting Google Sheets data from {len(sheet_ids)} sheets using '{tab_strategy}' tab strategy")
        
        sheets_data = {
            "sheets": {},
            "summary": {
                "total_sheets": len(sheet_ids),
                "total_tabs": 0,
                "total_rows": 0
            },
            "collection_timestamp": datetime.now().isoformat()
        }
        
        for i, sheet_id in enumerate(sheet_ids, 1):
            sheet_id = sheet_id.strip()
            if not sheet_id:
                continue
                
            logger.info(f"Processing sheet {i}/{len(sheet_ids)}: {sheet_id}")
            
            try:
                spreadsheet = self.sheets_client.open_by_key(sheet_id)
                sheet_title = spreadsheet.title
                
                logger.info(f"Opened spreadsheet: '{sheet_title}'")
                
                # Determine which tabs to process
                if tab_strategy == "auto":
                    tabs_to_process = self._detect_relevant_tabs(spreadsheet)
                else:
                    tabs_to_process = settings.google_sheets_tabs
                
                if not tabs_to_process:
                    logger.warning(f"No tabs to process in sheet: {sheet_title}")
                    continue
                
                sheet_data = {
                    "title": sheet_title,
                    "sheet_id": sheet_id,
                    "tabs": {},
                    "tab_count": len(tabs_to_process)
                }
                
                # Process each tab
                for tab_name in tabs_to_process:
                    logger.info(f"Processing tab: {tab_name}")
                    
                    try:
                        worksheet = spreadsheet.worksheet(tab_name)
                        
                        # Get all values from the worksheet
                        all_values = worksheet.get_all_values()
                        
                        if not all_values:
                            logger.warning(f"No data found in tab: {tab_name}")
                            continue
                        
                        # First row is typically headers
                        headers = all_values[0] if all_values else []
                        data_rows = all_values[1:] if len(all_values) > 1 else []
                        
                        tab_data = {
                            "headers": headers,
                            "rows": data_rows,
                            "row_count": len(data_rows),
                            "column_count": len(headers),
                            "sample_data": data_rows[:3] if data_rows else []  # First 3 rows for preview
                        }
                        
                        sheet_data["tabs"][tab_name] = tab_data
                        sheets_data["summary"]["total_rows"] += len(data_rows)
                        
                        logger.info(f"Collected {len(data_rows)} rows from {sheet_title} > {tab_name}")
                        
                    except gspread.WorksheetNotFound:
                        logger.error(f"Worksheet '{tab_name}' not found in spreadsheet '{sheet_title}'")
                        continue
                    except Exception as tab_error:
                        logger.error(f"Error processing tab '{tab_name}' in sheet '{sheet_title}': {tab_error}")
                        continue
                
                sheets_data["sheets"][sheet_id] = sheet_data
                sheets_data["summary"]["total_tabs"] += len(sheet_data["tabs"])
                
                logger.info(f"Completed processing sheet '{sheet_title}': {len(sheet_data['tabs'])} tabs processed")
                
            except Exception as sheet_error:
                logger.error(f"Error processing sheet {sheet_id}: {sheet_error}")
                continue
        
        logger.info(f"Sheets data collection completed: {sheets_data['summary']['total_sheets']} sheets, {sheets_data['summary']['total_tabs']} tabs, {sheets_data['summary']['total_rows']} total rows")
        return sheets_data
    
    def collect_all_data(self) -> Dict[str, Any]:
        """
        Collect data from all configured sources
        
        Returns:
            Dictionary containing all collected data
        """
        logger.info("Starting data collection from all sources")
        
        try:
            jira_data = self.collect_jira_data()
            sheets_data = self.collect_sheets_data()
            
            combined_data = {
                "jira": jira_data,
                "sheets": sheets_data,
                "collection_completed": datetime.now().isoformat()
            }
            
            logger.info("Data collection completed successfully")
            return combined_data
            
        except Exception as e:
            logger.error(f"Error in data collection: {e}")
            raise
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate collected data for completeness
        
        Args:
            data: Collected data dictionary
            
        Returns:
            True if data is valid, False otherwise
        """
        try:
            # Check if we have both Jira and Sheets data
            if "jira" not in data or "sheets" not in data:
                logger.error("Missing required data sources")
                return False
            
            # Check if Jira data has boards
            if not data["jira"].get("boards"):
                logger.error("No Jira boards data found")
                return False
            
            # Check if Sheets data has tabs
            if not data["sheets"].get("tabs"):
                logger.error("No Google Sheets tabs data found")
                return False
            
            logger.info("Data validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating data: {e}")
            return False
