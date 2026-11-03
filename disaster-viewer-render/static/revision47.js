'use strict';
// Capture the position immediately before rendering, including when a download
// finishes after the reader has scrolled. Explicit selection handlers still scroll.
function preserveRender47(render){return function(...args){
 const x=window.scrollX,y=window.scrollY,currentView=view,intent=scrollIntent34;
 const result=render.apply(this,args);
 if(!document.hidden&&currentView===view&&view!=='realtime'){
  window.scrollTo({left:x,top:y,behavior:'instant'});
  requestAnimationFrame(()=>{if(currentView===view&&intent===scrollIntent34)window.scrollTo({left:x,top:y,behavior:'instant'});});
 }
 return result;
};}
renderLatestNews=preserveRender47(renderLatestNews);
renderMarine38=preserveRender47(renderMarine38);
if(typeof renderBulletins==='function')renderBulletins=preserveRender47(renderBulletins);

// A hidden pane or a zoom animation must not permanently remove weather tiles.
const frameBefore47=showAtmosphereFrame;
showAtmosphereFrame=function(...args){
 const result=frameBefore47(...args);
 if(atmosphereTiles){atmosphereTiles.options.keepBuffer=2;atmosphereTiles.options.updateWhenZooming=true;}
 return result;
};
