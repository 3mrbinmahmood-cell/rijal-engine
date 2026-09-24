/* Extract candidate names from a selected chain; Rijal evidence is queried from the full database. */
(function(root){'use strict';
function parse(text,max=12){let raw=String(text).slice(0,2400),clean=raw.normalize('NFD').replace(/[\u064B-\u065F\u0670\u200B\u200C]/g,'');let stop=clean.search(/(?:ان رسول الله|ان النبي|قال رسول الله|قال النبي|ذكر النبي|صلى الله عليه وسلم)/u);if(stop>=0)clean=clean.slice(0,stop);let markers=/(?:^|[\s،.:؛])(?:حدثنا|حدثني|اخبرنا|اخبرني|سمعت|عن)\s+/gu;let hits=[...clean.matchAll(markers)],parts=[];for(let i=0;i<hits.length&&parts.length<max;i++){let start=hits[i].index+hits[i][0].length,end=hits[i+1]?.index??clean.length;let rawName=clean.slice(start,end).replace(/^\s+/,'').split(/(?:\s+قال(?:\s*[:،.]|\s*$)|[:،.؛\n]|\s+ان\s+)/u,1)[0].trim();if(rawName.length>2&&rawName.length<140&&!/^(?:رسول|النبي|الله)/u.test(rawName))parts.push(rawName)}return parts}
root.ShamelaSanad={parse};
})(typeof self!=='undefined'?self:globalThis);
