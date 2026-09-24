/* Contract and DOM mount tests; no real browser engine is required. */
const assert=require('assert'),vm=require('vm'),fs=require('fs'),path=require('path');
const base=path.resolve(__dirname,'..');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.style={};this.dataset={};this.textContent='';this.listeners={}}
 append(...items){this.children.push(...items)}
 addEventListener(type,fn){this.listeners[type]=fn}
 querySelector(selector){return this.children.find(e=>e.tagName===selector)||null}
 showModal(){this.open=true}close(){this.open=false}
}
(async()=>{
 const host=new Element('header'),body=new Element('body'),created=[],calls=[];
 const document={readyState:'complete',createElement:tag=>{const e=new Element(tag);created.push(e);return e},
  getElementById:id=>created.find(e=>e.id===id),querySelector:s=>s==='header'?host:null,body};
 const response={results:[{page_id:'stable-page',citation:{title:'المصدر'}}]};
 const root={getSelection:()=>({toString:()=> 'أسامة بن عمير'}),open:(...args)=>calls.push(['open',...args])};
 const context={window:root,document,URL,Error,console,fetch:async(url)=>{calls.push(['fetch',url.href]);return{ok:true,json:async()=>response}}};
 Object.defineProperty(context,'localStorage',{get(){throw Error('Adapter must never touch reader storage')}});
 vm.createContext(context);for(const f of ['rijal-db-client.js','rijal-db-button.js'])vm.runInContext(fs.readFileSync(path.join(base,'reader_adapter',f),'utf8'),context);
 assert.equal(host.children.length,1);const b=host.children[0];assert.equal(b.id,'rijalDatabaseButton');b.listeners.click();
 const dialog=document.getElementById('rijalDatabaseDialog');assert(dialog.open);assert.equal(new URL(dialog.querySelector('iframe').src).searchParams.get('q'),'أسامة بن عمير');
 const client=new root.RijalDatabaseClient();const result=await client.search('أسامة بن عمير',{scope:'entries',limit:20});assert.equal(result.results[0].page_id,'stable-page');
 const url=new URL(calls.find(x=>x[0]==='fetch')[1]);assert.equal(url.pathname,'/api/v1/search');assert.equal(url.searchParams.get('scope'),'entries');
 await client.page('stable-page');await client.sources(2,{offset:100});await client.entry('entry-id');
 await client.identity('entry-id');await client.identityDates('entry-id');
 await client.identityGraph('entry-id',{relation:'teacher',limit:8});
 await client.graphEvidence('entry-id','teacher','mention-id',{limit:2});
 await client.graphMention('mention-id',{relation:'student'});
 const urls=calls.filter(x=>x[0]==='fetch').map(x=>new URL(x[1]));
 assert(urls.some(u=>u.pathname==='/api/v1/identity/entry/entry-id'));
 assert(urls.some(u=>u.pathname==='/api/v1/identity/graph/entry-id'&&u.searchParams.get('relation')==='teacher'));
 assert(urls.some(u=>u.pathname==='/api/v1/graph/evidence/entry-id'&&u.searchParams.get('mention')==='mention-id'));
 const before=created.length;vm.runInContext(fs.readFileSync(path.join(base,'reader_adapter','rijal-db-button.js'),'utf8'),context);assert.equal(created.length,before,'Repeated mount must not duplicate the button');
 console.log('PASS reader adapter: asynchronous API contract, query encoding, in-reader modal, repeated mount, no access to annotation storage');
})().catch(e=>{console.error(e);process.exit(1)});
