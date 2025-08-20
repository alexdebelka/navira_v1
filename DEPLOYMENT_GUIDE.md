# Navira Deployment Guide for Streamlit Community Cloud

This guide will help you deploy your Navira application to Streamlit Community Cloud successfully.

## 🚀 Quick Deployment Steps

### 1. Fix Data Loading Paths ✅

The data loading paths have been updated to work in both local and deployed environments. The `navira/data_loader.py` file now uses dynamic paths that resolve relative to the script location.

### 2. Authentication Setup

Your app currently uses a SQLite-based authentication system. For deployment, you have two options:

#### Option A: Keep SQLite (Recommended for simplicity)

The current SQLite system will work on Streamlit Community Cloud. The database file will be created automatically when the app starts.

**Default admin credentials:**
- Username: `admin`
- Password: `admin123`

**⚠️ Security Note:** Change the default admin password after first deployment!

#### Option B: Use Streamlit Secrets (For enhanced security)

If you want to use Streamlit's secrets management:

1. **Create a secrets configuration:**
   ```yaml
   # In Streamlit Community Cloud Secrets
   database:
     path: "users.db"
   
   admin:
     username: "admin"
     email: "admin@navira.com"
     password: "your_secure_password_here"
   
   session:
     expiry_hours: 24
     cleanup_interval: 3600
   ```

2. **Update auth.py to use secrets:**
   ```python
   # Add this to the top of auth.py
   import streamlit as st
   
   # Use secrets if available, otherwise use defaults
   if hasattr(st, 'secrets') and st.secrets:
       DB_PATH = st.secrets.get("database", {}).get("path", "users.db")
       ADMIN_USERNAME = st.secrets.get("admin", {}).get("username", "admin")
       ADMIN_EMAIL = st.secrets.get("admin", {}).get("email", "admin@navira.com")
       ADMIN_PASSWORD = st.secrets.get("admin", {}).get("password", "admin123")
   else:
       DB_PATH = "users.db"
       ADMIN_USERNAME = "admin"
       ADMIN_EMAIL = "admin@navira.com"
       ADMIN_PASSWORD = "admin123"
   ```

### 3. Environment Variables (Optional)

You can set these environment variables in Streamlit Community Cloud:

- `NAVIRA_OUT_DIR`: Path to processed data directory (defaults to `data/processed`)
- `NAVIRA_DEBUG`: Set to "true" for debug logging

### 4. Data Files

Ensure your data files are included in your repository:

```
navira/
├── data/
│   ├── establishments.parquet
│   ├── annual_procedures.parquet
│   └── processed/
└── ...
```

### 5. Requirements

Make sure your `requirements.txt` includes all necessary dependencies:

```txt
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.15.0
pyarrow>=12.0.0
```

## 🔧 Deployment Checklist

- [ ] Data files are in the `data/` directory
- [ ] `requirements.txt` is up to date
- [ ] Authentication system is configured
- [ ] All import paths are relative
- [ ] No hardcoded file paths
- [ ] Error handling is in place

## 🐛 Common Issues and Solutions

### Issue: "File not found" errors
**Solution:** The data loader now uses dynamic paths. Ensure your data files are in the correct location.

### Issue: Authentication not working
**Solution:** Check that the SQLite database can be created. The app will create it automatically.

### Issue: Import errors
**Solution:** All imports now use relative paths. Make sure your file structure matches the expected layout.

## 🔒 Security Recommendations

1. **Change default admin password** immediately after deployment
2. **Use environment variables** for sensitive configuration
3. **Regularly update dependencies** to patch security vulnerabilities
4. **Monitor access logs** if available

## 📊 Monitoring and Analytics

The app includes analytics tracking. To enable it in production:

1. Set up your analytics service (Google Analytics, Mixpanel, etc.)
2. Configure the tracking in `analytics_integration.py`
3. Add analytics keys to Streamlit secrets if needed

## 🚀 Deployment Commands

```bash
# 1. Commit your changes
git add .
git commit -m "Prepare for deployment"

# 2. Push to GitHub
git push origin main

# 3. Deploy on Streamlit Community Cloud
# - Connect your GitHub repository
# - Set the main file path to: app.py
# - Configure any secrets if needed
```

## 📞 Support

If you encounter issues during deployment:

1. Check the Streamlit Community Cloud logs
2. Verify all data files are present
3. Test the app locally with the same configuration
4. Review the error messages in the deployment logs

---

**Note:** This deployment guide assumes you're using the updated code with the fixes applied. The data loading paths and authentication system have been made deployment-friendly.
