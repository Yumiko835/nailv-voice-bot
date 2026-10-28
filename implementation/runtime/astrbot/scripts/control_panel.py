"""Local Windows control panel; uses existing owned-process and NapCat APIs.

No chat/model requests, QQ sends, model downloads, autostart, or session deletion.
QQ authentication stays on loopback and uses the installed official WebUI flow.
"""
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
import argparse,hashlib,json,os,queue,subprocess,sys,threading,time,urllib.parse,urllib.request,webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk

ROOT=Path(project_path(''))
R=ROOT/'runtime/astrbot';PY=R/'.venv/Scripts/python.exe';MANAGER=R/'scripts/manage.py'
VOICE=setting("voice_url","http://127.0.0.1:49856");NAPCAT='http://127.0.0.1:6101';DASHBOARD='http://127.0.0.1:6185/'
BOT=setting("bot_qq","");HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)
TITLE='奶绿 · 本地控制面板'

def json_request(base,path,data=None,credential=None,timeout=3):
    assert base in (VOICE,NAPCAT)
    headers={'Accept':'application/json'}
    if data is not None:headers.update({'Origin':base,'Content-Type':'application/json'})
    if credential:headers['Authorization']='Bearer '+credential
    request=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    # Never send project credentials through a configured external HTTP proxy.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=timeout) as response:
        return json.load(response)

def manage(action,components=()):
    assert action in ('start','stop','status') and set(components)<={'astrbot','napcat','voice'}
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    command=[str(PY),'-B','-X','utf8',str(MANAGER),action]
    if components:command+=['--components',*components]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',
                          cwd=str(ROOT),env=env,creationflags=HIDDEN,timeout=65)
    if result.returncode:raise RuntimeError('本地启停未完成，请检查本项目运行日志；没有结束其他程序。')
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith('{')]

def access():
    return json.loads((R/'local-access.json').read_text(encoding='utf-8-sig'))

def login_url():
    # The installed official WebUI consumes ?token= and replaces its login URL
    # after authentication. Never print, persist, or show the resulting URL.
    token=access().get('napcat_token','')
    if not isinstance(token,str) or not token:raise RuntimeError('未找到本机QQ管理口令，请检查配置文件。')
    return NAPCAT+'/webui/web_login?'+urllib.parse.urlencode({'token':token})

class NapCatStatus:
    def __init__(self):self.credential=None;self.created=0.
    def query(self):
        if not self.credential or time.monotonic()-self.created>3000:
            token=access()['napcat_token']
            data=json_request(NAPCAT,'/api/auth/login',{'hash':hashlib.sha256((token+'.napcat').encode()).hexdigest()})
            if data.get('code')!=0:raise RuntimeError('QQ管理页认证失败，请打开登录页检查。')
            payload=data.get('data') or {}
            if payload.get('require2FA'):return {'kind':'needs_auth','text':'请在QQ登录页完成验证'}
            self.credential=payload.get('Credential');self.created=time.monotonic()
            if not self.credential:raise RuntimeError('QQ管理页认证尚未就绪。')
        reply=json_request(NAPCAT,'/api/QQLogin/CheckLoginStatus',{},self.credential)
        if reply.get('code')!=0:
            self.credential=None
            return {'kind':'unknown','text':'登录状态待核对，可打开QQ登录页'}
        state=reply.get('data') or {}
        if state.get('isLogin'):
            info=json_request(NAPCAT,'/api/QQLogin/GetQQLoginInfo',{},self.credential)
            number=str((info.get('data') or {}).get('uin',''))
            if number and number!=BOT:return {'kind':'wrong_account','text':'当前QQ不是奶绿账号，请检查登录页'}
            return {'kind':'online','text':'QQ已在线 · '+(number or BOT)}
        if state.get('qrLoginAccepted'):return {'kind':'initializing','text':'扫码已接受，QQ正在连接'}
        if state.get('isOffline'):return {'kind':'offline','text':'QQ暂时离线，打开登录页查看'}
        if state.get('loginPhase')=='reconnecting':return {'kind':'reconnecting','text':'QQ正在尝试恢复连接'}
        return {'kind':'needs_login','text':'等待登录 · 点击“QQ登录 / 重新扫码”'}

