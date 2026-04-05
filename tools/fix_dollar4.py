import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\frontend\lib\modules\pos\ui\pos_page.dart")
content = f.read_text(encoding="utf-8")

# The file literally has: '\\$\\$cost'
# We want: '\$$cost'
# In Python string, the file content is: '\\\\$\\\\$cost'
# We want it to be: '\\$$cost'
old = "'\\\\$\\$cost'"
new = "'\\$$cost'"
content = content.replace(old, new)

f.write_text(content, encoding="utf-8")
print("OK")