"""Read-only localhost browser for the independent new-Milkgreen library. No model calls."""
from __future__ import annotations

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import argparse,contextlib,json,os,re,sqlite3,threading,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

PAGE=r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新奶绿 · 人物资料库</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f7f5;color:#243c35;font:15px/1.75 "Microsoft YaHei",system-ui,sans-serif}header{background:#1d4a40;color:white;padding:30px max(24px,calc((100vw - 1160px)/2))}header small{color:#bcd8cc}h1{font-size:30px;margin:4px 0}main{max-width:1160px;margin:24px auto;padding:0 22px}.notice{background:#fff5db;border:1px solid #e6d9ad;padding:14px 18px;border-radius:9px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}.stat{background:white;padding:16px 20px;border:1px solid #d9e4dd;border-radius:9px}.stat b{display:block;font-size:25px}.stat span{font-size:13px;color:#61776f}nav{display:flex;gap:8px;border-bottom:1px solid #cfddd5;margin:24px 0 20px;padding-bottom:12px;flex-wrap:wrap}button,select,input{font:inherit}button{cursor:pointer;border:1px solid #b9cec2;border-radius:7px;background:white;color:#1d4a40;padding:9px 18px}button.active,button.primary{background:#24634f;color:white;border-color:#24634f}form{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input{flex:1;min-width:220px;padding:11px 14px;border:1px solid #b9cec2;border-radius:7px}select{padding:10px;border:1px solid #b9cec2;border-radius:7px;background:white}article{background:white;border:1px solid #d7e3db;border-radius:10px;padding:22px;margin:15px 0}article h2{font-size:19px;margin:6px 0 10px}.meta{font-size:13px;color:#61776f}.pill{display:inline-block;border-radius:20px;background:#edf3ed;color:#47654e;font-size:12px;padding:2px 10px;margin-right:8px}.draft{background:#fff1d3;color:#8c681d}pre{font:14px/1.8 "Microsoft YaHei",system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f5;border-radius:6px;padding:14px}a{color:#17647a;text-underline-offset:3px}details{margin-top:12px}summary{cursor:pointer}code{font-size:12px;overflow-wrap:anywhere}.muted{color:#647b72}.pager{display:flex;gap:12px;align-items:center;margin:20px 0 40px}[hidden]{display:none!important}#identity{white-space:pre-wrap;background:white;border:1px solid #d7e3db;padding:24px;border-radius:9px}footer{margin:30px 0 40px;font-size:13px;color:#647b72}@media(max-width:680px){.stats{grid-template-columns:repeat(2,1fr)}header{padding:22px}h1{font-size:25px}article{padding:17px}}
</style></head><body><header><small>独立项目 / 本地浏览 / 不调用付费模型</small><h1>新奶绿 · 人物资料库</h1><div>找原文、核对出处，再决定哪些材料能代表她。</div></header><main><div class="notice">全量保留版已获用户认可，7,621条文字已生成正式语义索引。这里的浏览与关键词搜索仍在本地完成。原始字幕、存疑与排除内容各自保存；整版认可不代表逐条回听过全部音源。</div><div class="stats" id="stats"></div><p class="muted" id="coverage-note"></p><nav><button data-tab="raw" class="active">全文原文</button><button data-tab="candidates">人物资料</button><button data-tab="identity">人设骨架</button></nav>
<section id="raw"><p class="muted">关键词检索，例如：香菜、做饭、小时候。支持空格分隔多个关键词；这里不是自然语言问答。</p><form id="raw-form"><input id="raw-query" placeholder="输入要找的关键词" aria-label="搜索原字幕"><select id="genre" aria-label="片名分类"><option value="all">全部来源</option><option value="talk">杂谈 / 电台提示</option><option value="unspecified">普通 / 未分类</option><option value="game">游戏提示</option><option value="watchalong">看片提示</option><option value="music">歌曲提示</option></select><button class="primary">搜索原文</button></form><div id="raw-note" class="muted"></div><div id="raw-results"></div><div class="pager" id="raw-pager" hidden><button id="raw-prev">上一页</button><span id="raw-page"></span><button id="raw-next">下一页</button></div></section>
<section id="candidates" hidden><p class="muted">已采纳资料和原始证据可在下方查看。勾选“只看本次补充”查看全量补充批次；存疑与排除区单独保存，不并入正式索引。</p><form id="candidate-form"><select id="category" aria-label="人物资料类别"><option value="facts">事实 / 偏好 / 名词</option><option value="corpus">经历 / 观点</option><option value="behaviors">归纳的互动情境</option><option value="episodes">原始互动片段</option><option value="held">待回听 / 有争议</option><option value="rejected">已排除候选</option></select><label><input type="checkbox" id="new-only" style="min-width:auto;flex:none">只看本次补充</label><input id="candidate-query" placeholder="筛选内容或条目ID" aria-label="筛选人物资料"><button class="primary">查看资料</button></form><div id="candidate-note" class="muted"></div><div id="candidate-results"></div><div class="pager" id="candidate-pager" hidden><button id="candidate-prev">上一页</button><span id="candidate-page"></span><button id="candidate-next">下一页</button></div></section><section id="identity" hidden></section><footer>全文与候选各自保存，原文和时间戳可追溯。这个阅读器不会登录QQ、发送消息或调用模型。</footer></main><script>
const $=id=>document.getElementById(id);let rawOffset=0,candidateOffset=0;const pageSize=20;
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function stamp(ms){const sec=Math.floor(ms/1000);return [Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(x=>String(x).padStart(2,'0')).join(':')}
function link(text,url){const a=el('a',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a}
async function api(path){const r=await fetch(path);if(!r.ok)throw Error((await r.json()).error||'读取失败');return r.json()}
async function loadStats(){const d=await api('/api/stats');const values=[[d.raw.records_with_text,'有字录播'],[d.coverage?.completed_windows,'已分析长文本'],[d.approved_count,'已采纳资料（含互动分类）'],[d.production.held_candidates,'存疑候选（单独保留）']];$('coverage-note').textContent=d.coverage?.all_input_processed?'全部 '+d.coverage.total_windows+' 段均已分析；'+Number(d.coverage.covered_cues_without_overlap).toLocaleString()+' 行字幕覆盖核验，无漏段。4条空记录没有文字可提炼。':'正在读取覆盖报告。';$('stats').replaceChildren(...values.map(v=>{const box=el('div',undefined,'stat');box.append(el('b',Number(v[0]||0).toLocaleString()),el('span',v[1]));return box}))}
function switchTab(name){for(const tab of ['raw','candidates','identity'])$(tab).hidden=tab!==name;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));if(name==='candidates')loadCandidates();if(name==='identity')api('/api/identity').then(d=>$('identity').textContent=d.text).catch(showError)}
function showError(e){alert(e.message)}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));
async function loadRaw(){const q=$('raw-query').value.trim();if(!q){$('raw-note').textContent='请输入一个或几个关键词。';return}const d=await api('/api/search?'+new URLSearchParams({q,genre:$('genre').value,offset:rawOffset}));$('raw-note').textContent=d.results.length?'结果保留原始错字和说话人不确定性；点“查看上下文”可看连续字幕。':'没找到匹配原文。可缩短关键词，或用空格分开。';$('raw-results').replaceChildren();for(const r of d.results){const card=el('article');card.append(el('span','未核对原字幕','pill draft'),el('span',r.genre_label,'pill'),el('h2',r.title),el('div',r.date.slice(0,10)+' · '+stamp(r.start_ms)+'–'+stamp(r.end_ms)+' · '+r.source_id,'meta'),el('pre',r.excerpt));const details=el('details');details.append(el('summary','查看这段及前后上下文'));details.ontoggle=async()=>{if(details.open&&!details.dataset.loaded){const data=await api('/api/context?id='+r.id);details.append(el('pre',data.cues.map(x=>stamp(x.start_ms)+'  '+x.text).join('\n')));details.dataset.loaded='1'}};card.append(details,link('打开录播，在这个时间附近核对',r.jump_url));$('raw-results').append(card)}$('raw-pager').hidden=!d.results.length&&!rawOffset;$('raw-prev').disabled=rawOffset===0;$('raw-next').disabled=!d.has_more;$('raw-page').textContent='第 '+(rawOffset/pageSize+1)+' 页'}
$('raw-form').onsubmit=e=>{e.preventDefault();rawOffset=0;loadRaw().catch(showError)};$('raw-prev').onclick=()=>{rawOffset=Math.max(0,rawOffset-pageSize);loadRaw().catch(showError)};$('raw-next').onclick=()=>{rawOffset+=pageSize;loadRaw().catch(showError)};
async function loadCandidates(){const d=await api('/api/candidates?'+new URLSearchParams({category:$('category').value,q:$('candidate-query').value,new_only:$('new-only').checked?'1':'0',offset:candidateOffset}));$('candidate-note').textContent='本类共 '+d.total+' 条。';$('candidate-results').replaceChildren();for(const r of d.items){const card=el('article');card.append(el('span',r.review==='approved'?'用户认可':(r.machine_review?.verdict==='reject'?'已排除':'存疑 · 待核对'),'pill'+(r.review==='approved'?'':' draft')),el('h2',r.text||r.name||r.id),el('code',r.id));if(r.response_posture)card.append(el('p','回应姿态：'+r.response_posture));if(r.samples?.length){const s=r.samples[0];card.append(el('p','情境概括（非逐字问题）：'+s.user),el('pre',s.reply))}if(r.machine_review?.reason)card.append(el('p','机器核对：'+r.machine_review.reason,'muted'));for(const ref of (r.source_refs||[]).slice(0,4)){const s=d.sources[ref.source_id];const details=el('details');details.append(el('summary',(s?.date?.slice(0,10)||'')+' · '+(s?.title||ref.source_id)+' · '+stamp(ref.start_seconds*1000)),el('pre',ref.quote));if(s?.source_url)details.append(link('核对来源',s.source_url+(s.source_url.includes('?')?'&':'?')+'t='+Math.floor(ref.start_seconds||0)));card.append(details)}$('candidate-results').append(card)}$('candidate-pager').hidden=!d.total;$('candidate-prev').disabled=candidateOffset===0;$('candidate-next').disabled=candidateOffset+pageSize>=d.total;$('candidate-page').textContent='第 '+(candidateOffset/pageSize+1)+' 页'}
$('candidate-form').onsubmit=e=>{e.preventDefault();candidateOffset=0;loadCandidates().catch(showError)};$('category').onchange=()=>{candidateOffset=0;loadCandidates().catch(showError)};$('new-only').onchange=()=>{candidateOffset=0;loadCandidates().catch(showError)};$('candidate-prev').onclick=()=>{candidateOffset=Math.max(0,candidateOffset-pageSize);loadCandidates().catch(showError)};$('candidate-next').onclick=()=>{candidateOffset+=pageSize;loadCandidates().catch(showError)};loadStats().catch(showError);
</script></body></html>'''

def create_handler(root):
    dbpath=root/'data/raw-index/library.sqlite3'
    def db():
        conn=sqlite3.connect('file:'+str(dbpath).replace('\\','/')+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row;return conn
    def read(relative,default):
        try:return json.loads((root/relative).read_text(encoding='utf-8'))
        except (OSError,ValueError):return default
    def category_items(category):
        paths={'facts':'persona/facts.json','corpus':'persona/corpus.json','behaviors':'persona/behaviors.json','episodes':'persona/behavior-episodes.json','held':'review/待回听或争议候选.json','rejected':'review/已排除候选.json'}
        return read(paths.get(category,'persona/facts.json'),{}).get('items',[])
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data,status=200,mime='application/json; charset=utf-8'):
            raw=data.encode('utf-8') if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            try:self.route()
            except (ValueError,sqlite3.Error) as exc:self.send({'error':str(exc)[:180]},400)
            except (OSError,KeyError,TypeError):self.send({'error':'资料暂不可读，请稍后重试。'},500)
        def route(self):
            parsed=urllib.parse.urlsplit(self.path);args=urllib.parse.parse_qs(parsed.query)
            arg=lambda name,default='':args.get(name,[default])[0]
            offset=min(max(int(arg('offset','0')),0),100000)
            if parsed.path=='/':self.send(PAGE,mime='text/html; charset=utf-8');return
            if parsed.path=='/api/health':self.send({'project':'new-milkgreen-library','root':str(root),'pid':os.getpid(),'read_only':True,'paid_model_calls':False});return
            if parsed.path=='/api/stats':
                items=sum((category_items(k) for k in ['facts','corpus','behaviors']),[])
                self.send({'raw':read('outputs/全文底库报告.json',{}),'production':read('outputs/资料库制作报告.json',{}),'coverage':read('outputs/全量提炼覆盖核验.json',{}),'candidate_count':len(items),'approved_count':sum(x.get('review')=='approved' for x in items)});return
            if parsed.path=='/api/identity':
                self.send({'text':(root/'persona/identity.md').read_text(encoding='utf-8')});return
            if parsed.path=='/api/candidates':
                items=category_items(arg('category','facts'));needle=arg('q').strip()[:100].casefold()
                if arg('new_only')=='1':items=[x for x in items if x.get('collection_batch')=='full-extraction-supplement-20261023']
                if needle:items=[x for x in items if needle in json.dumps(x,ensure_ascii=False).casefold()]
                subset=items[offset:offset+20];ids={r['source_id'] for x in subset for r in x.get('source_refs',[])}
                with contextlib.closing(db()) as conn:sources={sid:dict(conn.execute('SELECT id,title,date,source_url FROM sources WHERE id=?',(sid,)).fetchone()) for sid in ids}
                self.send({'total':len(items),'items':subset,'sources':sources});return
            if parsed.path=='/api/search':
                query=arg('q').strip()[:100];terms=re.findall(r'[\w\u3400-\u9fff]+',query,flags=re.UNICODE)
                if not terms:raise ValueError('请输入关键词。')
                large=[x for x in terms if len(x)>=3];short=[x for x in terms if len(x)<3]
                joins=' JOIN chunks_fts f ON f.rowid=c.id' if large else ''
                conditions=[];params=[]
                if large:conditions.append('chunks_fts MATCH ?');params.append(' AND '.join('"'+x.replace('"','""')+'"' for x in large))
                for term in short:conditions.append('instr(c.text,?)>0');params.append(term)
                kind=arg('genre','all')
                if kind!='all':conditions.append('s.genre=?');params.append(kind)
                order='bm25(chunks_fts)' if large else 'c.id'
                sql=f'SELECT c.id,c.source_id,c.start_ms,c.end_ms,c.text,s.title,s.date,s.genre,s.source_url FROM chunks c JOIN sources s ON s.id=c.source_id{joins} WHERE '+ ' AND '.join(conditions)+f' ORDER BY {order} LIMIT 21 OFFSET ?'
                with contextlib.closing(db()) as conn:rows=[dict(x) for x in conn.execute(sql,params+[offset])]
                for row in rows[:20]:
                    indexes=[row['text'].find(t) for t in terms if row['text'].find(t)>=0];start=max(0,min(indexes,default=0)-120)
                    row['excerpt']=('…' if start else '')+row.pop('text')[start:start+600]
                    row['genre_label']={'talk':'杂谈/电台提示','unspecified':'片名未分类','game':'游戏提示','watchalong':'看片提示','music':'歌曲提示'}.get(row['genre'],row['genre'])
                    url=row['source_url'];row['jump_url']=url+('&' if '?' in url else '?')+'t='+str(row['start_ms']//1000)
                self.send({'results':rows[:20],'has_more':len(rows)>20});return
            if parsed.path=='/api/context':
                row_id=int(arg('id'))
                with contextlib.closing(db()) as conn:
                    row=conn.execute('SELECT * FROM chunks WHERE id=?',(row_id,)).fetchone()
                    if row is None:self.send({'error':'没有这个片段。'},404);return
                    cues=[dict(x) for x in conn.execute('SELECT ordinal,start_ms,end_ms,text FROM cues WHERE source_id=? AND ordinal>=? AND ordinal<? ORDER BY ordinal',(row['source_id'],max(0,row['lo']-8),row['hi']+8))]
                self.send({'source_id':row['source_id'],'cues':cues});return
            self.send({'error':'Not found'},404)
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--port',type=int,default=0);args=p.parse_args();root=args.root.resolve()
    if not (root/'data/raw-index/library.sqlite3').is_file():raise FileNotFoundError('Library database missing')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),create_handler(root));server.daemon_threads=True
    info={'project':'new-milkgreen-library','root':str(root),'pid':os.getpid(),'port':server.server_port,'url':f'http://127.0.0.1:{server.server_port}/'}
    (root/'logs').mkdir(exist_ok=True);(root/'logs/reader.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