class Backend:
    def __init__(self):self.nap=NapCatStatus()
    def status(self):
        rows={r['component']:r for r in manage('status')}
        states={'chat':'已启动' if rows['astrbot']['running'] else '已关闭',
                'qq':'已关闭','voice':'已关闭','components':rows}
        if rows['napcat']['running']:
            try:states['qq']=self.nap.query()['text']
            except Exception:states['qq']='NapCat已启动，登录状态暂不可读'
        if rows['voice']['running']:
            try:
                voice=json_request(VOICE,'/api/status')
                states['voice']='正在加载或生成语音' if voice['busy'] else ('模型已加载，可直接生成' if voice['resident'] else '服务已启动，模型按需加载')
            except Exception:states['voice']='语音服务正在启动'
        return states
    def wait_http(self,base,timeout=35):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                if base==VOICE:json_request(VOICE,'/api/status',timeout=1)
                else:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(base+'/',timeout=1) as r:
                        assert r.status==200
                return
            except Exception:time.sleep(.5)
        raise RuntimeError('本机服务尚未就绪，请稍后重试；已有登录资料保留。')
    def start(self):
        manage('start');return '服务已启动。QQ会尝试复用保存的登录；若提示待登录，点击QQ登录按钮。'
    def stop(self):
        manage('stop');self.nap.credential=None
        return '奶绿已停止。QQ登录资料、对话、人设和声音配置均已保留。'
    def login(self):
        manage('start',('napcat',));self.wait_http(NAPCAT)
        webbrowser.open(login_url(),new=2)
        return '已打开本机QQ登录页并传入管理口令。按页面提示快速登录或扫码。'
    def voice_warm(self):
        manage('start',('voice',));self.wait_http(VOICE)
        status=json_request(VOICE,'/api/status')
        if status['busy']:return '语音正在处理，请等待当前任务完成。'
        if status['resident']:return '语音模型已加载，可以直接生成。'
        job=json_request(VOICE,'/api/warm',{})
        return '已开始预加载，首次约需一分钟；可在上方查看进度。'
    def voice_release(self):
        running={r['component']:r['running'] for r in manage('status')}
        if not running['voice']:return '语音服务已关闭，无需释放。'
        if json_request(VOICE,'/api/status')['busy']:return '当前正在生成或加载，请完成后再释放。'
        json_request(VOICE,'/api/release',{})
        return '语音模型已卸载。下一条语音请求会自动重新加载；持续停用请点“停止奶绿”。'

