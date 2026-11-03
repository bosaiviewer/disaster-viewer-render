'use strict';
// Invalidate queued viewport restorations when the browser leaves this page.
function clearBrowserAnchors48(){scrollIntent34++;expansionAnchor35=null;if(expansionFrame35!==null){cancelAnimationFrame(expansionFrame35);expansionFrame35=null;}}
document.addEventListener('visibilitychange',clearBrowserAnchors48);
for(const name of ['blur','focus','pagehide','pageshow'])window.addEventListener(name,clearBrowserAnchors48);
