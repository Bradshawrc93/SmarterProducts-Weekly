"""
Document Builder Service - Google Docs and PDF Generation
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from config.settings import settings

logger = logging.getLogger(__name__)


class DocumentBuilder:
    """Builds and manages Google Docs and PDF exports"""
    
    def __init__(self):
        self.docs_service = None
        self.drive_service = None
        self._setup_services()
    
    def _setup_services(self):
        """Initialize Google Docs and Drive services"""
        try:
            credentials = Credentials.from_service_account_info(
                settings.google_credentials,
                scopes=[
                    'https://www.googleapis.com/auth/documents',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            
            self.docs_service = build('docs', 'v1', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            logger.info("Google Docs and Drive services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google services: {e}")
            raise
    
    def create_google_doc(self, content: Dict[str, str], folder_id: Optional[str] = None) -> str:
        """
        Create a new Google Doc with the provided content
        
        Args:
            content: Dictionary with report content (title, summary, insights)
            folder_id: Google Drive folder ID. If None, uses settings folder
            
        Returns:
            Document ID of the created Google Doc
        """
        if folder_id is None:
            folder_id = settings.google_drive_folder_id
        
        logger.info("Creating new Google Doc")
        
        try:
            # Create the document
            doc_title = content.get("title", f"Weekly Report - {datetime.now().strftime('%Y-%m-%d')}")
            
            document = {
                'title': doc_title
            }
            
            doc = self.docs_service.documents().create(body=document).execute()
            doc_id = doc.get('documentId')
            
            logger.info(f"Created Google Doc with ID: {doc_id}")
            
            # Move to specified folder if provided
            if folder_id:
                self.drive_service.files().update(
                    fileId=doc_id,
                    addParents=folder_id,
                    removeParents='root'
                ).execute()
                logger.info(f"Moved document to folder: {folder_id}")
            
            # Add content to the document
            self._populate_document(doc_id, content)
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Error creating Google Doc: {e}")
            raise
    
    def _populate_document(self, doc_id: str, content: Dict[str, str]):
        """Populate the Google Doc with formatted content"""
        try:
            # Build the document content
            requests = []
            
            # Add title
            title = content.get("title", "Weekly Report")
            requests.append({
                'insertText': {
                    'location': {'index': 1},
                    'text': f"{title}\n\n"
                }
            })
            
            # Add generation timestamp
            timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
            requests.append({
                'insertText': {
                    'location': {'index': len(title) + 3},
                    'text': f"Generated on: {timestamp}\n\n"
                }
            })
            
            current_index = len(title) + len(timestamp) + 7
            
            # Add summary section
            if content.get("summary"):
                summary_header = "## Executive Summary\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': summary_header
                    }
                })
                current_index += len(summary_header)
                
                summary_content = f"{content['summary']}\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': summary_content
                    }
                })
                current_index += len(summary_content)
            
            # Add insights section
            if content.get("insights"):
                insights_header = "## Strategic Insights & Recommendations\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': insights_header
                    }
                })
                current_index += len(insights_header)
                
                insights_content = f"{content['insights']}\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': insights_content
                    }
                })
                current_index += len(insights_content)
            
            # Add footer
            footer = "---\n\nThis report was automatically generated by the SmarterProducts Weekly system.\nFeel free to edit this document before the final distribution.\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': footer
                }
            })
            
            # Apply formatting
            self._add_formatting_requests(requests, title, len(title) + 3)
            
            # Execute all requests
            if requests:
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info("Document content populated successfully")
            
        except Exception as e:
            logger.error(f"Error populating document: {e}")
            raise
    
    def _add_formatting_requests(self, requests: list, title: str, title_end_index: int):
        """Add formatting requests for the document"""
        try:
            # Format title as heading
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': 1,
                        'endIndex': len(title) + 1
                    },
                    'textStyle': {
                        'bold': True,
                        'fontSize': {'magnitude': 18, 'unit': 'PT'}
                    },
                    'fields': 'bold,fontSize'
                }
            })
            
            # Format timestamp as italic
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': title_end_index,
                        'endIndex': title_end_index + 30  # Approximate timestamp length
                    },
                    'textStyle': {
                        'italic': True,
                        'fontSize': {'magnitude': 10, 'unit': 'PT'}
                    },
                    'fields': 'italic,fontSize'
                }
            })
            
        except Exception as e:
            logger.error(f"Error adding formatting: {e}")
    
    def update_google_doc(self, doc_id: str, content: Dict[str, str]) -> bool:
        """
        Update an existing Google Doc with new content
        
        Args:
            doc_id: Document ID to update
            content: New content to replace existing content
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating Google Doc: {doc_id}")
        
        try:
            # Get current document to find content length
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            doc_content = doc.get('body', {}).get('content', [])
            
            # Calculate total content length
            total_length = 0
            for element in doc_content:
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            total_length += len(text_run['textRun'].get('content', ''))
            
            # Clear existing content and add new content
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': total_length
                        }
                    }
                }
            ]
            
            # Execute delete request first
            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            # Add new content
            self._populate_document(doc_id, content)
            
            logger.info("Document updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False
    
    def export_doc_as_pdf(self, doc_id: str) -> bytes:
        """
        Export Google Doc as PDF
        
        Args:
            doc_id: Document ID to export
            
        Returns:
            PDF content as bytes
        """
        logger.info(f"Exporting document as PDF: {doc_id}")
        
        try:
            # Export the document as PDF
            request = self.drive_service.files().export_media(
                fileId=doc_id,
                mimeType='application/pdf'
            )
            
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"PDF export progress: {int(status.progress() * 100)}%")
            
            pdf_content = file_io.getvalue()
            
            logger.info("PDF export completed successfully")
            return pdf_content
            
        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")
            raise
    
    def get_document_link(self, doc_id: str) -> str:
        """
        Get shareable link for Google Doc
        
        Args:
            doc_id: Document ID
            
        Returns:
            Shareable Google Docs URL
        """
        return f"https://docs.google.com/document/d/{doc_id}/edit"
    
    def apply_template(self, data: Dict[str, Any], template_name: str) -> str:
        """
        Apply a template to format the data
        
        Args:
            data: Data to format
            template_name: Name of template to use
            
        Returns:
            Formatted content string
        """
        # This is a placeholder for template functionality
        # You can expand this to load and apply custom templates
        logger.info(f"Applying template: {template_name}")
        
        try:
            # Basic template application
            formatted_content = f"""
# {data.get('title', 'Weekly Report')}

## Summary
{data.get('summary', 'No summary available')}

## Insights
{data.get('insights', 'No insights available')}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            return formatted_content.strip()
            
        except Exception as e:
            logger.error(f"Error applying template: {e}")
            raise
