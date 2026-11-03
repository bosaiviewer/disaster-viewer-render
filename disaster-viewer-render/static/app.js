'use strict';
const $ = id => document.getElementById(id);
let allItems = [], items = [], selected = null, map, layer, busy = false, mapInitialized = false;
const markers = new Map();
let view='home';let provider='jma',generation=0;const tabState={};
function isUS(q){return q.provider==='usgs';}
function shownTime(q){return isUS(q)?q.time+' JST':originTime(q.time);}
function symbol(q){return isUS(q)?'M '+q.magnitude:q.scale;}
function markerTitle(q){return (q.displayName||q.name)+' / '+(isUS(q)?'M '+q.magnitude:'最大震度 '+compactScale45(q.scale));}
function el(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if(cls) n.className=cls; return n; }
function setLoading(kind,on){const ids={earthquakes:['earthquake-view','status','list'],cyclones:['cyclone-view','cyclone-status','cyclone-list'],volcanoes:['volcanoes-view','volcano-status','volcano-list'],tsunami:['tsunami-view','tsunami-status','tsunami-current']};const [rootId,statusId,listId]=ids[kind]||[];const root=$(rootId)||$(kind+'-view'),status=$(statusId),list=$(listId);root?.classList.toggle('is-loading',on);status?.classList.toggle('loading-status',on);status?.setAttribute('aria-busy',String(on));let banner=$('loading-'+kind);if(!banner&&list){banner=el('div',undefined,'loading-banner');banner.id='loading-'+kind;banner.setAttribute('role','status');banner.append(el('span',undefined,'loading-spinner'),el('strong','情報を取得しています…'),el('span',kind==='cyclones'?'海外の情報は取得に時間がかかる場合があります。':'表示済みの情報は、更新が完了するまで保持します。'));list.before(banner);}if(banner)banner.hidden=!on;}
function speakText(text,button){if(!appSettings.experimentalAudio)return;if(!('speechSynthesis'in window)){if(button)button.textContent='このブラウザーは音声に対応していません';return;}speechSynthesis.cancel();const spoken=speechReading(text);const u=new SpeechSynthesisUtterance(spoken);applyJapaneseVoice(u);u.rate=1;if(button){button.setAttribute('aria-pressed','true');u.onend=u.onerror=()=>button.setAttribute('aria-pressed','false');}speechSynthesis.speak(u);}
function speechButton(text){const button=el('button','🔊 音声で説明','speech-button secondary');button.type='button';button.setAttribute('aria-label','この情報の説明を音声で再生');button.onclick=()=>{if(button.getAttribute('aria-pressed')==='true'){speechSynthesis.cancel();button.setAttribute('aria-pressed','false');return;}speakText(typeof text==='function'?text():text,button);};return button;}
function quakeSpeech(q){const extra=supplements.get(q.reportId),comments=extra?.status==='ok'&&Array.isArray(extra.comments)?extra.comments:[q.messages?.domestic,...(q.isForeign?[q.messages?.foreign]:[]),q.messages?.comment,...(Array.isArray(q.information)?q.information:[])];const info=[...new Set(comments.filter(x=>typeof x==='string'&&x.trim()))].join(' ');return originTime(q.time)+'、'+(q.displayName||q.name)+'で地震がありました。'+(info?info+' ':'')+(q.scale&&q.scale!=='不明'?'最大震度は'+q.scale+'です。':'')+(q.magnitude!=='不明'?'地震の規模はマグニチュード'+q.magnitude+'です。':'')+'深さは'+q.depth+'です。';}
function quakeOverview(q,us=false){const host=el('section',undefined,'quake-overview');host.append(el('p',us?'世界の地震 · USGS':'気象庁が発表した地震','eyebrow'),el('h3',q.displayName||q.name,'quake-place-title'),el('p',(us?q.time:originTime(q.time))+'（日本時間）','quake-origin-time'));const metrics=el('div',undefined,'quake-metrics');for(const [label,value,tone]of (us?[['地震の規模','M '+q.magnitude,'magnitude'],['震源の深さ',q.depth,'depth']]:[['最大震度','震度 '+q.scale,'scale-'+q.scaleCode],['地震の規模','M '+q.magnitude,'magnitude'],['震源の深さ',q.depth,'depth']])){const card=el('div',undefined,'quake-metric '+tone);card.append(el('span',label),el('strong',value,tone.startsWith('scale-')?'scale-chip '+tone:undefined));metrics.append(card);}host.append(metrics);return host;}
function readableUSValue(key,value){if(['magnitude','depth','maxmmi','num-responses'].includes(key)){if(value===null||String(value).trim()===''||!Number.isFinite(Number(value)))return '未提供';return String(value);}if(key==='review-status')return {automatic:'専門家の確認前（自動解析）',reviewed:'専門家による確認済み'}[value]||'確認状況の情報なし';if(key==='alertlevel')return {green:'低い（緑）',yellow:'注意を要する（黄）',orange:'大きな影響のおそれ（橙）',red:'甚大な影響のおそれ（赤）'}[value]||'推定情報なし';return value??'未提供';}
function originTime(s){const m=String(s).match(/^(\d{4})[/-](\d{2})[/-](\d{2})[ T](\d{2}):(\d{2})/);return m?`${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}ごろ`:s;}
function coordinates(c,precision=1){return c?`${c[0]<0?'南緯':'北緯'}${Math.abs(c[0]).toFixed(precision)}度/${c[1]<0?'西経':'東経'}${Math.abs(c[1]).toFixed(precision)}度`:'不明（地図表示なし）';}
function scaleBadge(value,code){return el('span','震度 '+value,'scale-chip scale-'+code);}
// This is an illustrative effect-based comparison, never a measured JMA intensity.
function approximateShindo(raw){const n=Number(raw);if(!Number.isFinite(n)||n<=0)return null;const level=Math.max(1,Math.min(12,Math.round(n)));return ['0','0～1','1','2','3','4','5弱','5強','6弱','6強','7','7'][level-1];}
function metric(q,kind='magnitude'){
  if(kind==='pager'){const value=q.alert;const levels={green:['緑',1],yellow:['黄',2],orange:['橙',3],red:['赤',4]};return levels[value]?{text:levels[value][0],tone:'pager-'+value,rank:levels[value][1]}:{text:'-',tone:'missing',rank:-999};}
  const raw=kind==='dyfi'?q.cdi:kind==='shakemap'?q.mmi:q.magValue;
  const value=raw===null||raw===undefined||raw===''?NaN:Number(raw);
  if(!Number.isFinite(value))return {text:'-',tone:'missing',rank:-999};
  if(kind!=='magnitude')return {text:String(Math.round(value)),tone:'mmi-'+Math.min(8,Math.max(1,Math.round(value))),rank:value};
  return {text:'M '+value.toFixed(1),tone:'mag-'+(value>=7.5?5:value>=6.5?4:value>=5.5?3:value>=4.5?2:value>=2.5?1:0),rank:value};
}
function icon(q,active=false){const m=isUS(q)?metric(q):{text:compactScale45(q.scale),tone:'scale-'+q.scaleCode};return L.divIcon({className:'pin '+m.tone+(active?' selected':''),html:el('span',isUS(q)?m.text.replace('M ',''):m.text),iconSize:[38,38],iconAnchor:[19,19]});}
function clearSelection(){if('speechSynthesis'in window)speechSynthesis.cancel();selected=null;document.querySelectorAll('.report').forEach(b=>b.setAttribute('aria-pressed','false'));for(const q of items){const marker=markers.get(q.id);if(marker)marker.setIcon(icon(q));}disposeIntensityMaps();$('detail').replaceChildren();$('detail-panel').hidden=true;detailVersion=null;map?.closePopup();restack();}
function applyFilters(preserve=false){const windowRows=quakeWindow44(allItems,$('quake-period44')?.value||'all');items=windowRows.filter(q=>provider!=='usgs'||$('mag-filter').value==='all'||(q.magValue!==null&&q.magValue!==undefined&&q.magValue>=Number($('mag-filter').value)));render(preserve);if(!busy)$('status').textContent='表示中 · '+items.length+' / '+Math.min(quakeLimit45(allItems),allItems.length)+'件'+($('quake-period44')?.value==='24h'?'（24時間以内）':'');}

