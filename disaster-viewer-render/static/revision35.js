'use strict';
// The entire observation page remains available; only river/flood information is experimental.
const syncAppearance35=syncExperimentalAppearance34;
syncExperimentalAppearance34=function(){syncAppearance35();const option=$('atmosphere-layer').querySelector('option[value=rivers]');option.textContent='河川・洪水情報（実験中）';option.classList.toggle('experimental-locked',!appSettings.experimentalRivers);option.style.color=appSettings.experimentalRivers?'':'#788892';};syncExperimentalAppearance34();

// Gray road map below weather overlays; place labels follow the map's zoom level.
const baseBackground35=observationBackground34;
observationBackground34=async function(target){if(!target)return;if(!target._basePromise35)target._basePromise35=baseBackground35(target);await target._basePromise35;if(!target.getPane('observation-outline34')){target._basePromise35=null;return;}if(target._labels35)return;target._labels35=true;
 const pane=target.createPane('observation-roads36');pane.style.zIndex=190;pane.style.pointerEvents='none';
 const roads=L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png',{pane:'observation-roads36',minZoom:6,minNativeZoom:5,maxNativeZoom:18,maxZoom:18,noWrap:true,bounds:[[20,122],[47,155]],className:'observation-gray-tiles36',attribution:'<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener noreferrer">地理院タイル</a>（淡色化）'}).addTo(target);
 const cities=L.layerGroup();for(const [lat,lon,name]of [[43.06,141.35,'札幌'],[38.27,140.87,'仙台'],[35.68,139.76,'東京'],[35.18,136.91,'名古屋'],[34.69,135.5,'大阪'],[34.39,132.46,'広島'],[33.59,130.4,'福岡'],[26.21,127.68,'那覇']])L.marker([lat,lon],{pane:'observation-outline34',interactive:false,icon:L.divIcon({className:'map-place35 city',html:el('span',name),iconSize:[90,24],iconAnchor:[45,12]})}).addTo(cities);
 const show=()=>{if(target.getZoom()<6){if(!target.hasLayer(cities))cities.addTo(target);}else if(target.hasLayer(cities))target.removeLayer(cities);};target.on('zoomend',show);show();target._roads36=roads;target._labelsReady35=true;
};installObservationBasemap=observationBackground34;

// A receiver's health clock must continue even if one map or notification cannot render.
let liveProcessingError35='',liveRenderBusy35=false;
function liveTask35(name,task){try{return task();}catch(error){liveProcessingError35=name;console.error('Live '+name,error);return undefined;}}
const renderBefore35=renderLive;
renderLive=function(){if(liveRenderBusy35)return;liveRenderBusy35=true;try{renderBefore35();liveProcessingError35='';}catch(error){liveProcessingError35='表示を再試行しています';console.error('Live render',error);}finally{liveRenderBusy35=false;}};
startLiveClock=function(){cancelAnimationFrame(liveClockFrame);liveLastClock=0;let expiry='';const tick=time=>{if(!liveActive)return;liveClockFrame=requestAnimationFrame(tick);if(time-liveLastClock<1000)return;liveLastClock=time;
 liveTask35('接続状態',updateLiveHealth);const host=$('live-map-clock');if(host)host.textContent=new Date().toLocaleString('ja-JP',{timeZone:'Asia/Tokyo',hour12:false})+' 日本時間';
 if(Date.now()-liveTsunamiLastAttempt>=1000)liveTask35('津波の更新',refreshLiveTsunami);
 liveTask35('津波通知',processTsunamiChanges);const key=activeLiveWarnings().map(r=>r.id).join(',')+'|'+Boolean(liveCancellation&&liveAge(liveCancellation.time)<60000)+'|'+liveTsunamiAreas().map(a=>a.code).join(',')+'|'+liveTsunamiNotices.filter(n=>Date.now()-n.time<180000).length;if(key!==expiry||liveProcessingError35){expiry=key;renderLive();}
};liveClockFrame=requestAnimationFrame(tick);};
const healthBefore35=updateLiveHealth;updateLiveHealth=function(){healthBefore35();if(liveActive&&!liveConnectedAt&&liveAttempts===0&&!liveLastFailure&&navigator.onLine!==false){const host=$('live-source-health');host.dataset.state='quiet';host.querySelector('strong').textContent='接続準備中 · 最新情報を確認しています';}if(liveProcessingError35)$('live-source-health').append(el('small','表示の一部を再試行中。受信は継続しています。','live-fetch-error'));};

