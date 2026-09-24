const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.hidden=false;this.events={};this.classes=new Set(['hidden']);this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),contains:x=>this.classes.has(x)}}
 append(...items){this.children.push(...items)}
 replaceChildren(...items){this.children=items;this.textContent=''}
 addEventListener(name,fn){this.events[name]=fn}
 setAttribute(name,value){this[name]=value}
 focus(){}
}
(async()=>{
 const ids=['corpusModal','corpusQuery','rijalQuery','q','corpusStatus','corpusResults','corpusDetail','corpusPrev','corpusNext','corpusSearch'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));nodes.rijalQuery.value='أحمد بن محمد';
 let ready,searches=0,identities=0,pages=0,evidence=0,mentions=0,members=0;
 const document={getElementById:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>{if(name==='DOMContentLoaded')ready=fn}};
 const root={ShamelaSanad:{parse:input=>input==='ali'?['علي ابن حجر']:input==='two'?['أحمد بن محمد','سعيد بن خالد']:['أحمد بن محمد']},RijalDatabaseClient:class{
  async books(){return[{id:'taqrib',title:'تقريب التهذيب'},{id:'tahdhib',title:'تهذيب التهذيب'},{id:'mizzi',title:'تهذيب الكمال في أسماء الرجال'},{id:'sullam',title:'سلم الوصول إلى طبقات الفحول'}]}
  async search(q,{book}={}){searches++;if(q==='علي ابن حجر'){if(book==='tahdhib')throw Error('Book search unavailable');return{results:book?[]:[{id:'ali',title:'علي بن حجر السعدي',citation:{title:'كتاب الرجال'}}],has_more:false}}if(q==='سعيد بن خالد')return{results:[{id:'said',title:'سعيد بن خالد',citation:{title:'كتاب الرجال'}}],has_more:false};if(q==='عائشة'){const subject={id:'aisha',title:'5 - عائشة بنت أبي بكر',citation:{title:'سلم الوصول إلى طبقات الفحول'}};const incidental={id:'mention',title:'973 - محمد بن عطاء عن عائشة',citation:{title:'لسان الميزان'}};return{results:book==='sullam'?[subject]:book?[]:[incidental,subject],has_more:false}}assert.equal(q,'أحمد بن محمد');const grade={id:'entry-1',title:'أحمد بن محمد ثقة',citation:{title:'تقريب التهذيب'}};const generic={id:'entry-2',title:'أحمد بن محمد',citation:{title:'كتاب الرجال'}};return{results:book==='taqrib'?[grade]:book?[]:[generic,grade],has_more:false}}
  async entry(){return{entry:{title:'أحمد بن محمد'},citation:{title:'كتاب الرجال'},text:'نص المصدر',page_id:'page-1'}}
  async identity(){identities++;return{identity_kind:'provisional_cluster',entry_count:2,name_key:'احمد بن محمد',identity_id:'provisional'}}
  async identityDates(){return{summary:{},claims:[{year:210,exact_quote:'مات سنة عشر ومائتين',page_id:'date-page'}]}}
  async page(id){pages++;return{text:'نص صفحة '+id,citation:{title:'كتاب الرجال'}}}
  async graphEvidence(id,relation,mention,{offset}){evidence++;return{results:[{entry_id:'entry-1',page_id:offset?'graph-page-2':'graph-page'}],has_more:offset===0}}
  async graphMention(){mentions++;return{results:[{identity_id:'other',display_name:'سعيد بن خالد',source_entries:2,identity_kind:'provisional_cluster'}],has_more:false}}
  async identityMembers(id,{offset}){members++;return{results:offset?[]:[{entry_id:'entry-1',name_label:'أحمد بن محمد',book_id:'كتاب'}],has_more:false}}
  async identityGraph(id,{relation}){return{results:relation==='teacher'?[{name:'سعيد بن خالد',source_entries:2,mention_id:'mention-1'}]:[],has_more:false}}
 }};
 const context={window:root,document,console,Promise,Error};
 Object.defineProperty(context,'localStorage',{get(){throw Error('Must not access existing notes')}});
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'..','full-corpus.js'),'utf8'),context);ready();
 root.showFullCorpusForName('أحمد بن محمد');await new Promise(resolve=>setImmediate(resolve));
 assert.equal(searches,5);assert.equal(nodes.corpusResults.children.length,2);assert(nodes.corpusResults.children[0].textContent.includes('عبارة حكم'));
 nodes.corpusResults.children[0].events.click();await new Promise(resolve=>setImmediate(resolve));
 function all(node){return [node,...node.children.flatMap(all)]}
 function byText(value){return all(nodes.corpusDetail).find(x=>x.tagName==='button'&&x.textContent===value)}
 assert.equal(identities,1);assert(all(nodes.corpusDetail).some(x=>x.textContent.includes('ربط مؤقت')));
 assert(all(nodes.corpusDetail).some(x=>x.textContent==='الشيوخ المذكورون'));
 assert(all(nodes.corpusDetail).some(x=>x.textContent==='التلاميذ المذكورون'));
 assert(all(nodes.corpusDetail).some(x=>x.tagName==='table'));
 await byText('صفحة الدليل').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(pages,1);
 await byText('مواضع الدليل').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(evidence,1);
 await byText('صفحة المصدر').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(pages,2);
 await byText('عرض المزيد').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(evidence,2);
 await byText('هويات تذكر الاسم').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(mentions,1);
 await byText('مداخل هذه الهوية').events.click();await new Promise(resolve=>setImmediate(resolve));assert.equal(members,1);
 root.showFullCorpusSanad('حدثنا أحمد بن محمد',true);await new Promise(resolve=>setImmediate(resolve));assert.equal(nodes.corpusResults.children.length,2);assert(nodes.corpusResults.children[1].children.some(x=>x.textContent.includes('تراجم تبدأ بالاسم')));assert(nodes.corpusStatus.textContent.includes('الأول: أحمد بن محمد'));assert.equal(searches,10);
 root.showFullCorpusSanad('two',true);await new Promise(resolve=>setImmediate(resolve));await new Promise(resolve=>setImmediate(resolve));const chain=all(nodes.corpusResults).find(x=>x.className==='chain-link found');assert(chain,'recorded teacher mention gives a green link');await chain.events.click();await new Promise(resolve=>setImmediate(resolve));assert(evidence>2,'green link opens relationship evidence');
 root.showFullCorpusForName('عائشة');await new Promise(resolve=>setImmediate(resolve));assert(nodes.corpusResults.children[0].textContent.includes('عائشة بنت أبي بكر'));assert(nodes.corpusResults.children[1].textContent.includes('محمد بن عطاء'));
 root.showFullCorpusSanad('ali',true);await new Promise(resolve=>setImmediate(resolve));assert(nodes.corpusResults.children[1].children.some(x=>x.textContent.includes('علي بن حجر السعدي')));
 root.closeFullCorpus();assert(nodes.corpusModal.classList.contains('hidden'));
 assert(!fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8').includes('onclick="openRijal()"'));assert(!fs.readFileSync(path.join(__dirname,'..','reader.js'),'utf8').match(/function analyzeCurrentSanad\(\)\{[^}]*loadRijal/));
 console.log('PASS full-corpus reader view: search, sanad candidates, evidence, no notes access');
})().catch(e=>{console.error(e);process.exit(1)});
