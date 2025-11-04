"""
Configuration settings for SmarterProducts Weekly Automation
"""
import os
import json
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, ConfigDict


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
    jira_boards_raw: Optional[str] = Field(default=None, validation_alias="JIRA_BOARDS")
    
    @property
    def jira_boards(self) -> List[str]:
        """Parse JIRA_BOARDS from comma-separated string"""
        if not self.jira_boards_raw:
            return []
        return [board.strip() for board in self.jira_boards_raw.split(',') if board.strip()]
    
    # =============================================================================
    # GOOGLE SERVICES SETTINGS
    # =============================================================================
    google_credentials: dict = Field(env="GOOGLE_CREDENTIALS")
    google_drive_folder_id: str = Field(env="GOOGLE_DRIVE_FOLDER_ID")
    google_sheets_ids_raw: Optional[str] = Field(default=None, validation_alias="GOOGLE_SHEETS_IDS")
    google_sheets_tab_strategy: str = Field(default="auto", env="GOOGLE_SHEETS_TAB_STRATEGY")
    google_sheets_tabs_raw: Optional[str] = Field(default=None, validation_alias="GOOGLE_SHEETS_TABS")
    
    @validator('google_credentials', pre=True)
    def parse_google_credentials(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @property
    def google_sheets_ids(self) -> List[str]:
        """Parse GOOGLE_SHEETS_IDS from comma-separated string"""
        if not self.google_sheets_ids_raw:
            return []
        return [sheet_id.strip() for sheet_id in self.google_sheets_ids_raw.split(',') if sheet_id.strip()]
    
    @property
    def google_sheets_tabs(self) -> List[str]:
        """Parse GOOGLE_SHEETS_TABS from comma-separated string"""
        if not self.google_sheets_tabs_raw:
            return []
        return [tab.strip() for tab in self.google_sheets_tabs_raw.split(',') if tab.strip()]
    
    # =============================================================================
    # OPENAI SETTINGS
    # =============================================================================
    openai_api_key: str = Field(env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    
    # =============================================================================
    # EMAIL SETTINGS
    # =============================================================================
    # SMTP Configuration (for sending emails directly from your account)
    smtp_server: str = Field(default="smtp.gmail.com", env="SMTP_SERVER")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")  # Use App Password for Gmail
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")
    
    # Legacy SendGrid (not used anymore, but kept for backward compatibility)
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    
    preview_email_recipients_raw: Optional[str] = Field(default=None, validation_alias="PREVIEW_EMAIL_RECIPIENTS")
    final_email_recipients_raw: Optional[str] = Field(default=None, validation_alias="FINAL_EMAIL_RECIPIENTS")
    from_email: str = Field(env="FROM_EMAIL")
    from_name: str = Field(default="Weekly Reports System", env="FROM_NAME")
    
    @property
    def preview_email_recipients(self) -> List[str]:
        """Parse PREVIEW_EMAIL_RECIPIENTS from comma-separated string"""
        if not self.preview_email_recipients_raw:
            return []
        return [email.strip() for email in self.preview_email_recipients_raw.split(',') if email.strip()]
    
    @property
    def final_email_recipients(self) -> List[str]:
        """Parse FINAL_EMAIL_RECIPIENTS from comma-separated string"""
        if not self.final_email_recipients_raw:
            return []
        return [email.strip() for email in self.final_email_recipients_raw.split(',') if email.strip()]
    
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
    
    model_config = SettingsConfigDict(
        env_file=[".env", "config.env", ".env.local"],
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )


# Global settings instance
settings = Settings()
