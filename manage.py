#!/usr/bin/env python3
"""
Management commands for SmarterProducts Weekly Automation
This file contains the CLI commands that will be executed by Heroku Scheduler
"""
import logging
import traceback
from datetime import datetime
import click
from config.settings import settings
from services.data_collector import DataCollector
from services.content_generator import ContentGenerator
from services.document_builder import DocumentBuilder
from services.notification import NotificationService
from models.state import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """SmarterProducts Weekly Automation Management Commands"""
    pass


@cli.command()
def migrate():
    """Initialize/migrate database tables"""
    try:
        logger.info("Initializing database tables...")
        state_manager = StateManager()
        logger.info("Database migration completed successfully")
        return True
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return False


@cli.command()
def test_connections():
    """Test all external service connections"""
    logger.info("Testing external service connections...")
    
    success_count = 0
    total_tests = 4
    
    # Test Jira connection
    try:
        logger.info("Testing Jira connection...")
        data_collector = DataCollector()
        # Just initialize the client, don't fetch data
        if data_collector.jira_client:
            logger.info("✅ Jira connection successful")
            success_count += 1
        else:
            logger.error("❌ Jira connection failed")
    except Exception as e:
        logger.error(f"❌ Jira connection failed: {e}")
    
    # Test Google Services connection
    try:
        logger.info("Testing Google Services connection...")
        if data_collector.sheets_client:
            logger.info("✅ Google Services connection successful")
            success_count += 1
        else:
            logger.error("❌ Google Services connection failed")
    except Exception as e:
        logger.error(f"❌ Google Services connection failed: {e}")
    
    # Test OpenAI connection
    try:
        logger.info("Testing OpenAI connection...")
        content_generator = ContentGenerator()
        # Test with a simple prompt
        test_response = content_generator.client.chat.completions.create(
            model="gpt-3.5-turbo",  # Use cheaper model for testing
            messages=[{"role": "user", "content": "Say 'connection test successful'"}],
            max_tokens=10
        )
        if test_response.choices[0].message.content:
            logger.info("✅ OpenAI connection successful")
            success_count += 1
        else:
            logger.error("❌ OpenAI connection failed")
    except Exception as e:
        logger.error(f"❌ OpenAI connection failed: {e}")
    
    # Test SendGrid connection
    try:
        logger.info("Testing SendGrid connection...")
        notification_service = NotificationService()
        if notification_service.sendgrid_client:
            logger.info("✅ SendGrid connection successful")
            success_count += 1
        else:
            logger.error("❌ SendGrid connection failed")
    except Exception as e:
        logger.error(f"❌ SendGrid connection failed: {e}")
    
    logger.info(f"Connection test results: {success_count}/{total_tests} successful")
    return success_count == total_tests