const supplements=new Map();
function localTime(s) { return s ? new Date(s).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo',hour12:false}) + ' JST' : '未取得'; }
try {
  map = L.map('map',{minZoom:1,maxBounds:[[-85,-40],[85,320]],maxBoundsViscosity:1}).setView([36.5,138],5);
  const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{referrerPolicy:'strict-origin-when-cross-origin',maxZoom:18,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
  tiles.on('tileerror',()=>{$('map-note').textContent='背景地図の読み込みに失敗しました。地震一覧・詳細は引き続き利用できます。';});
  layer=L.layerGroup().addTo(map);
} catch (_) { $('map').textContent='地図を読み込めませんでした。地震一覧・詳細をご利用ください。'; }
$('reset').onclick=()=>map?.setView([36.5,138],5,{animate:false});
function showAll(){if(map&&markers.size)map.fitBounds([...markers.values()].map(m=>m.getLatLng()),{padding:[40,40],maxZoom:5,animate:false});}
$('show-all').onclick=showAll;
function mapCoords(coords){return [coords[0],((coords[1]-140+180)%360+360)%360-180+140];}
let detailVersion=null;
function quakeVersion(q){return JSON.stringify(q,(k,v)=>k==='displayName'?undefined:v);}
function toggleQuake(id,pan=true,fromMap=false){if(selected===id){clearSelection();return;}choose(id,pan,fromMap);}
function choose(id, pan=true, fromMap=false) {
  const q=items.find(x=>x.id===id); if(!q)return;if('speechSynthesis'in window)speechSynthesis.cancel();selected=id;detailVersion=quakeVersion(q);disposeIntensityMaps();$('detail-panel').hidden=false;
  document.querySelectorAll('.report').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===id)));
  for(const q of items){const m=markers.get(q.id);if(m)m.setIcon(icon(q,q.id===id));}
  restack();
  if(pan && q.coords && map)map.setView(mapCoords(q.coords),6,{animate:false});
  if(fromMap){const row=[...document.querySelectorAll('.report')].find(n=>n.dataset.id===id);if(row){const list=$('list');list.scrollTop+=row.getBoundingClientRect().top-list.getBoundingClientRect().top-(list.clientHeight-row.clientHeight)/2;row.focus({preventScroll:true});if(window.innerWidth<=850)$('history').scrollIntoView({block:'start'});}}
  const d=$('detail'); d.replaceChildren();
  if(isUS(q)){showUSGS(q,d);return;}
  showReport(q,d);
  const history=el('details',undefined,'history');
  history.dataset.key='history';
  history.append(el('summary',`更新履歴（${q.historyCount}件の過去の発表）`));
  history.append(el('p','取得範囲内の震度速報・震源に関する情報・続報を、新しい順に表示しています。最新発表は含みません。','caption'));
  if(!q.history.length)history.append(el('p','過去の発表はありません。','caption'));
  for(const report of q.history){
    const entry=el('details',undefined,'history-entry');
    entry.dataset.key='report:'+report.id;
    entry.append(el('summary',`過去の発表 · ${report.issued} · ${reportTitle45(report)} · M ${report.magnitude} · 最大震度 ${report.scale}`));
    const content=el('div',undefined,'history-content'); entry.append(content);entry.addEventListener('toggle',()=>{if(entry.open&&!content.hasChildNodes())showReport(report,content);});history.append(entry);
  }
  d.append(history);
}
function showReport(q,d){
  const overview=quakeOverview(q),title=overview.querySelector('.quake-place-title');d.append(overview);if(d.id==='detail')d.append(speechButton(()=>quakeSpeech(q)));
  const dl=el('dl'); for(const [k,v] of [['発表日時（日本時間）',q.issued],['発表元',q.source],['震源座標',q.coordinateText||coordinates(q.coords)]]){const block=el('div');const value=el('dd');value.append(k==='最大震度'?scaleBadge(q.scale,q.scaleCode):document.createTextNode(v));block.append(el('dt',k),value);dl.append(block);} d.append(dl);const metadata=el('p','情報の種類：'+reportTitle45(q)+' ／ 発表元：'+q.source,'technical-meta');
  if(q.correction!=='None') d.append(el('p','訂正情報：'+({Unknown:'訂正の有無は不明',ScaleOnly:'震度の訂正',DestinationOnly:'震源の訂正',ScaleAndDestination:'震度・震源の訂正'}[q.correction]||'詳細不明')));
  const info=el('section',undefined,'quake-info'); d.append(info);
  fillInformation(info,q,null);
  loadSupplement(q).then(extra=>{
    if(!info.isConnected)return;
    if(extra.displayName){q.displayName=extra.displayName;title.textContent=extra.displayName;const button=[...document.querySelectorAll('.report')].find(n=>n.dataset.id===selected&&items.find(x=>x.id===selected)?.reportId===q.reportId);if(button)button.querySelector('strong').textContent=extra.displayName;}
    fillInformation(info,q,extra);showIntensityMap(q,d,extra);
  });
  if(q.intensitySource)d.append(el('p',q.intensitySource.issued+' 発表の直前の震度速報から震度を引き継いでいます。','notice'));
  d.append(el('h3','各地の震度'));
  if(!q.points.length){d.append(el('p','この発表には各地の震度情報がありません。'),metadata);return;}
  d.append(el('p',q.points.every(p=>p.isArea)?'都道府県 → 地域の順に開けます。地域名を押すと地図上でも選択できます。各階層の震度は掲載地域の最大値です。':'都道府県 → 市町村 → 区（ある場合）→ 観測点の順に開けます。各階層の震度は掲載観測点の最大値です。','info-time'));
  const legend=el('div',undefined,'scale-legend');for(const [code,label] of [[10,'1'],[20,'2'],[30,'3'],[40,'4'],[45,'5弱'],[50,'5強'],[55,'6弱'],[60,'6強'],[70,'7']])legend.append(scaleBadge(label,code));d.append(legend);
  const tree=el('div',undefined,'intensity-tree');
  for(const node of q.pointTree)tree.append(treeNode(node,q.reportId,''));d.append(tree,metadata);
}
function treeNode(node,id,path){
  const block=el('details',undefined,'intensity-node'),summary=el('summary');
  const key=path+'/'+node.name;block.dataset.key='tree:'+id+key;
  summary.append(el('span',node.name),scaleBadge(node.scale,node.scaleCode));block.append(summary);
  const content=el('div',undefined,'tree-content');
  for(const child of node.children)content.append(treeNode(child,id,key));
  if(node.points?.length){
    const table=el('table'),head=el('thead'),tr=el('tr');
    for(const label of ['観測点・地域','震度']){const th=el('th',label);th.scope='col';tr.append(th);}head.append(tr);table.append(head);
    const body=el('tbody');for(const point of node.points){const row=el('tr'),value=el('td');value.append(scaleBadge(point.scale,point.scaleCode));const cell=el('td'),button=el('button',point.addr,'station-link');button.type='button';button.dataset.stationName=point.addr;button.dataset.stationPref=point.pref;cell.append(button);row.append(cell,value);body.append(row);}table.append(body);content.append(table);
  }
  block.addEventListener('toggle',()=>{if(!block.open)block.querySelectorAll('details[open]').forEach(n=>n.open=false);});
  block.append(content);return block;
}
async function loadSupplement(q){
  if(supplements.has(q.reportId))return supplements.get(q.reportId);
  const control=new AbortController(),timer=setTimeout(()=>control.abort(),20000);
  try{const res=await fetch('/api/reports/'+encodeURIComponent(q.reportId)+'/supplement',{signal:control.signal});const data=await res.json();if(data.status==='ok'){supplements.set(q.reportId,data);if(supplements.size>200)supplements.delete(supplements.keys().next().value);}return data;}
  catch(_){return {status:'error',message:'気象庁の補足情報を取得できませんでした。再度この地震を選択すると再試行します。'};}
  finally{clearTimeout(timer);}
}
function fillInformation(info,q,extra){
  info.replaceChildren(el('h3','この地震に関する情報'));
  info.append(el('p',`${q.issued} 発表時点の内容です。現在の津波警報・注意報の状況ではありません。`,'info-time'));
  if(extra?.status==='ok'){
    for(const text of extra.comments)info.append(el('p',text,'source-comment'));
    if(!extra.comments.length)info.append(el('p','この発表には付加文がありません。'));
    const link=el('a','出典：気象庁の発表原文');link.href=extra.url;info.append(link);
  }else{
    const messages=[['日本への津波の影響',q.messages.domestic]];
    if(q.isForeign)messages.push(['海外の津波の可能性',q.messages.foreign]);
    for(const [label,text] of messages){const line=el('p');line.append(el('strong',label+'：'),document.createTextNode(text));info.append(line);}
    if(q.messages.comment)info.append(el('p',q.messages.comment,'source-comment'));
    info.append(el('p',extra?.message||'気象庁の補足情報を確認しています…','supplement-status'));
    info.append(el('p','P2P地震情報の区分・付加文を表示しています。追加の付加文は未確認です。','info-time'));
  }
}

