# SmarterProducts-Weekly

An automated weekly reporting system that generates comprehensive reports from Jira boards and Google Sheets data, enhanced with AI-generated insights.

## 🚀 Features

- **Automated Data Collection**: Pulls data from multiple Jira boards and Google Sheets
- **AI-Powered Content**: Uses OpenAI to generate summaries and strategic insights
- **Two-Stage Workflow**: 
  - **Tuesday Evening**: Creates Google Doc for review/editing
  - **Wednesday Morning**: Converts to PDF and emails to stakeholders
- **Heroku Deployment**: Fully configured for Heroku with GitHub integration
- **Email Notifications**: Professional HTML emails with attachments
- **State Management**: PostgreSQL database tracks execution history

## 📋 Prerequisites

Before setting up the project, you'll need:

1. **Heroku Account** with CLI installed
2. **GitHub Account** (for deployment integration)
3. **Jira Account** with API access
4. **Google Cloud Project** with service account
5. **OpenAI API Account**
6. **SendGrid Account** (or Heroku SendGrid add-on)

## 🛠️ Setup Instructions

### 1. Clone and Deploy to Heroku

```bash
# Clone the repository
git clone https://github.com/Bradshawrc93/SmarterProducts-Weekly.git
cd SmarterProducts-Weekly

# Create Heroku app
heroku create your-app-name

# Add required add-ons
heroku addons:create heroku-postgresql:mini
heroku addons:create sendgrid:starter
heroku addons:create scheduler:standard

# Connect to GitHub for auto-deployment
# (Do this via Heroku Dashboard: Deploy > GitHub > Connect Repository)
```

### 2. Configure Environment Variables

Copy `config.env.example` and fill in your actual values:

```bash
# Copy the example file
cp config.env.example .env
```

Then set each variable in Heroku:

```bash
# Jira Configuration
heroku config:set JIRA_BASE_URL=https://yourcompany.atlassian.net
heroku config:set JIRA_API_TOKEN=your_jira_api_token
heroku config:set JIRA_EMAIL=your_email@company.com
heroku config:set JIRA_BOARDS=PROJ-1,PROJ-2,PROJ-3

# Google Services (paste entire JSON as one line)
heroku config:set GOOGLE_CREDENTIALS='{"type":"service_account","project_id":"..."}'
heroku config:set GOOGLE_DRIVE_FOLDER_ID=your_folder_id
heroku config:set GOOGLE_SHEETS_ID=your_sheets_id
heroku config:set GOOGLE_SHEETS_TABS="Weekly Metrics,KPIs,Issues"

# OpenAI
heroku config:set OPENAI_API_KEY=sk-your_openai_key
heroku config:set OPENAI_MODEL=gpt-4

# Email Configuration
heroku config:set PREVIEW_EMAIL_RECIPIENTS=your_email@company.com
heroku config:set FINAL_EMAIL_RECIPIENTS=stakeholder1@company.com,stakeholder2@company.com
heroku config:set FROM_EMAIL=reports@yourcompany.com
heroku config:set FROM_NAME="Weekly Reports System"

# Application Settings
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
heroku config:set ENVIRONMENT=production
```

### 3. Set Up Scheduled Jobs

Configure Heroku Scheduler to run the automation:

```bash
# Open scheduler dashboard
heroku addons:open scheduler

# Add these two jobs in the Heroku Dashboard:

# Tuesday Preview Job (10 PM UTC - adjust for your timezone)
# Schedule: 0 22 * * 2
# Command: python manage.py run-preview-generation

# Wednesday Final Job (8 AM UTC - adjust for your timezone)  
# Schedule: 0 8 * * 3
# Command: python manage.py run-final-distribution
```

### 4. Initialize Database

```bash
# Deploy the app first, then initialize database
git push heroku main

# Initialize database tables
heroku run python manage.py migrate

# Test connections
heroku run python manage.py test-connections
```

