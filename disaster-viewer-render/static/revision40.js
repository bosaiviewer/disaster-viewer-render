'use strict';
function scrollInfo40(node){if(!node||node.hidden||document.hidden)return;expansionAnchor35=null;const intent=++scrollIntent34;requestAnimationFrame(()=>{if(!document.hidden&&intent===scrollIntent34&&node.isConnected&&!node.hidden&&node.getClientRects().length)node.scrollIntoView({block:'start',behavior:'instant'});});}
// Only explicit selections scroll. Background refreshes continue to preserve the viewport.
const chooseInfo40=choose;choose=function(id,pan=true,fromMap=false){const result=chooseInfo40(id,pan,fromMap);if((pan||fromMap)&&selected===id)scrollInfo40($('detail-panel'));return result;};
const cycloneChoose40=chooseCyclone;chooseCyclone=function(q,pan=false){cycloneChoose40(q,pan);if(pan)scrollInfo40($('cyclone-detail'));};
const volcanoChoose40=chooseVolcano;chooseVolcano=function(q,toggle){const result=volcanoChoose40(q,toggle);if(toggle&&volcanoSelected===q.id)scrollInfo40($('volcano-detail'));return result;};
const amedasChoose40=selectAmedas;selectAmedas=function(row){amedasChoose40(row);if(amedasSelected===row.id)scrollInfo40($('atmosphere-detail'));};
const tsunamiArea40=selectTsunamiArea;selectTsunamiArea=function(r,a){tsunamiArea40(r,a);if(tsunamiArea!==null)scrollInfo40($('tsunami-map-label'));};
const tsunamiObservation40=selectTsunamiObservation;selectTsunamiObservation=function(r,o){tsunamiObservation40(r,o);if(tsunamiObservation!==null)scrollInfo40($('tsunami-map-label'));};

// Split wind danger forecasts using the supplied warning-class codes, not guessed wind speeds.
function renderWarningTimeline40(box,area,times){
 const labels={5:'特別警報級',4:'危険警報級',3:'警報級',2:'注意報級'},levels={'51':5,'50':5,'41':4,'31':3,'30':3,'22':2,'21':2,'20':2};
 for(const kind of area.kinds||[])for(const part of kind.significancyParts||[]){const wind=part.type==='風危険度';for(const type of wind?['強風','暴風']:[(part.type==='波危険度'?'波浪':part.type.replaceAll('危険度',''))])for(const local of part.locals||[]){const codes=(local.codes||[]).map(String),accept=code=>!wind||(type==='強風'?levels[code]===2:levels[code]>=3);if(!codes.some(c=>levels[c]&&accept(c)))continue;const card=el('div',undefined,'timeline-strip-row'),heading=el('strong',type+(local.areaName?'\n'+local.areaName:''));heading.style.whiteSpace='pre-line';card.append(heading);const strip=el('div',undefined,'timeline-strip');codes.forEach((code,i)=>{const level=accept(code)?levels[code]||0:0,cell=el('span',labels[level]||(code==='00'?'未提供':'基準未満'));cell.dataset.level=level;cell.title=weatherTime(times[i]?.dateTime||times[i])+'から ／ 配信区分 '+code;cell.append(el('small',weatherTime(times[i]?.dateTime||times[i])));strip.append(cell);});card.append(strip);box.append(card);}}
}

// Coastal polygons derived from the existing JMA seismic regions; omit the four connected main islands.
let islandGeo40=null,islandMainland41=null;
const islandData40=lazyPromise48(()=>Promise.all(['/static/seismic-islands.geojson','/static/seismic-main-islands.geojson'].map(url=>fetch(url).then(r=>{if(!r.ok)throw Error();return r.json();}))).then(([geo,main])=>{islandGeo40=geo;islandMainland41=main;seismicPaintKey=null;if(liveActive)renderLive();return geo;}).catch(()=>null));
// Mask the stroke itself as well, so a legitimate nearshore island halo cannot spill onto a main island.
function maskIslandHalo41(map,renderer,layer){
 if(!islandMainland41||!layer._path)return;map._islandMasks41??=new Map();let state=map._islandMasks41.get(renderer);
 if(!state){const ns='http://www.w3.org/2000/svg',defs=document.createElementNS(ns,'defs'),mask=document.createElementNS(ns,'mask'),rect=document.createElementNS(ns,'rect'),path=document.createElementNS(ns,'path'),id='island-mask41-'+L.stamp(renderer);mask.id=id;mask.setAttribute('maskUnits','userSpaceOnUse');mask.setAttribute('x','-10000000');mask.setAttribute('y','-10000000');mask.setAttribute('width','20000000');mask.setAttribute('height','20000000');for(const [key,value]of Object.entries({x:-10000000,y:-10000000,width:20000000,height:20000000,fill:'white'}))rect.setAttribute(key,String(value));path.setAttribute('fill','black');path.setAttribute('fill-rule','evenodd');mask.append(rect,path);defs.append(mask);renderer._container.prepend(defs);const update=()=>{const polygons=islandMainland41.geometry.type==='Polygon'?[islandMainland41.geometry.coordinates]:islandMainland41.geometry.coordinates;path.setAttribute('d',polygons.flatMap(polygon=>polygon.map(ring=>ring.map(([lon,lat],i)=>{const p=map.latLngToLayerPoint([lat,lon]);return (i?'L':'M')+p.x+' '+p.y;}).join(' ')+'Z')).join(' '));};state={id,update};map._islandMasks41.set(renderer,state);map.on('zoomend moveend viewreset',update);update();}
 layer._path.setAttribute('mask','url(#'+state.id+')');
}
function islandHaloWidth43(zoom){return Math.max(3,Math.min(12,2*((Number.isFinite(zoom)?zoom:5)-3)));}
function addIslandHalos40(geo,scales,color,group,pane){
 if(!geo)return;const map=group._map||group._mapToAdd;if(!map)return;const key=pane||'overlayPane';map._islandRenderers40??={};const renderer=map._islandRenderers40[key]??=L.svg({pane:key}),options={pane:key,renderer,interactive:false,onEachFeature:(_,layer)=>layer.on('add',()=>maskIslandHalo41(map,renderer,layer)),filter:f=>scales.has(String(f.properties.code))};

 const halos=L.geoJSON(geo,{...options,style:f=>({color:color(scales.get(String(f.properties.code))),weight:islandHaloWidth43(map.getZoom()),opacity:1,lineCap:'round',lineJoin:'round',fill:false,className:'island-intensity-halo40'})});const resize=()=>halos.setStyle({weight:islandHaloWidth43(map.getZoom())});halos.on('add',()=>{resize();map.on('zoomend',resize)});halos.on('remove',()=>map.off('zoomend',resize));return halos.addTo(group);
}

const liveChoose40=chooseLive;chooseLive=function(row){liveChoose40(row);if(liveSelected===row.id)scrollInfo40($('realtime-detail'));};



const stepChoose40=pickStep;pickStep=function(q,s,key,fromMap=false){stepChoose40(q,s,key,fromMap);if(!fromMap&&cycloneStep===key){const node=[...$('cyclone-detail').querySelectorAll('[data-step]')].find(n=>n.dataset.step===key);scrollInfo40(node);}};
