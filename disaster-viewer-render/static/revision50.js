"use strict";
function isActiveCyclone50(q){return !q.transitionTo&&(q.ongoing===true||q.historyGroup==='developing');}
function informationSymbol50(value){const s=String(value||'');return /津波/.test(s)?'🌊':/地震|震度|南海|後発/.test(s)?'〰️':/火山|噴火|降灰/.test(s)?'🌋':/台風|低気圧|ハリケーン/.test(s)?'🌀':/警報|注意報|警戒/.test(s)?'⚠️':/気象|天気|雨|雪/.test(s)?'☁️':'ℹ️';}
function addInformationSymbol50(node,value){if(!node||node.querySelector(':scope > .information-symbol50'))return;const icon=el('span',informationSymbol50(value),'information-symbol50');icon.setAttribute('aria-hidden','true');node.prepend(icon,document.createTextNode(' '));}
const renderNews50=renderLatestNews;renderLatestNews=function(){renderNews50();for(const node of $('latest-list').querySelectorAll('.news-category'))addInformationSymbol50(node,node.textContent);};
const importantRender50=renderImportant44;renderImportant44=function(){importantRender50();for(const node of importantHost44.querySelectorAll('button>strong'))addInformationSymbol50(node,node.textContent);};

// The common location survives internal view resets, but never changes itself on navigation.
const sharedRegion50={region:'',city:'',cities:[],regions:[],revision:0};
const cityLists50=new Map();let sharedReady50=null,locationLoad50=0;
function sharedCity50(){return sharedRegion50.cities.find(c=>c.code===sharedRegion50.city);}
function sharedOffice50(){return sharedCity50()?.office||sharedRegion50.regions.find(r=>r.code===sharedRegion50.region)?.offices?.[0];}
function selectValue50(id,value){const s=$(id);if(!s||!Array.from(s.options).some(o=>o.value===value))return false;s.value=value;return true;}
async function cityList50(region){if(!cityLists50.has(region))cityLists50.set(region,fetchMeteo('/api/briefings/cities/'+encodeURIComponent(region)).catch(e=>{cityLists50.delete(region);throw e;}));return cityLists50.get(region);}
function locationMessage50(text){$('shared-location-status50').textContent=text;}
async function chooseSharedRegion50(){const token=++locationLoad50;sharedRegion50.revision++;sharedRegion50.region=$('shared-region50').value;sharedRegion50.city='';sharedRegion50.cities=[];const city=$('shared-city50');city.replaceChildren();city.disabled=true;if(!sharedRegion50.region){locationMessage50('地域が必要な画面に自動で反映します。未選択なら通常どおり操作できます。');changeView(view);return;}locationMessage50('市区町村を取得中…');try{const data=await cityList50(sharedRegion50.region);if(token!==locationLoad50)return;sharedRegion50.cities=data.items||[];const options=document.createDocumentFragment();for(const row of sharedRegion50.cities)options.append(new Option(row.name,row.code));city.append(options);sharedRegion50.city=data.defaultCity||principalCity51(sharedRegion50.region,sharedRegion50.cities)?.code||'';city.value=sharedRegion50.city;city.disabled=!city.options.length;locationMessage50('選択した地域を、地域指定のある画面で自動選択します。');await applySharedLocation50(view);}catch(e){if(token===locationLoad50)locationMessage50(e.message||'地域一覧を取得できません。');}}
async function applySharedLocation50(next){
 if(!sharedRegion50.region)return;const revision=sharedRegion50.revision,city=sharedCity50(),region=sharedRegion50.region;
 const current=()=>view===next&&revision===sharedRegion50.revision;
 if(next==='home'){await sharedReady50;if(!current())return;selectValue50('home-region',region);await loadHomeCities(sharedRegion50.city||undefined);}
 else if(next==='weather'||next==='warnings'){await enterWeatherView(next);}
 else if(next==='latest'){if(selectValue50('latest-region33',region)){latestLimit=40;renderLatestNews();}}
 else if(next==='bulletins'){if(selectValue50('bulletins-region33',region))renderBulletins();}
 else if(next==='early'){await renderEarly();if(!current())return;if(selectValue50('early-region',region))await renderEarly();}
 else if(next==='outlook'){await loadWeatherCatalog();if(!current())return;renderNationalOutlook();const office=weatherCatalog.offices.find(o=>o.code===sharedOffice50());if(office&&selectValue50('outlook-region',office.parent))renderNationalOutlook();}
 else if(next==='atmosphere'&&city?.coords){atmosphereMap?.setView(city.coords,8,{animate:false});}
}
const enterRegion50=enterWeatherView;enterWeatherView=async function(kind){
 const revision=sharedRegion50.revision,region=sharedRegion50.region,office=sharedOffice50();
 if(region&&kind==='weather'){await loadWeatherCatalog();if(view!=='weather'||revision!==sharedRegion50.revision)return;selectValue50('weather-office',office);}
 await enterRegion50(kind);if(!region||revision!==sharedRegion50.revision||view!==kind)return;
 if(kind==='warnings'){warningRegion=null;await chooseWarningRegion(region,true);if(revision!==sharedRegion50.revision||view!==kind)return;const city=sharedCity50();if(city&&weatherWarnings?.items?.some(c=>c.code===city.code)){weatherWarningSelected=city.code;renderWeatherWarningList();renderWeatherWarningDetail();paintWarningDashboard(false);}}
 else if(kind==='weather'){const city=sharedCity50();if(city?.forecastArea&&selectValue50('forecast-area',city.forecastArea))renderWeatherForecast();}
};
const enterHome50=enterHomeWeather;enterHomeWeather=async function(){if(!sharedRegion50.region)return enterHome50();await sharedReady50;if(view!=='home')return;selectValue50('home-region',sharedRegion50.region);await loadHomeCities(sharedRegion50.city||undefined);};
const changeRegion50=changeView;changeView=function(next){changeRegion50(next);if(view!==next)return;if(sharedRegion50.region&&!['weather','warnings','home'].includes(next))queueMicrotask(()=>{if(view===next)applySharedLocation50(next).catch(e=>locationMessage50(e.message));});};

