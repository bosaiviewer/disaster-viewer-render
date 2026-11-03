'use strict';
// JMA jmatile PNG grids publish even-numbered levels. Odd-level requests can
// return a valid but completely transparent PNG, so HTTP/image success is not enough.
function nativeJmaZoom49(zoom,levels=[4,6,8,10]){return levels.filter(z=>z<=zoom).at(-1)??levels[0];}
const JmaRasterLayer49=L.TileLayer.extend({
 _clampZoom(zoom){
  const clamped=L.TileLayer.prototype._clampZoom.call(this,zoom);
  return this.options.nativeLevels49?nativeJmaZoom49(clamped,this.options.nativeLevels49):clamped;
 }
});
