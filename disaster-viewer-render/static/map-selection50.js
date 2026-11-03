"use strict";
// One gesture observer per map. Station maps replace only the clear callback.
L.Map.addInitHook(function(){bindStationGestures48(this,event=>clearMapSelection50(this,event));});
function clearMapSelection50(m,event){
 const id=m.getContainer().id;m.closePopup();
 if(id==='map'){if(selected)clearSelection();}
 else if(id==='cyclone-map'){if(cycloneSelected)clearCyclone();}
 else if(id==='volcano-map'){if(volcanoSelected)clearVolcano();}
 else if(id==='tsunami-map'){if(tsunamiArea||tsunamiObservation){const r=tsunamiData?.history?.find(r=>r.id===tsunamiSelection)||tsunamiData?.current?.find(r=>r.id===tsunamiSelection);tsunamiArea=null;tsunamiObservation=null;updateTsunamiPressed();showTsunamiMap(r);} }
 else if(id==='realtime-map'){if(liveSelected||selectedWarningRegion){liveSelected=null;selectedWarningRegion=null;renderLive();}}
 else if(id==='warnings-map'){if(weatherWarningSelected){weatherWarningSelected=null;renderWeatherWarningDetail();renderWeatherWarningList();paintWarningDashboard(false);}}
 else if(id==='early-map'){if($('early-region').value){$('early-region').value='';renderEarly();}}
 else if(id==='chart-vector-map'){if(chartSelectedFeature){chartSelectedFeature=null;$('chart-vector-detail').replaceChildren();paintChartVectors();}}
 else if(id==='atmosphere-map'){
  if(marineSelected38){marineSelected38=null;renderMarine38();}
  if(amedasSelected){amedasSelected=null;$('atmosphere-detail').hidden=true;renderAmedas();}
  if(selectedRiverCode||selectedRiverStation){selectedRiverCode=null;selectedRiverStation=null;riverDetailToken++;$('atmosphere-detail').hidden=true;riverCamera.hidden=true;riverSelect.value='';paintRiverGauges();}
 }

 m.fire('selectionclear50');
}
