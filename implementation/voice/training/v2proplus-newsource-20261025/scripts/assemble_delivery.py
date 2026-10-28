
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from common import *
import numpy as np,soundfile as sf,runpy,shutil
basepath=T/'generated/test/manifest.json';retrypath=T/'generated/retry-rp135/manifest.json';base=read(basepath);retries={r['id']:r for r in read(retrypath)['samples']};oldcheck={r['id']:r for r in read(T/'generated/test/technical-verification.json')['checks']};retrycheck={r['id']:r for r in read(T/'generated/retry-rp135/content-check.json')};rows=[];checks=[]
for original in base['samples']:
 key=original['id']
 if key=='excited-oral':continue
 row=retries[key] if key in ['daily','excited','gentle'] else original
 check=retrycheck[key] if key in ['daily','excited','gentle'] else oldcheck[key];error=check.get('error',check.get('full_phoneme_error_retaining_repeats'));assert error<=.25,(key,check)
 y,sr=sf.read(row['raw'],dtype='float32');assert sr==32000 and sf.info(row['raw']).subtype=='PCM_24' and np.isfinite(y).all() and sha(row['raw'])==row['raw_sha256'];assert 1<row['seconds']<12
 rows.append(row);checks.append({'id':key,'expected':row['text'],'recognized':check['recognized'],'full_phoneme_error_retaining_repeats':error,'human_sound_quality_verified':False})
assert len(rows)==11 and len({r['style'] for r in rows})==10
bankpath=T/'prompts/manifest.json';bank=read(bankpath)
if not (T/'prompts/before-optional-alternate-quarantine.json').exists():shutil.copy2(bankpath,T/'prompts/before-optional-alternate-quarantine.json')
bank['alternates']['excited_oral'].update(enabled=False,inference_state='Quarantined: early EOS on the same test sentence across RP1.10/RP1.35 and seeds42/73/137; no new source selected.',original_audio_preserved=True);bank['active_reference_count']=10;bank['archived_reference_count']=1;write(bankpath,bank)
listing=base|{'version':'proplus-listening-v2-content-corrected','samples':rows,'source_manifests':[{'path':str(basepath),'sha256':sha(basepath)},{'path':str(retrypath),'sha256':sha(retrypath)}],'active_reference_count':10,'archived_optional_reference_count':1,'excluded_failed_demo_ids':['excited-oral'],'content_checks':checks,'human_quality_verified':False};write(T/'listening.json',listing);verify_protected()
deployment=read(T/'deployment-first-tests.json');deployment.update(ready=True,content_check_warning_ids=[],prompts_manifest_sha256=sha(bankpath),active_reference_clips=10,archived_optional_reference_clips=1,generated_test_samples=11,human_quality_verified=False);write(T/'deployment.json',deployment)
status('proplus-ready',GPT_epochs=10,SoVITS_epochs=10,gpt_default_epoch=6,sovits_default_epoch=10,emotion_styles=10,reference_clips=10,archived_optional_reference_clips=1,test_samples=11,human_quality_verified=False)
write(T/'completion.json',{'complete':True,'both_stages_trained_epochs':10,'technical_validation_complete':True,'content_checks_passed':11,'human_listening_pending':True,'active_reference_clips':10,'archived_optional_reference_clips':1,'page':'http://127.0.0.1:49850/voice-proplus','output':str(T)})
runpy.run_path(str(Path(__file__).parent/'write_delivery_notes.py'),run_name='__main__')
with (T/'使用说明.md').open('a',encoding='utf-8') as stream:stream.write('\n## 本轮生成修正\n\n一般句子恢复官方重复惩罚1.35；明确的“妈妈妈妈”测试保留1.10。初次的日常、开心、温柔异常结果未覆盖，正常版本另存于 generated/retry-rp135。页面展示11条内容核对后的结果，不能据此认定无电音或像本人。口癖备用参考曾在多次种子下过早结束，音频与失败输出保留，暂不自动使用；10种主要情绪仍各有1段现有参考。\n')
print(json.dumps({'active_styles':10,'active_references':10,'preserved_optional_reference':1,'test_samples':11,'human_audio_quality_pending':True},ensure_ascii=False))
