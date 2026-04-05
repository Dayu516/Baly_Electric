import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\frontend\lib\modules\pos\ui\pos_page.dart")
content = f.read_text(encoding="utf-8")

# Fix sell_price display
content = content.replace(
    "_info('售價', '\\${d['sell_price']}'),",
    "_info('售價', '\\$${d[\"sell_price\"]}'),"
)

# Fix cost_price display
content = content.replace(
    "_info('成本', '\\${d['cost_price']}'),",
    "_info('成本', '\\$${d[\"cost_price\"]}'),"
)

# Fix cost display in supplier list
content = content.replace(
    "'\\$\\$$cost'",
    "'\\$${cost}'"
)

f.write_text(content, encoding="utf-8")
print("OK")