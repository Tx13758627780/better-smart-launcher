import hashlib
import json
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent / 'pydeps'))
from loguru import logger
logger.remove()
from androguard.core.apk import APK
from androguard.core.dex import DEX

OUT = ROOT.parent.parent / 'outputs'
base = OUT / 'Smart-Launcher-6.6-021-known-injections-removed.apk'
new = OUT / 'Smart-Launcher-6.6-021-cleaned-pinyin-search.apk'
old_apk, new_apk = APK(str(base)), APK(str(new))
assert set(old_apk.get_permissions()) == set(new_apk.get_permissions())
assert old_apk.get_certificates_der_v3() == new_apk.get_certificates_der_v3()
assert sorted(new_apk.get_dex_names()) == ['classes.dex','classes2.dex']
changes, added_classes, counts = [],[],{}
forbidden = re.compile(r'com[./]huonew|com[./]bamen|gamekillerapp|apisyncs|AppComponentFactoryImpl|Lod/ccc/d/f/a/dd|lllllll[./]lll[./]l|sdk\.bin|com[./]omg[./]bamboo|BambooServer|ResponseInvoker|IOServer')
with zipfile.ZipFile(base) as before, zipfile.ZipFile(new) as after:
    assert after.testzip() is None
    assert len(after.namelist()) == len(set(after.namelist()))
    assert set(before.namelist()) - set(after.namelist()) == {'assets/dexopt/baseline.prof','assets/dexopt/baseline.profm'}
    assert set(after.namelist()) - set(before.namelist()) == {'assets/local-pinyin-LICENSE.txt'}
    archive_changes = [n for n in before.namelist() if n in after.namelist() and before.read(n) != after.read(n)]
    assert set(archive_changes) == {'classes.dex','classes2.dex'}
    assert before.read('AndroidManifest.xml') == after.read('AndroidManifest.xml')
    for name in ['classes.dex','classes2.dex']:
        raw = after.read(name)
        assert raw[12:32] == hashlib.sha1(raw[32:]).digest()
        assert struct.unpack_from('<I',raw,8)[0] == zlib.adler32(raw[12:]) & 0xffffffff
        olddex, newdex = DEX(before.read(name)), DEX(raw)
        assert not any(forbidden.search(s) for s in newdex.get_strings())
        oldclasses = {c.get_name():c for c in olddex.get_classes()}
        newclasses = {c.get_name():c for c in newdex.get_classes()}
        assert not (set(oldclasses) - set(newclasses))
        added_classes.extend(set(newclasses) - set(oldclasses))
        compared = 0
        for cname, oldclass in oldclasses.items():
            newclass = newclasses[cname]
            assert oldclass.get_superclassname() == newclass.get_superclassname()
            assert oldclass.get_interfaces() == newclass.get_interfaces()
            assert oldclass.get_access_flags() == newclass.get_access_flags()
            assert [(f.get_name(),f.get_descriptor(),f.get_access_flags()) for f in oldclass.get_fields()] == [(f.get_name(),f.get_descriptor(),f.get_access_flags()) for f in newclass.get_fields()]
            oldmethods = {(m.get_name(),m.get_descriptor()):m for m in oldclass.get_methods()}
            newmethods = {(m.get_name(),m.get_descriptor()):m for m in newclass.get_methods()}
            assert set(oldmethods) == set(newmethods)
            for key, oldm in oldmethods.items():
                newm = newmethods[key]
                assert oldm.get_access_flags() == newm.get_access_flags()
                oldc, newc = oldm.get_code(),newm.get_code()
                assert bool(oldc) == bool(newc)
                if not oldc:
                    continue
                compared += 1
                assert oldc.get_registers_size() == newc.get_registers_size()
                assert oldc.get_ins_size() == newc.get_ins_size()
                assert oldc.get_tries_size() == newc.get_tries_size()
                oldins = [(i.get_name(),i.get_output()) for i in oldc.get_bc().get_instructions()]
                newins = [(i.get_name(),i.get_output()) for i in newc.get_bc().get_instructions()]
                if oldins != newins:
                    assert len(oldins) == len(newins)
                    diff = [{'index':i,'old':a,'new':b} for i,(a,b) in enumerate(zip(oldins,newins)) if a!=b]
                    changes.append({'class':cname,'method':key,'differences':diff})
        counts[name] = {'original_classes':len(oldclasses),'final_classes':len(newclasses),'original_methods_compared':compared}
        for cname in set(newclasses)-set(oldclasses):
            assert cname.startswith('LLocalPinyin')
            for m in newclasses[cname].get_methods():
                if m.get_code():
                    for instruction in m.get_code().get_bc().get_instructions():
                        text = instruction.get_output()
                        assert not re.search(r'Ljava/net/|Ldalvik/system/|Ljava/lang/Thread;|Ljava/util/concurrent/Executors;',text)
    assert set(added_classes) == {'LLocalPinyin;','LLocalPinyin$1;','LLocalPinyin$NameForms;',
        'LLocalPinyinData;','LLocalPinyinData$Table;'}
    assert len(changes) == 2, [(c['class'],c['method'],len(c['differences'])) for c in changes]
    assert {c['class'] for c in changes} == {'Lqw2;','Lf13;'}
    for changed in changes:
        assert changed['method'] == ('invokeSuspend','(Ljava/lang/Object;)Ljava/lang/Object;')
        assert len(changed['differences']) == 1, changed
        only = changed['differences'][0]
        assert only['old'][0] == 'invoke-virtual' and 'Lpl7;->g(Ljava/lang/String; Ljava/lang/String; Ljava/lang/String;)I' in only['old'][1], changed
        assert only['new'][0] == 'invoke-static' and 'LLocalPinyin;->score(Lpl7; Ljava/lang/String; Ljava/lang/String; Ljava/lang/String;)I' in only['new'][1], changed
        assert only['old'][1].split(', Lpl7;->')[0] == only['new'][1].split(', LLocalPinyin;->')[0], changed

result = {'sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'zip_integrity':'passed','dex_checksums':'passed',
    'manifest_byte_identical':True,'same_certificate':True,'added_permissions':[],
    'classes_and_method_checks':counts,'changed_original_code':changes,'new_classes':sorted(added_classes),
    'known_injected_code_absent':True,'new_code_has_no_network_loader_or_thread_creation':True,'device_tested':False}
(ROOT / 'verification-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))