function render(preserveDetail=false) {
  const focusId=document.activeElement?.dataset?.id;
  const oldSelection=selected,oldDetailRoot=$('detail').firstElementChild;
  const expanded=new Set([...document.querySelectorAll('#detail details[open]')].map(n=>n.dataset.key).filter(Boolean));
  $('list').replaceChildren(); layer?.clearLayers(); markers.clear();$('count').textContent=items.length+' / '+allItems.length+'件';
  if(!items.length){$('list').append(el('p','表示できる地震情報はありません。', 'empty'));clearSelection();return;}
  for(const q of items){const b=el('button',undefined,'report');b.type='button';b.dataset.id=q.id;b.setAttribute('aria-pressed',String(q.id===selected));b.setAttribute('aria-label',`${q.name}、${isUS(q)?'M '+q.magnitude:'最大震度'+q.scale}、${shownTime(q)}、${q.type}`);
    const badge=isUS(q)?metric(q,$('list-metric').value):{text:q.scale,tone:'scale-'+q.scaleCode};b.append(el('span',badge.text,'badge '+badge.tone));
    const content=el('span');content.append(el('strong',q.displayName||q.name),el('small',shownTime(q)),el('small',reportTitle45(q)+(q.historyCount>0?' · 更新履歴 '+q.historyCount+'件':'')));if(isUS(q)&&['dyfi','shakemap'].includes($('list-metric').value)){const converted=approximateShindo($('list-metric').value==='dyfi'?q.cdi:q.mmi);if(converted)content.append(el('small','震度'+converted+'程度（参考）','mmi-comparison'));}b.append(content);if(!isUS(q))b.append(el('span',q.magnitude==='不明'?'M 不明':'M '+q.magnitude,'mag'));b.onclick=()=>toggleQuake(q.id);$('list').append(b);
    if(q.coords&&map){const m=L.marker(mapCoords(q.coords),{icon:icon(q,q.id===selected),bubblingMouseEvents:false,title:markerTitle(q)}).addTo(layer);m.bindTooltip(el('span',markerTitle(q)),{permanent:false,direction:'top',offset:[0,-18]});m.on('click',event=>{if(event.originalEvent)L.DomEvent.stopPropagation(event.originalEvent);toggleQuake(q.id,false,true);if(selected)showNearby(q);});markers.set(q.id,m);}
  }
  restack();
  if(!mapInitialized&&markers.size){if(provider==='jma')japanView34(map);else showAll();mapInitialized=true;}
  if(items.some(q=>q.id===selected)){if(!preserveDetail&&detailVersion!==quakeVersion(items.find(q=>q.id===selected)))choose(selected,false);}else clearSelection();
  if(selected===oldSelection&&oldDetailRoot!==$('detail').firstElementChild)document.querySelectorAll('#detail details').forEach(n=>{n.open=Boolean(n.dataset.key)&&expanded.has(n.dataset.key);});
  if(focusId) [...document.querySelectorAll('.report')].find(b=>b.dataset.id===focusId)?.focus({preventScroll:true});
}
async function updateNames(){
  if(provider!=='jma')return;
  try{const res=await fetch('/api/event-names',{signal:AbortSignal.timeout(15000)});const data=await res.json();if(provider!=='jma')return;
    for(const q of allItems){const name=data.names?.[q.reportId]||supplements.get(q.reportId)?.displayName;if(!name)continue;q.displayName=name;
      const row=[...document.querySelectorAll('.report')].find(n=>n.dataset.id===q.id);if(row){row.querySelector('strong').textContent=name;row.setAttribute('aria-label',`${name}、最大震度${q.scale}、${shownTime(q)}、${q.type}`);}
      const marker=markers.get(q.id);if(marker){marker.setTooltipContent(el('span',name+' / 最大震度 '+q.scale));const icon=marker.getElement();if(icon){icon.title=name+' 最大震度'+q.scale;icon.setAttribute('aria-label',name+' 最大震度'+q.scale);}}
    }
  }catch(_){/* Existing P2P names remain usable if JMA is unavailable. */}
}
async function refresh(){
  if(view!=='earthquakes')return;
  const requested=provider,requestGeneration=generation;
  if(busy)return;busy=true;setLoading('earthquakes',true);$('refresh').disabled=true;$('status').textContent='地震情報を取得中…';
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),60000);
  try{const res=await fetch(requested==='usgs'?'/api/usgs/earthquakes':'/api/earthquakes',{cache:'no-store',signal:controller.signal});const data=await res.json();if(requested!==provider||requestGeneration!==generation)return;
    if(!Array.isArray(data.items))throw new Error();
    if(data.lastSuccess || !items.length){allItems=data.items;applyFilters();updateNames();$('updated').textContent='最終成功：'+localTime(data.lastSuccess);}
    $('coverage').textContent=data.notice||'';$('coverage').hidden=!data.notice;
    $('error').hidden=!data.error;$('error').textContent=data.error||'';
    $('status').textContent=data.stale?'更新に失敗・以前の情報を表示':items.length?'取得完了 · '+items.length+'件の地震':'取得完了 · 情報なし';
  }catch(_){if(requested!==provider||requestGeneration!==generation)return;$('status').textContent='サーバーに接続できません';$('error').hidden=false;$('error').textContent='アプリの起動と通信環境を確認してください。取得済みの表示は保持しています。';if(!items.length)$('list').replaceChildren(el('p','未取得です。「今すぐ更新」で再試行できます。','empty'));}
  finally{clearTimeout(timeout);if(requested===provider&&requestGeneration===generation){busy=false;setLoading('earthquakes',false);$('refresh').disabled=false;}}
}
const productLabels={'dyfi':'DYFI（体感報告）','shakemap':'ShakeMap（揺れの推定分布）','losspager':'PAGER（被害規模の推定）','origin':'震源・規模の解析','phase-data':'観測波の解析','moment-tensor':'断層の動きの解析','oaf':'余震の確率予測','ground-failure':'地すべり・液状化の推定'};
function productPanel(product){
  const box=el('div',undefined,'product-body'),p=product.properties;
  box.append(el('p',`更新：${product.time} JST ／ 提供元：${product.source} ／ ${product.status==='DELETE'?'取り下げ':'更新情報'}`,'info-time'));
  for(const [key,label] of [['magnitude','マグニチュード'],['depth','深さ（km）'],['maxmmi','推定される最大の揺れ（MMI・日本の震度とは異なります）'],['num-responses','体感報告数'],['alertlevel','被害規模の推定区分'],['review-status','確認状況'],['title','表題']]){
    if(p[key]!==undefined){const value=readableUSValue(key,p[key]);box.append(el('p',label+'：'+value));}
  }
  const raw=el('details');raw.append(el('summary','配信データの全項目・資料リンク'));
  raw.addEventListener('toggle',()=>{if(!raw.open||raw.dataset.loaded)return;raw.dataset.loaded='true';
    const table=el('table');for(const [key,value] of Object.entries(p)){const row=el('tr');row.append(el('th',key),el('td',typeof value==='object'?JSON.stringify(value):String(value)));table.append(row);}raw.append(table);
    const links=el('ul');for(const link of product.links){const a=el('a',link.name);a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';const li=el('li');li.append(a);links.append(li);}raw.append(links);
  });box.append(raw);return box;
}
async function showUSGS(q,host){
  host.append(quakeOverview(q,true));const dl=el('dl');
  for(const [label,value] of [['震源座標',coordinates(q.coords,3)],['最終更新（日本時間・JST）',q.issued]]){const block=el('div');block.append(el('dt',label),el('dd',value));dl.append(block);}host.append(dl);
  if(q.url){const link=el('a','USGSの地震ページ（英語）');link.href=q.url;host.append(link);}
  const info=el('div',undefined,'usgs-products');host.append(info);host.append(el('p','解析に関する補足：規模の種類 '+(q.magType||'未提供')+' ／ 解析元 '+(q.source||'未提供')+' ／ 確認状況 '+(q.status==='reviewed'?'専門家による確認済み':q.status==='automatic'?'専門家の確認前（自動解析）':q.status||'不明'),'technical-meta')); info.append(el('p','関連情報と公開されている更新履歴を取得中…','info-time'));
  try{
    const res=await fetch('/api/usgs/events/'+encodeURIComponent(q.id),{signal:AbortSignal.timeout(35000)});const data=await res.json();if(!info.isConnected)return;
    if(data.status!=='ok')throw new Error(data.message||'取得できませんでした。');
    info.replaceChildren();if(data.stale)info.append(el('p',data.message,'error'));
    info.append(el('h3','揺れ・被害・津波に関する関連情報'),el('p','以下は当該地震の解析・配信情報です。気象庁震度や現在の警報と同じものではありません。','info-time'));
    info.append(el('p','併記する震度は体感・被害の説明を比べた参考値で、気象庁の観測値ではありません。MMIと気象庁震度は一対一に換算できません。','info-time'));
    const active=data.current.filter(p=>p.status!=='DELETE');
    const cards=[['dyfi','DYFI｜体感報告','住民から寄せられた「どれくらい揺れを感じたか」の報告です。'],['shakemap','ShakeMap｜揺れの推定分布','観測と計算から推定した揺れの強さの分布です。MMIは気象庁の震度と異なります。'],['losspager','PAGER｜被害規模の推定','人口や建物の情報から人的・経済的被害の規模を推定します。実際に確認された被害数ではありません。'],['ptwc','PTWC｜太平洋津波警報センター','PTWC由来の震源解析や津波関連資料です。震源解析があるだけで津波警報が発表されたとは限りません。']];
    for(const [kind,title,description] of cards){const section=el('section',undefined,'product-card');section.append(el('h4',title),el('p',description));
      const candidates=active.filter(p=>kind==='ptwc'?p.source==='pt'||p.source==='ptwc'||JSON.stringify(p.properties).toLowerCase().includes('ptwc'):p.kind===kind).sort((a,b)=>b.weight-a.weight||b.updateTime-a.updateTime);
      if(kind!=='ptwc'){const props=candidates[0]?.properties;const badge=metric({cdi:props?.maxmmi,mmi:props?.maxmmi,alert:props?.alertlevel},kind==='losspager'?'pager':kind);const heading=section.querySelector('h4');heading.className='product-heading';heading.prepend(el('span',badge.text,'product-badge '+badge.tone));if(kind==='dyfi'||kind==='shakemap'){const converted=approximateShindo(props?.maxmmi);if(converted)heading.append(el('span','≒ 震度'+converted+'程度（参考）','mmi-comparison'));}}
      if(candidates.length){section.append(el('p','配信種別：'+(productLabels[candidates[0].kind]||candidates[0].kind)));section.append(productPanel(candidates[0]));}else section.append(el('p','取得した配信データにはありません。','info-time'));
      if(kind==='ptwc'){const link=el('a','津波の最新情報：NOAA / tsunami.gov（英語）');link.href='https://www.tsunami.gov/';section.append(link);}
      info.append(section);
    }
    const current=el('details',undefined,'history');current.append(el('summary',`取得した現行の配信データ（${data.current.length}件）`));
    const history=el('details',undefined,'history');history.append(el('summary',`更新履歴（${data.history.length}件の過去の配信データ）`));
    history.append(el('p','旧版を含める指定でUSGSが返した全件を掲載しています。配信種別・解析機関ごとの更新であり、全機関共通の発表順や、過去の完全な保存を保証するものではありません。','info-time'));
    for(const [container,rows] of [[current,data.current],[history,data.history]]){
      if(!rows.length)container.append(el('p','該当する配信データはありません。'));
      for(const p of rows){const entry=el('details',undefined,'history-entry');entry.append(el('summary',`${p.time} JST · ${productLabels[p.kind]||p.kind} · ${p.source}${p.properties.magnitude?' · M '+p.properties.magnitude:''}${p.status==='DELETE'?' · 取り下げ':''}`));entry.addEventListener('toggle',()=>{if(entry.open&&!entry.dataset.loaded){entry.dataset.loaded='true';entry.append(productPanel(p));}});container.append(entry);}
    }
    info.append(current,history);
  }catch(error){if(info.isConnected)info.replaceChildren(el('p',error.message||'関連情報を取得できませんでした。地震を選び直してください。','error'));}
}
function restack(){
  if(!map)return;
  const magnitude=q=>isUS(q)?metric(q).rank:Number.isFinite(Number(q.magnitude))?Number(q.magnitude):-999;
  const priority=q=>{const kind=$('stack-order').value;return ['newest','oldest'].includes(kind)?(kind==='oldest'?-1:1)*(quakeEpoch31(q)||0):kind==='intensity'?q.scaleCode:kind==='magnitude'?magnitude(q):metric(q,kind).rank;};
  const ordered=[...items].sort((a,b)=>priority(a)-priority(b)||magnitude(a)-magnitude(b));
  ordered.forEach((q,i)=>{const m=markers.get(q.id);if(m)m.setZIndexOffset((q.id===selected?1000000:(i+1)*10)-map.latLngToLayerPoint(m.getLatLng()).y);});
}
map?.on('zoomend moveend viewreset',restack);$('stack-order').onchange=restack;
function switchTab(next){
  $('mag-filter').value='2.5';$('list-metric').value='magnitude';if($('quake-period44')){$('quake-period44').value='all';syncPeriodLabels45(next);}map?.setView([36,138],5,{animate:false});
  tabState[provider]={allItems};provider=next;generation++;busy=false;mapInitialized=false;
  allItems=tabState[next]?.allItems||[];selected=null;clearSelection();
  for(const name of ['jma','usgs']){const button=$('tab-'+name);button.setAttribute('aria-selected',String(name===next));button.tabIndex=name===next?0:-1;}
  $('stack-order').replaceChildren(...(next==='usgs'?[['magnitude','Mが大きい順'],['dyfi','DYFIが大きい順'],['shakemap','ShakeMapが大きい順'],['pager','PAGERが高い順'],['newest','発生順（新しい地震を手前）'],['oldest','発生順（古い地震を手前）']]:[['intensity','震度が大きい順'],['magnitude','Mが大きい順'],['newest','発生順（新しい地震を手前）'],['oldest','発生順（古い地震を手前）']]).map(([value,label])=>{const option=el('option',label);option.value=value;return option;}));
  $('usgs-filter-control').hidden=$('list-metric-control').hidden=next!=='usgs';$('filter-note').hidden=next!=='usgs';
  $('filter-note').textContent=next==='usgs'?'最新500件の取得範囲から絞り込みます。DYFI・ShakeMapはMMIを四捨五入。MMIは気象庁震度とは異なる尺度です。':'';
  $('map-note').textContent=next==='usgs'?'数字はマグニチュード（M）です。色はMの区分（2.5未満・2.5以上・4.5以上・5.5以上・6.5以上・7.5以上）、選択中は青です。':'数字は最大震度です。重なり順を切り替えられます。';
  $('list-note').textContent=next==='usgs'?'USGSの最新500イベント。発生時刻は日本時間（JST）、秒まで表示します。':'気象庁の最新100地震。速報・震源情報・続報は更新履歴から確認できます。時刻は日本時間です。';
  $('updated').textContent='最終成功：確認中';$('error').hidden=true;$('coverage').hidden=true;
  applyFilters();$('list').scrollTop=0;refresh();
}
for(const name of ['jma','usgs']){$('tab-'+name).onclick=()=>switchTab(name);$('tab-'+name).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?'jma':e.key==='End'?'usgs':provider==='jma'?'usgs':'jma';switchTab(next);$('tab-'+next).focus();}};}
$('refresh').onclick=refresh;
$('mag-filter').onchange=()=>{mapInitialized=false;applyFilters(true);};$('list-metric').onchange=()=>render(true);
document.addEventListener('keydown',e=>{if(view==='earthquakes'&&e.key==='Escape')clearSelection();});
setInterval(()=>{if($('auto').checked)refresh();},60000);
refresh();


