const {test} = require('node:test');
const assert = require('node:assert/strict');
const P = require('../core.js');
const fresh = () => ({claims: [], attempt: null});
test('progress is based on counts and rounds only for display', () => {
 for (const [filled,total,expected] of [[0,200,'0%'],[1,1000,'<1%'],[1,500,'<1%'],[1,200,'1%'],[5,1000,'1%'],[375,500,'75%'],[199,200,'99%'],[999,1000,'99%'],[1000,1000,'100%']]) assert.equal(P.progress(filled,total),expected);
});
test('currency is exact integer pence and rejects invalid or excessive precision',()=>{
 for(const [text,expected] of [['2',200],['2.01',201],['2.1',210],['1.999',null],['-2',null],['Infinity',null],['1e3',null],['',null]]) assert.equal(P.parseMoney(text),expected);
});
test('automatic selection finds exact, distinct balanced amounts at all three levels',()=>{
 for(const n of [200,500,1000]) for(const target of [200,500,1000]) for(let repeat=0;repeat<8;repeat++) {
  const values=Array.from({length:n},(_,i)=>i+1), picked=P.allocate(values,target);
  assert.ok(picked); assert.equal(picked.reduce((a,b)=>a+b,0),target);
  assert.equal(new Set(picked).size,picked.length); assert.ok(picked.every(v=>values.includes(v)));
  if(target===1000) assert.ok(picked.length>=5 && picked.length<=10);
 }
});
test('scarce allocation uses exact fallback and never silently increases amount',()=>{
 assert.deepEqual(P.allocate([1,2,197],200),[1,2,197]);
 assert.equal(P.allocate([199,202],200),null);
 assert.equal(P.allocate([1,2,3],200),null);
 assert.equal(P.allocate([200],199),null);
 assert.deepEqual(P.allocate([200],200),[200]);
});
test('reservation, return and review keep counts exclusive; approval alone advances progress',()=>{
 const c=fresh(), t=1000;
 P.start(c,[50,150],'Tester','',200,t,'EPC-000001');
 assert.deepEqual(P.counts(c,200,t),{approved:0,pending:0,reserved:2,available:198,amount:0});
 P.finish(c,'EPC-000001',t+1);
 assert.equal(P.counts(c,200,t+1).pending,2); assert.equal(P.counts(c,200,t+1).amount,0);
 assert.throws(()=>P.finish(c,'EPC-000001',t+2),/already/);
 P.review(c,'EPC-000001','approved');
 assert.deepEqual(P.counts(c,200,t+2),{approved:2,pending:0,reserved:0,available:198,amount:200});
 assert.equal(P.progress(2,200),'1%');
 assert.throws(()=>P.review(c,'EPC-000001','released'),/no longer pending/);
});
test('expired and replaced attempts cannot return; expiry releases square counts',()=>{
 const c=fresh(); P.start(c,[200],'Tester','',200,0,'EPC-000001');
 assert.equal(P.counts(c,200,P.RESERVATION_MS).reserved,0);
 assert.throws(()=>P.finish(c,'EPC-000001',P.RESERVATION_MS),/expired/);
 P.start(c,[199,1],'Tester','',200,0,'EPC-000002');
 assert.throws(()=>P.finish(c,'EPC-000001',1),/no longer active/);
 P.finish(c,'EPC-000002',1); P.review(c,'EPC-000002','released');
 assert.equal(P.counts(c,200,2).available,200);
});
test('checkout validates minimum, range, unique amounts, name and unavailable squares',()=>{
 const c=fresh();
 for(const amounts of [[199],[0,200],[200,200],[201]]) assert.throws(()=>P.start(c,amounts,'Tester','',200,0,'bad'));
 assert.throws(()=>P.start(c,[200],'','',200,0,'bad'));
 P.start(c,[200],'Tester','',200,0,'ok'); P.finish(c,'ok',1);
 assert.throws(()=>P.start(c,[200],'Tester','',200,2,'bad'),/no longer available/);
});
