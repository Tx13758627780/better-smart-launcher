import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
STUDIO = Path(r'C:\Program Files\Android\Android Studio')
JAVA = STUDIO / 'jbr/bin/java.exe'
JAVAC = STUDIO / 'jbr/bin/javac.exe'
TOOLS = Path(r'C:\Users\Xi\AppData\Local\Android\Sdk\build-tools\36.1.0')
ANDROID = Path(r'C:\Users\Xi\AppData\Local\Android\Sdk\platforms\android-36.1\android.jar')
BASE = WORK.parent / 'outputs/Smart-Launcher-6.6-021-known-injections-removed.apk'
FINAL = WORK.parent / 'outputs/Smart-Launcher-6.6-021-cleaned-pinyin-search.apk'
BASE_SHA = 'ee8482d8c8ec8d22e08461c22645566ac919a5246d9c91e45d8348c8257ff762'
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
BUILD = ROOT / 'full-build'
if BUILD.exists():
    assert BUILD.parent == ROOT and BUILD.name == 'full-build'
    shutil.rmtree(BUILD)
CLASSES, DEX, PATCHER, PATCHED = (BUILD / name for name in ['classes','dex','patcher','patched'])
for directory in [CLASSES, DEX, PATCHER, PATCHED]:
    directory.mkdir(parents=True)

def run(label,args,env=None):
    result = subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)
    (ROOT / (label + '.log')).write_text(result.stdout + result.stderr,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(label + ': ' + result.stdout + result.stderr)
    print(label + ': passed',flush=True)
    return result.stdout + result.stderr

run('generate-data',[sys.executable,ROOT / 'generate_data.py'])
run('matcher-compile',[JAVAC,'-encoding','UTF-8','-d',CLASSES,
    ROOT / 'LocalPinyin.java',ROOT / 'LocalPinyinData.java',ROOT / 'pl7.java',ROOT / 'PinyinTest.java'])
tests = run('matcher-tests',[JAVA,'-cp',CLASSES,'PinyinTest'])
helpers = sorted(CLASSES.glob('LocalPinyin*.class'))
assert {p.name for p in helpers} == {'LocalPinyin.class','LocalPinyin$1.class','LocalPinyin$NameForms.class',
    'LocalPinyinData.class','LocalPinyinData$Table.class'}
run('helper-d8',[JAVA,'-cp',TOOLS / 'lib/d8.jar','com.android.tools.r8.D8','--min-api','28',
    '--release','--lib',ANDROID,'--classpath',CLASSES,'--output',DEX,*helpers])
cp = ';'.join(str(p) for p in [STUDIO / 'plugins/android/lib/smali-dexlib2-3.0.9.jar',
    STUDIO / 'lib/module-intellij.libraries.guava.jar',STUDIO / 'plugins/android/lib/jsr305-2.0.1.jar',PATCHER])
run('patcher-compile',[JAVAC,'-encoding','UTF-8','-cp',cp,'-d',PATCHER,ROOT / 'PatchSearchDex.java'])
patches = run('patch-original-search',[JAVA,'-cp',cp,'PatchSearchDex',BASE,DEX / 'classes.dex',PATCHED])
removed = []
with zipfile.ZipFile(BASE) as before, zipfile.ZipFile(BUILD / 'unsigned.apk','w') as after:
    for info in before.infolist():
        if info.filename in ['assets/dexopt/baseline.prof','assets/dexopt/baseline.profm']:
            removed.append(info.filename)
            continue
        data = before.read(info)
        if info.filename in ['classes.dex','classes2.dex']:
            data = (PATCHED / info.filename).read_bytes()
        new = copy.copy(info)
        new.extra = b''
        after.writestr(new,data)
    after.writestr('assets/local-pinyin-LICENSE.txt',(ROOT / 'pypinyin-LICENSE.txt').read_bytes(),compress_type=zipfile.ZIP_DEFLATED)

run('zipalign',[TOOLS / 'zipalign.exe','-P','16','-f','4',BUILD / 'unsigned.apk',BUILD / 'aligned.apk'])
env = dict(os.environ,APK_CLEANUP_KEY_PASSWORD=(WORK / 'cleanup-local-signing.password').read_text(encoding='ascii'))
signer = [JAVA,'-jar',TOOLS / 'lib/apksigner.jar']
run('sign',signer + ['sign','--ks',WORK / 'cleanup-local-signing.p12','--ks-key-alias','local-cleanup',
    '--ks-pass','env:APK_CLEANUP_KEY_PASSWORD','--key-pass','env:APK_CLEANUP_KEY_PASSWORD',
    '--min-sdk-version','28','--v1-signing-enabled','false','--v2-signing-enabled','true',
    '--v3-signing-enabled','true','--v4-signing-enabled','false','--out',FINAL,BUILD / 'aligned.apk'],env)
verify = run('verify-signature',signer + ['verify','--verbose','--print-certs',FINAL])
assert 'cb64f0ffe37685fa2dc42e38deba1d87f4ccd2f0c924d7b746746ca91542a1e2' in verify
assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in verify
run('verify-v2',signer + ['verify','--min-sdk-version','24','--max-sdk-version','27','--verbose',FINAL])
run('verify-align',[TOOLS / 'zipalign.exe','-c','-P','16','4',FINAL])
run('verify-package',[TOOLS / 'aapt2.exe','dump','badging',FINAL])
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
summary = {'base_sha256':BASE_SHA,'file':FINAL.name,'sha256':hashlib.sha256(FINAL.read_bytes()).hexdigest(),
    'size':FINAL.stat().st_size,'new_permissions':[],'same_signing_certificate':True,'tests':tests,
    'patch_summary':patches,'removed_stale_optimization_profiles':removed,'runtime_device_test':False}
(ROOT / 'build-result.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))

