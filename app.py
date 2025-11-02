"""
Main Flask application for SmarterProducts Weekly Automation
"""
import logging
import os
from flask import Flask, jsonify, request
from datetime import datetime
from config.settings import settings
from models.state import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = settings.secret_key

# Initialize state manager
state_manager = StateManager()


@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'SmarterProducts Weekly Automation',
        'timestamp': datetime.now().isoformat(),
        'environment': settings.environment
    })


@app.route('/status')
def status():
    """Get system status and recent execution history"""
    try:
        history = state_manager.get_execution_history(limit=5)
        
        return jsonify({
            'status': 'operational',
            'recent_executions': history,
            'configuration': {
                'jira_boards': settings.jira_boards,
                'google_sheets_tabs': settings.google_sheets_tabs,
                'preview_recipients': len(settings.preview_email_recipients),
                'final_recipients': len(settings.final_email_recipients)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/trigger/<job_type>', methods=['POST'])
def trigger_job(job_type):
    """Manually trigger a job (for testing purposes)"""
    if job_type not in ['preview', 'final']:
        return jsonify({'error': 'Invalid job type. Use "preview" or "final"'}), 400
    
    try:
        # This would typically be handled by the scheduler
        # For now, just log the trigger request
        logger.info(f"Manual trigger requested for job: {job_type}")
        
        state_manager.log_execution(
            job_type=job_type,
            status="triggered_manually",
            details={'triggered_by': request.remote_addr}
        )
        
        return jsonify({
            'message': f'{job_type.title()} job triggered successfully',
            'job_type': job_type,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error triggering job {job_type}: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/config')
def get_config():
    """Get current configuration (sanitized)"""
    try:
        config = {
            'environment': settings.environment,
            'timezone': settings.timezone,
            'jira': {
                'base_url': settings.jira_base_url,
                'boards': settings.jira_boards,
                'email': settings.jira_email
            },
            'google': {
                'drive_folder_id': settings.google_drive_folder_id,
                'sheets_id': settings.google_sheets_id,
                'sheets_tabs': settings.google_sheets_tabs
            },
            'openai': {
                'model': settings.openai_model
            },
            'email': {
                'from_email': settings.from_email,
                'from_name': settings.from_name,
                'preview_recipients_count': len(settings.preview_email_recipients),
                'final_recipients_count': len(settings.final_email_recipients)
            },
            'scheduling': {
                'preview_schedule': settings.preview_schedule,
                'final_schedule': settings.final_schedule
            }
        }
        
        return jsonify(config)
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            '/ - Health check',
            '/status - System status',
            '/config - Configuration',
            '/trigger/<job_type> - Manual job trigger (POST)'
        ],
        'timestamp': datetime.now().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500


if __name__ == '__main__':
    # This is for local development only
    # In production, Gunicorn will handle the WSGI serving
    port = int(os.environ.get('PORT', 5000))
    debug = settings.environment == 'development'
    
    logger.info(f"Starting Flask app on port {port}, debug={debug}")
    app.run(host='0.0.0.0', port=port, debug=debug)
