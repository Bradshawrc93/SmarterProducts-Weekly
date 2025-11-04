"""
Notification Service - Email Integration via SMTP
"""
import logging
from typing import List, Optional
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config.settings import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles email notifications via SMTP"""
    
    def __init__(self):
        # SMTP configuration from settings
        self.smtp_server = getattr(settings, 'smtp_server', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'smtp_port', 587)
        self.smtp_username = getattr(settings, 'smtp_username', None)
        self.smtp_password = getattr(settings, 'smtp_password', None)
        self.use_tls = getattr(settings, 'smtp_use_tls', True)
        
        # If SMTP username not set, use from_email
        if not self.smtp_username:
            self.smtp_username = settings.from_email
        
        logger.info(f"SMTP configured: {self.smtp_server}:{self.smtp_port} (TLS: {self.use_tls})")
    
    def _send_email_smtp(self, recipients: List[str], subject: str, html_content: str, 
                         plain_content: str, attachment_data: Optional[bytes] = None, 
                         attachment_filename: Optional[str] = None) -> bool:
        """
        Send email via SMTP
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            html_content: HTML email body
            plain_content: Plain text email body
            attachment_data: Optional attachment data (bytes)
            attachment_filename: Optional attachment filename
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{settings.from_name} <{settings.from_email}>"
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add plain text and HTML parts
            part1 = MIMEText(plain_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Add attachment if provided
            if attachment_data and attachment_filename:
                attachment = MIMEBase('application', 'pdf')
                attachment.set_payload(attachment_data)
                encoders.encode_base64(attachment)
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment_filename}'
                )
                msg.attach(attachment)
            
            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
                logger.info(f"Email sent successfully via SMTP to {', '.join(recipients)}")
                return True
                
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def send_preview_notification(self, doc_link: str, recipients: Optional[List[str]] = None) -> bool:
        """
        Send preview notification with Google Doc link
        
        Args:
            doc_link: URL to the Google Doc
            recipients: List of email addresses. If None, uses settings.preview_email_recipients
            
        Returns:
            True if successful, False otherwise
        """
        if recipients is None:
            recipients = settings.preview_email_recipients
        
        logger.info(f"Sending preview notification to {len(recipients)} recipients")
        
        try:
            subject = f"Weekly Report Preview Ready - {datetime.now().strftime('%B %d, %Y')}"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                        📊 Weekly Report Preview Ready
                    </h2>
                    
                    <p>Hello!</p>
                    
                    <p>Your weekly report has been generated and is ready for review. The report includes:</p>
                    
                    <ul style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #3498db;">
                        <li>📈 <strong>Executive Summary</strong> - Key accomplishments and metrics</li>
                        <li>🎯 <strong>Strategic Insights</strong> - Analysis and recommendations</li>
                        <li>📊 <strong>Data Analysis</strong> - Jira and Google Sheets insights</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{doc_link}" 
                           style="background-color: #3498db; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  display: inline-block;">
                            📝 Review Report in Google Docs
                        </a>
                    </div>
                    
                    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #856404;">⏰ Next Steps:</h4>
                        <p style="margin-bottom: 0;">
                            Please review the report and make any necessary edits. 
                            The final PDF version will be automatically sent tomorrow morning at 8 AM.
                        </p>
                    </div>
                    
                    <p style="margin-top: 30px; font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 15px;">
                        This is an automated message from the SmarterProducts Weekly reporting system.<br>
                        Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
            </body>
            </html>
            """
            
            plain_content = f"""
Weekly Report Preview Ready

Hello!

Your weekly report has been generated and is ready for review.

Review the report here: {doc_link}

The report includes:
- Executive Summary with key accomplishments and metrics
- Strategic Insights with analysis and recommendations  
- Data Analysis from Jira and Google Sheets

