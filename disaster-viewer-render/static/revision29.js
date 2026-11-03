"use strict";
const seismicData29=lazyPromise48(()=>Promise.all([fetch('/static/seismic-regions.geojson').then(r=>{if(!r.ok)throw Error();return r.json()}),fetch('/static/eew-area-names.json').then(r=>{if(!r.ok)throw Error();return r.json()})]).then(([geo,names])=>({geo,names})).catch(()=>null));
async function showRegionalIntensityMap(q,section,extra){
 const host=section.parentElement,shell=el('div',undefined,'intensity-map-shell'),box=el('div',undefined,'intensity-map'),overlay=el('div','地域の震度区分を取得中…','intensity-map-message');shell.append(box,overlay);section.append(shell);
 const data=await seismicData29,islands=await islandData40;if(!section.isConnected)return;
 const sm=L.map(box,{minZoom:3,maxZoom:13,maxBounds:[[-80,-40],[80,320]],maxBoundsViscosity:1});intensityMaps.add(sm);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{referrerPolicy:'strict-origin-when-cross-origin',maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(sm);
 const layers=L.featureGroup().addTo(sm),scales=new Map(),names=data?.names||{},byName=new Map(Object.entries(names).map(([code,name])=>[name,code]));
 for(const row of extra.regions||[])if(row.scaleCode>=0)scales.set(String(row.code),row.scaleCode);
 for(const point of q.points||[]){if(!point.isArea)continue;const code=byName.get(point.addr||point.name),scale=Number(point.scaleCode??point.scale);if(code&&Number.isFinite(scale)&&scale>=0)scales.set(code,Math.max(scales.get(code)??-1,scale));}
 if(data&&scales.size){
  const buttons=[...host.querySelectorAll('.station-link')],polygons=new Map(),readout=el('p',undefined,'station-readout');readout.setAttribute('role','status');section.append(readout);let current=null;
  const matches=code=>buttons.filter(b=>b.dataset.stationName===names[code]);
  const paint=()=>{for(const [code,layer]of polygons){layer.setStyle({color:current===code?'#126f84':'#fff',weight:current===code?4:1,fillColor:reportIntensityColor(scales.get(code),host),fillOpacity:1});if(current===code)layer.bringToFront();matches(code).forEach(b=>b.setAttribute('aria-pressed',String(current===code)));}};
  const clear=()=>{current=null;sm.closePopup();readout.textContent='';paint();};
  const pick=(code,fromMap=false)=>{if(current===code){clear();return;}current=code;paint();readout.textContent=names[code]+' ／ 震度 '+liveScale(scales.get(code));polygons.get(code).openPopup();if(!fromMap)scrollInfo40(box);if(fromMap){const button=matches(code)[0];if(button){for(let n=button.parentElement;n&&n!==host;n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;button.scrollIntoView({block:'start',behavior:'instant'});button.focus({preventScroll:true});}}};
  addIslandHalos40(islands,scales,code=>reportIntensityColor(code,host),layers);
  L.geoJSON(data.geo,{filter:f=>scales.has(String(f.properties.code)),style:f=>({color:'#fff',weight:1,fillColor:reportIntensityColor(scales.get(String(f.properties.code)),host),fillOpacity:1}),onEachFeature:(f,l)=>{const code=String(f.properties.code),text=(names[code]||'地域')+' ／ 震度'+compactScale45(liveScale(scales.get(code)));polygons.set(code,l);l.bindTooltip(text,{sticky:true});l.bindPopup(el('p',text),{autoPan:false});l.on('click',()=>pick(code,true));matches(code).forEach(b=>{b.disabled=false;b.onclick=()=>pick(code);b.dataset.mapped='true';b.setAttribute('aria-pressed','false');});}}).addTo(layers);
  bindStationGestures48(sm,clear);
  bindIntensityCollapse(host,sm,()=>buttons.filter(b=>b.getAttribute('aria-pressed')==='true'),clear);
  overlay.hidden=true;section.append(el('p','小さな島の周りの色は見やすさのための補助表示で、海上の観測範囲ではありません。気象庁の地震情報の地域区分ごとの最大震度です。地域または一覧の地域名を押すと選択し、もう一度押すと解除します。'+(q.intensitySource?'直前の震度速報（'+q.intensitySource.issued+'発表）から引き継いでいます。':''),'caption'));
 }else overlay.textContent=data?'この発表には、地図に表示できる震度情報がありません。':'地域の地図を取得できません。震度情報の有無を確認できません。';
 if(q.coords)L.marker(mapCoords(q.coords),{icon:L.divIcon({className:'quake-epicenter-pin',html:'✕',iconSize:[30,30],iconAnchor:[15,15]})}).bindTooltip('震源').addTo(layers);
 requestAnimationFrame(()=>{if(!box.isConnected)return;sm.invalidateSize();const bounds=layers.getBounds();if(bounds.isValid())sm.fitBounds(bounds,{padding:[35,35],maxZoom:9,animate:false});else sm.setView([36,138],5,{animate:false});});
}
function installObservationBasemap(map){map.eachLayer(layer=>{if(layer instanceof L.TileLayer)map.removeLayer(layer)});L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png',{maxZoom:18,maxNativeZoom:18,className:'observation-basemap',bounds:[[15,115],[55,160]],noWrap:true,attribution:'<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル（淡色地図）</a>'}).addTo(map);map.setMaxBounds([[15,115],[55,160]]);map.setMinZoom(4);}
// Remove views and controls whose live data supply has not been connected.
for(const node of document.querySelectorAll('[data-view="evacuation"]'))node.remove();
$('evacuation-view').hidden=true;
for(const key of ['waves','detections']){liveSettings[key]=false;document.querySelector('[data-live-setting="'+key+'"]')?.closest('label')?.remove();}
$('live-felt-count')?.parentElement?.setAttribute('hidden','');
for(const value of ['shaking'])document.querySelector('#live-example option[value="'+value+'"]')?.remove();
// No browsing API can promise uninterrupted delivery; failures stay visible.

$('cyclone-detail').addEventListener('toggle',event=>{const details=event.target;if(details.tagName!=='DETAILS'||details.open||!details.isConnected||!cycloneStep)return;const selectedNode=[...$('cyclone-detail').querySelectorAll('[data-step]')].find(n=>n.dataset.step===cycloneStep);if(selectedNode&&(details===selectedNode||details.contains(selectedNode))){cycloneStep=null;cycloneMap?.closePopup();for(const b of $('cyclone-detail').querySelectorAll('.step-button'))b.setAttribute('aria-pressed','false');for(const m of stepMarkers.values())m.getElement()?.classList.remove('site-selected');}},true);

function reportIntensityColor(code,host){const badge=host.querySelector('.scale-legend .scale-'+code);if(badge)return getComputedStyle(badge).backgroundColor;const sample=scaleBadge('',code);host.append(sample);const color=getComputedStyle(sample).backgroundColor;sample.remove();return color;}
function bindIntensityCollapse(host,map,selectedButtons,clear){const root=$('detail');const onToggle=event=>{const node=event.target;if(node.tagName==='DETAILS'&&!node.open&&node.isConnected&&selectedButtons().some(b=>node.contains(b)))clear();};root.addEventListener('toggle',onToggle,true);map.once('unload',()=>root.removeEventListener('toggle',onToggle,true));}

for(const node of document.querySelectorAll('[data-live-setting=voiceDetection]'))node.closest('label')?.remove();
