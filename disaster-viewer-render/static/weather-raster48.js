'use strict';
// Keep the displayed frame until its replacement actually has usable images.
// The old implementation removed it before the index request or new tiles loaded.
function renderWeatherRaster48(row){
 const map=atmosphereMap,key=atmosphereData.key;
 const token=map._rasterToken48=(map._rasterToken48||0)+1;
 let status=document.getElementById('atmosphere-render-status48');
 if(!status){status=el('p',undefined,'caption raster-status48');status.id='atmosphere-render-status48';$('atmosphere-map').before(status);}
 let previous=map._rasterDisplayed48;
 if(atmosphereTiles&&atmosphereTiles!==previous)map.removeLayer(atmosphereTiles);
 const wide=key==='satellite-wide',satellite=key==='satellite'||wide,opacity=satellite?.75:.8;
 const layer=new JmaRasterLayer49(row.url,{
  tileSize:key.startsWith('current-')?512:256,opacity:0,nativeLevels49:satellite?null:[4,6,8,10],
  minNativeZoom:wide?3:4,maxNativeZoom:wide?5:satellite?6:key==='thunder'?9:10,maxZoom:12,
  noWrap:true,bounds:wide?[[-70,55],[70,225]]:[[20,118],[50,155]],
  keepBuffer:2,updateWhenIdle:false,updateWhenZooming:true,attribution:'気象庁'
 });
 layer.weatherTime48=row.valid;let success=0,failed=0,retries=0,timer;
 const current=()=>map._rasterToken48===token&&map.hasLayer(layer);
 const retained=()=>previous&&map.hasLayer(previous)?'表示中は '+compactTime(previous.weatherTime48)+' の画像です。':'';
 const message=()=>{status.textContent=compactTime(row.valid)+' の画像を取得中… '+retained();};
 const commit=()=>{
  if(!current())return;
  layer.setOpacity(opacity);map._rasterDisplayed48=layer;
  if(previous&&previous!==layer&&map.hasLayer(previous))map.removeLayer(previous);previous=null;
  status.textContent='画像の表示時刻：'+compactTime(row.valid)+'（日本時間）'+(failed?' ／ 一部の画像は取得できません。':'');
 };
 layer.on('loading',()=>{if(current()){success=0;failed=0;message();}});
 layer.on('tileload',()=>success++);
 layer.on('tileerror',()=>failed++);
 layer.on('load',()=>{
  if(!current())return;
  if(success){commit();return;}
  if(failed){status.textContent='指定時刻の画像を取得できません。'+retained();$('atmosphere-error').hidden=false;$('atmosphere-error').textContent='画像の通信失敗・提供範囲外・提供終了の可能性があります。時刻を変更するか、再取得してください。';}
 });
 const ready=()=>Object.values(layer._tiles||{}).some(t=>t.current&&t.loaded&&t.el.complete&&t.el.naturalWidth>0);
 const recover=()=>{
  clearTimeout(timer);timer=setTimeout(()=>{
   if(!current()||view!=='atmosphere'||document.hidden||map._animatingZoom)return;
   if(ready()){commit();return;}
   if(!layer.isLoading()&&retries<2){retries++;layer.redraw();}
  },250);
 };
 map.on('zoomend moveend resize',recover);
 layer.once('remove',()=>{clearTimeout(timer);map.off('zoomend moveend resize',recover);});
 atmosphereTiles=layer;layer.addTo(map);message();recover();
}