// Parse and store new bulletins independently from optional sound and map work.
addLiveItem=function(row){if(!row?.id||row.test===true||![551,552,556,9902].includes(row.code))return;
 const old=liveItems.get(row.id);if(old&&JSON.stringify(old)===JSON.stringify(row))return;liveItems.set(row.id,row);while(liveItems.size>250)liveItems.delete(liveItems.keys().next().value());
 if([556,9902].includes(row.code)&&row.cancelled&&liveAge(row.time)<60000)liveCancellation=row;
 if(row.code===551){if(old)liveStationAttempts.delete(row.id);if(row.stations?.length)liveStations.set(row.id,{time:row.time,points:row.stations});liveTask35('震度の取得',()=>fetchLiveStations(row));if(liveAge(row.time)<1800000)liveTask35('長周期地震動の確認',()=>scheduleLongPeriodChecks(row));}
 if(row.code===552&&liveAge(row.time)>=-60000&&liveAge(row.time)<120000)liveTask35('津波の発表処理',()=>receiveLiveTsunami(row));
 if([556,9902].includes(row.code))liveTask35('速報の通知',()=>notifyEewUpdate(row,liveReady&&liveAge(row.time)<120000));
 if(row.code===551&&liveReady&&liveAge(row.time)<120000&&!old)liveTask35('地震の通知',()=>enqueueLiveAudio(liveQuakeSpeech34(row),'voiceQuake',{tone:row.issue?.type==='ScalePrompt'?'quake-prompt':row.issue?.type==='Destination'?'quake-source':'quake-info',key:'quake-'+row.id}));
 renderLive();
};
ingestLiveBatch31=function(rows){liveIngesting31=true;try{for(const row of [...rows].reverse())liveTask35('発表の読み込み',()=>addLiveItem(row));}finally{liveIngesting31=false;renderLive();}};
// Detect half-open sockets with an actual ping/pong timeout. Quiet earthquake periods alone are not errors.
let transportTimer35=null;
const connectBefore35=connectRealtime;connectRealtime=function(){if(!liveActive||liveSocket&&[WebSocket.OPEN,WebSocket.CONNECTING??0].includes(liveSocket.readyState))return;connectBefore35();const socket=liveSocket;if(!socket)return;const previous=socket.onmessage;socket.onmessage=event=>{if(socket!==liveSocket)return;previous?.(event);};};
const wolfStartBefore35=startWolfx;startWolfx=function(){wolfStartBefore35();const socket=wolfSocket;if(!socket)return;const previous=socket.onmessage;socket.onmessage=event=>{socket._lastReply35=Date.now();previous?.(event);};socket._lastReply35=Date.now();};
function checkTransport35(){if(!liveActive)return;for(const socket of [liveSocket,wolfSocket]){if(!socket)continue;if(socket.readyState===0){socket._connectingSince35??=Date.now();if(Date.now()-socket._connectingSince35>20000)socket.close();}}
 const socket=wolfSocket;if(socket?.readyState===WebSocket.OPEN){if(Date.now()-(socket._lastReply35||wolfLast)>90000){wolfState='応答待ち・再接続中';socket.close();}else liveTask35('接続確認',()=>socket.send('ping'));}
 if(!liveSocket)connectRealtime();if(!wolfSocket)startWolfx();
}
transportTimer35=setInterval(checkTransport35,15000);
window.addEventListener('online',()=>{if(liveActive){connectRealtime();startWolfx();pullRealtime();}});
document.addEventListener('visibilitychange',()=>{if(liveActive&&!document.hidden){checkTransport35();startLiveClock();recoverWolfxSnapshot();}});

// Expanding a section grows below its summary without moving the reading position.
let expansionAnchor35=null,expansionFrame35=null;
function rememberExpansion35(event){const summary=event.target.closest?.('summary');if(!summary||!document.querySelector('main').contains(summary)){expansionAnchor35=null;return;}if(event.type==='keydown'&&!['Enter',' '].includes(event.key)){expansionAnchor35=null;return;}expansionAnchor35={summary,top:summary.getBoundingClientRect().top,until:Date.now()+65000,view};}
document.addEventListener('pointerdown',rememberExpansion35,true);document.addEventListener('keydown',rememberExpansion35,true);
for(const kind of ['wheel','touchmove'])document.addEventListener(kind,()=>{expansionAnchor35=null;},{passive:true,capture:true});
function keepExpansionPosition35(){if(expansionFrame35!==null)return;expansionFrame35=requestAnimationFrame(()=>{expansionFrame35=null;const anchor=expansionAnchor35;if(!anchor||!anchor.summary.isConnected||anchor.view!==view||Date.now()>anchor.until){expansionAnchor35=null;return;}const delta=anchor.summary.getBoundingClientRect().top-anchor.top;if(Math.abs(delta)>1)window.scrollTo({top:window.scrollY+delta,left:window.scrollX,behavior:'instant'});});}
document.addEventListener('toggle',event=>{if(event.target.tagName==='DETAILS'&&expansionAnchor35)keepExpansionPosition35();},true);
new MutationObserver(()=>{if(expansionAnchor35)keepExpansionPosition35();}).observe(document.querySelector('main'),{childList:true,subtree:true});
document.addEventListener('load',event=>{if(event.target?.tagName==='IMG'&&expansionAnchor35)keepExpansionPosition35();},true);

// Remove pointer focus after a committed selection; native popup internals belong to the browser.
let pointerSelect37=null;document.addEventListener('pointerdown',event=>{pointerSelect37=event.target.closest?.('select')||null;},true);document.addEventListener('change',event=>{const node=event.target;if(node.tagName==='SELECT'&&pointerSelect37===node&&!node.closest('.shared-location50'))requestAnimationFrame(()=>{if(document.activeElement===node)node.blur();});},true);document.addEventListener('keydown',event=>{if(event.target.tagName==='SELECT')pointerSelect37=null;},true);document.addEventListener('keyup',event=>{if(event.target.tagName==='SELECT'&&!event.target.closest('.shared-location50')&&['Escape','Enter'].includes(event.key)){const node=event.target;requestAnimationFrame(()=>{let open=false;try{open=node.matches(':open');}catch(_){}if(!open&&document.activeElement===node)node.blur();});}},true);