@cli.command()
def generate_weekly_doc():
    """
    Generate Google Doc report (can be run manually or on Tuesday evening)
    
    This creates the Google Doc report. PDF generation and email sending are handled separately.
    - Use 'test-pdf-email' to generate and optionally test email with PDF
    - Use 'run-final-distribution' to generate PDF for manual email distribution
    """
    logger.info("🚀 Starting weekly Google Doc generation...")
    
    state_manager = StateManager()
    
    try:
        # Log job start
        state_manager.log_execution(
            job_type="doc_generation",
            status="running",
            details={"start_time": datetime.now().isoformat()}
        )
        
        # Step 1: Collect data
        logger.info("📊 Collecting data from Jira and Google Sheets...")
        data_collector = DataCollector()
        collected_data = data_collector.collect_all_data()
        
        # Check for data collection errors
        errors = []
        
        # Check Jira data
        jira_data = collected_data.get("jira", {})
        if not jira_data.get("boards"):
            errors.append("❌ No Jira data collected - check board configuration")
        
        # Check Sheets data
        sheets_data = collected_data.get("sheets", {})
        if not sheets_data.get("sheets"):
            errors.append("❌ No Google Sheets data collected - check sheet IDs and permissions")
        else:
            # Check for missing date tabs
            for sheet_id, sheet_data in sheets_data["sheets"].items():
                if not sheet_data.get("tabs"):
                    sheet_title = sheet_data.get("title", "Unknown Sheet")
                    errors.append(f"❌ No date tab found for '{sheet_title}' - expected tab with previous Monday's date")
        
        logger.info("✅ Data collection completed")
        
        # Step 2: Generate content with AI (only if no critical errors)
        report_content = {}
        
        if not errors:
            logger.info("🤖 Generating content with OpenAI...")
            content_generator = ContentGenerator()
            report_content = content_generator.generate_complete_report(collected_data)
            logger.info("✅ Content generation completed successfully")
        else:
            logger.warning("⚠️ Skipping AI generation due to data collection errors")
            report_content = {
                "title": "Weekly Product Team Report - Data Collection Issues",
                "summary": "Data collection encountered errors. Please review and fix before generating final report.",
                "insights": "Unable to generate insights due to data collection issues."
            }
        
        # Step 3: Create/Update Google Doc (always, even with errors)
        logger.info("📝 Creating/updating Google Doc...")
        document_builder = DocumentBuilder()
        
        # Add error information to content if there are errors
        if errors:
            report_content["errors"] = "\n".join(errors)
        else:
            # Add data summary for successful runs
            report_content["raw_data_summary"] = f"""
Jira Boards Processed: {len(jira_data.get('boards', {}))}
Total Jira Issues: {jira_data.get('summary', {}).get('total_issues', 0)}
Google Sheets Processed: {len(sheets_data.get('sheets', {}))}
Total Sheet Tabs: {sheets_data.get('summary', {}).get('total_tabs', 0)}
Total Sheet Rows: {sheets_data.get('summary', {}).get('total_rows', 0)}
"""
        
        doc_id = document_builder.create_or_update_google_doc(report_content)
        doc_url = document_builder.get_document_link(doc_id)
        
        logger.info(f"✅ Google Doc created/updated: {doc_url}")
        
        # Step 4: Save document info
        state_manager.save_doc_id(doc_id, doc_url, "doc_generation")
        
        # Note: Email notifications are disabled - PDF can be generated manually using test-pdf-email command
        
        # Log successful completion
        status = "completed_with_errors" if errors else "completed"
        state_manager.log_execution(
            job_type="doc_generation",
            status=status,
            details={
                "end_time": datetime.now().isoformat(),
                "doc_id": doc_id,
                "doc_url": doc_url,
                "notification_sent": notification_sent,
                "errors_found": len(errors),
                "errors": errors,
                "data_summary": {
                    "jira_boards": len(jira_data.get("boards", {})),
                    "sheets_processed": len(sheets_data.get("sheets", {})),
                    "total_jira_issues": jira_data.get("summary", {}).get("total_issues", 0)
                }
            }
        )
        
        if errors:
            logger.warning("⚠️ Google Doc generated with data collection errors - please review and fix")
        else:
            logger.info("🎉 Google Doc generation completed successfully!")
        
        return True
        
    except Exception as e:
        error_msg = f"Google Doc generation failed: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Log failure
        state_manager.log_execution(
            job_type="doc_generation",
            status="failed",
            error_message=error_msg,
            details={
                "end_time": datetime.now().isoformat(),
                "error_traceback": traceback.format_exc()
            }
        )
        
        # Send error notification
        try:
            notification_service = NotificationService()
            notification_service.send_error_notification(
                error=error_msg,
                context={
                    "job_type": "doc_generation",
                    "timestamp": datetime.now().isoformat(),
                    "error_details": str(e)
                }
            )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification: {notification_error}")
        
        return False

@cli.command()
def run_preview_generation():
    """
    Alias for generate_weekly_doc (for backward compatibility)
    """
    return generate_weekly_doc()