function installSharedLocation50(){
 const box=el('section',undefined,'shared-location50');box.setAttribute('aria-label','共通の地域設定');
 for(const [id,title]of [['shared-region50','都道府県など'],['shared-city50','市区町村']]){const label=el('label',title),s=el('select');s.id=id;if(id==='shared-region50'){s.append(new Option('選択してください。',''));s.disabled=true;}label.append(s);box.append(label);}
 const reset=el('button','リセット','secondary');reset.type='button';reset.onclick=()=>{box.querySelector('#shared-region50').value='';chooseSharedRegion50();};box.append(reset);const status=el('p','地域が必要な画面に自動で反映します。未選択なら通常どおり操作できます。','caption');status.id='shared-location-status50';status.setAttribute('role','status');box.append(status);document.querySelector('header>div').classList.add('header-summary50');document.querySelector('header>div').append(box);
 $('shared-city50').disabled=true;$('shared-region50').onchange=chooseSharedRegion50;$('shared-city50').onchange=()=>{sharedRegion50.city=$('shared-city50').value;sharedRegion50.revision++;applySharedLocation50(view).catch(e=>locationMessage50(e.message));};
 sharedReady50=(async()=>{const geo=weatherRegionGeo||await(await fetch('/static/weather-regions.geojson')).json();sharedRegion50.regions=geo.features.map(f=>f.properties);const options=document.createDocumentFragment();for(const row of sharedRegion50.regions)options.append(new Option(row.name,row.code));$('shared-region50').append(options);$('shared-region50').disabled=false;})();sharedReady50.catch(e=>locationMessage50(e.message));
}
function installCredits50(){
 const section=el('section',undefined,'panel home-release50');section.id='home-release50';section.append(el('h2','更新情報・出典'),el('p','Ver.0.50 ／ 地域の共通選択、地図操作、台風の重要表示、監視カメラの初期位置を更新しました。'));
 const details=el('details'),summary=el('summary','参考文献・情報取得元・地図素材');details.append(summary);const ul=el('ul');
 for(const [name,url,note]of [['気象庁','https://www.jma.go.jp/','地震、津波、台風、火山、警報・注意報、天気予報、観測・各種気象分布'],['P2P地震情報','https://www.p2pquake.net/develop/json_api_v2/','地震情報、緊急地震速報（警報）の中継'],['USGS','https://earthquake.usgs.gov/','世界の地震、DYFI、ShakeMap、PAGER等'],['国立情報学研究所・気象庁防災情報XMLデータベース','https://agora.ex.nii.ac.jp/cps/weather/report/','発表原文と公開アーカイブ'],['NOAA / NHC','https://www.nhc.noaa.gov/','ハリケーン情報'],['GDACS','https://www.gdacs.org/','世界の熱帯低気圧・影響推定（CC BY 4.0）'],['JTWC','https://www.metoc.navy.mil/jtwc/jtwc.html','熱帯低気圧の進路予報'],['Fiji Meteorological Service','https://www.met.gov.fj/','南太平洋の公式速報'],['海上保安庁・海しる','https://www.msil.go.jp/','海の補助情報'],['Open-Meteo','https://open-meteo.com/','世界の天気・モデルによる推計'],['気象庁・予報区等GIS','https://www.data.jma.go.jp/developer/gis.html','気象区域・地震区域等の地図（加工）'],['OpenStreetMap','https://www.openstreetmap.org/copyright','背景地図（© OpenStreetMap contributors）'],['Natural Earth','https://www.naturalearthdata.com/','世界地図（Public Domain）'],['国土地理院・避難場所','https://www.gsi.go.jp/bousaichiri/hinanbasho','指定緊急避難場所・指定避難所（表示用に加工）'],['ハザードマップポータルサイト','https://disaportal.gsi.go.jp/hazardmap/copyright/opendata.html','洪水・津波・高潮・土砂災害の想定区域'],['Leaflet','https://leafletjs.com/','地図表示ライブラリ（BSD-2-Clause）']]){const li=el('li');li.append(safeSourceLink(name,url),document.createTextNode(' — '+note));ul.append(li);}if(wolfxEnabled49()){const li=el('li');li.append(safeSourceLink('Wolfx','https://wolfx.jp/'),document.createTextNode(' — 気象庁発表の予報中継（非公式）'));ul.append(li);}details.append(ul);section.append(details);$('home-settings').after(section);
 const footer=document.querySelector('footer');if(footer){const note=footer.querySelector('p');footer.replaceChildren();if(note)footer.append(note);}
}
whenViewerReady48(()=>{installSharedLocation50();installCredits50();renderImportant44();if(latestData)renderLatestNews();});
