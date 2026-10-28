"""CPU-only screening and same-text rhythm diagnostics, without modifying audio."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import sys
from pathlib import Path
support = Path(__file__).parent.parent / 'cosyvoice3-20261026'
if not (support / 'common.py').exists():
    support = Path(__file__).parent.parent
sys.path.insert(0, str(support))
from common import *
setup()
import audio_critic as ac
import numpy as np
from scipy import ndimage

C = O / 'cross-engine-20261026'
P = C / 'rhythm-bridge'
Q = ROOT / 'voice/comparison/cosyvoice2-20261026/rhythm-bridge-20261026'
original = read(C / 'all-models.json')['engines']
cv3 = read(P / 'cv3/manifest.json')['samples']
cv2 = read(Q / 'generated/manifest.json')['samples']
# Mandatory full critic already ran on each fresh batch, including content.
assert read(P / 'cv3/critic/ranking.json')['device'] == 'CPU only'
assert read(Q / 'generated/critic/ranking.json')['device'] == 'CPU only'

arms = {
    'gpt-reference': {'label': 'GPT-V2 ProPlus · 你认可的节奏', 'rows': original['gptv2-e14']},
    'cv3-original': {'label': 'CV3 · 原版对照', 'rows': original['cv3-half']},
    'cv3-light': {'label': 'CV3 · 标点减量', 'rows': [r for r in cv3 if r['trial'] == 'punctuation-only']},
    'cv3-bridge': {'label': 'GPT节奏 → CV3重建声音', 'rows': [r for r in cv3 if r['trial'] == 'gpt-audio-guidance']},
    'cv2-bridge': {'label': 'GPT节奏 → CV2重建声音', 'rows': cv2},
}
critic = ac.Critic()
bank = read(O / 'prompts/manifest.json')['prompts']
anchors = [np.asarray(critic.file(r['path'], r['text'])['embedding']) for r in bank.values()]
threshold = read(O / 'critic/calibration.json')['conservative_threshold']

def profile(row):
    y = ac.load_audio(row['raw'], 24000)
    n = 240
    frames = np.pad(y, (0, (-len(y)) % n)).reshape(-1, n)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    cutoff = max(.0002, np.percentile(rms, 90) * .035)
    active = rms > cutoff
    ix = np.flatnonzero(active)
    assert len(ix)
    start, end = int(ix[0]), int(ix[-1]) + 1
    quiet = ~active[start:end]
    labels, count = ndimage.label(quiet)
    pauses = []
    kept = np.zeros(len(quiet), dtype=float)
    for label in range(1, count + 1):
        ids = np.flatnonzero(labels == label)
        if len(ids) >= 8:  # >=80ms, never called a word-aligned pause.
            pauses.append({'start_s': (start + int(ids[0])) * .01,
                           'end_s': (start + int(ids[-1]) + 1) * .01,
                           'seconds': len(ids) * .01})
            kept[ids] = 1.
    curve = np.interp(np.linspace(0, len(kept) - 1, 200), np.arange(len(kept)), kept)
    return {'duration_seconds': len(y) / 24000, 'energy_threshold': float(cutoff),
            'energy_pause_runs_ge80ms': pauses, 'pause_count': len(pauses),
            'pause_seconds': sum(r['seconds'] for r in pauses),
            'active_span_seconds': (end - start) * .01,
            'pause_fraction_ge80ms': float(kept.mean()),
            'not_word_aligned_and_not_a_breath_detector': True,
            '_normalized_pause_curve': curve.tolist()}

results = {}
for case in read(P / 'plan.json')['chosen_cases']:
    teacher = next(r for r in original['gptv2-e14'] if r['id'] == case)
    tf = critic.file(teacher['raw'], teacher['text'])
    tp = profile(teacher)
    results[case] = []
    for key, arm in arms.items():
        row = next(r for r in arm['rows'] if r.get('base_case', r['id']) == case)
        assert ac.spoken(row['text']) == ac.spoken(teacher['text'])
        assess = ac.assess(critic, row, bank[row['style']], anchors, threshold)
        gf = critic.file(row['raw'], row['text'])
        gp = profile(row)
        gf0 = np.asarray(gf['acoustic']['_f0_st'])
        tf0 = np.asarray(tf['acoustic']['_f0_st'])
        comparison = {
            'same_spoken_words': True,
            'teacher_is_synthetic_GPT_not_real_speaker_ground_truth': True,
            'duration_ratio_to_GPT': gp['duration_seconds'] / tp['duration_seconds'],
            'pause_fraction_delta_to_GPT': gp['pause_fraction_ge80ms'] - tp['pause_fraction_ge80ms'],
            'normalized_time_pause_disagreement': float(np.mean(abs(np.asarray(gp['_normalized_pause_curve']) - np.asarray(tp['_normalized_pause_curve'])))),
            'same_text_voiced_f0_dtw_semitones': ac.dtw(gf0, tf0),
            'median_centered_voiced_f0_dtw_semitones': ac.dtw(gf0 - np.median(gf0), tf0 - np.median(tf0)),
            'no_default_or_checkpoint_selection_from_teacher_distance': True,
        }
        results[case].append({'arm': key, 'label': arm['label'], 'sample': row,
                              'critic': assess, 'pause_profile': gp, 'teacher_comparison': comparison})
        print(json.dumps({'case': case, 'arm': key, 'gate': assess['technical_gate_passed'],
                          'seconds': round(gp['duration_seconds'], 2), 'pause_seconds': round(gp['pause_seconds'], 2),
                          'f0_dtw_to_GPT': comparison['same_text_voiced_f0_dtw_semitones'],
                          'flags': assess['review_flags']}, ensure_ascii=False), flush=True)
    write(P / 'analysis.json', {'cases': results, 'human_quality_verified': False})

write(P / 'screening.json', {
    'CPU_only': not ac.torch.cuda.is_initialized(),
    'cuda_allocated_bytes': ac.torch.cuda.memory_allocated(),
    'all_new_outputs_have_full_four_dimension_critic_and_content_checks': True,
    'no_training_or_default_change': True,
    'human_preference': 'GPT-V2 ProPlus rhythm currently best',
    'limitations': ['Energy pauses are approximate, not forced word alignment.',
                   'Same-text DTW to synthetic GPT measures its similarity, not real-person likeness.',
                   'Voice conversion may alter pitch or preserve artifacts; no automatic listening pass.',
                   'Low artifact risk score is not proof of no electrical sound.'],
})
assert not ac.torch.cuda.is_initialized()