## 🔧 Configuration Details

### Required API Keys and Setup

#### 1. Jira API Token
- Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
- Create a new token
- Use your email and token for authentication

#### 2. Google Service Account
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project or select existing
- Enable Google Docs API and Google Drive API
- Create a service account and download JSON key
- Share your Google Drive folder and Sheets with the service account email

#### 3. OpenAI API Key
- Go to [OpenAI Platform](https://platform.openai.com/api-keys)
- Create a new API key
- Ensure you have sufficient credits/quota

#### 4. SendGrid (Email)
- Heroku SendGrid add-on provides `SENDGRID_API_KEY` automatically
- Or create account at [SendGrid](https://sendgrid.com/) for custom setup

### Customizing AI Prompts

Edit the prompt templates to customize AI-generated content:

- `config/prompts/summary_prompt.txt` - Weekly summary generation
- `config/prompts/insights_prompt.txt` - Strategic insights generation

The prompts support these variables:
- `{jira_data}` - Formatted Jira board data
- `{sheets_data}` - Formatted Google Sheets data  
- `{week_start}` - Start date of current week
- `{week_end}` - End date of current week

## 📊 Usage

### Automatic Operation
The system runs automatically on schedule:
- **Tuesday 10 PM**: Generates Google Doc preview
- **Wednesday 8 AM**: Sends PDF report via email

### Manual Commands

```bash
# Test all connections
heroku run python manage.py test-connections

# Manually run preview generation
heroku run python manage.py run-preview-generation

# Manually run final distribution  
heroku run python manage.py run-final-distribution

# View execution history
heroku run python manage.py show-history

# Clean up old records
heroku run python manage.py cleanup-old-records --days 90
```

### Web Interface

The app provides a simple web interface:
- `https://your-app.herokuapp.com/` - Health check
- `https://your-app.herokuapp.com/status` - System status and history
- `https://your-app.herokuapp.com/config` - Current configuration (sanitized)

## 🔍 Monitoring and Troubleshooting

### Logs
```bash
# View recent logs
heroku logs --tail

# View logs for specific component
heroku logs --source app --tail
```

### Common Issues

1. **"No Google Doc found from preview generation"**
   - Ensure Tuesday preview job ran successfully
   - Check logs: `heroku logs --grep "preview"`

2. **API Connection Failures**
   - Verify all environment variables are set correctly
   - Test connections: `heroku run python manage.py test-connections`

3. **Email Not Sending**
   - Check SendGrid add-on is active
   - Verify recipient email addresses are correct
   - Check SendGrid dashboard for delivery status

4. **Google Services Errors**
   - Ensure service account has access to Drive folder and Sheets
   - Verify Google APIs are enabled in Cloud Console
   - Check service account JSON format in environment variable

### Error Notifications

The system automatically sends error notifications to preview email recipients when jobs fail. Check your email for detailed error information.

## 🔄 Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/Bradshawrc93/SmarterProducts-Weekly.git
cd SmarterProducts-Weekly

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp config.env.example .env
# Edit .env with your values

# Initialize database (requires PostgreSQL)
python manage.py migrate

# Test connections
python manage.py test-connections

# Run Flask app locally
python app.py
```

### Project Structure

```
├── app.py                  # Main Flask application
├── manage.py              # CLI commands for scheduled jobs
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku process definition
├── runtime.txt           # Python version
├── config/
│   ├── settings.py       # Configuration management
│   └── prompts/          # OpenAI prompt templates
├── services/
│   ├── data_collector.py # Jira & Google Sheets integration
│   ├── content_generator.py # OpenAI integration
│   ├── document_builder.py # Google Docs & PDF generation
│   └── notification.py   # Email service
├── models/
│   └── state.py          # Database models
└── templates/            # Future: HTML templates
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the logs: `heroku logs --tail`
2. Review the troubleshooting section above
3. Create an issue in the GitHub repository