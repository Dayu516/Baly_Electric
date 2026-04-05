import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\frontend\lib\modules\pos\ui\pos_page.dart")
content = f.read_text(encoding="utf-8")

# Fix line 656: _info('售價', '$${d['sell_price']}') → _info('售價', '\${d['sell_price']}')
content = content.replace(
    "_info('售價', '$$",
    "_info('售價', '\\$"
)
content = content.replace(
    "_info('成本', '$$",
    "_info('成本', '\\$"
)

# Fix line 690: '$$cost' → '\$$cost' but need '\$cost' actually
# The issue is $$ in Dart means literal $, but we want string interpolation
# Actually '$$cost' should be '\$${cost}' for "$55" display
content = content.replace("'$$cost'", "'\\\$\$cost'")

f.write_text(content, encoding="utf-8")
print("OK")