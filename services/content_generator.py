"""
Content Generation Service - OpenAI Integration
"""
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
import openai
from config.settings import settings

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Generates content using OpenAI API"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    def _load_prompt_template(self, template_name: str) -> str:
        """Load prompt template from file"""
        try:
            template_path = f"config/prompts/{template_name}.txt"
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Remove comment lines that start with #
            lines = content.split('\n')
            template_lines = [line for line in lines if not line.strip().startswith('#')]
            return '\n'.join(template_lines).strip()
            
        except FileNotFoundError:
            logger.error(f"Prompt template not found: {template_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            raise
    
    def _format_data_for_prompt(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Format collected data into structured format for the new report template"""
        try:
            # Calculate proper date ranges
            today = datetime.now()
            
            # Last Monday (data collection period start)
            days_since_monday = today.weekday()
            if days_since_monday == 0:  # Today is Monday
                # Go back to previous Monday (7 days ago)
                target_monday = today - timedelta(days=7)
            else:
                # Go back to last Monday (this week's Monday - 7 days)
                this_monday = today - timedelta(days=days_since_monday)
                target_monday = this_monday - timedelta(days=7)
            
            # This Tuesday (data collection period end)
            this_tuesday = target_monday + timedelta(days=8)  # Last Monday + 8 days = this Tuesday
            
            # This Wednesday (report date)
            days_until_wednesday = (2 - today.weekday()) % 7
            if days_until_wednesday == 0 and today.weekday() > 2:
                days_until_wednesday = 7
            this_wednesday = today + timedelta(days=days_until_wednesday)
            
            week_start = target_monday.strftime('%-m/%-d/%y')
            week_end = this_tuesday.strftime('%-m/%-d/%y') 
            report_date = this_wednesday.strftime('%-m/%-d/%y')
            
            # Create structured data for the new report format
            structured_data = {
                "reporting_period": {
                    "start_date": week_start,
                    "end_date": week_end,
                    "report_date": report_date
                },
                "teams": []
            }
            
            # Map Jira boards to teams and combine with Google Sheets data
            jira_boards = data.get("jira", {}).get("boards", {})
            sheets_data = data.get("sheets", {}).get("sheets", {})
            
            # Create a mapping to track which sheets have been matched to teams
            matched_sheets = set()
            
            # First pass: Create teams from Jira boards and try to match sheets
            team_counter = 1
            for board_key, board_data in jira_boards.items():
                team_info = {
                    "team_number": team_counter,
                    "team_name": board_key,
                    "google_sheet_data": {},
                    "jira_data": {}
                }
                
                # Extract Jira metrics and issue details
                stats = board_data.get("stats", {})
                issues = board_data.get("issues", [])
                
                # Filter issues by status categories
                completed_issues = [issue for issue in issues 
                                   if any(word in issue.get('status', '').lower() 
                                         for word in ['done', 'completed', 'closed', 'resolved'])]
                in_progress_issues = [issue for issue in issues 
                                     if any(word in issue.get('status', '').lower() 
                                           for word in ['progress', 'development', 'review'])]
                blocked_issues = [issue for issue in issues 
                                if any(word in issue.get('status', '').lower() 
                                      for word in ['blocked', 'impediment'])]
                new_issues = [issue for issue in issues 
                           if self._is_issue_created_in_period(issue, target_monday, this_tuesday)]
                
                team_info["jira_data"] = {
                    "issues_completed": stats.get('completed', 0),
                    "issues_in_progress": stats.get('in_progress', 0),
                    "new_issues_created": len(new_issues),
                    "total_issues": stats.get('total', 0),
                    "blocked_issues": stats.get('blocked', 0),
                    # Include actual issue details for context (limit to top issues to manage token usage)
                    "completed_issues_detail": [
                        {
                            "key": issue.get('key'),
                            "summary": issue.get('summary'),
                            "description": issue.get('description', '')[:200] if issue.get('description') else '',  # Limit description length
                            "status": issue.get('status'),
                            "assignee": issue.get('assignee')
                        }
                        for issue in completed_issues[:10]  # Limit to top 10 to avoid token bloat
                    ],
                    "in_progress_issues_detail": [
                        {
                            "key": issue.get('key'),
                            "summary": issue.get('summary'),
                            "description": issue.get('description', '')[:200] if issue.get('description') else '',  # Limit description length
                            "status": issue.get('status'),
                            "assignee": issue.get('assignee'),
                            "priority": issue.get('priority')
                        }
                        for issue in in_progress_issues[:10]  # Limit to top 10
                    ],
                    "blocked_issues_detail": [
                        {
                            "key": issue.get('key'),
                            "summary": issue.get('summary'),
                            "description": issue.get('description', '')[:200] if issue.get('description') else '',  # Limit description length
                            "status": issue.get('status'),
                            "assignee": issue.get('assignee')
                        }
                        for issue in blocked_issues[:10]  # Limit to top 10
                    ],
                    "new_issues_detail": [
                        {
                            "key": issue.get('key'),
                            "summary": issue.get('summary'),
                            "description": issue.get('description', '')[:200] if issue.get('description') else '',  # Limit description length
                            "status": issue.get('status'),
                            "assignee": issue.get('assignee')
                        }
                        for issue in new_issues[:10]  # Limit to top 10
                    ]
                }
                
                # Try to find matching Google Sheets data
                team_sheet_data, matched_sheet_id, extracted_team_name = self._find_team_sheet_data(board_key, sheets_data)
                if team_sheet_data and matched_sheet_id and extracted_team_name:
                    team_info["google_sheet_data"] = team_sheet_data
                    team_info["team_name"] = extracted_team_name  # Use team name from sheet instead of board key
                    matched_sheets.add(matched_sheet_id)
                else:
                    # If no matching sheet found, try to create a readable name from board key
                    # Map common board keys to team names
                    board_key_mapping = {
                        "SMR": "SmarterPosting",
                        "SMRTRR": "SmarterAR", 
                        "SMRTRTH": "SmarterAuth",
                        "SMRTRCDNG": "SmarterCoding"
                    }
                    team_info["team_name"] = board_key_mapping.get(board_key, board_key)
                
                structured_data["teams"].append(team_info)
                team_counter += 1
            
            # Second pass: Ensure ALL sheets are represented as teams
            # Add any sheets that didn't match Jira boards as separate teams
            for sheet_id, sheet_data in sheets_data.items():
                # Skip if this sheet was already matched to a Jira board
                if sheet_id in matched_sheets:
                    continue
                
                sheet_title = sheet_data.get("title", "Unknown Sheet")
                extracted_team_name = self._extract_team_name_from_sheet_title(sheet_title)
                
                # Check if we already have a team with this exact team name
                existing_team = next(
                    (team for team in structured_data["teams"] 
                     if team["team_name"].lower() == extracted_team_name.lower()),
                    None
                )
                
                if existing_team:
                    # Add sheet data to existing team if it doesn't have any
                    if not existing_team.get("google_sheet_data"):
                        existing_team["google_sheet_data"] = self._extract_sheet_team_data(sheet_data)
                else:
                    # Add as a new separate team with extracted team name
                    team_info = {
                        "team_number": team_counter,
                        "team_name": extracted_team_name,
                        "google_sheet_data": self._extract_sheet_team_data(sheet_data),
                        "jira_data": {
                            "issues_completed": 0,
                            "issues_in_progress": 0,
                            "new_issues_created": 0,
                            "total_issues": 0,
                            "blocked_issues": 0
                        }
                    }
                    structured_data["teams"].append(team_info)
                    team_counter += 1
            
            # Sort teams in desired order
            team_order = ["SmarterAR", "SmarterCoding", "SmarterAuth", "SmarterPosting"]
            structured_data["teams"] = self._sort_teams(structured_data["teams"], team_order)
            
            # Renumber teams based on sorted order
            for i, team in enumerate(structured_data["teams"], 1):
                team["team_number"] = i
            
            # Convert to JSON string for the prompt
            import json
            structured_json = json.dumps(structured_data, indent=2)
            
            return {
                "structured_data": structured_json,
                "week_start": week_start,
                "week_end": week_end,
                "report_date": report_date
            }
            
        except Exception as e:
            logger.error(f"Error formatting data for prompt: {e}")
            raise

    def _sort_teams(self, teams: List[Dict], desired_order: List[str]) -> List[Dict]:
        """
        Sort teams according to a desired order
        
        Args:
            teams: List of team dictionaries
            desired_order: List of team names in desired order
            
        Returns:
            Sorted list of teams
        """
        # Create a mapping of team name to priority (lower number = higher priority)
        order_map = {team_name: index for index, team_name in enumerate(desired_order)}
        
        def get_sort_key(team):
            team_name = team.get("team_name", "")
            # Get priority from order_map, or use a high number (999) for teams not in the list
            priority = order_map.get(team_name, 999)
            # If priority is same, sort by team number to maintain consistency
            return (priority, team.get("team_number", 0))
        
        return sorted(teams, key=get_sort_key)
    
    def _is_issue_created_in_period(self, issue: Dict, start_date: datetime, end_date: datetime) -> bool:
        """Check if an issue was created within the reporting period"""
        try:
            from dateutil import parser
            created_date = parser.parse(issue.get('created', ''))
            return start_date <= created_date <= end_date
        except:
            return False

    def _extract_team_name_from_sheet_title(self, sheet_title: str) -> str:
        """
        Extract a clean team name from a Google Sheet title
        
        Examples:
        - "SmarterPosting Weekly Tracker Template" -> "SmarterPosting"
        - "SmarterAR Weekly Tracker Template" -> "SmarterAR"
        - "SmarterCoding Weekly Tracker Template" -> "SmarterCoding"
        - "SmarterAuth Weekly Tracker" -> "SmarterAuth"
        
        Returns:
            Clean team name extracted from sheet title
        """
        import re
        # Remove common suffixes like "Weekly Tracker", "Template", etc.
        # Look for the main product name (typically starts with "Smarter")
        match = re.match(r'^(Smarter[A-Za-z]+)', sheet_title)
        if match:
            return match.group(1)
        # If no "Smarter" prefix, try to get the first word
        words = sheet_title.split()
        if words:
            return words[0]
        return sheet_title
    
    def _find_team_sheet_data(self, jira_board_key: str, sheets_data: Dict) -> Tuple[Dict, Optional[str], Optional[str]]:
        """
        Find Google Sheets data that matches a Jira board key
        
        Returns:
            Tuple of (sheet_data_dict, matched_sheet_id, team_name) or ({}, None, None) if no match
        """
        for sheet_id, sheet_data in sheets_data.items():
            sheet_title = sheet_data.get("title", "")
            # Simple matching - look for board key in sheet title or vice versa
            if (jira_board_key.lower() in sheet_title.lower() or 
                sheet_title.lower() in jira_board_key.lower() or
                any(jira_board_key.lower() in tab_name.lower() for tab_name in sheet_data.get("tabs", {}).keys())):
                # Extract team name from sheet title
                team_name = self._extract_team_name_from_sheet_title(sheet_title)
                return (self._extract_sheet_team_data(sheet_data), sheet_id, team_name)
        return ({}, None, None)

    def _extract_sheet_team_data(self, sheet_data: Dict) -> Dict:
        """Extract team-specific data from a Google Sheet"""
        team_data = {}
        
        # Look through all tabs for team data
        for tab_name, tab_data in sheet_data.get("tabs", {}).items():
            headers = tab_data.get("headers", [])
            rows = tab_data.get("rows", [])
            
            if not rows:
                continue
            
            # Map common column names to our expected fields
            column_mapping = {
                "general update": "general_update",
                "general_update": "general_update", 
                "update": "general_update",
                "key wins": "key_wins",
                "key_wins": "key_wins",
                "wins": "key_wins",
                "next week focus": "next_week_focus",
                "next_week_focus": "next_week_focus",
                "focus": "next_week_focus",
                "next week": "next_week_focus",
                "risk": "risk",
                "risks": "risk",
                "blockers": "blockers",
                "blocker": "blockers",
                "general sentiment": "general_sentiment",
                "general_sentiment": "general_sentiment",
                "sentiment": "general_sentiment"
            }
            
            # Create header index mapping
            header_indices = {}
            for i, header in enumerate(headers):
                clean_header = header.lower().strip()
                if clean_header in column_mapping:
                    header_indices[column_mapping[clean_header]] = i
            
            # Extract data from first row (assuming single team per sheet)
            if rows and header_indices:
                first_row = rows[0]
                for field, index in header_indices.items():
                    if index < len(first_row):
                        team_data[field] = first_row[index]
        
        return team_data
    
    def generate_summary(self, data: Dict[str, Any], custom_prompt: Optional[str] = None) -> str:
        """
        Generate complete Product Team Progress Report using OpenAI
        
        Args:
            data: Collected data from Jira and Sheets
            custom_prompt: Optional custom prompt override
            
        Returns:
            Generated complete report content
        """
        logger.info("Generating Product Team Progress Report with OpenAI")
        
        try:
            # Load prompt template or use custom
            if custom_prompt:
                prompt_template = custom_prompt
            else:
                prompt_template = self._load_prompt_template("summary_prompt")
            
            # Format data for prompt (now returns structured JSON)
            formatted_data = self._format_data_for_prompt(data)
            
            # Fill in the template
            prompt = prompt_template.format(**formatted_data)
            
            # Generate content with OpenAI (increased token limit for full report)
            # For reasoning models, we need much higher token limits since reasoning tokens are separate
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a senior product operations analyst creating executive-level weekly reports."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=8000  # Increased significantly for reasoning models
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            logger.info(f"Product Team Progress Report generated successfully (length: {len(generated_content)} chars)")
            if len(generated_content) == 0:
                logger.warning("⚠️ OpenAI returned empty content! Full response: %s", response)
                logger.warning("Response choices: %s", [c.message.content[:200] if c.message.content else "None" for c in response.choices])
            
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise
    
    def generate_insights(self, data: Dict[str, Any], custom_prompt: Optional[str] = None) -> str:
        """
        Generate strategic insights using OpenAI
        
        Args:
            data: Collected data from Jira and Sheets
            custom_prompt: Optional custom prompt override
            
        Returns:
            Generated insights content
        """
        logger.info("Generating strategic insights with OpenAI")
        
        try:
            # Load prompt template or use custom
            if custom_prompt:
                prompt_template = custom_prompt
            else:
                prompt_template = self._load_prompt_template("insights_prompt")
            
            # Format data for prompt
            formatted_data = self._format_data_for_prompt(data)
            
            # Fill in the template
            prompt = prompt_template.format(**formatted_data)
            
            # Generate content with OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a senior product strategist providing strategic insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            logger.info("Strategic insights generated successfully")
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            raise
    
    def customize_tone(self, content: str, style_guide: str) -> str:
        """
        Customize the tone of generated content
        
        Args:
            content: Original content to modify
            style_guide: Style guidelines for customization
            
        Returns:
            Content with customized tone
        """
        logger.info("Customizing content tone")
        
        try:
            prompt = f"""
Please revise the following content to match this style guide:

STYLE GUIDE:
{style_guide}

ORIGINAL CONTENT:
{content}

Please provide the revised content that maintains all the original information but adjusts the tone and style according to the guidelines.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert editor specializing in business communications."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.5
            )
            
            customized_content = response.choices[0].message.content.strip()
            
            logger.info("Content tone customization completed")
            return customized_content
            
        except Exception as e:
            logger.error(f"Error customizing tone: {e}")
            raise
    
    def generate_complete_report(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate complete Product Team Progress Report
        
        Args:
            data: Collected data from all sources
            
        Returns:
            Dictionary with generated report content
        """
        logger.info("Generating complete Product Team Progress Report")
        
        try:
            # Generate the complete report using the new structured approach
            complete_report = self.generate_summary(data)  # This now generates the full report
            
            # Calculate proper dates for the title
            today = datetime.now()
            days_since_monday = today.weekday()
            if days_since_monday == 0:  # Today is Monday
                previous_monday = today - timedelta(days=7)
            else:
                previous_monday = today - timedelta(days=days_since_monday + 7)
            
            this_wednesday = previous_monday + timedelta(days=9)
            report_date = this_wednesday.strftime('%-m/%-d/%y')
            
            report_content = {
                "title": f"Product Team Progress Report {report_date}",
                "summary": complete_report,  # The complete report is now in summary
                "insights": "",  # No longer used - everything is in the main report
                "generation_timestamp": datetime.now().isoformat()
            }
            
            logger.info("Complete Product Team Progress Report generation finished")
            return report_content
            
        except Exception as e:
            logger.error(f"Error generating complete report: {e}")
            raise
