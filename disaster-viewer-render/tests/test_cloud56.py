import os,unittest,base64
from unittest.mock import patch
import cloud_entry56 as cloud

class Cloud56Tests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'EV_CLOUD_ACCESS':'private','EV_PREVIEW_PASSWORD':'test-only-password-123'});self.env.start();self.addCleanup(self.env.stop);self.client=cloud.app.test_client()
 def auth(self,password='test-only-password-123'):
  return {'Authorization':'Basic '+base64.b64encode(('viewer:'+password).encode()).decode()}
 def test_health_is_minimal_and_does_not_collect(self):
  with patch('requests.get') as get:
   response=self.client.get('/healthz');self.assertEqual(response.status_code,200);get.assert_not_called();self.assertEqual(response.json['mode'],'on-demand')
 def test_preview_requires_authentication(self):
  r=self.client.get('/');self.assertEqual(r.status_code,401);self.assertIn('Basic',r.headers['WWW-Authenticate']);self.assertEqual(self.client.get('/',headers=self.auth('wrong')).status_code,401)
 def test_valid_preview_serves_viewer_without_fetching(self):
  with patch('requests.get') as get:
   r=self.client.get('/',headers=self.auth());self.assertEqual(r.status_code,200);get.assert_not_called();self.assertIn('no-store',r.headers['Cache-Control'])
 def test_missing_secret_fails_closed(self):
  with patch.dict(os.environ,{'EV_PREVIEW_PASSWORD':''}):self.assertEqual(self.client.get('/').status_code,503)
 def test_invalid_mode_does_not_expose_viewer(self):
  with patch.dict(os.environ,{'EV_CLOUD_ACCESS':'oops'}):self.assertEqual(self.client.get('/').status_code,503)
 def test_explicit_public_mode(self):
  with patch.dict(os.environ,{'EV_CLOUD_ACCESS':'public'}):self.assertEqual(self.client.get('/').status_code,200)
 def test_cross_site_post_is_rejected(self):
  headers=dict(self.auth(),Origin='https://outside.example');self.assertEqual(self.client.post('/api/speech',headers=headers,json={'text':'test'}).status_code,403)
  headers=dict(self.auth(),**{'Sec-Fetch-Site':'cross-site'});self.assertEqual(self.client.post('/api/speech',headers=headers,json={'text':'test'}).status_code,403)
 def test_browser_voice_fallback_avoids_windows_process(self):
  with patch('voice.synthesize') as synth:
   r=self.client.post('/api/speech',headers=self.auth(),json={'text':'test'});self.assertEqual(r.status_code,503);self.assertEqual(r.json['fallback'],'browser');synth.assert_not_called()
 def test_render_https_forwarding_is_same_origin(self):
  headers=dict(self.auth(),Origin='https://localhost',**{'X-Forwarded-Proto':'https'})
  response=self.client.post('/api/speech',headers=headers,json={'text':'test'})
  self.assertEqual(response.status_code,503);self.assertEqual(response.json['fallback'],'browser')
 def test_gunicorn_single_worker_and_dynamic_port(self):
  import runpy
  with patch.dict(os.environ,{'PORT':'12345'}):c=runpy.run_module('gunicorn_conf56')
  self.assertEqual(c['bind'],'0.0.0.0:12345');self.assertEqual(c['workers'],1);self.assertEqual(c['threads'],4)

if __name__=='__main__':unittest.main()
