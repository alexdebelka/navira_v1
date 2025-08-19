# 🧹 Manual Project Cleanup Guide

## 🗑️ **Files You Can Safely Delete**

### **Test Files (Development Only)**
```bash
rm test_auth.py
rm test_navigation.py
rm quick_test.py
rm tests/test_data_pipeline.py
```

### **Development/Setup Files**
```bash
rm create_test_users.py
rm setup_auth.py
```

### **Redundant Documentation**
```bash
rm AUTHENTICATION_README.md
rm IMPLEMENTATION_SUMMARY.md
rm ANALYTICS_INTEGRATION_GUIDE.md
```

### **System Files**
```bash
rm .DS_Store
rm -rf __pycache__/
rm -rf pages/__pycache__/
rm -rf tests/__pycache__/
rm -rf navira/__pycache__/
rm -rf lib/__pycache__/
```

### **Optional Analytics Files**
*These are alternatives to Google Analytics 4 - keep if you want options:*
```bash
# Only delete if you're only using GA4
rm analytics_custom.py
rm analytics_mixpanel.py
```

## 🔒 **Files You MUST Keep**

### **Core Application**
- `app.py` - Main application
- `main.py` - Hospital explorer
- `auth.py` - Authentication system
- `auth_wrapper.py` - Auth wrapper
- `sidebar_utils.py` - Sidebar navigation
- `user_management.py` - User management CLI

### **Pages**
- `pages/dashboard.py` - Hospital dashboard
- `pages/national.py` - National overview
- `pages/hospital_explorer.py` - Hospital explorer page

### **Analytics (GA4)**
- `analytics_ga4.py` - Google Analytics 4 integration
- `analytics_integration.py` - Analytics integration helper
- `analytics_dashboard.py` - Analytics dashboard
- `GOOGLE_ANALYTICS_SETUP.md` - GA4 setup guide
- `TRACKING_ENHANCEMENT_GUIDE.md` - Comprehensive tracking guide

### **Data & Configuration**
- `users.db` - User database
- `session.json` - Session storage
- `requirements.txt` - Dependencies
- `Makefile` - Build commands
- `scripts/build_parquet.py` - Data processing script

### **Documentation**
- `README.md` - Main documentation
- `LICENSE` - License file

## 🚀 **Quick Cleanup Commands**

### **Option 1: Automated Cleanup**
```bash
python cleanup_project.py
```

### **Option 2: Manual Cleanup (Safe)**
```bash
# Delete test files
rm test_auth.py test_navigation.py quick_test.py
rm tests/test_data_pipeline.py

# Delete development files
rm create_test_users.py setup_auth.py

# Delete redundant docs
rm AUTHENTICATION_README.md IMPLEMENTATION_SUMMARY.md ANALYTICS_INTEGRATION_GUIDE.md

# Delete system files
rm .DS_Store
rm -rf __pycache__/ pages/__pycache__/ tests/__pycache__/ navira/__pycache__/ lib/__pycache__/

# Optional: Delete alternative analytics
rm analytics_custom.py analytics_mixpanel.py
```

### **Option 3: Nuclear Cleanup (Everything)**
```bash
# Delete everything except essential files
find . -name "*.py" -not -name "app.py" -not -name "main.py" -not -name "auth.py" -not -name "auth_wrapper.py" -not -name "sidebar_utils.py" -not -name "user_management.py" -not -name "analytics_ga4.py" -not -name "analytics_integration.py" -not -name "analytics_dashboard.py" -not -name "cleanup_project.py" -delete

# Delete test files
rm -rf tests/

# Delete cache
find . -name "__pycache__" -type d -exec rm -rf {} +

# Delete system files
rm -f .DS_Store
```

## 📊 **Expected Results**

After cleanup, your project should have:

### **Core Files (Essential)**
```
navira/
├── app.py                          # Main application
├── main.py                         # Hospital explorer
├── auth.py                         # Authentication
├── auth_wrapper.py                 # Auth wrapper
├── sidebar_utils.py                # Sidebar navigation
├── user_management.py              # User management
├── analytics_ga4.py                # GA4 integration
├── analytics_integration.py        # Analytics helper
├── analytics_dashboard.py          # Analytics dashboard
├── pages/
│   ├── dashboard.py                # Hospital dashboard
│   ├── national.py                 # National overview
│   └── hospital_explorer.py        # Hospital explorer
├── users.db                        # User database
├── session.json                    # Session storage
├── requirements.txt                # Dependencies
├── Makefile                        # Build commands
├── scripts/
│   └── build_parquet.py           # Data processing
├── GOOGLE_ANALYTICS_SETUP.md       # GA4 setup guide
├── TRACKING_ENHANCEMENT_GUIDE.md   # Tracking guide
├── README.md                       # Main documentation
└── LICENSE                         # License
```

### **Optional Files (Keep if needed)**
```
navira/
├── analytics_custom.py             # Custom analytics (optional)
├── analytics_mixpanel.py           # Mixpanel integration (optional)
└── cleanup_project.py              # This cleanup script
```

## ⚠️ **Important Notes**

1. **Backup First**: Always backup your project before cleanup
2. **Test After Cleanup**: Run your app to ensure everything works
3. **Keep Analytics**: Don't delete GA4 files if you want analytics
4. **Version Control**: Use git to track changes and revert if needed

## 🎯 **After Cleanup**

1. **Test the application**:
   ```bash
   streamlit run app.py
   ```

2. **Verify analytics**:
   - Check Google Analytics dashboard
   - Test tracking events

3. **Update documentation**:
   - Update README.md if needed
   - Remove references to deleted files

---

**🎉 Your project will be much cleaner and easier to maintain!**
