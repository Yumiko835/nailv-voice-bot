
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
import numpy as np,soundfile as sf
from scipy import signal
O=T/'inference-diagnosis-20261025';rows=read(O/'decoder-matrix.json');results=[]
def stats(y):
 _,_,s=signal.stft(y,32000,nperseg=1024,noverlap=768);power=np.abs(s)**2;high=power[192:].sum(0);allpower=power.sum(0);rms=np.sqrt(np.mean(np.pad(y,(0,(-len(y))%640)).reshape(-1,640)**2,axis=1));active=rms>max(.001,rms.max()*.1);flat=np.exp(np.log(power+1e-14).mean(0))/(power.mean(0)+1e-14)
 return {'rms':float(np.sqrt(np.mean(y*y))),'active_rms':float(np.sqrt(np.mean(rms[active]**2))),'median_spectral_flatness':float(np.median(flat)),'above_6khz_energy_fraction':float(high.sum()/allpower.sum()),'peak':float(np.abs(y).max()),'finite':bool(np.isfinite(y).all())}
for row in rows:
 y,sr=sf.read(row['native_float'],dtype='float32');assert sr==32000;results.append({'id':row['id'],**stats(y)})
write(O/'numeric-checks.json',results)
comparisons=[]
for source in ['mama-rp135','gentle-rp135']:
 for model in ['official','e10']:
  x,_=sf.read(O/'fixed-semantic'/(source+'-'+model+'-fp16')/'native-float.wav');y,_=sf.read(O/'fixed-semantic'/(source+'-'+model+'-fp32')/'native-float.wav');comparisons.append({'id':source+'-'+model,'fp16_fp32_correlation':float(np.corrcoef(x,y)[0,1]),'difference_rms_to_fp32_db':float(20*np.log10(np.sqrt(np.mean((x-y)**2))/np.sqrt(np.mean(y*y))))})
write(O/'precision-comparison.json',comparisons)
chosen=[r for r in rows if r['id'] in ['gentle-rp135-official-fp32','gentle-rp135-e2-fp32','gentle-rp135-e10-fp32']];target=min(next(z for z in results if z['id']==r['id'])['active_rms'] for r in chosen)*.9
auditions=[]
for r in chosen:
 y,sr=sf.read(r['native_float'],dtype='float32');rms=next(z for z in results if z['id']==r['id'])['active_rms'];gain=min(1.,target/rms);out=O/('listen-'+r['acoustic_model']+'.wav');sf.write(out,np.r_[np.zeros(5120,dtype='float32'),y*gain,np.zeros(10240,dtype='float32')],sr,subtype='PCM_24');auditions.append({'model':r['acoustic_model'],'path':str(out),'gain_db':float(20*np.log10(gain)),'same_active_rms':target,'positive_gain':False})
write(O/'auditions.json',auditions);print(json.dumps({'stats':results,'precision':comparisons,'auditions':auditions},ensure_ascii=False,indent=2))
