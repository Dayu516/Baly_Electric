#!/bin/sh
# 安裝 pre-push hook — push 前自動跑 make lint + make unit

HOOK_FILE="$(git rev-parse --git-dir)/hooks/pre-push"

cat > "$HOOK_FILE" << 'EOF'
#!/bin/sh
echo "Running pre-push checks (make lint + make unit)..."
cd backend && make lint && make unit

if [ $? -ne 0 ]; then
  echo "❌ Pre-push checks failed. Push aborted."
  exit 1
fi

echo "✅ Checks passed. Proceeding push."
EOF

chmod +x "$HOOK_FILE"
echo "✅ pre-push hook installed at $HOOK_FILE"
