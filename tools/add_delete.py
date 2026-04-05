import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\tools\data-cleaner\app.py")
content = f.read_text(encoding="utf-8")

# 1. 加刪除 API
content = content.replace(
    '@app.put("/api/items/{index}")',
    '''@app.delete("/api/items/{index}")
async def delete_item(index: int):
    """刪除單筆資料。"""
    if index < 0 or index >= len(_state["cleaned"]):
        return JSONResponse({"error": "Index out of range"}, status_code=400)
    removed = _state["cleaned"].pop(index)
    return {"ok": True, "removed": removed.get("name", "")}


@app.put("/api/items/{index}")'''
)

# 2. 操作欄加刪除按鈕
content = content.replace(
    """'<span style="color:#2E7D32;">✓</span>'
        }
      </td>""",
    """'<span style="color:#2E7D32;">✓</span>'
        }
        <button class="btn btn-danger btn-sm" style="margin-left:4px;font-size:11px;padding:2px 8px;" onclick="deleteItem(${globalIdx})">刪除</button>
      </td>"""
)

# 3. 加 deleteItem JS
content = content.replace(
    "function exportCSV(bucket) {",
    """async function deleteItem(index) {
  if (!confirm('確定刪除這筆品項？')) return;
  await fetch(`/api/items/${index}`, { method: 'DELETE' });
  loadItems(currentBucket, currentPage);
  refreshStats();
}

function exportCSV(bucket) {"""
)

f.write_text(content, encoding="utf-8")
print("OK")