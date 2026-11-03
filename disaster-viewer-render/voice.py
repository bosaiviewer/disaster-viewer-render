"""Locally generated Japanese speech for immediate mute without pausing playback."""
import os,json,subprocess,base64,hashlib,threading
from collections import OrderedDict
_cache=OrderedDict();_lock=threading.Lock()
SCRIPT=r'''
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[Text.Encoding]::UTF8
$data=[Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$speaker=New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice=$speaker.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'ja-JP'} | Select-Object -First 1
if(-not $voice){
 $speaker.Dispose()
 Add-Type -AssemblyName System.Runtime.WindowsRuntime
 $type=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
 $synth=New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
 $selected=$type::AllVoices | Where-Object {$_.Language -eq 'ja-JP'} | Select-Object -First 1
 if(-not $selected){throw 'Japanese voice is not installed'}
 $synth.Voice=$selected
 function Wait-WinRT($operation,$resultType){
  $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1
  $task=$method.MakeGenericMethod($resultType).Invoke($null,@($operation));$task.Wait();return $task.Result
 }
 $stream=Wait-WinRT ($synth.SynthesizeTextToStreamAsync([string]$data.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
 $reader=[Windows.Storage.Streams.DataReader,Windows.Storage.Streams,ContentType=WindowsRuntime]::new($stream)
 $null=Wait-WinRT ($reader.LoadAsync([uint32]$stream.Size)) ([uint32])
 $bytes=New-Object byte[] $stream.Size;$reader.ReadBytes($bytes)
 [Console]::Out.Write([Convert]::ToBase64String($bytes));exit 0
}
$speaker.SelectVoice($voice.VoiceInfo.Name)
$stream=New-Object IO.MemoryStream
$speaker.SetOutputToWaveStream($stream)
$speaker.Speak([string]$data.text)
$speaker.SetOutputToNull()
[Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))
$speaker.Dispose();$stream.Dispose()
'''
def synthesize(text):
 if not isinstance(text,str) or not 1<=len(text)<=1200:raise ValueError('Text length')
 key=hashlib.sha256(text.encode('utf-8')).hexdigest()
 with _lock:
  if key in _cache:return _cache[key]
 if os.name!='nt':raise RuntimeError('Windows voice unavailable')
 command=['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')]
 result=subprocess.run(command,input=json.dumps({'text':text},ensure_ascii=False).encode('utf-8'),capture_output=True,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError('Japanese Windows voice unavailable')
 try:audio=base64.b64decode(result.stdout.strip(),validate=True)
 except ValueError:raise RuntimeError('Invalid audio')
 if not audio.startswith(b'RIFF') or len(audio)>12_000_000:raise RuntimeError('Invalid audio')
 with _lock:
  _cache[key]=audio
  while len(_cache)>30:_cache.popitem(last=False)
 return audio
