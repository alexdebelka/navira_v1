#!/bin/bash

# Navira Deployment Script
# This script prepares your application for deployment to Streamlit Community Cloud

echo "🚀 Navira Deployment Preparation"
echo "================================"

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Run deployment tests
echo "🔍 Running deployment tests..."
python test_deployment.py
if [ $? -ne 0 ]; then
    echo "❌ Deployment tests failed. Please fix the issues before deploying."
    exit 1
fi

echo "✅ All tests passed!"

# Check git status
echo "📋 Checking git status..."
if [ -d ".git" ]; then
    git_status=$(git status --porcelain)
    if [ -n "$git_status" ]; then
        echo "⚠️  You have uncommitted changes:"
        echo "$git_status"
        echo ""
        read -p "Do you want to commit these changes? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git add .
            git commit -m "Prepare for deployment - $(date)"
            echo "✅ Changes committed"
        fi
    else
        echo "✅ No uncommitted changes"
    fi
else
    echo "⚠️  Not a git repository. Consider initializing git for version control."
fi

# Check requirements.txt
echo "📦 Checking requirements.txt..."
if [ -f "requirements.txt" ]; then
    echo "✅ requirements.txt found"
    echo "Contents:"
    cat requirements.txt
else
    echo "❌ requirements.txt not found. Creating one..."
    cat > requirements.txt << EOF
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.15.0
pyarrow>=12.0.0
EOF
    echo "✅ Created requirements.txt"
fi

# Check data files
echo "📁 Checking data files..."
if [ -d "data" ]; then
    data_files=$(find data -name "*.parquet" | wc -l)
    echo "✅ Found $data_files parquet files in data directory"
else
    echo "❌ data directory not found"
    exit 1
fi

# Create .streamlit directory and config if it doesn't exist
echo "⚙️  Setting up Streamlit configuration..."
mkdir -p .streamlit
if [ ! -f ".streamlit/config.toml" ]; then
    cat > .streamlit/config.toml << EOF
[server]
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
EOF
    echo "✅ Created .streamlit/config.toml"
fi

echo ""
echo "🎉 Deployment preparation complete!"
echo ""
echo "Next steps:"
echo "1. Push your code to GitHub:"
echo "   git push origin main"
echo ""
echo "2. Deploy on Streamlit Community Cloud:"
echo "   - Connect your GitHub repository"
echo "   - Set main file path to: app.py"
echo "   - Configure secrets if needed (see DEPLOYMENT_GUIDE.md)"
echo ""
echo "3. Default admin credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo "   ⚠️  Change this password after deployment!"
echo ""
echo "📖 See DEPLOYMENT_GUIDE.md for detailed instructions"
