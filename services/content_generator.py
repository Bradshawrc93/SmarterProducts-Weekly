"""
Content Generation Service - OpenAI Integration
"""
import logging
from typing import Dict, Any, Optional
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
        """Format collected data for use in prompts"""
        try:
            # Calculate week dates
            today = datetime.now()
            week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
            week_end = (today + timedelta(days=6-today.weekday())).strftime('%Y-%m-%d')
            
            # Format Jira data
            jira_summary = []
            if data.get("jira", {}).get("boards"):
                for board_key, board_data in data["jira"]["boards"].items():
                    stats = board_data.get("stats", {})
                    jira_summary.append(f"""
Board: {board_key}
- Total Issues: {stats.get('total', 0)}
- Completed: {stats.get('completed', 0)}
- In Progress: {stats.get('in_progress', 0)}
- Blocked: {stats.get('blocked', 0)}

Recent Issues:""")
                    
                    # Add recent issues (limit to 5 per board)
                    for issue in board_data.get("issues", [])[:5]:
                        jira_summary.append(f"  • {issue['key']}: {issue['summary']} ({issue['status']})")
            
            jira_formatted = '\n'.join(jira_summary) if jira_summary else "No Jira data available"
            
            # Format Sheets data (now handling multiple sheets)
            sheets_summary = []
            if data.get("sheets", {}).get("sheets"):
                for sheet_id, sheet_data in data["sheets"]["sheets"].items():
                    sheet_title = sheet_data.get("title", "Unknown Sheet")
                    sheets_summary.append(f"""
Spreadsheet: {sheet_title}
- Total Tabs: {sheet_data.get('tab_count', 0)}""")
                    
                    # Add data from each tab
                    for tab_name, tab_data in sheet_data.get("tabs", {}).items():
                        sheets_summary.append(f"""
  Tab: {tab_name}
  - Rows: {tab_data.get('row_count', 0)}
  - Columns: {tab_data.get('column_count', 0)}
  - Headers: {', '.join(tab_data.get('headers', [])[:5])}""")
                        
                        # Add sample data (first few rows)
                        if tab_data.get("sample_data"):
                            sheets_summary.append("  Sample Data:")
                            for i, row in enumerate(tab_data["sample_data"][:2]):
                                sheets_summary.append(f"    Row {i+1}: {', '.join(str(cell)[:15] for cell in row[:3])}")
            
            sheets_formatted = '\n'.join(sheets_summary) if sheets_summary else "No Google Sheets data available"
            
            return {
                "jira_data": jira_formatted,
                "sheets_data": sheets_formatted,
                "week_start": week_start,
                "week_end": week_end
            }
            
        except Exception as e:
            logger.error(f"Error formatting data for prompt: {e}")
            raise
    
    def generate_summary(self, data: Dict[str, Any], custom_prompt: Optional[str] = None) -> str:
        """
        Generate weekly summary using OpenAI
        
        Args:
            data: Collected data from Jira and Sheets
            custom_prompt: Optional custom prompt override
            
        Returns:
            Generated summary content
        """
        logger.info("Generating weekly summary with OpenAI")
        
        try:
            # Load prompt template or use custom
            if custom_prompt:
                prompt_template = custom_prompt
            else:
                prompt_template = self._load_prompt_template("summary_prompt")
            
            # Format data for prompt
            formatted_data = self._format_data_for_prompt(data)
            
            # Fill in the template
            prompt = prompt_template.format(**formatted_data)
            
            # Generate content with OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional business analyst creating weekly reports."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            logger.info("Weekly summary generated successfully")
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
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
        Generate complete report with summary and insights
        
        Args:
            data: Collected data from all sources
            
        Returns:
            Dictionary with generated content sections
        """
        logger.info("Generating complete report")
        
        try:
            summary = self.generate_summary(data)
            insights = self.generate_insights(data)
            
            # Get current week info
            today = datetime.now()
            week_start = (today - timedelta(days=today.weekday())).strftime('%B %d, %Y')
            week_end = (today + timedelta(days=6-today.weekday())).strftime('%B %d, %Y')
            
            report_content = {
                "title": f"Weekly Report: {week_start} - {week_end}",
                "summary": summary,
                "insights": insights,
                "generation_timestamp": datetime.now().isoformat()
            }
            
            logger.info("Complete report generation finished")
            return report_content
            
        except Exception as e:
            logger.error(f"Error generating complete report: {e}")
            raise
