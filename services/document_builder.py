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
    
    def _get_report_date_name(self) -> str:
        """
        Get the proper report name based on the Wednesday of the current week
        
        Returns:
            Report name in format "Weekly Product Team Report MM/DD/YY"
        """
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        # Find the Wednesday of this week
        days_since_monday = today.weekday()  # 0=Monday, 1=Tuesday, etc.
        
        if days_since_monday <= 2:  # Monday, Tuesday, or Wednesday
            # This week's Wednesday
            days_to_wednesday = 2 - days_since_monday  # Wednesday is weekday 2
            wednesday = today + timedelta(days=days_to_wednesday)
        else:  # Thursday, Friday, Saturday, Sunday
            # Next week's Wednesday
            days_to_next_wednesday = 9 - days_since_monday  # 7 days + 2 for Wednesday
            wednesday = today + timedelta(days=days_to_next_wednesday)
        
        # Format as MM/DD/YY (no leading zeros)
        formatted_date = wednesday.strftime("%-m/%-d/%y")
        
        report_name = f"Weekly Product Team Report {formatted_date}"
        logger.info(f"Report name: {report_name}")
        return report_name

    def _find_existing_doc(self, doc_title: str, folder_id: str) -> Optional[str]:
        """
        Find existing Google Doc with the same title in the folder
        
        Args:
            doc_title: Title to search for
            folder_id: Folder ID to search in
            
        Returns:
            Document ID if found, None otherwise
        """
        try:
            # Search for documents with this title in the folder
            query = f"name='{doc_title}' and parents in '{folder_id}' and mimeType='application/vnd.google-apps.document'"
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                doc_id = files[0]['id']  # Take the first match
                logger.info(f"Found existing document: {doc_title} (ID: {doc_id})")
                return doc_id
            else:
                logger.info(f"No existing document found with title: {doc_title}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching for existing document: {e}")
            return None

    def create_or_update_google_doc(self, content: Dict[str, str], folder_id: Optional[str] = None) -> str:
        """
        Create a new Google Doc or update existing one with the provided content
        
        Args:
            content: Dictionary with report content (title, summary, insights, errors)
            folder_id: Google Drive folder ID. If None, uses settings folder
            
        Returns:
            Document ID of the created/updated Google Doc
        """
        if folder_id is None:
            folder_id = settings.google_drive_folder_id
        
        logger.info("Creating or updating Google Doc for weekly report")
        
        try:
            # Generate the proper report title
            doc_title = self._get_report_date_name()
            
            # Check if document already exists
            existing_doc_id = self._find_existing_doc(doc_title, folder_id)
            
            if existing_doc_id:
                logger.info(f"Updating existing document: {doc_title}")
                # Clear and repopulate existing document
                self._clear_document_content(existing_doc_id)
                self._populate_document(existing_doc_id, {**content, "title": doc_title})
                return existing_doc_id
            else:
                logger.info(f"Creating new document: {doc_title}")
                # Create new document
                document = {'title': doc_title}
                
                doc = self.docs_service.documents().create(body=document).execute()
                doc_id = doc.get('documentId')
                
                logger.info(f"Created Google Doc with ID: {doc_id}")
                
                # Move to specified folder
                if folder_id:
                    self.drive_service.files().update(
                        fileId=doc_id,
                        addParents=folder_id,
                        removeParents='root'
                    ).execute()
                    logger.info(f"Moved document to folder: {folder_id}")
                
                # Add content to the document
                self._populate_document(doc_id, {**content, "title": doc_title})
                
                return doc_id
            
        except Exception as e:
            logger.error(f"Error creating/updating Google Doc: {e}")
            raise

    def _clear_document_content(self, doc_id: str):
        """Clear all content from a Google Doc"""
        try:
            # Get current document to find content length
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            doc_content = doc.get('body', {}).get('content', [])
            
            # Calculate total content length
            total_length = 1  # Start at 1 to preserve the document structure
            for element in doc_content:
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            total_length += len(text_run['textRun'].get('content', ''))
            
            if total_length > 1:
                # Clear existing content
                requests = [{
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': total_length - 1
                        }
                    }
                }]
                
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info("Cleared existing document content")
            
        except Exception as e:
            logger.error(f"Error clearing document content: {e}")
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
            
            # Add errors section if there are any data collection issues
            if content.get("errors"):
                error_header = "⚠️ DATA COLLECTION ISSUES - PLEASE REVIEW\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': error_header
                    }
                })
                current_index += len(error_header)
                
                error_content = f"{content['errors']}\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': error_content
                    }
                })
                current_index += len(error_content)
                
                error_instructions = "Please fix the above issues and re-run the report generation.\n\n---\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': error_instructions
                    }
                })
                current_index += len(error_instructions)
            
            # Add the complete report content (now everything is in 'summary')
            if content.get("summary"):
                # The summary now contains the complete formatted report
                report_content = f"{content['summary']}\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': report_content
                    }
                })
                current_index += len(report_content)
            
            # Add raw data section for debugging (if no errors)
            if not content.get("errors") and content.get("raw_data_summary"):
                data_header = "## Data Sources Summary\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': data_header
                    }
                })
                current_index += len(data_header)
                
                data_content = f"{content['raw_data_summary']}\n\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': data_content
                    }
                })
                current_index += len(data_content)
            
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
