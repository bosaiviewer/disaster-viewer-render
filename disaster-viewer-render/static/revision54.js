"use strict";
// Reset only transient submenus on information changes, never on an ordinary refresh.
const atmosphereDefaults54=new WeakMap();let atmosphereKind54=menu38.value;
function rememberAtmosphereDefaults54(root=$('atmosphere-view')){for(const select of root.querySelectorAll('select'))if(select!==menu38&&!atmosphereDefaults54.has(select))atmosphereDefaults54.set(select,select.value);}
rememberAtmosphereDefaults54();new MutationObserver(()=>rememberAtmosphereDefaults54()).observe($('atmosphere-view'),{childList:true,subtree:true});
function resetAtmosphereMenus54(){stopDust53();dustState53.product='surface';dustState53.area='jp';dustState53.speed='900';dustState53.selectedTime=null;dustState53.index=0;landslideKind53='all';for(const select of $('atmosphere-view').querySelectorAll('select'))if(select!==menu38&&atmosphereDefaults54.has(select))select.value=atmosphereDefaults54.get(select);}
const loadBefore54=loadAtmosphere;loadAtmosphere=async function(){const key=menu38.value;if(atmosphereKind54!==key)resetAtmosphereMenus54();atmosphereKind54=key;return loadBefore54();};menu38.onchange=loadAtmosphere;$('atmosphere-refresh').onclick=loadAtmosphere;
const changeBefore54=changeView;changeView=function(next){if(view==='atmosphere'){resetAtmosphereMenus54();atmosphereKind54=null;}changeBefore54(next);};

// New loading nodes share a wall-clock phase instead of starting from zero on every live repaint.
const spinnerStates54=new WeakMap(),spinnerNodes54=new WeakSet();
function phaseSpinners54(root){if(!root)return;const nodes=[];if(root.matches?.('.loading-text,.loading-status,.loading-spinner'))nodes.push(root);nodes.push(...root.querySelectorAll?.('.loading-text,.loading-status,.loading-spinner')||[]);for(const node of nodes){const delay=-(performance.now()%750)+'ms';if((node.classList.contains('loading-text')||node.classList.contains('loading-status'))&&!spinnerStates54.get(node)){node.style.setProperty('--spinner-delay54',delay);spinnerStates54.set(node,true);}if(node.classList.contains('loading-spinner')&&!spinnerNodes54.has(node)){node.style.animationDelay=delay;spinnerNodes54.add(node);}}}
const markBefore54=markLoadingTexts;markLoadingTexts=function(root,...args){markBefore54(root,...args);const target=root||document.querySelector('main');if(target){for(const node of [target,...target.querySelectorAll?.('[style*="spinner-delay54"]')||[]])if(!node.classList.contains('loading-text')&&!node.classList.contains('loading-status'))spinnerStates54.set(node,false);phaseSpinners54(target);}};
new MutationObserver(rows=>{for(const row of rows)for(const node of row.addedNodes)if(node.nodeType===1)phaseSpinners54(node);}).observe(document.querySelector('main'),{childList:true,subtree:true});

// Common region controls remain native selects in every view.
whenViewerReady48(()=>{phaseSpinners54(document.querySelector('main'));$('home-release50').querySelector('p').textContent='Ver.0.55 ／ 地域選択を元のプルダウンに統一し、選択時の強制フォーカス解除・取得中の選択肢更新を修正。ライブ取得ラベルの余白も調整しました。';});
