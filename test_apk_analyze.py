import zipfile
import os
import shutil
from src.core.file_analyzer import analyze_file

apk_dir = 'test_apk'
os.makedirs(apk_dir, exist_ok=True)

with open(os.path.join(apk_dir, 'AndroidManifest.xml'), 'w', encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="utf-8"?><manifest package="com.test.app"></manifest>')

os.makedirs(os.path.join(apk_dir, 'META-INF'), exist_ok=True)
with open(os.path.join(apk_dir, 'META-INF', 'MANIFEST.MF'), 'w', encoding='utf-8') as f:
    f.write('Manifest-Version: 1.0')

with zipfile.ZipFile('test.apk', 'w') as z:
    for root, dirs, files in os.walk(apk_dir):
        for file in files:
            full_path = os.path.join(root, file)
            arc_name = os.path.relpath(full_path, apk_dir)
            z.write(full_path, arc_name)

shutil.rmtree(apk_dir, ignore_errors=True)

print('Created test.apk')
print('Testing analyze_file...')
result = analyze_file(os.path.join(os.getcwd(), 'test.apk'))
print('Analysis result:', result)

os.remove('test.apk')
