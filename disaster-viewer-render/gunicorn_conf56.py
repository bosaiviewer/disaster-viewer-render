"""One worker shares request caches; no scheduler or collector is started."""
import os
port=int(os.environ.get('PORT','10000'))
if not 1<=port<=65535:raise ValueError('PORT is outside the valid range')
bind=f'0.0.0.0:{port}'
worker_class='gthread'
workers=1
threads=4
timeout=180
graceful_timeout=30
accesslog='-'
errorlog='-'
capture_output=True
preload_app=False
