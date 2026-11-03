"""On-demand preview WSGI entry; no collector and no mutation of the Windows app."""
import os,secrets,json
from flask import Flask
from werkzeug.wrappers import Request,Response
from werkzeug.middleware.proxy_fix import ProxyFix
if os.name=='posix':os.environ.setdefault('EV_DATA_DIR','/tmp/disaster-viewer56')
from app import app as viewer

def access_mode():return os.environ.get('EV_CLOUD_ACCESS','private')
def message(text,status):return Response(text,status,content_type='text/plain; charset=utf-8')
def data(value,status=200):return Response(json.dumps(value,ensure_ascii=False),status,content_type='application/json; charset=utf-8')

def check(request):
 mode=access_mode()
 if mode not in ('private','public'):return message('EV_CLOUD_ACCESSを private または public に設定してください。',503)
 if mode=='private':
  password=os.environ.get('EV_PREVIEW_PASSWORD','')
  if len(password)<16:return message('確認用パスワードが未設定です。EV_PREVIEW_PASSWORDに16文字以上の値を設定してください。',503)
  auth=request.authorization
  valid=bool(auth and auth.type=='basic' and secrets.compare_digest((auth.username or '').encode(),b'viewer') and secrets.compare_digest((auth.password or '').encode(),password.encode()))
  if not valid:
   response=message('確認用ユーザー名 viewer と設定したパスワードでログインしてください。',401)
   response.headers['WWW-Authenticate']='Basic realm="Disaster Viewer Preview", charset="UTF-8"'
   return response
 if request.method not in ('GET','HEAD','OPTIONS'):
  origin=request.headers.get('Origin')
  if origin and origin!=request.host_url.rstrip('/') or request.headers.get('Sec-Fetch-Site')=='cross-site':return data({'error':'別サイトからの操作は受け付けません。'},403)
 if request.path=='/api/speech':return data({'error':'この環境ではブラウザーの日本語音声を使用します。','fallback':'browser'},503)
 return None

class Preview56:
 def __init__(self,application):self.application=application
 def __call__(self,environ,start_response):
  request=Request(environ)
  response=data({'status':'ready','mode':'on-demand','version':'0.56'}) if request.path=='/healthz' else check(request)
  def headers(status,values,exc_info=None):
   values=[(k,v) for k,v in values if not(access_mode()=='private' and k.lower()=='cache-control')]
   values.append(('X-Content-Type-Options','nosniff'))
   if access_mode()=='private':values.extend([('Cache-Control','private, no-store'),('X-Robots-Tag','noindex, nofollow')])
   return start_response(status,values,exc_info)
  return response(environ,headers) if response is not None else self.application(environ,headers)

app=Flask(__name__)
app.wsgi_app=ProxyFix(Preview56(viewer.wsgi_app),x_for=0,x_proto=1,x_host=0,x_port=0,x_prefix=0)
