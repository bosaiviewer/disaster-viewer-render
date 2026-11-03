'use strict';
// Promise-compatible, single-flight loading without parsing unused maps at home.
function lazyPromise48(factory){let pending;const get=()=>pending??=(Promise.resolve().then(factory));return {then:(...args)=>get().then(...args),catch:(...args)=>get().catch(...args),finally:(...args)=>get().finally(...args)};}

let viewerReady48=typeof document!=='undefined'&&document.readyState==='complete';
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{viewerReady48=true;},{once:true});
function whenViewerReady48(callback){if(viewerReady48)callback();else document.addEventListener('DOMContentLoaded',callback,{once:true});}
