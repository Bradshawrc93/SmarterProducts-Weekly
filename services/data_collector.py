"""
Data Collection Service - Jira and Google Sheets Integration
"""
import logging
import re
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
        
        # Calculate date ranges for current and previous week
        today = datetime.now()
        days_since_monday = today.weekday()
        
        # Current week: Last Monday to this Tuesday
        if days_since_monday == 0:  # Today is Monday
            current_week_start = today - timedelta(days=7)
        else:
            this_monday = today - timedelta(days=days_since_monday)
            current_week_start = this_monday - timedelta(days=7)
        
        current_week_end = current_week_start + timedelta(days=8)  # Last Monday + 8 days = this Tuesday
        
        # Previous week: 14 days ago Monday to 7 days ago Tuesday
        previous_week_start = current_week_start - timedelta(days=7)
        previous_week_end = current_week_start  # Previous week ends when current week starts
        
        logger.info(f"Current week: {current_week_start.strftime('%Y-%m-%d')} to {current_week_end.strftime('%Y-%m-%d')}")
        logger.info(f"Previous week: {previous_week_start.strftime('%Y-%m-%d')} to {previous_week_end.strftime('%Y-%m-%d')}")
        
        jira_data = {
            "boards": {},
            "summary": {
                "total_issues": 0,
                "completed_issues": 0,
                "in_progress_issues": 0,
                "blocked_issues": 0,
                "to_do_issues": 0
            },
            "collection_timestamp": datetime.now().isoformat(),
            "date_ranges": {
                "current_week_start": current_week_start.strftime('%Y-%m-%d'),
                "current_week_end": current_week_end.strftime('%Y-%m-%d'),
                "previous_week_start": previous_week_start.strftime('%Y-%m-%d'),
                "previous_week_end": previous_week_end.strftime('%Y-%m-%d')
            }
        }
        
        try:
            for board_key in boards:
                logger.info(f"Processing board: {board_key}")
                
                # Get issues from current week (updated in the period)
                current_week_start_str = current_week_start.strftime('%Y-%m-%d')
                current_week_end_str = current_week_end.strftime('%Y-%m-%d')
                
                # JQL query to get recent issues updated in current week
                jql_current = f"""
                project = {board_key} 
                AND updated >= "{current_week_start_str}"
                AND updated <= "{current_week_end_str}"
                ORDER BY updated DESC
                """
                
                issues = self.jira_client.search_issues(
                    jql_current, 
                    maxResults=100,
                    fields='summary,description,status,assignee,priority,updated,created'
                )
                
                board_data = {
                    "issues": [],
                    "stats": {
                        "total": 0,
                        "completed": 0,
                        "in_progress": 0,
                        "blocked": 0,
                        "to_do": 0
                    },
                    "previous_week_completed": 0,
                    "status_groups": {
                        "to_do": [],
                        "in_progress": [],
                        "completed_this_week": [],
                        "blocked": []
                    }
                }

                issue_map: Dict[str, Dict[str, Any]] = {}

                def _serialize_issue(issue_obj):
                    description = ""
                    if hasattr(issue_obj.fields, 'description') and issue_obj.fields.description:
                        description = issue_obj.fields.description
                    elif isinstance(issue_obj.fields.description, str):
                        description = issue_obj.fields.description

                    return {
                        "key": issue_obj.key,
                        "summary": issue_obj.fields.summary,
                        "description": description,
                        "status": issue_obj.fields.status.name,
                        "assignee": issue_obj.fields.assignee.displayName if issue_obj.fields.assignee else "Unassigned",
                        "priority": issue_obj.fields.priority.name if issue_obj.fields.priority else "None",
                        "updated": issue_obj.fields.updated,
                        "created": issue_obj.fields.created
                    }
                
                # Get previous week's completed issues for velocity comparison
                previous_week_start_str = previous_week_start.strftime('%Y-%m-%d')
                previous_week_end_str = previous_week_end.strftime('%Y-%m-%d')
                
                jql_previous = f"""
                project = {board_key}
                AND status in (Done, Completed, Closed, Resolved)
                AND status CHANGED TO (Done, Completed, Closed, Resolved) DURING ("{previous_week_start_str}", "{previous_week_end_str}")
                """
                
                try:
                    previous_week_issues = self.jira_client.search_issues(
                        jql_previous,
                        maxResults=200,
                        fields='status'
                    )
                    board_data["previous_week_completed"] = len(previous_week_issues)
                    logger.info(f"Previous week completed issues for {board_key}: {len(previous_week_issues)}")
                except Exception as e:
                    logger.warning(f"Could not fetch previous week data for {board_key}: {e}")
                    # Fallback: try a simpler query
                    try:
                        jql_previous_simple = f"""
                        project = {board_key}
                        AND status in (Done, Completed, Closed, Resolved)
                        AND updated >= "{previous_week_start_str}"
                        AND updated <= "{previous_week_end_str}"
                        """
                        previous_week_issues = self.jira_client.search_issues(
                            jql_previous_simple,
                            maxResults=200,
                            fields='status'
                        )
                        board_data["previous_week_completed"] = len(previous_week_issues)
                        logger.info(f"Previous week completed (fallback) for {board_key}: {len(previous_week_issues)}")
                    except Exception as e2:
                        logger.warning(f"Fallback query also failed for {board_key}: {e2}")
                        board_data["previous_week_completed"] = 0
                
                for issue in issues:
                    issue_map[issue.key] = _serialize_issue(issue)

                # Fetch additional status-based issue groups
                status_queries = {
                    "to_do": f"""
                    project = {board_key}
                    AND statusCategory = "To Do"
                    """,
                    "in_progress": f"""
                    project = {board_key}
                    AND statusCategory = "In Progress"
                    """,
                    "completed_this_week": f"""
                    project = {board_key}
                    AND statusCategory = "Done"
                    AND status CHANGED TO (Done, Completed, Closed, Resolved)
                        DURING ("{current_week_start_str}", "{current_week_end_str}")
                    """
                }

                status_keys: Dict[str, set] = {
                    "to_do": set(),
                    "in_progress": set(),
                    "completed_this_week": set(),
                    "blocked": set()
                }

                for status_label, jql_query in status_queries.items():
                    try:
                        status_issues = self.jira_client.search_issues(
                            jql_query,
                            maxResults=200,
                            fields='summary,description,status,assignee,priority,updated,created'
                        )
                        for issue in status_issues:
                            issue_map.setdefault(issue.key, _serialize_issue(issue))
                            status_keys[status_label].add(issue.key)
                        logger.info(f"{board_key} - Retrieved {len(status_issues)} issues for status group '{status_label}'")
                    except Exception as status_error:
                        logger.warning(f"Could not fetch '{status_label}' issues for {board_key}: {status_error}")

                # Identify blocked issues from the collected set
                for key, issue_data in issue_map.items():
                    if 'blocked' in issue_data.get('status', '').lower() or 'impediment' in issue_data.get('status', '').lower():
                        status_keys["blocked"].add(key)

                # Populate status groups with serialized issue data
                for status_label in board_data["status_groups"].keys():
                    board_data["status_groups"][status_label] = [
                        issue_map[key] for key in status_keys.get(status_label, set())
                    ]

                # Finalize issues list and stats
                board_data["issues"] = list(issue_map.values())
                board_data["stats"]["total"] = len(issue_map)
                board_data["stats"]["completed"] = len(status_keys["completed_this_week"])
                board_data["stats"]["in_progress"] = len(status_keys["in_progress"])
                board_data["stats"]["to_do"] = len(status_keys["to_do"])
                board_data["stats"]["blocked"] = len(status_keys["blocked"])

                jira_data["boards"][board_key] = board_data
                jira_data["summary"]["total_issues"] += board_data["stats"]["total"]
                jira_data["summary"]["completed_issues"] += board_data["stats"]["completed"]
                jira_data["summary"]["in_progress_issues"] += board_data["stats"]["in_progress"]
                jira_data["summary"]["blocked_issues"] += board_data["stats"]["blocked"]
                jira_data["summary"]["to_do_issues"] += board_data["stats"]["to_do"]
                
                logger.info(
                    f"Collected {len(board_data['issues'])} total issues from {board_key} "
                    f"(current week completed: {board_data['stats']['completed']}, "
                    f"to-do: {board_data['stats']['to_do']}, in progress: {board_data['stats']['in_progress']}, "
                    f"previous week completed: {board_data['previous_week_completed']})"
                )
        
        except Exception as e:
            logger.error(f"Error collecting Jira data: {e}")
            raise
        
        return jira_data
    
    def _get_previous_monday_date(self) -> str:
        """
        Get the date of last Monday (previous week) in MM/DD/YY format
        
        Returns:
            Date string in MM/DD/YY format (e.g., "10/27/25")
        """
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        # Find last Monday (previous week's Monday)
        days_since_monday = today.weekday()  # 0=Monday, 1=Tuesday, etc.
        
        if days_since_monday == 0:  # Today is Monday
            # Go back to previous Monday (7 days ago)
            target_monday = today - timedelta(days=7)
        else:
            # Go back to last Monday (this week's Monday - 7 days)
            this_monday = today - timedelta(days=days_since_monday)
            target_monday = this_monday - timedelta(days=7)
        
        # Format as MM/DD/YY (with leading zeros removed for month/day)
        formatted_date = target_monday.strftime("%-m/%-d/%y")
        
        logger.info(f"Target date for weekly tabs: {formatted_date} (last Monday)")
        return formatted_date

    def _find_date_based_tab(self, spreadsheet, target_date: str) -> Optional[str]:
        """
        Find a tab that matches the target date
        
        Args:
            spreadsheet: Google Sheets spreadsheet object
            target_date: Target date in MM/DD/YY format
            
        Returns:
            Tab name if found, None otherwise
        """
        try:
            all_worksheets = spreadsheet.worksheets()
            
            # Try exact match first (including trimming whitespace)
            for worksheet in all_worksheets:
                tab_name = worksheet.title.strip()
                if tab_name == target_date:
                    logger.info(f"Found exact date match: '{tab_name}'")
                    return worksheet.title  # Return original title to preserve formatting
            
            # Try variations with different formatting
            # Parse target date to try different formats
            try:
                target_dt = datetime.strptime(target_date, "%m/%d/%y")
                
                # Generate alternative formats to look for
                alt_formats = [
                    target_dt.strftime("%m/%d/%Y"),    # 10/27/2025
                    target_dt.strftime("%m-%d-%y"),    # 10-27-25
                    target_dt.strftime("%m-%d-%Y"),    # 10-27-2025
                    target_dt.strftime("%-m/%-d/%y"),  # 10/27/25 (no leading zeros)
                    target_dt.strftime("%m/%d/%y"),    # 10/27/25 (with leading zeros)
                ]
                
                for worksheet in all_worksheets:
                    tab_name = worksheet.title.strip()
                    if tab_name in alt_formats:
                        logger.info(f"Found date match with alternative format: '{tab_name}' (target: {target_date})")
                        return worksheet.title  # Return original title
                
                # Try fuzzy matching - look for tabs that contain the date
                for worksheet in all_worksheets:
                    tab_name = worksheet.title.strip()
                    # Remove common prefixes/suffixes and check if date is contained
                    clean_tab = re.sub(r'^(week|weekly|report|data)\s*[-_]?\s*', '', tab_name.lower())
                    clean_tab = re.sub(r'\s*[-_]?\s*(week|weekly|report|data)$', '', clean_tab)
                    
                    if target_date in clean_tab or any(alt_format in clean_tab for alt_format in alt_formats):
                        logger.info(f"Found fuzzy date match: '{tab_name}' (contains target date)")
                        return tab_name
                        
            except ValueError:
                logger.error(f"Could not parse target date: {target_date}")
            
            logger.warning(f"No tab found matching date: {target_date}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding date-based tab: {e}")
            return None

    def _detect_relevant_tabs(self, spreadsheet) -> List[str]:
        """
        Detect relevant tabs based on date (previous Monday) for weekly tracker sheets
        
        Args:
            spreadsheet: Google Sheets spreadsheet object
            
        Returns:
            List of relevant tab names (should be one tab with the target date)
        """
        try:
            # Get the target date (previous Monday)
            target_date = self._get_previous_monday_date()
            
            # Try to find the tab with this date
            date_tab = self._find_date_based_tab(spreadsheet, target_date)
            
            if date_tab:
                logger.info(f"Found weekly tracker tab: '{date_tab}'")
                return [date_tab]
            else:
                # No matching date tab found - log warning but continue
                logger.warning(f"⚠️ MISSING DATE TAB: Could not find tab for date '{target_date}' in spreadsheet '{spreadsheet.title}'")
                
                # List available tabs for debugging
                all_tabs = [ws.title for ws in spreadsheet.worksheets()]
                logger.warning(f"Available tabs in '{spreadsheet.title}': {all_tabs}")
                
                # Return empty list but don't fail - let the report generation continue
                return []
            
        except Exception as e:
            logger.error(f"Error detecting date-based tabs: {e}")
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
