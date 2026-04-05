import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\frontend\lib\modules\pos\ui\pos_page.dart")
content = f.read_text(encoding="utf-8")

# Line 690: '\\$\\$cost' should be '\\$${cost}' in the actual file content
# In the file it appears as: '\\$\$cost'
# We want it to be: '\$${cost}'
# In a Dart string, \$ is literal dollar, ${cost} is interpolation
content = content.replace(
    "cost != null ? '\\\\\\$\\$cost' : '未報價'",
    "cost != null ? '\\$\\$cost' : '未報價'"
)

f.write_text(content, encoding="utf-8")
print("OK")