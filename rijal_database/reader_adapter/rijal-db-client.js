/* Versioned, opt-in reader interface. Does not touch SHAMELA_DATA, R, or localStorage. */
(function(root){'use strict';
class RijalDatabaseClient{
 constructor(base='http://127.0.0.1:8765'){this.base=base.replace(/\/$/,'')}
 async request(path,params={},signal){const url=new URL(this.base+'/api/v1/'+path);for(const [k,v]of Object.entries(params))if(v!==undefined&&v!==null&&v!=='')url.searchParams.set(k,v);let response;try{response=await fetch(url,{signal})}catch(e){if(e.name==='AbortError')throw e;throw Error('شغّل قاعدة الرجال المحلية أولًا: START_WINDOWS.bat')};const result=await response.json();if(!response.ok)throw Error(result.error||'تعذر الاتصال بقاعدة الرجال');return result}
 search(query,options={}){const {signal,...params}=options;return this.request('search',{q:query,...params},signal)}
 page(id){return this.request('page/'+encodeURIComponent(id))}
 entry(id){return this.request('entry/'+encodeURIComponent(id))}
 sources(textId,options={}){return this.request('sources',{text_id:textId,...options})}
 books(query=''){return this.request('books',{q:query})}
 stats(){return this.request('stats')}
 open(query=''){const url=new URL(this.base+'/');if(query)url.searchParams.set('q',query);return root.open(url.href,'_blank','noopener')}
}
root.RijalDatabaseClient=RijalDatabaseClient;
})(typeof window==='undefined'?globalThis:window);
