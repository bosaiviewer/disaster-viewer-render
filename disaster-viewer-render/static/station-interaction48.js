'use strict';
// Clear only on a short, stationary primary-pointer click on map background.
// Native map dragging, wheel zoom, multi-touch and long presses keep selection.
function bindStationGestures48(map,clear){
 map._clearSelection48=clear;if(map._selectionGestures48)return;map._selectionGestures48=true;
 const box=map.getContainer();let gesture=null;
 const down=e=>{if(!e.isPrimary||e.button!==0){if(gesture)gesture.valid=false;return;}gesture={x:e.clientX,y:e.clientY,start:performance.now(),valid:true,ended:false};};
 const move=e=>{if(gesture&&Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>6)gesture.valid=false;};
 const up=e=>{if(!gesture)return;move(e);gesture.ended=true;if(performance.now()-gesture.start>450)gesture.valid=false;};
 const cancel=()=>{if(gesture)gesture.valid=false;};
 const click=event=>{const original=event.originalEvent,target=original?.target;
  if(!original||!gesture?.valid||!gesture.ended||performance.now()-gesture.start>700)return;
  if(target?.closest?.('.leaflet-interactive,.leaflet-control,.leaflet-popup'))return;
  gesture=null;map._clearSelection48(event);
 };
 const filterStationClick=event=>{if(event.isTrusted&&event.detail!==0&&event.target.closest?.('.station-pin,.leaflet-marker-icon,.leaflet-interactive')&&gesture&&(!gesture.valid||!gesture.ended||performance.now()-gesture.start>700)){event.preventDefault();event.stopImmediatePropagation();}};
 const listeners=[['click',filterStationClick],['pointerdown',down],['pointermove',move],['pointerup',up],['pointercancel',cancel],['wheel',cancel],['contextmenu',cancel]];
 for(const [type,fn]of listeners)box.addEventListener(type,fn,{capture:true,passive:type!=='click'});
 map.on('dragstart zoomstart',cancel);map.on('click',click);
 map.once('unload',()=>{for(const [type,fn]of listeners)box.removeEventListener(type,fn,true);map.off('dragstart zoomstart',cancel);map.off('click',click);});
}
