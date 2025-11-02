"""
Notification Service - Email Integration
"""
import logging
from typing import List, Optional
from datetime import datetime
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from config.settings import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles email notifications via SendGrid"""
    
    def __init__(self):
        self.sendgrid_client = SendGridAPIClient(api_key=settings.sendgrid_api_key)
    
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
            
            # Send to each recipient
            success_count = 0
            for recipient in recipients:
                try:
                    message = Mail(
                        from_email=(settings.from_email, settings.from_name),
                        to_emails=recipient,
                        subject=subject,
                        html_content=html_content,
                        plain_text_content=plain_content
                    )
                    
                    response = self.sendgrid_client.send(message)
                    
                    if response.status_code in [200, 202]:
                        success_count += 1
                        logger.info(f"Preview notification sent successfully to {recipient}")
                    else:
                        logger.error(f"Failed to send preview notification to {recipient}: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error sending preview notification to {recipient}: {e}")
            
            success = success_count == len(recipients)
            logger.info(f"Preview notification sent to {success_count}/{len(recipients)} recipients")
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
            encoded_pdf = base64.b64encode(pdf_data).decode()
            
            attachment = Attachment(
                FileContent(encoded_pdf),
                FileName(pdf_filename),
                FileType("application/pdf"),
                Disposition("attachment")
            )
            
            # Send to each recipient
            success_count = 0
            for recipient in recipients:
                try:
                    message = Mail(
                        from_email=(settings.from_email, settings.from_name),
                        to_emails=recipient,
                        subject=subject,
                        html_content=html_content,
                        plain_text_content=plain_content
                    )
                    
                    message.attachment = attachment
                    
                    response = self.sendgrid_client.send(message)
                    
                    if response.status_code in [200, 202]:
                        success_count += 1
                        logger.info(f"Final report sent successfully to {recipient}")
                    else:
                        logger.error(f"Failed to send final report to {recipient}: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error sending final report to {recipient}: {e}")
            
            success = success_count == len(recipients)
            logger.info(f"Final report sent to {success_count}/{len(recipients)} recipients")
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
            
            # Send to each recipient
            success_count = 0
            for recipient in recipients:
                try:
                    message = Mail(
                        from_email=(settings.from_email, settings.from_name),
                        to_emails=recipient,
                        subject=subject,
                        html_content=html_content,
                        plain_text_content=plain_content
                    )
                    
                    response = self.sendgrid_client.send(message)
                    
                    if response.status_code in [200, 202]:
                        success_count += 1
                        logger.info(f"Error notification sent successfully to {recipient}")
                    else:
                        logger.error(f"Failed to send error notification to {recipient}: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error sending error notification to {recipient}: {e}")
            
            success = success_count == len(recipients)
            logger.info(f"Error notification sent to {success_count}/{len(recipients)} recipients")
            return success
            
        except Exception as e:
            logger.error(f"Error sending error notifications: {e}")
            return False
