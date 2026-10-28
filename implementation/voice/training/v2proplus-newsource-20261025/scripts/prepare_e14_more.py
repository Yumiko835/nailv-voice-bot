
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

O = T / 'e14-more-sentences-20261025'
assert not (O / 'requests.json').exists(), 'Preserve existing audition; do not overwrite.'
models = read(T / 'selected-models.json')
assert models['gpt']['epoch'] == 6 and models['sovits_epoch'] == 14
assert models['gpt']['sha256'] == 'd429536133baeff4b0676e56a1a341ed1cde43374d102540e71835c4e7821169'
assert models['sovits']['sha256'] == '17b5b27b418109dd308cf7bc9ebb382ddfe14b0d723d3e632b92b81043528aa4'
for key in ['gpt', 'sovits']:
    assert sha(models[key]['path']) == models[key]['sha256']
assert models['inference'] == {'acoustic_precision':'float32', 'noise_scale':0.5, 'repetition_penalty':1.35, 'output_EQ':None}
write(O / 'selected-models-before.json', models)
write(O / 'deployment-before.json', read(T / 'deployment.json'))
write(O / 'feedback.json', {
    'user_feedback':'我觉得原14轮最好，用原14轮生成更多的句子我听听',
    'choice':'original acoustic epoch14; ProPlus GPT epoch6; no weight merging, no EQ',
    'new_samples_human_quality_verified':False,
})
models['sovits_selection_basis'] = 'User compared original e14/e16/e18/e20, merges and EQ, and explicitly chose ORIGINAL e14 on 2026-10-25. Keep original e14 + ProPlus GPT e6, noise_scale0.5, no merge or EQ. More sentence auditions requested; no claim of noise-free output.'
write(T / 'selected-models.json', models)
deployment = read(T / 'deployment.json')
deployment.update(models=models, SoVITS_epochs_trained=20,
    known_quality_issue='User prefers original e14 among tested candidates; residual electric timbre/naturalness still require listening. No EQ or merged weights adopted.',
    original_e14_user_selected=True)
write(T / 'deployment.json', deployment)

rows = [
    ('a01','日常闲聊','daily','回到聊天','嗯，来了。你刚刚说到哪儿了？我去倒了杯水。'),
    ('a02','日常闲聊','daily','自然接话','先别着急，你慢慢说，我听着呢。'),
    ('a03','日常闲聊','daily','随口一说','我本来就打算出门的，结果看了一眼外面，又坐回来了。'),
    ('a04','日常闲聊','daily','思索与口癖','那个，等一下啊，我先想想这个东西放哪儿了。'),
    ('b01','重复词与连读','daily','妈妈妈妈','妈妈妈妈，这么喜欢叫妈妈吗？'),
    ('b02','重复词与连读','daily','好好好与等等我','好好好，我知道啦。你先等等我，别一口气全说完呀。'),
    ('b03','重复词与连读','gentle','慢慢来','慢慢来，慢慢来，先把这句话说清楚。'),
    ('b04','重复词与连读','explaining','不是不是','不是不是，我不是说你，我是说刚刚那个东西。'),
    ('c01','咬字与句尾','serious','近似发音','先说清楚，这件事情到底是谁说的呀？'),
    ('c02','咬字与句尾','daily','数字与时间','今天星期四，下午三点半，别又记成四点三十分了。'),
    ('c03','咬字与句尾','daily','短句收尾','行吧，那就这么说好了。剩下的事情，我们回头再商量。'),
    ('c04','咬字与句尾','surprised','疑问与对照','你是不是又把那两个放反了？左边是新的，右边才是旧的。'),
    ('d01','稍长的聊天','daily','连贯讲一件小事','我刚刚在找那个充电器，桌上找了一遍，包里也翻了一遍。结果你猜怎么着？它就插在旁边，我还一直拿着手机的另一头。'),
    ('d02','稍长的聊天','explaining','解释前因后果','我的意思是，我们先把已经确定的事情讲清楚，剩下的不着急下结论。你刚刚说的那个也有道理，只是放在这件事情上，可能还要再想一想。'),
    ('e01','十种语气','daily','日常闲聊','今天也没干什么，收拾了一下桌子，然后就坐这儿发了一会儿呆。'),
    ('e02','十种语气','excited','开心兴奋','哎，真的可以！我刚刚就是随手试了一下，居然一下就弄好了。'),
    ('e03','十种语气','teasing','调侃戏谑','你刚刚还说不想看呢，怎么现在凑得比谁都近啊？'),
    ('e04','十种语气','gentle','温柔低语','累了就先歇一会儿吧，水就放在旁边，不用急着把事情都做完。'),
    ('e05','十种语气','lazy','慵懒随性','嗯，我还想再坐一会儿。外面太阳那么大，等晚一点再出去吧。'),
    ('e06','十种语气','tsundere','傲娇小抱怨','我都跟你说了两遍了，你还问。算了，过来，我再给你讲一遍。'),
    ('e07','十种语气','surprised','惊讶疑惑','啊？你已经弄完了？不是，你什么时候开始做的，我怎么都没看见？'),
    ('e08','十种语气','serious','认真严肃','这个我们还是说清楚一点，你可以有不同的想法，但别替别人下结论。'),
    ('e09','十种语气','sigh','无奈叹气','唉，刚收拾好，又乱了。行吧，先吃饭，回来再慢慢弄。'),
    ('e10','十种语气','explaining','解释确认','对，我说的是旁边那个小盒子，不是你手里这个。你看一下，是不是正好能放进去？'),
]
samples = []
for index, (short, group, style, title, text) in enumerate(rows):
    samples.append({'id':'e14-more-'+short, 'group':group,
        'audition_label':short.upper()+' · '+title, 'style':style,
        'text':text, 'seed':42, 'temperature':0.85})
write(O / 'requests.json', {'purpose':'Additional original e14 listening sentences; not streamer quotations.', 'samples':samples})
write(O / 'reference-manifest.json', read(T / 'prompts/manifest.json'))
write(O / 'settings.json', {'gpt_epoch':6, 'sovits_epoch':14, 'models':models,
    'reference_manifest_sha256':sha(O / 'reference-manifest.json'),
    'temperature':0.85, 'seed':42, 'repetition_penalty':1.35,
    'weight_merging':False, 'output_EQ':None, 'no_additional_training':True,
    'sentences_are_authored_test_copy_not_streamer_quotes':True})
status('proplus-comparing-continuation', completed=0, total=len(samples),
    activity='generating-original-e14-more-sentences', gpt_epoch=6, default_acoustic_epoch=14)
print(json.dumps({'out':str(O), 'samples':len(samples)}, ensure_ascii=False))
