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
 let ready,searches=0,identities=0,pages=0,evidence=0,mentions=0,members=0;
 const document={getElementById:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>{if(name==='DOMContentLoaded')ready=fn}};
 const root={ShamelaSanad:{parse:()=>['أحمد بن محمد']},RijalDatabaseClient:class{
  async search(q){searches++;assert.equal(q,'أحمد بن محمد');return{results:[{id:'entry-1',title:'أحمد بن محمد',citation:{title:'كتاب الرجال'}}],has_more:false}}
  async entry(){return{entry:{title:'أحمد بن محمد'},citation:{title:'كتاب الرجال'},text:'نص المصدر',page_id:'page-1'}}
  async identity(){identities++;return{identity_kind:'provisional_cluster',entry_count:2,name_key:'احمد بن محمد',identity_id:'provisional'}}
  async identityDates(){return{summary:{},claims:[{year:210,exact_quote:'مات سنة عشر ومائتين',page_id:'date-page'}]}}
  async page(id){pages++;return{text:'نص صفحة '+id,citation:{title:'كتاب الرجال'}}}
  async graphEvidence(id,relation,mention,{offset}){evidence++;return{results:[{entry_id:'entry-1',page_id:offset?'graph-page-2':'graph-page'}],has_more:offset===0}}
  async graphMention(){mentions++;return{results:[{identity_id:'other',display_name:'سعيد بن خالد',source_entries:2,identity_kind:'provisional_cluster'}],has_more:false}}
  async identityMembers(id,{offset}){members++;return{results:offset?[]:[{entry_id:'entry-1',name_label:'أحمد بن محمد',book_id:'كتاب'}],has_more:false}}
  async identityGraph(id,{relation}){return{results:relation==='teacher'?[{name:'سعيد',source_entries:2,mention_id:'mention-1'}]:[]}}
 }};
 const context={window:root,document,console,Promise,Error};
 Object.defineProperty(context,'localStorage',{get(){throw Error('Must not access existing notes')}});
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'..','full-corpus.js'),'utf8'),context);ready();
 root.showFullCorpusForName('أحمد بن محمد');await new Promise(resolve=>setImmediate(resolve));
 assert.equal(searches,1);assert.equal(nodes.corpusResults.children.length,1);
 nodes.corpusResults.children[0].events.click();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(identities,1);assert(nodes.corpusDetail.children.some(x=>x.textContent.includes('ربط مؤقت')));
 const date=nodes.corpusDetail.children.find(x=>x.children.some(y=>y.textContent==='صفحة دليل التاريخ'));
 await date.children[1].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(pages,1);
 const graph=nodes.corpusDetail.children.find(x=>x.children.some(y=>y.textContent==='مواضع الدليل'));
 await graph.children[1].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(evidence,1);
 const item=graph.children[3].children[1].children[0];await item.children[1].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(pages,2);
 await graph.children[3].children[1].children[1].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(evidence,2);
 await graph.children[2].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(mentions,1);
 const other=graph.children[4].children[1].children[0];await other.children[1].events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(members,1);
 root.showFullCorpusSanad('حدثنا أحمد بن محمد',true);await new Promise(resolve=>setImmediate(resolve));assert.equal(nodes.corpusResults.children.length,1);assert(nodes.corpusResults.children[0].children.some(x=>x.textContent.includes('مداخل مرشحة')));assert.equal(searches,2);
 root.closeFullCorpus();assert(nodes.corpusModal.classList.contains('hidden'));
 assert(!fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8').includes('onclick="openRijal()"'));assert(!fs.readFileSync(path.join(__dirname,'..','reader.js'),'utf8').match(/function analyzeCurrentSanad\(\)\{[^}]*loadRijal/));
 console.log('PASS full-corpus reader view: search, sanad candidates, evidence, no notes access');
})().catch(e=>{console.error(e);process.exit(1)});