Please review the report and make any necessary edits. The final PDF version will be automatically sent tomorrow morning at 8 AM.

Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            """
            
            # Send email via SMTP
            success = self._send_email_smtp(
                recipients=recipients,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending preview notifications: {e}")
            return False
    
    def send_final_report(self, pdf_data: bytes, doc_link: str, recipients: Optional[List[str]] = None) -> bool:
        """
        Send final report with PDF attachment and Google Doc link
        
        Args:
            pdf_data: PDF file content as bytes
            doc_link: URL to the Google Doc
            recipients: List of email addresses. If None, uses settings.final_email_recipients
            
        Returns:
            True if successful, False otherwise
        """
        if recipients is None:
            recipients = settings.final_email_recipients
        
        logger.info(f"Sending final report to {len(recipients)} recipients")
        
        try:
            report_date = datetime.now().strftime('%B %d, %Y')
            subject = f"Weekly Report - {report_date}"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                        📊 Weekly Report - {report_date}
                    </h2>
                    
                    <p>Hello!</p>
                    
                    <p>Please find attached the weekly report for your review. This report includes comprehensive insights from our project data and strategic recommendations for the upcoming week.</p>
                    
                    <div style="background-color: #e8f5e8; border: 1px solid #27ae60; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #27ae60;">📎 Report Formats:</h4>
                        <ul style="margin-bottom: 0;">
                            <li><strong>PDF Attachment:</strong> Complete report ready for printing/sharing</li>
                            <li><strong>Google Doc:</strong> Live document for collaboration and updates</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{doc_link}" 
                           style="background-color: #27ae60; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  display: inline-block; margin-right: 10px;">
                            📝 View in Google Docs
                        </a>
                    </div>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #495057;">📈 Report Highlights:</h4>
                        <p style="margin-bottom: 0;">
                            This week's report includes data analysis from Jira project boards, 
                            Google Sheets metrics, and AI-generated insights to help guide strategic decisions.
                        </p>
                    </div>
                    
                    <p>If you have any questions about the report or need additional analysis, please don't hesitate to reach out.</p>
                    
                    <p style="margin-top: 30px; font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 15px;">
                        This is an automated weekly report from the SmarterProducts system.<br>
                        Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
            </body>
            </html>
            """
            
            plain_content = f"""
Weekly Report - {report_date}

Hello!

Please find attached the weekly report for your review. This report includes comprehensive insights from our project data and strategic recommendations for the upcoming week.

You can also view the live Google Doc version here: {doc_link}

Report Highlights:
- Data analysis from Jira project boards
- Google Sheets metrics and insights  
- AI-generated strategic recommendations

If you have any questions about the report or need additional analysis, please don't hesitate to reach out.

Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            """
            
            # Prepare PDF attachment
            pdf_filename = f"Weekly_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Send email via SMTP with PDF attachment
            success = self._send_email_smtp(
                recipients=recipients,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                attachment_data=pdf_data,
                attachment_filename=pdf_filename
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending final reports: {e}")
            return False
    
    def send_error_notification(self, error: str, context: dict, recipients: Optional[List[str]] = None) -> bool:
        """
        Send error notification to administrators
        
        Args:
            error: Error message
            context: Additional context about the error
            recipients: List of admin email addresses. If None, uses preview recipients
            
        Returns:
            True if successful, False otherwise
        """
        if recipients is None:
            recipients = settings.preview_email_recipients  # Send errors to preview recipients
        
        logger.info(f"Sending error notification to {len(recipients)} recipients")
        
        try:
            subject = f"⚠️ Weekly Report System Error - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            context_str = "\n".join([f"  {k}: {v}" for k, v in context.items()])
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">
                        ⚠️ System Error Alert
                    </h2>
                    
                    <div style="background-color: #fdf2f2; border: 1px solid #e74c3c; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #e74c3c;">Error Details:</h4>
                        <p style="font-family: monospace; background-color: #fff; padding: 10px; border-radius: 3px;">
                            {error}
                        </p>
                    </div>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #495057;">Context Information:</h4>
                        <pre style="font-family: monospace; font-size: 12px; background-color: #fff; padding: 10px; border-radius: 3px; overflow-x: auto;">
{context_str}
                        </pre>
                    </div>
                    
                    <p>Please check the system logs and resolve the issue to ensure the weekly report generation continues normally.</p>
                    
                    <p style="margin-top: 30px; font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 15px;">
                        Automated error notification from SmarterProducts Weekly system<br>
                        Timestamp: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
            </body>
            </html>
            """
            
            plain_content = f"""
SYSTEM ERROR ALERT

Error Details:
{error}

Context Information:
{context_str}

Please check the system logs and resolve the issue to ensure the weekly report generation continues normally.

Timestamp: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            """
            
            # Send email via SMTP
            success = self._send_email_smtp(
                recipients=recipients,
                subject=subject,
                html_content=html_content,
                plain_content=plain_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending error notifications: {e}")
            return False
