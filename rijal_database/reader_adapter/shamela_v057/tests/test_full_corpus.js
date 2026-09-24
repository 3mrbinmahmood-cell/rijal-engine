const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.hidden=false;this.events={};this.classes=new Set(['hidden']);this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),contains:x=>this.classes.has(x)}}
 append(...items){this.children.push(...items)}
 replaceChildren(...items){this.children=items;this.textContent=''}
 addEventListener(name,fn){this.events[name]=fn}
 focus(){}
}
(async()=>{
 const ids=['corpusModal','corpusQuery','rijalQuery','q','corpusStatus','corpusResults','corpusDetail','corpusPrev','corpusNext','corpusSearch'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));nodes.rijalQuery.value='أحمد بن محمد';
 let ready,searches=0,identities=0;
 const document={getElementById:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>{if(name==='DOMContentLoaded')ready=fn}};
 const root={RijalDatabaseClient:class{
  async search(q){searches++;assert.equal(q,'أحمد بن محمد');return{results:[{id:'entry-1',title:'أحمد بن محمد',citation:{title:'كتاب الرجال'}}],has_more:false}}
  async entry(){return{entry:{title:'أحمد بن محمد'},citation:{title:'كتاب الرجال'},text:'نص المصدر',page_id:'page-1'}}
  async identity(){identities++;return{identity_kind:'provisional_cluster',entry_count:2,name_key:'احمد بن محمد',identity_id:'provisional'}}
  async identityDates(){return{summary:null,claims:[]}}
  async identityGraph(){return{results:[]}}
 }};
 const context={window:root,document,console,Promise,Error};
 Object.defineProperty(context,'localStorage',{get(){throw Error('Must not access existing notes')}});
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'..','full-corpus.js'),'utf8'),context);ready();
 root.showFullCorpus();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(searches,1);assert.equal(nodes.corpusResults.children.length,1);
 nodes.corpusResults.children[0].events.click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(identities,1);assert(nodes.corpusDetail.children.some(x=>x.textContent.includes('ربط مؤقت')));
 root.closeFullCorpus();assert(nodes.corpusModal.classList.contains('hidden'));
 console.log('PASS full-corpus reader view: search, source entry, provisional status, no notes access');
})().catch(e=>{console.error(e);process.exit(1)});
