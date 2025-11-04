"""
Document Builder Service - Google Docs and PDF Generation
"""
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime
import io
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from config.settings import settings

logger = logging.getLogger(__name__)


class DocumentBuilder:
    """Builds and manages Google Docs and PDF exports"""
    
    def __init__(self):
        self.docs_service = None
        self.drive_service = None
        self._setup_services()
    
    def _setup_services(self):
        """Initialize Google Docs and Drive services with OAuth support"""
        try:
            # Check if OAuth is configured for document creation
            import os  # Imported here to avoid top-level dependency
            if (os.path.exists('token.json') and 
                getattr(settings, 'use_oauth_for_docs', False)):
                
                logger.info("Using OAuth for document creation")
                from google.oauth2.credentials import Credentials as OAuthCredentials
                
                SCOPES = [
                    'https://www.googleapis.com/auth/documents',
                    'https://www.googleapis.com/auth/drive'
                ]
                
                credentials = OAuthCredentials.from_authorized_user_file('token.json', SCOPES)
                
            else:
                logger.info("Using service account for document creation")
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
        
        # Find this week's Wednesday
        days_until_wednesday = (2 - today.weekday()) % 7  # Wednesday is weekday 2
        if days_until_wednesday == 0 and today.weekday() > 2:  # If past Wednesday, get next Wednesday
            days_until_wednesday = 7
        wednesday = today + timedelta(days=days_until_wednesday)
        
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
            # Search for documents with this title in the folder (with shared drive support)
            # Exclude trashed files
            query = f"name='{doc_title}' and parents in '{folder_id}' and mimeType='application/vnd.google-apps.document' and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
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
                # Create new document directly in shared drive folder
                if folder_id:
                    # Create directly in folder with shared drive support
                    file_metadata = {
                        'name': doc_title,
                        'parents': [folder_id],
                        'mimeType': 'application/vnd.google-apps.document'
                    }
                    
                    doc = self.drive_service.files().create(
                        body=file_metadata,
                        supportsAllDrives=True
                    ).execute()
                    doc_id = doc.get('id')
                    
                    logger.info(f"Created Google Doc directly in shared drive folder: {doc_id}")
                else:
                    # Fallback: create in root
                    document = {'title': doc_title}
                    doc = self.docs_service.documents().create(body=document).execute()
                    doc_id = doc.get('documentId')
                    logger.info(f"Created Google Doc in root: {doc_id}")
                
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
            body = doc.get('body', {})
            
            # Get the actual end index from the body (accounts for all content including tables)
            end_index = body.get('endIndex', 1)
            
            if end_index > 1:
                # Clear existing content (but keep the first character to preserve document structure)
                # Need to subtract 1 from end_index because it's exclusive
                delete_end = end_index - 1
                if delete_end > 1:
                    requests = [{
                        'deleteContentRange': {
                            'range': {
                                'startIndex': 1,
                                'endIndex': delete_end
                            }
                        }
                    }]
                    
                    self.docs_service.documents().batchUpdate(
                        documentId=doc_id,
                        body={'requests': requests}
                    ).execute()
                    
                    logger.info(f"Cleared existing document content (deleted range 1-{delete_end})")
                else:
                    logger.info("Document already empty or nearly empty")
            else:
                logger.info("Document already empty")
            
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
            
            # Add generation timestamp (insert after title and newlines)
            timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
            timestamp_text = f"Generated on: {timestamp}\n\n"
            title_length = len(title) + 2  # title + 2 newlines
            requests.append({
                'insertText': {
                    'location': {'index': title_length},
                    'text': timestamp_text
                }
            })
            
            # Calculate current index: title + newlines + timestamp + newlines
            current_index = title_length + len(timestamp_text)
            
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
            post_table_formatting_data = None
            if content.get("summary"):
                # Parse markdown and apply proper formatting
                markdown_content = content['summary']
                text_content, formatting_requests, table_ranges = self._parse_markdown_to_docs_format(markdown_content, current_index)
                
                # Insert text content (tables are included as formatted text)
                content_start_index = current_index
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': text_content
                    }
                })
                current_index += len(text_content)
                
                # Apply formatting requests
                requests.extend(formatting_requests)
                
                # Ensure all "Team:" headers are properly formatted as Heading 2
                team_header_pattern = re.compile(r'^Team:\s+[^\n]+', re.MULTILINE)
                team_header_matches = list(team_header_pattern.finditer(text_content))
                
                for match in team_header_matches:
                    match_text = match.group(0)
                    # Only format if it doesn't contain a number after "Team"
                    if not re.search(r'Team\s+\d+:', match_text):
                        header_start_abs = content_start_index + match.start()
                        # Include until newline or end of line
                        line_end = text_content.find('\n', match.end())
                        if line_end == -1:
                            header_end_abs = content_start_index + match.end()
                        else:
                            header_end_abs = content_start_index + line_end
                        
                        # Check if this isn't already in formatting_requests
                        already_formatted = any(
                            req.get('updateParagraphStyle', {}).get('range', {}).get('startIndex') == header_start_abs
                            for req in formatting_requests
                        )
                        
                        if not already_formatted:
                            requests.append({
                                'updateParagraphStyle': {
                                    'range': {
                                        'startIndex': header_start_abs,
                                        'endIndex': header_end_abs
                                    },
                                    'paragraphStyle': {
                                        'namedStyleType': 'HEADING_2'
                                    },
                                    'fields': 'namedStyleType'
                                }
                            })
            
            # Add footer
            footer = "---\n\nThis report was automatically generated by the SmarterProducts Weekly system.\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': footer
                }
            })
            
            # Apply formatting
            self._add_formatting_requests(requests, title, len(title) + 3)
            
            # Execute all requests (phase 1: insert text, tables, basic formatting)
            if requests:
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info("Document content populated successfully")
            
            # Create and populate tables if we have any
            if table_ranges and len(table_ranges) > 0:
                logger.info(f"Creating and populating {len(table_ranges)} tables...")
                self._create_and_populate_tables(doc_id, table_ranges)
            
        except Exception as e:
            logger.error(f"Error populating document: {e}")
            raise
    
    def _execute_with_retry(self, doc_id: str, requests_list: list, max_retries: int = 3):
        """
        Execute batch update with retry logic and exponential backoff for rate limits
        
        Args:
            doc_id: Document ID
            requests_list: List of request dictionaries
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests_list}
                ).execute()
                return True
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit error
                    wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        logger.error(f"Rate limit retry exhausted after {max_retries} attempts")
                        return False
                else:
                    # Non-rate-limit error, don't retry
                    logger.error(f"HTTP error during batch update: {e}")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error during batch update: {e}")
                return False
        return False

    def _create_and_populate_tables(self, doc_id: str, table_insertion_info: list):
        """
        Create tables and populate cells with content using batched operations and retry logic
        
        Args:
            doc_id: Document ID
            table_insertion_info: List of table info dicts with insert_index, table_data, num_rows, num_cols
        """
        try:
            if not table_insertion_info:
                logger.info("No tables to create")
                return
            
            logger.info(f"Creating {len(table_insertion_info)} tables...")
            
            # First, create all table structures
            # Process in reverse order to avoid index shifting
            for table_idx in range(len(table_insertion_info) - 1, -1, -1):
                table_info = table_insertion_info[table_idx]
                table_data = table_info['table_data']
                insert_index = table_info['insert_index']
                num_rows = len(table_data)
                num_cols = len(table_data[0]) if table_data else 0
                
                logger.info(f"Creating table {table_idx + 1}: {num_rows} rows x {num_cols} cols at index {insert_index}")
                
                # Find and delete placeholder first
                doc = self.docs_service.documents().get(documentId=doc_id).execute()
                body = doc.get('body', {})
                content = body.get('content', [])
                
                placeholder_found = False
                for element in content:
                    if 'paragraph' in element:
                        para = element['paragraph']
                        para_start = element.get('startIndex')
                        para_end = element.get('endIndex')
                        
                        # Check if this paragraph contains our placeholder
                        para_text = ''
                        for elem in para.get('elements', []):
                            if 'textRun' in elem:
                                para_text += elem['textRun'].get('content', '')
                        
                        if '[TABLE PLACEHOLDER]' in para_text:
                            # Delete the placeholder and create table in one batch
                            requests = [
                                {
                                    'deleteContentRange': {
                                        'range': {
                                            'startIndex': para_start,
                                            'endIndex': para_end - 1
                                        }
                                    }
                                },
                                {
                                    'insertTable': {
                                        'location': {'index': para_start + 1},
                                        'rows': num_rows,
                                        'columns': num_cols
                                    }
                                }
                            ]
                            if self._execute_with_retry(doc_id, requests):
                                placeholder_found = True
                            break
                
                if not placeholder_found:
                    logger.warning(f"Could not find placeholder for table {table_idx + 1}")
                
                # Add delay between table creation to avoid rate limits
                if table_idx > 0:
                    time.sleep(3)
            
            # Now populate all tables with batched operations
            logger.info("Populating table cells with batched operations...")
            for table_idx, table_info in enumerate(table_insertion_info):
                table_data = table_info['table_data']
                logger.info(f"Processing table {table_idx + 1}: {len(table_data)} rows, {len(table_data[0]) if table_data else 0} cols")
                
                # Add delay between tables to avoid rate limits
                if table_idx > 0:
                    time.sleep(5)  # Increased delay between tables
                
                # Get current document structure
                doc = self.docs_service.documents().get(documentId=doc_id).execute()
                
                # Find the target table
                table_count = 0
                target_table_element = None
                for element in doc.get('body', {}).get('content', []):
                    if 'table' in element:
                        if table_count == table_idx:
                            target_table_element = element.get('table', {})
                            break
                        table_count += 1
                
                if not target_table_element:
                    logger.warning(f"Could not find table {table_idx + 1} in document")
                    continue
                
                # Build batched requests - process row by row to get correct indices
                num_cols = len(table_data[0]) if table_data else 0
                cell_locations = []  # Store (start_index, end_index, text, is_header) for formatting
                
                # Process each row separately to ensure correct indices
                for row_idx in range(len(table_data)):
                    row_data = table_data[row_idx]
                    
                    # Get fresh document structure for each row
                    doc = self.docs_service.documents().get(documentId=doc_id).execute()
                    # Find the target table again
                    table_count = 0
                    target_table_element = None
                    for element in doc.get('body', {}).get('content', []):
                        if 'table' in element:
                            if table_count == table_idx:
                                target_table_element = element.get('table', {})
                                break
                            table_count += 1
                    
                    if not target_table_element:
                        break
                    
                    # Get this specific row
                    table_rows = target_table_element.get('tableRows', [])
                    if row_idx >= len(table_rows):
                        continue
                    
                    row = table_rows[row_idx]
                    table_cells = row.get('tableCells', [])
                    
                    # Build requests for this row
                    row_requests = []
                    for col_idx in range(num_cols):
                        if col_idx >= len(row_data):
                            cell_text = ""
                        else:
                            cell_text = str(row_data[col_idx]) if row_data[col_idx] is not None else ""
                        
                        if col_idx >= len(table_cells):
                            continue
                        
                        cell = table_cells[col_idx]
                        # Get the start index from the first paragraph in the cell
                        start_index = None
                        for content_item in cell.get('content', []):
                            if 'paragraph' in content_item:
                                para = content_item['paragraph']
                                # First try textRun (for cells with existing content)
                                for para_element in para.get('elements', []):
                                    if 'textRun' in para_element:
                                        start_index = para_element.get('startIndex')
                                        break
                                # If no textRun found, use paragraph startIndex (for empty cells)
                                if start_index is None:
                                    start_index = content_item.get('startIndex')
                                    if start_index is not None:
                                        start_index = start_index + 1  # Skip paragraph marker
                                
                                if start_index is not None:
                                    row_requests.append({
                                        'insertText': {
                                            'location': {'index': start_index},
                                            'text': cell_text
                                        }
                                    })
                                    
                                    cell_locations.append({
                                        'start': start_index,
                                        'end': start_index + len(cell_text),
                                        'text': cell_text,
                                        'is_header': row_idx == 0
                                    })
                                    break
                    
                    # Execute inserts for this row
                    if row_requests:
                        if self._execute_with_retry(doc_id, row_requests):
                            logger.info(f"Inserted {len(row_requests)} cells for row {row_idx + 1}")
                        time.sleep(0.5)  # Small delay between rows
                
                # Now format headers if we have cell_locations
                if cell_locations:
                    logger.info(f"Batching {len(batch_requests)} cell insertions for table {table_idx + 1}...")
                    if self._execute_with_retry(doc_id, batch_requests):
                        logger.info(f"Successfully inserted {len(batch_requests)} cells in table {table_idx + 1}")
                    else:
                        logger.warning(f"Failed to insert cells for table {table_idx + 1} after retries")
                        # Continue to next table even if this one failed
                        continue
                    
                    # Wait a bit before formatting to avoid rate limits
                    time.sleep(2)
                    
                    # Now batch all formatting requests (bold headers)
                    format_requests = []
                    for cell_info in cell_locations:
                        if cell_info['is_header'] and cell_info['text']:
                            format_requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': cell_info['start'],
                                        'endIndex': cell_info['end']
                                    },
                                    'textStyle': {
                                        'bold': True
                                    },
                                    'fields': 'bold'
                                }
                            })
                    
                    # Execute formatting in batches of 20 to stay under rate limits
                    batch_size = 20
                    for i in range(0, len(format_requests), batch_size):
                        batch = format_requests[i:i + batch_size]
                        logger.info(f"Formatting batch {i // batch_size + 1} for table {table_idx + 1} ({len(batch)} requests)...")
                        if self._execute_with_retry(doc_id, batch):
                            logger.info(f"Successfully formatted batch {i // batch_size + 1}")
                        else:
                            logger.warning(f"Failed to format batch {i // batch_size + 1} after retries")
                        
                        # Wait between formatting batches
                        if i + batch_size < len(format_requests):
                            time.sleep(2)
                    
                    logger.info(f"Successfully populated table {table_idx + 1} ({len(batch_requests)} cells)")
                else:
                    logger.warning(f"No cells to populate for table {table_idx + 1}")
            
            logger.info("All tables populated successfully")
        
        except Exception as e:
            logger.error(f"Error populating tables: {e}")
            # Don't raise - allow document to be created even if table formatting fails
            import traceback
            logger.error(traceback.format_exc())
    
    def _apply_post_table_formatting(self, doc_id: str, formatting_data: dict):
        """
        Apply text formatting (headers, bold) after tables are inserted.
        This avoids index calculation issues by reading the document fresh
        and matching text content to find correct positions.
        
        Args:
            doc_id: Document ID
            formatting_data: Dict with text_content, content_start_index, formatting_requests, team_matches
        """
        try:
            # Get fresh document structure after table insertion
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            body = doc.get('body', {})
            content = body.get('content', [])
            
            # Extract all text from the document with proper index tracking
            def extract_text_with_indices(elements):
                """Extract text and track actual indices from document structure"""
                text_chunks = []  # List of (text, start_index) tuples
                
                for element in elements:
                    if 'paragraph' in element:
                        para_element = element
                        para = para_element.get('paragraph', {})
                        para_start = para_element.get('startIndex', 0)
                        
                        para_elements = para.get('elements', [])
                        for elem in para_elements:
                            if 'textRun' in elem:
                                text_run = elem.get('textRun', {})
                                text_content = text_run.get('content', '')
                                text_start = elem.get('startIndex', para_start)
                                if text_content:
                                    text_chunks.append((text_content, text_start))
                    elif 'table' in element:
                        # Tables have their own structure - skip for text extraction
                        # but note their position
                        table_start = element.get('startIndex', 0)
                        # Add a marker for table position
                        text_chunks.append((f'[TABLE_{table_start}]', table_start))
                
                return text_chunks
            
            text_chunks = extract_text_with_indices(content)
            
            # Build text-to-index mapping
            doc_text = ''
            char_to_index = {}  # Maps character position in doc_text to actual doc index
            
            current_char = 0
            for text_chunk, start_index in text_chunks:
                if not text_chunk.startswith('[TABLE_'):
                    # Regular text chunk
                    for i, char in enumerate(text_chunk):
                        char_to_index[current_char + i] = start_index + i
                    doc_text += text_chunk
                    current_char += len(text_chunk)
                # Skip table markers in doc_text but track them
            
            # Find the content section by matching text patterns
            text_content = formatting_data['text_content']
            formatting_requests = formatting_data['formatting_requests']
            team_matches = formatting_data['team_matches']
            
            requests = []
            
            # Apply formatting requests by finding text in the document
            for fmt_req in formatting_requests:
                if 'updateParagraphStyle' in fmt_req:
                    range_data = fmt_req['updateParagraphStyle'].get('range', {})
                    # Try to find the text at this range in the original text_content
                    # and then find it in the actual document
                    # For now, skip these as they're complex - headers are handled below
                    continue
                elif 'updateTextStyle' in fmt_req:
                    # Apply bold formatting by finding the bold text in document
                    range_data = fmt_req['updateTextStyle'].get('range', {})
                    original_start = range_data.get('startIndex', 0)
                    original_end = range_data.get('endIndex', 0)
                    
                    # Find the text at this position in original content
                    relative_start = original_start - formatting_data['content_start_index']
                    relative_end = original_end - formatting_data['content_start_index']
                    
                    if relative_start >= 0 and relative_end <= len(text_content):
                        target_text = text_content[relative_start:relative_end]
                        # Find this text in the actual document (skip table markers)
                        doc_pos = doc_text.find(target_text)
                        if doc_pos != -1 and doc_pos + len(target_text) <= len(doc_text):
                            # Get actual indices from mapping
                            actual_start = char_to_index.get(doc_pos, doc_pos)
                            actual_end = char_to_index.get(doc_pos + len(target_text) - 1, doc_pos + len(target_text))
                            if actual_end <= actual_start:
                                actual_end = actual_start + len(target_text)
                            
                            requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': actual_start,
                                        'endIndex': actual_end
                                    },
                                    'textStyle': {
                                        'bold': True
                                    },
                                    'fields': 'bold'
                                }
                            })
            
            # Apply Team: header formatting
            for match in team_matches:
                match_text = match.group(0)
                # Find this text in the actual document (skip table markers)
                doc_pos = doc_text.find(match_text)
                if doc_pos != -1 and doc_pos + len(match_text) <= len(doc_text):
                    header_start = char_to_index.get(doc_pos, doc_pos)
                    header_end = char_to_index.get(doc_pos + len(match_text) - 1, doc_pos + len(match_text))
                    if header_end <= header_start:
                        header_end = header_start + len(match_text)
                    
                    requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': header_start,
                                'endIndex': header_end
                            },
                            'paragraphStyle': {
                                'namedStyleType': 'HEADING_2'
                            },
                            'fields': 'namedStyleType'
                        }
                    })
            
            # Apply "## AI Summary and Insights" header formatting  
            ai_insights_pattern = re.compile(r'^AI Summary and Insights\s*$', re.MULTILINE)
            ai_match = ai_insights_pattern.search(text_content)
            if ai_match:
                ai_text = ai_match.group(0)
                doc_pos = doc_text.find(ai_text)
                if doc_pos != -1 and doc_pos + len(ai_text) <= len(doc_text):
                    header_start = char_to_index.get(doc_pos, doc_pos)
                    header_end = char_to_index.get(doc_pos + len(ai_text) - 1, doc_pos + len(ai_text))
                    if header_end <= header_start:
                        header_end = header_start + len(ai_text)
                    
                    requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': header_start,
                                'endIndex': header_end
                            },
                            'paragraphStyle': {
                                'namedStyleType': 'HEADING_2'
                            },
                            'fields': 'namedStyleType'
                        }
                    })
            
            # Apply all formatting requests
            if requests:
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                logger.info(f"Applied post-table formatting: {len(requests)} requests")
        
        except Exception as e:
            logger.error(f"Error applying post-table formatting: {e}")
            # Don't raise - allow document to be created even if formatting fails
            import traceback
            logger.error(traceback.format_exc())
    
    def _parse_markdown_to_docs_format(self, markdown_text: str, base_index: int) -> tuple[str, list]:
        """
        Parse markdown and convert to plain text with Google Docs formatting requests
        
        Converts:
        - ## Header -> Header 2 style
        - **Bold** -> Bold text formatting
        - ### Header -> Header 3 style
        - Markdown tables -> Google Docs tables with borders
        
        Returns:
            Tuple of (plain_text, formatting_requests, table_requests)
            Where table_requests is a list of table creation requests
        """
        plain_text = ""
        formatting_requests = []
        table_requests = []
        
        lines = markdown_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Skip horizontal rules (---) - remove them completely
            if re.match(r'^-{3,}\s*$', line.strip()):
                i += 1
                continue
            
            # Check for markdown tables (lines with pipes and separator row)
            if '|' in line and i + 1 < len(lines):
                # Check if next line is a separator (contains dashes and pipes)
                next_line = lines[i + 1].strip()
                if re.match(r'^\|[\s\-:|]+\|', next_line):
                    # Found a table - extract it
                    table_data, table_lines_consumed = self._extract_table(lines, i)
                    
                    if table_data:
                        # Store table insertion info
                        table_requests.append({
                            'insert_index': base_index + len(plain_text),
                            'table_data': table_data,
                            'num_rows': len(table_data),
                            'num_cols': len(table_data[0]) if table_data else 0
                        })
                        
                        # Add placeholder text (will be replaced by table)
                        placeholder = f"[TABLE PLACEHOLDER]\n"
                        plain_text += placeholder
                    
                    i += table_lines_consumed
                    continue
            
            # Check for headers (## or ###)
            header_match = re.match(r'^(#{2,3})\s+(.+)', line)
            if header_match:
                header_level = len(header_match.group(1))  # 2 or 3
                header_text = header_match.group(2)
                
                # Calculate indices after text is inserted
                header_start = base_index + len(plain_text)
                
                # Add header text
                plain_text += header_text + "\n"
                
                header_end = base_index + len(plain_text) - 1  # -1 to exclude newline
                
                # Add header formatting request
                formatting_requests.append({
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': header_start,
                            'endIndex': header_end
                        },
                        'paragraphStyle': {
                            'namedStyleType': f'HEADING_{header_level}' if header_level <= 2 else 'HEADING_2'
                        },
                        'fields': 'namedStyleType'
                    }
                })
                i += 1
                continue
            
            # Process bold text (**text**)
            processed_line = line
            bold_pattern = r'\*\*([^*]+)\*\*'
            
            # Find all bold sections
            bold_matches = list(re.finditer(bold_pattern, processed_line))
            
            if bold_matches:
                last_end = 0
                for match in bold_matches:
                    # Add text before bold
                    plain_text += processed_line[last_end:match.start()]
                    
                    # Add bold text
                    bold_text = match.group(1)
                    bold_start = base_index + len(plain_text)
                    plain_text += bold_text
                    bold_end = base_index + len(plain_text)
                    
                    # Add bold formatting request
                    formatting_requests.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': bold_start,
                                'endIndex': bold_end
                            },
                            'textStyle': {
                                'bold': True
                            },
                            'fields': 'bold'
                        }
                    })
                    
                    last_end = match.end()
                
                # Add remaining text after last bold
                plain_text += processed_line[last_end:]
            else:
                # No bold text, just add the line as-is
                plain_text += processed_line
            
            plain_text += "\n"
            i += 1
        
        return plain_text, formatting_requests, table_requests
    
    def _extract_table(self, lines: list, start_index: int) -> tuple[list, int]:
        """
        Extract table data from markdown lines
        
        Returns:
            Tuple of (table_data, lines_consumed)
            table_data is list of rows, each row is list of cells
        """
        table_data = []
        i = start_index
        separator_seen = False
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop if we hit an empty line after table
            if not line and separator_seen and table_data:
                break
            
            # Check if it's a table row (contains pipes)
            if '|' in line:
                # Parse cells (split by |, strip whitespace, skip empty first/last if they're just delimiters)
                cells = [cell.strip() for cell in line.split('|')]
                # Remove empty first/last cells if they're just from leading/trailing pipes
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                
                # Check if this is a separator row
                if re.match(r'^[\s\-:|]+$', line.replace('|', '')):
                    separator_seen = True
                    i += 1
                    continue
                
                # It's a data row
                if cells:
                    table_data.append(cells)
            else:
                # Not a table row anymore
                if separator_seen:
                    break
            
            i += 1
        
        return table_data, i - start_index
    
    def _format_table_as_text(self, table_data: list) -> str:
        """
        Format table data as markdown table text with borders
        
        Args:
            table_data: List of rows, each row is a list of cell strings
            
        Returns:
            Formatted markdown table string
        """
        if not table_data:
            return ""
        
        # Calculate column widths
        num_cols = max(len(row) for row in table_data) if table_data else 1
        col_widths = [0] * num_cols
        
        for row in table_data:
            for col_idx in range(num_cols):
                cell_text = row[col_idx] if col_idx < len(row) else ""
                col_widths[col_idx] = max(col_widths[col_idx], len(cell_text))
        
        # Format table
        lines = []
        
        for row_idx, row in enumerate(table_data):
            # Format row cells
            cells = []
            for col_idx in range(num_cols):
                cell_text = row[col_idx] if col_idx < len(row) else ""
                # Pad cell to column width
                padded_cell = cell_text.ljust(col_widths[col_idx])
                cells.append(padded_cell)
            
            # Create row with borders
            row_line = "| " + " | ".join(cells) + " |"
            lines.append(row_line)
            
            # Add separator after header row (first row)
            if row_idx == 0:
                separator_cells = ["-" * width for width in col_widths]
                separator_line = "| " + " | ".join(separator_cells) + " |"
                lines.append(separator_line)
        
        return "\n".join(lines)
    
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
