#!/usr/bin/env bash
# MoltBridge Agent — Initial Setup Script
# Run this in your GitHub Codespace or local environment

set -e

echo "🦞🔗 MoltBridge Agent Setup"
echo "=========================="
echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --quiet

# 3. Create data directories
echo ""
echo "📂 Creating data directories..."
mkdir -p data/{raw,analyzed,reports,logs,state}

# 4. Setup .env
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys!"
else
    echo "✅ .env already exists"
fi

# 5. Verify
echo ""
echo "🔍 Verifying setup..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from utils import log
log.info('Logger working ✅')
from analyzers.sentiment_analyzer import score_text
result = score_text('This is amazing!')
assert result['label'] == 'positive', 'Sentiment test failed'
print('Sentiment analyzer working ✅')
from blockchain.erc8004_client import generate_registration_file
reg = generate_registration_file('test')
assert 'eip-8004' in reg['type'], 'ERC-8004 test failed'
print('ERC-8004 client working ✅')
print()
print('🎉 Setup complete! Next steps:')
print('  1. Edit .env with your MOLTBOOK_API_KEY')
print('  2. Run: python src/main.py --register-moltbook')
print('  3. Run: python src/main.py --full')
"
