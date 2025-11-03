"""
Database models for state management
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSON
from config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class ReportExecution(Base):
    """Track report execution history and state"""
    __tablename__ = 'report_executions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week_identifier = Column(String(20), nullable=False)  # e.g., "2024-W45"
    job_type = Column(String(20), nullable=False)  # "preview" or "final"
    status = Column(String(20), nullable=False)  # "running", "completed", "failed"
    google_doc_id = Column(String(100), nullable=True)
    google_doc_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StateManager:
    """Manages application state using PostgreSQL database"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.db_available = False
        try:
            self.engine = create_engine(settings.database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self._create_tables()
            self.db_available = True
        except Exception as e:
            logger.warning(f"Database not available: {e}")
            logger.warning("Continuing without database (state tracking will be disabled)")
            self.db_available = False
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def _get_week_identifier(self) -> str:
        """Get current week identifier (e.g., '2024-W45')"""
        now = datetime.now()
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"
    
    def save_doc_id(self, doc_id: str, doc_url: str, job_type: str = "preview") -> bool:
        """
        Save Google Doc ID and URL for the current week
        
        Args:
            doc_id: Google Doc ID
            doc_url: Google Doc URL
            job_type: Type of job ("preview" or "final")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_available:
            logger.debug("Database not available, skipping save_doc_id")
            return False
        try:
            week_id = self._get_week_identifier()
            
            with self.SessionLocal() as session:
                # Check if record exists
                existing = session.query(ReportExecution).filter_by(
                    week_identifier=week_id,
                    job_type=job_type
                ).first()
                
                if existing:
                    # Update existing record
                    existing.google_doc_id = doc_id
                    existing.google_doc_url = doc_url
                    existing.status = "completed"
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new record
                    execution = ReportExecution(
                        week_identifier=week_id,
                        job_type=job_type,
                        status="completed",
                        google_doc_id=doc_id,
                        google_doc_url=doc_url
                    )
                    session.add(execution)
                
                session.commit()
                logger.info(f"Saved doc ID {doc_id} for week {week_id}, job {job_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving doc ID: {e}")
            return False
    
    def get_doc_id(self, week_identifier: Optional[str] = None, job_type: str = "preview") -> Optional[str]:
        """
        Get Google Doc ID for specified week
        
        Args:
            week_identifier: Week identifier. If None, uses current week
            job_type: Type of job ("preview" or "final")
            
        Returns:
            Google Doc ID if found, None otherwise
        """
        if not self.db_available:
            logger.debug("Database not available, returning None for get_doc_id")
            return None
        if week_identifier is None:
            week_identifier = self._get_week_identifier()
        
        try:
            with self.SessionLocal() as session:
                execution = session.query(ReportExecution).filter_by(
                    week_identifier=week_identifier,
                    job_type=job_type
                ).first()
                
                if execution and execution.google_doc_id:
                    logger.info(f"Retrieved doc ID {execution.google_doc_id} for week {week_identifier}")
                    return execution.google_doc_id
                else:
                    logger.warning(f"No doc ID found for week {week_identifier}, job {job_type}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving doc ID: {e}")
            return None
    
    def get_doc_url(self, week_identifier: Optional[str] = None, job_type: str = "preview") -> Optional[str]:
        """
        Get Google Doc URL for specified week
        
        Args:
            week_identifier: Week identifier. If None, uses current week
            job_type: Type of job ("preview" or "final")
            
        Returns:
            Google Doc URL if found, None otherwise
        """
        if week_identifier is None:
            week_identifier = self._get_week_identifier()
        
        try:
            with self.SessionLocal() as session:
                execution = session.query(ReportExecution).filter_by(
                    week_identifier=week_identifier,
                    job_type=job_type
                ).first()
                
                if execution and execution.google_doc_url:
                    return execution.google_doc_url
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving doc URL: {e}")
            return None
    
    def log_execution(self, job_type: str, status: str, details: Optional[Dict[str, Any]] = None, 
                     error_message: Optional[str] = None) -> bool:
        """
        Log execution status and details
        
        Args:
            job_type: Type of job ("preview" or "final")
            status: Execution status ("running", "completed", "failed")
            details: Additional execution details
            error_message: Error message if status is "failed"
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_available:
            logger.debug("Database not available, skipping log_execution")
            return False
        try:
            week_id = self._get_week_identifier()
            
            with self.SessionLocal() as session:
                # Check if record exists
                existing = session.query(ReportExecution).filter_by(
                    week_identifier=week_id,
                    job_type=job_type
                ).first()
                
                if existing:
                    # Update existing record
                    existing.status = status
                    existing.execution_details = details
                    existing.error_message = error_message
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new record
                    execution = ReportExecution(
                        week_identifier=week_id,
                        job_type=job_type,
                        status=status,
                        execution_details=details,
                        error_message=error_message
                    )
                    session.add(execution)
                
                session.commit()
                logger.info(f"Logged execution: {job_type} - {status} for week {week_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging execution: {e}")
            return False
    
    def get_execution_history(self, limit: int = 10) -> list:
        """
        Get recent execution history
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of execution records
        """
        try:
            with self.SessionLocal() as session:
                executions = session.query(ReportExecution).order_by(
                    ReportExecution.created_at.desc()
                ).limit(limit).all()
                
                history = []
                for execution in executions:
                    history.append({
                        'id': execution.id,
                        'week_identifier': execution.week_identifier,
                        'job_type': execution.job_type,
                        'status': execution.status,
                        'google_doc_id': execution.google_doc_id,
                        'google_doc_url': execution.google_doc_url,
                        'error_message': execution.error_message,
                        'execution_details': execution.execution_details,
                        'created_at': execution.created_at.isoformat() if execution.created_at else None,
                        'updated_at': execution.updated_at.isoformat() if execution.updated_at else None
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"Error retrieving execution history: {e}")
            return []
    
    def cleanup_old_records(self, days_to_keep: int = 90) -> bool:
        """
        Clean up old execution records
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self.SessionLocal() as session:
                deleted_count = session.query(ReportExecution).filter(
                    ReportExecution.created_at < cutoff_date
                ).delete()
                
                session.commit()
                logger.info(f"Cleaned up {deleted_count} old execution records")
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return False