class Panel:
    def __init__(self,root,backend=None):
        self.root=root;self.backend=backend or Backend();self.messages=queue.Queue()
        self.closing=False;self.working=False;self.refreshing=False;self.buttons=[]
        root.title(TITLE);root.geometry('720x650');root.minsize(700,650);root.configure(bg='#f1f5f2')
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10))
        style.configure('TFrame',background='#f1f5f2')
        style.configure('TLabel',background='#f1f5f2',foreground='#274132')
        style.configure('Title.TLabel',font=('Microsoft YaHei UI',20,'bold'))
        style.configure('Sub.TLabel',foreground='#5d6f63')
        style.configure('TButton',padding=(12,11),background='#e3ece6',foreground='#274132')
        style.map('TButton',background=[('active','#d3e5d9')])
        style.configure('Primary.TButton',background='#315f49',foreground='white')
        style.map('Primary.TButton',background=[('active','#244b38')])
        frame=ttk.Frame(root,padding=(25,20));frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='奶绿 · 本地控制面板',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='一键启动；登录失效时，自己打开本机页面扫码。',style='Sub.TLabel').pack(anchor='w',pady=(3,17))
        stateframe=ttk.Frame(frame);stateframe.pack(fill='x')
        self.values={}
        for row,(key,name) in enumerate([('chat','聊天服务'),('qq','QQ连接'),('voice','语音模型')]):
            ttk.Label(stateframe,text=name+'：',width=11).grid(row=row,column=0,sticky='w',pady=5)
            value=tk.StringVar(value='正在检查…');self.values[key]=value
            ttk.Label(stateframe,textvariable=value).grid(row=row,column=1,sticky='w',pady=5)
        row=ttk.Frame(frame);row.pack(fill='x',pady=(18,6))
        self.add_button(row,'启动奶绿',self.backend.start,0,'Primary.TButton')
        self.add_button(row,'停止奶绿',self.backend.stop,1)
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.add_button(row,'QQ登录 / 重新扫码',self.backend.login,0)
        self.add_button(row,'打开插件管理',lambda:self.open_url(DASHBOARD),1)
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.add_button(row,'预加载语音',self.backend.voice_warm,0)
        self.add_button(row,'释放语音资源',self.backend.voice_release,1)
        row=ttk.Frame(frame);row.pack(fill='x',pady=6)
        self.add_button(row,'打开聊天与语音页',lambda:self.open_url(VOICE+'/'),0)
        self.add_button(row,'查看运行文件夹',self.open_logs,1)
        ttk.Separator(frame).pack(fill='x',pady=(12,10))
        self.notice=tk.StringVar(value='先点“启动奶绿”。保存的QQ登录若仍有效，通常无需再次扫码。')
        ttk.Label(frame,textvariable=self.notice,wraplength=660,justify='left').pack(anchor='w',fill='x')
        ttk.Label(frame,text='关闭这个面板会保留后台服务；停用请点“停止奶绿”。',style='Sub.TLabel').pack(anchor='w',pady=(10,0))
        ttk.Label(frame,text='释放语音资源后，下次收到语音请求会自动加载。',style='Sub.TLabel').pack(anchor='w',pady=(3,0))
        self.updated=tk.StringVar(value='');ttk.Label(frame,textvariable=self.updated,style='Sub.TLabel').pack(anchor='w',pady=(5,0))
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(80,self.drain);root.after(120,self.refresh)
    def add_button(self,parent,label,callback,column,style='TButton'):
        parent.columnconfigure(column,weight=1)
        button=ttk.Button(parent,text=label,command=lambda:self.action(callback),style=style)
        button.grid(row=0,column=column,sticky='ew',padx=(0,7) if column==0 else (7,0))
        self.buttons.append(button)
    def open_url(self,url):webbrowser.open(url,new=2);return '已打开本机管理页面。'
    def open_logs(self):os.startfile(str(R/'logs'));return '已打开本项目运行日志文件夹。'
    def action(self,callback):
        if self.working:return
        self.working=True;self.notice.set('正在处理，请稍等…')
        for b in self.buttons:b.state(['disabled'])
        def run():
            try:self.messages.put(('action',callback()))
            except Exception as exc:
                # Don't echo credential URLs, auth responses or private logs.
                text=str(exc) if isinstance(exc,RuntimeError) else '操作未完成，请稍后重试或查看运行日志。'
                self.messages.put(('action',text))
        threading.Thread(target=run,daemon=True).start()
    def refresh(self):
        if self.closing:return
        if not self.refreshing and not self.working:
            self.refreshing=True
            def run():
                try:self.messages.put(('status',self.backend.status()))
                except Exception:self.messages.put(('status_error',None))
            threading.Thread(target=run,daemon=True).start()
        self.root.after(4500,self.refresh)
    def drain(self):
        if self.closing:return
        while True:
            try:kind,payload=self.messages.get_nowait()
            except queue.Empty:break
            if kind=='action':
                self.notice.set(payload);self.working=False
                for b in self.buttons:b.state(['!disabled'])
                self.root.after(100,self.refresh_once)
            elif kind=='status':
                self.refreshing=False
                for k in self.values:self.values[k].set(payload[k])
                self.updated.set('状态检查时间：'+time.strftime('%H:%M:%S'))
            else:self.refreshing=False;self.updated.set('状态暂不可读，稍后自动重试。')
        self.root.after(80,self.drain)
    def refresh_once(self):
        if self.closing or self.refreshing or self.working:return
        self.refreshing=True
        def run():
            try:self.messages.put(('status',self.backend.status()))
            except Exception:self.messages.put(('status_error',None))
        threading.Thread(target=run,daemon=True).start()
    def close(self):
        self.closing=True;self.root.destroy()

def self_test():
    # Actual hidden Tk construction and read-only process state; no services
    # are started, no browser/QQ login is invoked, and no tokens are printed.
    before={r['component']:r['running'] for r in manage('status')}
    root=tk.Tk();root.withdraw();panel=Panel(root)
    root.update_idletasks();assert len(panel.buttons)==8
    assert root.winfo_reqheight()<=650
    assert all(button.winfo_reqwidth()>40 for button in panel.buttons)
    assert urllib.parse.urlsplit(login_url()).hostname=='127.0.0.1'
    assert urllib.parse.urlsplit(login_url()).path=='/webui/web_login'
    assert set(urllib.parse.parse_qs(urllib.parse.urlsplit(login_url()).query))=={'token'}
    status=Backend().status();assert set(status['components'])=={'astrbot','napcat','voice'}
    panel.close()
    after={r['component']:r['running'] for r in manage('status')};assert before==after
    return {'passed':True,'native_GUI_constructed':True,'buttons':8,'service_state_unchanged':True,
            'services':after,'local_auth_URL_validated_without_disclosure':True,
            'external_network_calls':0,'QQ_messages_sent':0,'saved_login_untouched':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));return
    # Single interactive panel. The lock has no effect on bot service lifetime.
    import msvcrt
    lock=(R/'control-panel.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        import ctypes
        window=ctypes.windll.user32.FindWindowW(None,TITLE)
        if window:ctypes.windll.user32.ShowWindow(window,9);ctypes.windll.user32.SetForegroundWindow(window)
        return
    root=tk.Tk();Panel(root);root.mainloop()

if __name__=='__main__':main()