@cli.command()
def run_final_distribution():
    """
    Generate PDF for manual distribution (Wednesday morning job)
    
    Note: This generates the PDF but does not send emails automatically.
    You can manually email the PDF using your preferred email client.
    Use the test-pdf-email command if you want to test email functionality.
    """
    logger.info("🚀 Starting PDF generation for manual distribution...")
    
    state_manager = StateManager()
    
    try:
        # Log job start
        state_manager.log_execution(
            job_type="final",
            status="running",
            details={"start_time": datetime.now().isoformat()}
        )
        
        # Step 1: Get the Google Doc ID from doc generation
        logger.info("📄 Retrieving Google Doc from doc generation...")
        doc_id = state_manager.get_doc_id(job_type="doc_generation")
        doc_url = state_manager.get_doc_url(job_type="doc_generation")
        
        # Fallback to preview job type for backward compatibility
        if not doc_id:
            doc_id = state_manager.get_doc_id(job_type="preview")
            doc_url = state_manager.get_doc_url(job_type="preview")
        
        if not doc_id:
            raise Exception("No Google Doc found from preview generation. Please run preview generation first.")
        
        logger.info(f"✅ Found Google Doc: {doc_id}")
        
        # Step 2: Export Google Doc as PDF
        logger.info("📄 Exporting Google Doc as PDF...")
        document_builder = DocumentBuilder()
        pdf_data = document_builder.export_doc_as_pdf(doc_id)
        
        logger.info(f"✅ PDF export completed successfully ({len(pdf_data)} bytes)")
        logger.info(f"📄 Google Doc URL: {doc_url}")
        logger.info("📧 Note: Email sending is disabled. Please manually email the PDF.")
        
        # Step 3: Save final job info
        state_manager.save_doc_id(doc_id, doc_url, "final")
        
        # Log successful completion
        state_manager.log_execution(
            job_type="final",
            status="completed",
            details={
                "end_time": datetime.now().isoformat(),
                "doc_id": doc_id,
                "doc_url": doc_url,
                "pdf_size_bytes": len(pdf_data),
                "note": "Email sending disabled - manual distribution"
            }
        )
        
        logger.info("🎉 PDF generation completed successfully!")
        logger.info("💡 You can use 'test-pdf-email' command to test email functionality if needed.")
        return True
        
    except Exception as e:
        error_msg = f"Final distribution failed: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Log failure
        state_manager.log_execution(
            job_type="final",
            status="failed",
            error_message=error_msg,
            details={
                "end_time": datetime.now().isoformat(),
                "error_traceback": traceback.format_exc()
            }
        )
        
        # Note: Error notifications are disabled - check logs for errors
        
        return False


