"""
Configuration settings for SmarterProducts Weekly Automation
"""
import os
import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # =============================================================================
    # APPLICATION SETTINGS
    # =============================================================================
    environment: str = Field(default="development", env="ENVIRONMENT")
    secret_key: str = Field(env="SECRET_KEY")
    timezone: str = Field(default="America/New_York", env="TIMEZONE")
    
    # =============================================================================
    # JIRA SETTINGS
    # =============================================================================
    jira_base_url: str = Field(env="JIRA_BASE_URL")
    jira_api_token: str = Field(env="JIRA_API_TOKEN")
    jira_email: str = Field(env="JIRA_EMAIL")
    jira_boards: List[str] = Field(env="JIRA_BOARDS")
    
    @validator('jira_boards', pre=True)
    def parse_jira_boards(cls, v):
        if isinstance(v, str):
            return [board.strip() for board in v.split(',')]
        return v
    
    # =============================================================================
    # GOOGLE SERVICES SETTINGS
    # =============================================================================
    google_credentials: dict = Field(env="GOOGLE_CREDENTIALS")
    google_drive_folder_id: str = Field(env="GOOGLE_DRIVE_FOLDER_ID")
    google_sheets_ids: List[str] = Field(env="GOOGLE_SHEETS_IDS")
    google_sheets_tab_strategy: str = Field(default="auto", env="GOOGLE_SHEETS_TAB_STRATEGY")
    google_sheets_tabs: List[str] = Field(default=[], env="GOOGLE_SHEETS_TABS")
    
    @validator('google_credentials', pre=True)
    def parse_google_credentials(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @validator('google_sheets_ids', pre=True)
    def parse_google_sheets_ids(cls, v):
        if isinstance(v, str):
            return [sheet_id.strip() for sheet_id in v.split(',')]
        return v
    
    @validator('google_sheets_tabs', pre=True)
    def parse_google_sheets_tabs(cls, v):
        if isinstance(v, str):
            return [tab.strip() for tab in v.split(',') if tab.strip()]
        return v
    
    # =============================================================================
    # OPENAI SETTINGS
    # =============================================================================
    openai_api_key: str = Field(env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    
    # =============================================================================
    # EMAIL SETTINGS
    # =============================================================================
    sendgrid_api_key: str = Field(env="SENDGRID_API_KEY")
    preview_email_recipients: List[str] = Field(env="PREVIEW_EMAIL_RECIPIENTS")
    final_email_recipients: List[str] = Field(env="FINAL_EMAIL_RECIPIENTS")
    from_email: str = Field(env="FROM_EMAIL")
    from_name: str = Field(default="Weekly Reports System", env="FROM_NAME")
    
    @validator('preview_email_recipients', pre=True)
    def parse_preview_recipients(cls, v):
        if isinstance(v, str):
            return [email.strip() for email in v.split(',')]
        return v
    
    @validator('final_email_recipients', pre=True)
    def parse_final_recipients(cls, v):
        if isinstance(v, str):
            return [email.strip() for email in v.split(',')]
        return v
    
    # =============================================================================
    # DATABASE SETTINGS
    # =============================================================================
    database_url: str = Field(env="DATABASE_URL")
    
    # =============================================================================
    # MONITORING SETTINGS
    # =============================================================================
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # =============================================================================
    # OAUTH SETTINGS (for document creation)
    # =============================================================================
    use_oauth_for_docs: bool = Field(default=True, env="USE_OAUTH_FOR_DOCS")
    oauth_credentials_file: str = Field(default="oauth_credentials.json", env="OAUTH_CREDENTIALS_FILE")
    oauth_token_file: str = Field(default="token.json", env="OAUTH_TOKEN_FILE")
    
    # =============================================================================
    # SCHEDULING SETTINGS
    # =============================================================================
    preview_schedule: int = Field(default=22, env="PREVIEW_SCHEDULE")  # 10 PM
    final_schedule: int = Field(default=8, env="FINAL_SCHEDULE")      # 8 AM
    
    class Config:
        # Try multiple env file locations
        env_file = [".env", "config.env", ".env.local"]
        case_sensitive = False


# Global settings instance
settings = Settings()
