'use strict';
function quakeMillis44(value){const text=String(value||'').trim();if(!text)return NaN;const normalized=text.replace(/\//g,'-').replace(' ','T');return Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(normalized)?normalized:normalized+'+09:00');}
function quakeLimit45(rows){return rows.some(q=>q.provider==='usgs')?500:100;}
function quakeWindow44(rows,period='all',now=Date.now()){return rows.slice(0,quakeLimit45(rows)).filter(q=>period!=='24h'||(Number.isFinite(quakeMillis44(q.time))&&quakeMillis44(q.time)>=now-86400000&&quakeMillis44(q.time)<=now));}
function importantItems44(kind,data,now=Date.now()){
 if(data?.error||data?.stale)return [];
 const out=[],add=(id,rank,title,text,view,row,time)=>out.push({id:kind+':'+id,rank,title,text,view,row,time});
 if(kind==='tsunami'){
  const levels=[['大津波警報',0],['津波警報',1],['津波注意報',3]],areas=new Map();
  for(const r of data.current||[]){if(r.validUntil&&Date.parse(r.validUntil)<now)continue;for(const a of r.areas||[]){const hit=levels.find(([name])=>a.kind===name);if(hit){const old=areas.get(a.code||a.name);if(!old||hit[1]<old.rank)areas.set(a.code||a.name,{...a,rank:hit[1],time:r.time});}}}
  if(areas.size){const sorted=[...areas.values()].sort((a,b)=>a.rank-b.rank),top=sorted[0];add('active',top.rank,top.kind,sorted.map(a=>a.name+'：'+a.kind).join(' ／ '),'tsunami',null,top.time);}
 }
 if(kind==='earthquakes')for(const q of data.items||[]){const age=now-(Number.isFinite(quakeMillis44(q.time))?quakeMillis44(q.time):quakeMillis44(q.issued)),scale=Number(q.scaleCode),mag=Number(q.magValue??q.magnitude);if(!Number.isFinite(age)||age<0||age>quakeAlertDuration45(scale,mag)||!(scale>=45||mag>=7))continue;add(q.id,scale>=60?2:5,(q.displayName||q.name)+'の地震','最大震度 '+q.scale+' ／ M '+q.magnitude,'earthquakes',q,q.issued||q.time);}
 if(kind==='volcanoes')for(const q of data.items||[])if(Number(q.level)>=4)add(q.id,Number(q.level)>=5?2:4,q.name+'：'+q.warning,'居住地域への影響に警戒してください。','volcanoes',q,q.issued);
 if(kind==='cyclones')for(const q of data.items||[]){
  if(q.ongoing===false||q.transitionTo)continue;
  if(q.hourlyUpdate!==true)continue;
  const location=String(q.location||'');
  const age=now-Date.parse(q.issued||q.time);if(!Number.isFinite(age)||age<0||age>172800000)continue;
  add(q.id,6,q.name,location+'。進路と公式の防災情報を確認してください。','cyclones',q,q.issued||q.time);
 }

 return out;
}
function sortImportant44(rows){return rows.slice().sort((a,b)=>a.rank-b.rank||(Date.parse(b.time)||0)-(Date.parse(a.time)||0)||a.id.localeCompare(b.id));}

function quakeAlertDuration45(scale,mag){return scale>=60?21600000:scale>=55||mag>=7?10800000:scale>=50?7200000:3600000;}

function compactScale45(text){return String(text).replaceAll('弱','-').replaceAll('強','+');}
function syncPeriodLabels45(source){const n=document.getElementById('quake-period44');if(!n)return;const max=source==='usgs'?500:100;n.options[0].textContent='最新'+max+'件';n.options[1].textContent='24時間以内（最大'+max+'件）';}

function reportTitle45(q){const serial=Number(q.serial);return q.type+(serial>1?'（第'+String(serial).replace(/[0-9]/g,c=>String.fromCharCode(c.charCodeAt(0)+65248))+'報）':'');}
