'use strict';
// Every fetch, including lazily opened detail/history panels, gets a visible activity indicator.
let activeRequests=0;const pendingImages=new Set();
const nativeFetch=window.fetch.bind(window);
window.fetch=function(...args){activeRequests++;updateGlobalLoading();return nativeFetch(...args).finally(()=>{activeRequests=Math.max(0,activeRequests-1);updateGlobalLoading();});};
function updateGlobalLoading(){const n=document.getElementById('global-loading');if(n){const live=document.getElementById('realtime-view')?.hidden===false;const hidden=!live&&activeRequests+pendingImages.size===0;if(n.hidden!==hidden)n.hidden=hidden;n.classList.toggle('live-stream54',live);const text=live?' ライブ情報を常時取得中':' 情報を取得中…';if(n.lastChild?.nodeType===3&&n.lastChild.textContent!==text)n.lastChild.textContent=text;}}
const loadingSelector48='p,span,strong,small,div[role=status]';
function markLoadingTexts(root=document.querySelector('main'),seen=new Set()){
 if(!root)return;const nodes=[];if(root.matches?.(loadingSelector48))nodes.push(root);if(root.querySelectorAll)nodes.push(...root.querySelectorAll(loadingSelector48));
 for(const n of nodes){if(seen.has(n))continue;seen.add(n);if(n.children.length||n.closest('#global-loading')||n.classList.contains('loading-spinner'))continue;const text=n.textContent.trim();n.classList.toggle('loading-text',/取得中|更新中|読み込み中|確認中|接続準備中/.test(text));}
}
document.addEventListener('DOMContentLoaded',()=>{
 const badge=document.createElement('span');badge.id='global-loading';badge.setAttribute('role','status');badge.innerHTML='<i class="loading-spinner" aria-hidden="true"></i> 情報を取得中…';document.querySelector('header').append(badge);updateGlobalLoading();
 let pending=false;const roots=new Set();
 new MutationObserver(records=>{
  for(const record of records){const target=record.target.nodeType===3?record.target.parentElement:record.target;if(target?.matches?.(loadingSelector48)&&!target.children.length)roots.add(target);for(const node of record.addedNodes||[])if(node.nodeType===1)roots.add(node);else if(node.parentElement?.matches?.(loadingSelector48))roots.add(node.parentElement);}
  if(pending||!roots.size)return;pending=true;queueMicrotask(()=>{pending=false;const seen=new Set(),batch=[...roots];roots.clear();for(const root of batch)if(root.isConnected)markLoadingTexts(root,seen);});
 }).observe(document.querySelector('main'),{childList:true,characterData:true,subtree:true});markLoadingTexts();
});

document.addEventListener('DOMContentLoaded',()=>{const finished=e=>{if(e.target?.tagName==='IMG'){pendingImages.delete(e.target);updateGlobalLoading();}};document.addEventListener('load',finished,true);document.addEventListener('error',finished,true);new MutationObserver(rows=>{for(const row of rows){const n=row.target;if(n.tagName==='IMG'&&!n.classList.contains('leaflet-tile')&&n.getAttribute('src')&&!n.complete)pendingImages.add(n);}for(const n of pendingImages)if(!n.isConnected||n.complete)pendingImages.delete(n);updateGlobalLoading();}).observe(document.querySelector('main'),{attributes:true,attributeFilter:['src'],subtree:true});});
