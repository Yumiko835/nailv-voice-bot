"""Conservative local tail/weak-region repaint EXPERIMENT; untouched core is exact."""

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
if not (support / 'common.py').exists(): support = Path(__file__).parent.parent
sys.path.insert(0, str(support))
from common import *
setup()
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import numpy as np, soundfile as sf, parselmouth
from scipy import signal, ndimage
import audio_critic as ac

P = O / 'cross-engine-20261026/rhythm-bridge'
manifest = {'engine': 'GPT-V2 original with local CV3 replacement', 'samples': [],
            'human_quality_verified': False, 'automatic_artifact_diagnosis': False}
analysis = read(P / 'analysis.json')['cases']

def runs(mask, minimum=1):
    labels, count = ndimage.label(mask)
    return [np.flatnonzero(labels == n) for n in range(1, count + 1)
            if np.count_nonzero(labels == n) >= minimum]

for case, rows in analysis.items():
    source = next(r['sample'] for r in rows if r['arm'] == 'gpt-reference')
    rendered = next(r['sample'] for r in rows if r['arm'] == 'cv3-bridge')
    y, sr = sf.read(source['raw'], dtype='float32'); assert sr == 32000
    z = ac.load_audio(rendered['raw'], sr)
    hop = round(.01 * sr)
    def env(w):
        frames = np.pad(w, (0, (-len(w)) % hop)).reshape(-1, hop)
        return np.sqrt(np.mean(frames * frames, axis=1))
    ey, ez = env(y), env(z)
    # Constant energy-envelope lag only: no time stretch/pitch warp or cutting words.
    lags = range(-8, 9); distances = []
    for lag in lags:
        lo, hi = max(0, -lag), min(len(ey), len(ez) - lag)
        a, b = ey[lo:hi], ez[lo + lag:hi + lag]
        distances.append(float(np.mean((a / max(np.linalg.norm(a), 1e-9) - b / max(np.linalg.norm(b), 1e-9)) ** 2)))
    lag = list(lags)[int(np.argmin(distances))]
    index = np.arange(len(y)) + lag * hop
    valid = (index >= 0) & (index < len(z))
    aligned = y.copy(); aligned[valid] = z[index[valid]]
    rms_cut = max(.0002, float(np.percentile(ey, 90)) * .035)
    active = ey > rms_cut; ids = np.flatnonzero(active); first, last = int(ids[0]), int(ids[-1]) + 1
    quiet = ~active; quiet[:first] = False; quiet[last:] = False
    regions = []
    for ix in runs(quiet, 12):
        # Last110ms before a real quiet gap, and the gap itself. Not a word detector.
        regions.append((max(first * hop, int(ix[0]) * hop - round(.11 * sr)),
                        min(len(y), (int(ix[-1]) + 1) * hop), 'pre-pause-tail-and-gap'))
    regions.append((max(first * hop, last * hop - round(.12 * sr)),
                    min(len(y), last * hop + round(.03 * sr)), 'final-tail'))
    # Only quiet/low-energy, unvoiced, HF-rich runs are optional breath candidates.
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    pitch = snd.to_pitch_ac(time_step=.01, pitch_floor=65, pitch_ceiling=600)
    voiced = np.interp((np.arange(len(ey)) + .5) * .01, pitch.xs(),
                       (pitch.selected_array['frequency'] > 0).astype(float), left=0, right=0) > .5
    _, ts, stft = signal.stft(y, fs=sr, nperseg=1024, noverlap=1024-hop, boundary=None)
    freq = np.fft.rfftfreq(1024, 1 / sr); power = abs(stft) ** 2
    high = power[(freq >= 4500) & (freq <= 10000)].sum(axis=0)
    ratio = high / np.maximum(power.sum(axis=0), 1e-18)
    ratio = np.interp((np.arange(len(ey)) + .5) * .01, ts, ratio)
    low = (ey < np.percentile(ey[active], 65) * .18) & (ey > rms_cut * .7)
    breath = low & ~voiced & (ratio > .18)
    breath[:first] = False; breath[last:] = False
    for ix in runs(breath, 6):
        regions.append((int(ix[0]) * hop, min(len(y), (int(ix[-1]) + 1) * hop), 'weak-unvoiced-HF-candidate'))
    # Merge overlapping intervals before constructing20ms cosine crossfades.
    merged = []
    for lo, hi, kind in sorted(regions):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi); merged[-1][2].append(kind)
        else: merged.append([lo, hi, [kind]])
    mask = np.zeros(len(y), dtype=np.float32)
    for lo, hi, _ in merged:
        if hi <= lo: continue
        w = np.ones(hi-lo, dtype=np.float32); edge = min(round(.02 * sr), len(w)//2)
        fade = (.5 - .5 * np.cos(np.linspace(0, np.pi, edge))).astype(np.float32)
        w[:edge] = fade; w[-edge:] = fade[::-1]; mask[lo:hi] = w
    mask[~valid] = 0
    assert np.mean(mask > 0) <= .22, 'Too much replacement; preserve diagnostic and revise regions instead.'
    use = mask > 0
    scale = min(1., float(np.sqrt(np.mean(y[use] ** 2))) / max(1e-9, float(np.sqrt(np.mean(aligned[use] ** 2)))))
    out = y.copy(); out[use] = y[use]*(1-mask[use]) + aligned[use]*scale*mask[use]
    assert np.array_equal(out[~use], y[~use]) and abs(out).max() < 1
    folder = P / 'local-repaint' / case; folder.mkdir(parents=True, exist_ok=True)
    sf.write(folder / 'native-float.wav', out, sr, subtype='FLOAT')
    sf.write(folder / 'raw.wav', out, sr, subtype='PCM_24')
    gain = min(1., .08 / max(np.sqrt(np.mean(out*out)), 1e-9), .89 / max(abs(out).max(), 1e-9))
    sf.write(folder / 'speech.wav', np.r_[np.zeros(round(.16*sr)), out*gain, np.zeros(round(.32*sr))], sr, subtype='PCM_24')
    row = source | {'id': case+'-local-repaint', 'base_case': case, 'trial': 'local-repaint',
                    'raw': str(folder/'raw.wav'), 'playback': str(folder/'speech.wav'),
                    'sample_rate': sr, 'seconds': len(out)/sr,
                    'source_sha256': sha(source['raw']), 'rendered_sha256': sha(rendered['raw']),
                    'unchanged_sample_fraction': float(np.mean(~use)), 'untouched_core_is_sample_exact': True,
                    'constant_alignment_shift_ms': lag*10, 'replacement_gain_db': float(20*np.log10(scale)),
                    'replacement_regions': [{'start_s': lo/sr, 'end_s': hi/sr, 'kinds': kind} for lo,hi,kind in merged],
                    'limitations': 'Heuristic intervals can contain normal phonemes. Crossfading different waveforms may add artifacts. Not an automatic cure.'}
    manifest['samples'].append(row)
write(P/'local-repaint/manifest.json', manifest)
assert not ac.torch.cuda.is_initialized()
print(json.dumps({'local_candidates': len(manifest['samples']),
                  'unchanged_fractions': [r['unchanged_sample_fraction'] for r in manifest['samples']]}), flush=True)