function showNearby(q){
  if(!map||!q.coords)return;const origin=map.latLngToContainerPoint(mapCoords(q.coords));
  const nearby=items.filter(x=>x.coords&&origin.distanceTo(map.latLngToContainerPoint(mapCoords(x.coords)))<30);
  if(nearby.length<2)return;const content=el('div',undefined,'nearby-picker');content.append(el('strong','近く・同じ位置の地震を選択'));
  for(const row of nearby){const b=el('button',(row.displayName||row.name)+' / '+symbol(row)+' / '+shownTime(row));b.type='button';b.onclick=e=>{e.stopPropagation();map.closePopup();toggleQuake(row.id,false,true);};content.append(b);}
  L.popup({maxWidth:320,maxHeight:220,autoPan:false}).setLatLng(mapCoords(q.coords)).setContent(content).openOn(map);
}
const intensityMaps=new Set();
function disposeIntensityMaps(){for(const m of intensityMaps)m.remove();intensityMaps.clear();}
async function showIntensityMap(q,host,extra){
  if(!host.isConnected||host.querySelector('.intensity-map-section'))return;
  const section=el('section',undefined,'intensity-map-section');section.append(el('h3','震度地図'));
  const stations=extra.stations||[];const heading=[...host.querySelectorAll('h3')].find(n=>n.textContent==='各地の震度');if(heading)host.insertBefore(section,heading);else host.append(section);
  if(!stations.length){await showRegionalIntensityMap(q,section,extra);return;}
  section.append(el('p','地図の点、または下の震度一覧の観測点名を押すと選択できます。同じ観測点をもう一度押すと解除します。','info-time'));
  const box=el('div',undefined,'intensity-map');section.append(box);const readout=el('p',undefined,'station-readout');readout.setAttribute('role','status');section.append(readout);
  if(typeof L==='undefined')return;
  const sm=L.map(box,{minZoom:3,maxZoom:18});intensityMaps.add(sm);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{referrerPolicy:'strict-origin-when-cross-origin',maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(sm);
  const epicenter=q.coords?mapCoords(q.coords):null;if(epicenter)L.marker(epicenter,{icon:L.divIcon({className:'quake-epicenter-pin',html:'✕',iconSize:[30,30],iconAnchor:[15,15]}),title:(q.displayName||q.name||'震源')+'の震源'}).addTo(sm).bindPopup(el('p',(q.displayName||q.name||'地震')+' ／ 震源'));
  let current=null;const pins=[];
  const clean=s=>String(s||'').replace(/[＊*\s]/g,'');
  const buttons=[...host.querySelectorAll('.station-link')];const matches=p=>buttons.filter(b=>clean(b.dataset.stationName)===clean(p.name)&&(!b.dataset.stationPref||clean(b.dataset.stationPref)===clean(p.pref)));
  function paint(){section.dispatchEvent(new CustomEvent('station-selection47'));stations.forEach((p,i)=>{const active=current===p.id;pins[i]?.getElement()?.classList.toggle('site-selected',active);matches(p).forEach(b=>b.setAttribute('aria-pressed',String(active)));});}
  function stack(){[...stations.keys()].sort((a,b)=>stations[a].scaleCode-stations[b].scaleCode).forEach((i,r)=>pins[i].setZIndexOffset((stations[i].id===current?1000000:(r+1)*10)-sm.latLngToLayerPoint(pins[i].getLatLng()).y));}
  function pick(i,fromMap=false){const p=stations[i];if(current===p.id){current=null;sm.closePopup();readout.textContent='';paint();stack();return;}current=p.id;paint();stack();readout.textContent=p.pref+' '+p.name+' ／ 震度 '+p.scale;if(!section.closest('[hidden]'))sm.setView(p.coords,Math.max(sm.getZoom(),9),{animate:false});if(!section.closest('[hidden]'))pins[i].openPopup();if(!fromMap)scrollInfo40(box);
    if(fromMap){const b=matches(p)[0];if(b){let ancestor=b.parentElement;while(ancestor!==host&&ancestor){if(ancestor.tagName==='DETAILS')ancestor.open=true;ancestor=ancestor.parentElement;}b.scrollIntoView({block:'start',behavior:'instant'});b.focus({preventScroll:true});}}}
  stations.forEach((p,i)=>{const marker=L.marker(p.coords,{icon:L.divIcon({className:'station-pin scale-'+p.scaleCode,html:el('span',compactScale45(p.scale)),iconSize:[32,32],iconAnchor:[16,16]}),title:p.pref+' '+p.name+' 震度'+compactScale45(p.scale),bubblingMouseEvents:false}).addTo(sm).bindPopup(el('p',p.pref+' '+p.name+' ／ 震度 '+compactScale45(p.scale)));marker.on('click',()=>pick(i,true));pins.push(marker);matches(p).forEach(b=>{b.onclick=()=>section.activeStationMap47?section.activeStationMap47(p.id,false):pick(i);b.dataset.mapped='true';});});
  section.stationController47={getSelected:()=>current,clear:()=>{current=null;sm.closePopup();readout.textContent='';paint();stack();},select:(id,fromMap)=>{const i=stations.findIndex(p=>p.id===id);if(i>=0)pick(i,fromMap);}};
  bindStationGestures48(sm,()=>section.stationController47.clear());
  buttons.filter(b=>!b.dataset.mapped).forEach(b=>{b.disabled=true;b.title='この発表では観測点の座標を確認できません。';});
  bindIntensityCollapse(host,sm,()=>buttons.filter(b=>b.getAttribute('aria-pressed')==='true'),()=>{current=null;sm.closePopup();readout.textContent='';paint();stack();});
  sm.on('zoomend moveend',stack);
  requestAnimationFrame(()=>{if(!box.isConnected)return;sm.invalidateSize();const bounds=[...(epicenter?[epicenter]:[]),...stations.map(p=>p.coords)];if(bounds.length)sm.fitBounds(bounds,{padding:[36,36],maxZoom:11,animate:false});else sm.setView([36,138],5,{animate:false});paint();stack();});
}
