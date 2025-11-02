# Google Sheets Setup Guide

## 🔧 **Updated Configuration for Multiple Sheets**

Your system now supports **4 different Google Sheets** with **automatic tab detection**!

### **Configuration in `config.env`:**

```bash
# Multiple Google Sheets (comma-separated IDs)
GOOGLE_SHEETS_IDS=sheet_id_1,sheet_id_2,sheet_id_3,sheet_id_4

# Automatic tab detection (recommended)
GOOGLE_SHEETS_TAB_STRATEGY=auto

# Optional: Manual tab specification (only used if strategy is not "auto")
GOOGLE_SHEETS_TABS=Weekly Metrics,KPIs,Issues
```

## 🎯 **How to Get Sheet IDs**

For each of your 4 Google Sheets:

1. Open the Google Sheet in your browser
2. Look at the URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID_HERE]/edit`
3. Copy the `SHEET_ID_HERE` part
4. Add all 4 IDs to your config, separated by commas

**Example:**
```bash
GOOGLE_SHEETS_IDS=1AbC2DeF3GhI4JkL5MnO,1XyZ9WvU8TsR7QpO6NmL,1PoI9UyT8ReQ7WaS5DfG,1MnB6VcX4ZaS3DfG7HjK
```

## 🤖 **Automatic Tab Detection**

The system will automatically find relevant tabs by:

### **✅ Including Tabs With Keywords:**
- `metrics`, `kpi`, `data`, `weekly`, `monthly`, `report`
- `dashboard`, `summary`, `stats`, `performance`, `issues`
- `tasks`, `progress`, `status`, `tracking`

### **❌ Skipping Tabs With Keywords:**
- `template`, `example`, `backup`, `archive`, `old`, `test`

### **📊 Content-Based Detection:**
- Tabs with substantial data (more than just headers)
- Tabs with at least 3 rows of data
- If no keyword matches, includes all non-empty tabs

## 🔒 **Service Account Setup**

### **Step 1: Create Google Cloud Project**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "SmarterProducts-Weekly"
3. Enable APIs:
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)

### **Step 2: Create Service Account**
1. Go to [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click **"Create Service Account"**
3. Name: `smarterproducts-weekly`
4. Description: `Service account for weekly report automation`
5. Skip role assignment (we'll use sharing)
6. Create and download JSON key

### **Step 3: Share Your Sheets**
**CRITICAL:** Share each of your 4 Google Sheets with the service account:

1. Open each Google Sheet
2. Click **"Share"** button
3. Add the service account email: `smarterproducts-weekly@your-project-123456.iam.gserviceaccount.com`
4. Give **"Editor"** permissions
5. Uncheck **"Notify people"**

### **Step 4: Share Drive Folder**
1. Create/select a Google Drive folder for reports
2. Share with service account email
3. Give **"Editor"** permissions
4. Copy folder ID from URL: `https://drive.google.com/drive/folders/[FOLDER_ID_HERE]`

### **Step 5: Add to Config**
```bash
# Service account JSON (entire file contents as one line)
GOOGLE_CREDENTIALS={"type":"service_account","project_id":"your-project-123456",...}

# Drive folder for reports
GOOGLE_DRIVE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j

# Your 4 sheet IDs
GOOGLE_SHEETS_IDS=sheet1_id,sheet2_id,sheet3_id,sheet4_id

# Use automatic detection
GOOGLE_SHEETS_TAB_STRATEGY=auto
```

## 🧪 **Testing Your Setup**

Once configured, you can test with:

```bash
# Test Google Sheets connection
python test_google_sheets.py

# Test full data collection
python manage.py test-connections
```

## 📊 **What the System Will Collect**

For each of your 4 sheets, the system will:

1. **Detect Relevant Tabs** automatically based on content and naming
2. **Extract Headers** from the first row
3. **Collect All Data** from relevant tabs
4. **Provide Sample Data** for AI analysis
5. **Track Metrics** (row counts, column counts, etc.)

## 🔄 **Data Structure**

The collected data will be organized as:

```json
{
  "sheets": {
    "sheet_id_1": {
      "title": "Project Metrics Dashboard",
      "tabs": {
        "Weekly KPIs": {
          "headers": ["Date", "Metric", "Value"],
          "rows": [["2024-11-01", "Completion Rate", "85%"]],
          "row_count": 25,
          "column_count": 3
        }
      }
    }
  }
}
```

## 🎯 **Benefits of This Approach**

1. **Flexible**: Works with any number and type of sheets
2. **Automatic**: No need to manually specify tab names
3. **Intelligent**: Skips irrelevant tabs automatically
4. **Scalable**: Easy to add more sheets later
5. **Robust**: Handles missing tabs gracefully

## ❓ **Common Issues**

### **"Permission denied" errors:**
- Ensure service account email is shared on ALL 4 sheets
- Check that permissions are "Editor" not "Viewer"

### **"Sheet not found" errors:**
- Verify sheet IDs are correct (from URLs)
- Ensure sheets are not deleted or moved

### **"No tabs detected" errors:**
- Check that sheets have data (not just empty tabs)
- Verify tab names don't contain skip keywords

---

**Next Steps:** Set up your service account and add the 4 sheet IDs to your `config.env` file!
