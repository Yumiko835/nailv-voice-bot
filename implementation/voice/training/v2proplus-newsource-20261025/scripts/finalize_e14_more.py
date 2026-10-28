
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
import numpy as np
import soundfile as sf

O = T / 'e14-more-sentences-20261025'
manifest = read(O / 'generated/manifest.json')
requests = read(O / 'requests.json')['samples']
checks = read(O / 'generated/content-check.json')
selected = read(T / 'selected-models.json')
assert len(manifest['samples']) == len(requests) == len(checks) == 24
assert [r['id'] for r in requests] == [r['id'] for r in manifest['samples']]
assert selected == manifest['models']
assert selected['gpt']['epoch'] == 6 and selected['sovits_epoch'] == 14
assert selected['inference']['output_EQ'] is None
for key in ['gpt','sovits']:
    assert sha(selected[key]['path']) == selected[key]['sha256']
assert sha(O / 'reference-manifest.json') == read(O/'settings.json')['reference_manifest_sha256']
formats = []
for r, check in zip(manifest['samples'], checks):
    assert check['id'] == r['id'] and check['raw_sha256'] == r['raw_sha256']
    assert r['settings']['repetition_penalty'] == 1.35
    assert r['settings']['speed_factor'] == 1 and r['settings']['temperature'] == 0.85
    assert r['sample_rate'] == 32000 and not r['lossy_encoding'] and not r['output_resampling']
    assert r['trimmed_samples'] == 0 and r['playback_gain_db'] <= 0
    assert r['no_output_denoising'] and all(e['acoustic_model_dtype'] == 'torch.float32' and e['noise_scale'] == .5 for e in r['acoustic_decode_events'])
    for kind in ['raw','playback']:
        assert sha(r[kind]) == r[kind+'_sha256']
        info = sf.info(r[kind]); y, sr = sf.read(r[kind], dtype='float32')
        assert sr == 32000 and info.subtype == 'PCM_24' and info.channels == 1
        assert len(y) > 0 and np.isfinite(y).all() and np.max(np.abs(y)) < 1
        formats.append({'id':r['id'],'kind':kind,'frames':len(y),'sample_rate':sr,'subtype':info.subtype,'peak':float(np.max(np.abs(y)))})
    if r['id'] in ['e14-more-b02','e14-more-b03']:
        r['content_note'] = '建议重点听重复词是否完整、尾音是否拖长；自动转写有差异，需实际试听确认。'
    else:
        r['content_note'] = ''
manifest.update(purpose='More original e14 audition sentences requested by user; no new training, merged weights or EQ.',
    sentences_are_authored_test_copy_not_streamer_quotes=True,
    content_check_path=str(O / 'generated/content-check.json'),
    focus_ids=['e14-more-b02','e14-more-b03'], human_quality_verified=False)
write(O / 'manifest.json', manifest)
verify_protected()
write(O / 'technical-verification.json', {'samples':24,
    'total_audio_seconds':sum(r['seconds'] for r in manifest['samples']),
    'active_emotions':sorted({r['style'] for r in manifest['samples']}),
    'models_sha256_verified':True, 'protected_sources_unchanged':True,
    'no_weight_merging':True, 'no_output_EQ':True,
    'raw_and_playback_formats':formats,
    'automatic_recognition_is_not_human_acceptance':True,
    'human_sound_quality_verified':False})
lines=['# 原第14轮 · 更多句子试听', '',
    '用户在14/16/18/20轮及提亮对照后选择原14轮。本组全部固定原SoVITS第14轮＋本次ProPlus GPT第6轮，噪声采样量0.5、重复惩罚1.35、灵活度0.85，不插值、不均衡、不变速。', '',
    '24句为试听文案，并非主播原话。自动识别仅辅助检查，不能证明电音消失或音色自然。B02/B03自动转写的重复词有差异，B03时长偏长，均保留原生成音频待试听；没有改字、拼接或掩盖差异。', '',
    '| 编号 | 类别/语气 | 文字 | 时长 |', '|---|---|---|---|']
for r in manifest['samples']:
    lines.append(f"| {r['audition_label']} | {r['group']} / {r['label']} | {r['text']} | {r['seconds']:.2f}秒 |")
(O / '试听清单.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
status('proplus-ready', gpt_epoch=6, default_acoustic_epoch=14,
    completed_acoustic_epoch=20, original_e14_user_selected=True,
    expanded_e14_sentences=24, human_electrical_noise_resolved=False)
print(json.dumps({'samples':24, 'seconds':sum(r['seconds'] for r in manifest['samples']), 'native_format':'32k PCM24', 'models_verified':True},ensure_ascii=False))