@cli.command()
@click.option('--doc-id', help='Google Doc ID to use (optional - will find most recent if not provided)')
@click.option('--email', multiple=True, help='Email address(es) to send to (optional - uses settings if not provided)')
@click.option('--no-send', is_flag=True, help='Generate PDF but do not send email (for testing)')
def test_pdf_email(doc_id, email, no_send):
    """
    Generate PDF from Google Doc and optionally send via email
    
    This command allows you to:
    - Generate a PDF from an existing Google Doc
    - Optionally email the PDF (if --no-send is not used)
    - Works independently of the main report generation workflow
    
    Note: For regular workflow, PDFs are generated manually and emailed separately.
    
    Examples:
        # Generate PDF only (no email)
        python manage.py test-pdf-email --no-send
        
        # Use most recent doc and send to default recipients
        python manage.py test-pdf-email
        
        # Use specific doc ID and send to specific email
        python manage.py test-pdf-email --doc-id 1DURpBMshs4yWsm6riE_jEa4c7ov6Ff86aOy0YuHsIaI --email your@email.com
    """
    logger.info("🚀 Testing PDF generation and email functionality...")
    
    try:
        document_builder = DocumentBuilder()
        notification_service = NotificationService()
        
        # Step 1: Get or find the document ID
        if doc_id:
            logger.info(f"📄 Using provided doc ID: {doc_id}")
            target_doc_id = doc_id
            doc_url = document_builder.get_document_link(target_doc_id)
        else:
            logger.info("📄 Looking for most recent document...")
            state_manager = StateManager()
            
            # Try to get from state manager first
            target_doc_id = state_manager.get_doc_id(job_type="doc_generation")
            if not target_doc_id:
                target_doc_id = state_manager.get_doc_id(job_type="preview")
            
            if target_doc_id:
                logger.info(f"✅ Found doc ID from state manager: {target_doc_id}")
                doc_url = state_manager.get_doc_url(job_type="doc_generation")
                if not doc_url:
                    doc_url = state_manager.get_doc_url(job_type="preview")
                if not doc_url:
                    doc_url = document_builder.get_document_link(target_doc_id)
            else:
                # Try to find most recent doc in Google Drive
                logger.info("📄 Searching for most recent report in Google Drive...")
                # Use the report name generation method via reflection or create a public method
                # For now, we'll construct the report name manually
                from datetime import datetime, timedelta
                today = datetime.now()
                days_until_wednesday = (2 - today.weekday()) % 7
                if days_until_wednesday == 0 and today.weekday() > 2:
                    days_until_wednesday = 7
                wednesday = today + timedelta(days=days_until_wednesday)
                formatted_date = wednesday.strftime("%-m/%-d/%y")
                report_name = f"Weekly Product Team Report {formatted_date}"
                folder_id = settings.google_drive_folder_id
                target_doc_id = document_builder._find_existing_doc(report_name, folder_id)
                
                if target_doc_id:
                    logger.info(f"✅ Found most recent doc: {target_doc_id}")
                    doc_url = document_builder.get_document_link(target_doc_id)
                else:
                    raise Exception("Could not find a document. Please provide --doc-id or run generate-weekly-doc first.")
        
        logger.info(f"📄 Using document: {doc_url}")
        
        # Step 2: Export Google Doc as PDF
        logger.info("📄 Exporting Google Doc as PDF...")
        pdf_data = document_builder.export_doc_as_pdf(target_doc_id)
        
        logger.info(f"✅ PDF export completed successfully ({len(pdf_data)} bytes)")
        
        # Step 3: Send email if not disabled
        if no_send:
            logger.info("📧 Email sending disabled (--no-send flag)")
            logger.info(f"✅ PDF generated successfully ({len(pdf_data)} bytes)")
            logger.info(f"📄 Google Doc URL: {doc_url}")
            logger.info("💡 You can manually email the PDF using your email client")
        else:
            # Determine recipients
            if email:
                recipients = list(email)
                logger.info(f"📧 Sending to specified recipients: {recipients}")
            else:
                recipients = None  # Will use default from settings
                logger.info("📧 Using default recipients from settings")
            
            # Send email with PDF
            logger.info("📧 Sending email with PDF attachment...")
            report_sent = notification_service.send_final_report(pdf_data, doc_url, recipients=recipients)
            
            if report_sent:
                logger.info("✅ Email sent successfully!")
                logger.info(f"📧 Email sent to: {recipients if email else 'default recipients from settings'}")
            else:
                logger.warning("⚠️ Email failed to send")
        
        logger.info("🎉 PDF generation completed!")
        return True
        
    except Exception as e:
        error_msg = f"PDF and email test failed: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False


@cli.command()
@click.option('--days', default=90, help='Number of days of records to keep')
def cleanup_old_records(days):
    """Clean up old execution records"""
    logger.info(f"Cleaning up records older than {days} days...")
    
    try:
        state_manager = StateManager()
        success = state_manager.cleanup_old_records(days_to_keep=days)
        
        if success:
            logger.info("✅ Cleanup completed successfully")
        else:
            logger.error("❌ Cleanup failed")
        
        return success
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return False


@cli.command()
def show_history():
    """Show recent execution history"""
    try:
        state_manager = StateManager()
        history = state_manager.get_execution_history(limit=10)
        
        if not history:
            logger.info("No execution history found")
            return
        
        logger.info("Recent execution history:")
        logger.info("-" * 80)
        
        for record in history:
            status_emoji = {
                'completed': '✅',
                'failed': '❌',
                'running': '🔄',
                'triggered_manually': '🔧'
            }.get(record['status'], '❓')
            
            logger.info(f"{status_emoji} {record['week_identifier']} | {record['job_type'].upper()} | {record['status']} | {record['created_at']}")
            
            if record['error_message']:
                logger.info(f"   Error: {record['error_message']}")
        
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Error showing history: {e}")


if __name__ == '__main__':
    cli()
