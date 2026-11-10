/* Browser-session simulation only. No payments, accounts or network API calls. */
(() => {
  'use strict';
  const P = window.Penny, el = id => document.getElementById(id), format = P.money;
  const STORE = 'epc-group1-session-v1';
  let db = {owner: null, challenges: {}, references: [], receipt: null};
  let level = 2, pickedLevel = 2, view = 'mosaic', ownerMode = false;
  let selected = new Set(), records = {}, checkoutAttempt = null, suggestionTarget = null;
  let storageReady = true, noticeTimer, automaticNotice = '';
  try {
    const stored = JSON.parse(sessionStorage.getItem(STORE) || 'null');
    if (stored && stored.challenges && Array.isArray(stored.references)) db = stored;
    sessionStorage.setItem(STORE, JSON.stringify(db));
  } catch { storageReady = false; }
  const challengeKey = () => db.owner.email.toLowerCase() + ':' + level;
  function challenge() {
    const key = challengeKey();
    if (!db.challenges[key]) {
      db.challenges[key] = {claims: [], attempt: null, selection: [], donor: '', message: '', updatedAt: Date.now()};
      persist();
    }
    return db.challenges[key];
  }
  function message(id, text) {
    el(id).textContent = text; el(id).classList.toggle('show', Boolean(text));
  }
  function transaction(change) {
    const old = JSON.stringify(db);
    try {
      change(); sessionStorage.setItem(STORE, JSON.stringify(db)); storageReady = true; return true;
    } catch (error) {
      db = JSON.parse(old);
      message('campaignNotice', 'Unable to save this action: ' + error.message + ' No change was applied.');
      return false;
    }
  }
  function persist() {
    try { sessionStorage.setItem(STORE, JSON.stringify(db)); storageReady = true; return true; }
    catch { storageReady = false; message('campaignNotice','Browser session storage is unavailable. Enable it to continue to checkout; no claim has been saved.'); return false; }
  }
  function warn(text) { message('warning', text); }
  function totalSelection() { return [...selected].reduce((a,b)=>a+b,0); }
  function saveSelection() {
    const c = challenge(); c.selection = [...selected]; c.updatedAt = Date.now(); persist();
  }
  function refreshState() {
    if (!db.owner) return;
    const c = challenge(), now = Date.now(); let changed = false;
    if (c.attempt && c.attempt.expiresAt <= now) {
      c.attempt = null; changed = true;
      message('campaignNotice','The 30-minute reservation expired. Review your available selection before starting again.');
    }
    if (now - c.updatedAt >= P.RECOVERY_MS && (c.selection.length || c.donor || c.message)) {
      c.selection = []; c.donor = ''; c.message = ''; selected.clear();
      el('donor').value = ''; el('donormessage').value = ''; changed = true;
      message('campaignNotice','Your saved selection has expired. Please choose your squares again.');
    }
    if (changed) persist();
    const allowed = new Set(P.available({...c, attempt: null},level*100,now));
    selected = new Set(c.selection.filter(i=>allowed.has(i)));
    records = {};
    for (const claim of c.claims) if (['pending','approved'].includes(claim.status)) {
      claim.amounts.forEach(i=>records[i]={status:claim.status,name:claim.donor,message:claim.message});
    }
    if(c.attempt) c.attempt.amounts.forEach(i=>records[i]={status:'reserved',name:'Checkout reservation'});
  }
  function state(i) { return records[i]?.status || (selected.has(i)?'selected':'available'); }
  function hue(i) { return `hsl(${Math.round(195+285*(i-1)/(level*100))%360} 74% 67%)`; }
  function toggle(i) {
    refreshState();
    if(challenge().attempt) { warn('Resume or cancel the active checkout before editing your selection.'); return; }
    const focusSquare=document.activeElement?.dataset.square;
    if (records[i]) { warn('That square is not available.'); return; }
    if (selected.has(i)) selected.delete(i); else selected.add(i);
    suggestionTarget = null; saveSelection(); message('warning',''); render();
    if(focusSquare)document.querySelector(`[data-square="${focusSquare}"]:not(.hidden *)`)?.focus({preventScroll:true});
  }
function measurePixelPositions(n){
  // Every cell lies on the same square lattice. Generate full glyph masks, then
  // trim or grow ONLY perimeter cells to reach precisely 200/500/1000 squares.
  const text='£'+level;
  const measure=document.createElement('canvas').getContext('2d');
  let best=null;
  for(let rows=18;rows<=72;rows++){
    const size=rows*12;
    measure.font=`900 ${Math.round(size*.84)}px Arial Black,Arial,sans-serif`;
    const width=Math.ceil(measure.measureText(text).width/12)+6;
    if(width>140)continue;
    const can=document.createElement('canvas');can.width=width*12;can.height=size;
    const ctx=can.getContext('2d');ctx.fillStyle='#000';ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.font=measure.font;ctx.fillText(text,can.width/2,can.height/2+size*.035);
    const data=ctx.getImageData(0,0,can.width,can.height).data;
    const cells=new Set();
    for(let y=0;y<rows;y++)for(let x=0;x<width;x++){
      let hits=0;
      for(let yy=2;yy<12;yy+=3)for(let xx=2;xx<12;xx+=3){if(data[((y*12+yy)*can.width+x*12+xx)*4+3]>128)hits++}
      if(hits>=8)cells.add(y*width+x);
    }
    const error=Math.abs(cells.size-n);
    // Prefer a nearly exact dense glyph, so almost no pixels need adjustment.
    if(!best||error<best.error)best={width,rows,cells,error};
    if(error===0)break;
  }
  const {width,rows,cells}=best;
  const neighbours=(id)=>{
    const x=id%width,y=Math.floor(id/width);
    return [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].filter(([a,b])=>a>=0&&a<width&&b>=0&&b<rows).map(([a,b])=>b*width+a);
  };
  // Adjust only on the outer outline. Never randomly skip interior pixels.
  while(cells.size>n){
    let options=[...cells].filter(id=>neighbours(id).some(v=>!cells.has(v)));
    options.sort((a,b)=>{
      const da=neighbours(a).filter(v=>cells.has(v)).length;
      const db=neighbours(b).filter(v=>cells.has(v)).length;
      return da-db || a-b;
    });
    if(!options.length)break;
    cells.delete(options[0]);
  }
  while(cells.size<n){
    let border=new Set();
    for(const id of cells)for(const other of neighbours(id))if(!cells.has(other))border.add(other);
    let options=[...border];
    options.sort((a,b)=>{
      const da=neighbours(a).filter(v=>cells.has(v)).length;
      const db=neighbours(b).filter(v=>cells.has(v)).length;
      return db-da || a-b;
    });
    if(!options.length)break;
    cells.add(options[0]);
  }
  const sorted=[...cells].sort((a,b)=>a-b);
  const coords=sorted.map(id=>({x:id%width,y:Math.floor(id/width)}));
  const minX=Math.min(...coords.map(p=>p.x)),maxX=Math.max(...coords.map(p=>p.x));
  const minY=Math.min(...coords.map(p=>p.y)),maxY=Math.max(...coords.map(p=>p.y));
  return {cols:maxX-minX+1,rows:maxY-minY+1,positions:coords.map(p=>({x:p.x-minX,y:p.y-minY}))};
}
const artworkCache=new Map();
function pixelPositions(n){if(!artworkCache.has(n))artworkCache.set(n,measurePixelPositions(n));return artworkCache.get(n);}
function artwork(){
  const n=level*100,{cols,rows,positions}=pixelPositions(n),root=el('mosaic');
  root.innerHTML='';
  const frame=root.parentElement;
  const gap=2;
  // Fit as large as possible in the frame, filling its width and height.
  const availWidth=Math.max(260,frame.clientWidth-26);
  const availHeight=Math.max(330,Math.min(650,window.innerHeight*.68));
  const size=Math.max(5,Math.min(27,Math.floor((availWidth-(cols-1)*gap)/cols),Math.floor((availHeight-(rows-1)*gap)/rows)));
  root.style.gridTemplateColumns=`repeat(${cols}, ${size}px)`;
  root.style.gridTemplateRows=`repeat(${rows}, ${size}px)`;
  root.style.gap=gap+'px';root.style.width='max-content';root.style.height='max-content';
  const fragment=document.createDocumentFragment();
  for(let i=1;i<=n;i++){
    const p=positions[i-1],b=document.createElement('button');
    b.className='tile '+state(i);b.dataset.square=i;
    b.style.cssText=`grid-column:${p.x+1};grid-row:${p.y+1};--hue:${hue(i)};width:${size}px;height:${size}px`;
    b.title=format(i)+(records[i]?' — '+records[i].name+' ('+records[i].status+')':'');
    b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',String(selected.has(i)));b.disabled=Boolean(records[i])||Boolean(challenge().attempt);b.onclick=()=>toggle(i);fragment.append(b);
  }
  root.append(fragment);
}
  function drawGrid() {
    const root = el('grid'); root.replaceChildren();
    for(let i=1;i<=level*100;i++) {
      const b=document.createElement('button'); b.className='gridcell '+state(i); b.dataset.square=i;
      b.style.setProperty('--hue',hue(i)); b.textContent=format(i);
      b.setAttribute('aria-label',format(i)+' — '+state(i));
      b.setAttribute('aria-pressed',String(selected.has(i)));
      b.disabled=Boolean(records[i])||Boolean(challenge().attempt); b.onclick=()=>toggle(i); root.append(b);
    }
  }
  function render() {
    if (!db.owner) return;
    refreshState(); const c=challenge(), n=level*100, figures=P.counts(c,n);
    el('mosaic').classList.toggle('hidden',view!=='mosaic'); el('grid').classList.toggle('hidden',view!=='grid');
    if(view==='mosaic') artwork(); else drawGrid();
    const sum=totalSelection();
    el('total').textContent=format(sum); el('chosen').textContent=selected.size+' square'+(selected.size===1?'':'s');
    el('minnote').textContent='£2 minimum donation';
    if(sum>0 && sum<200)warn(`Add ${format(200-sum)} more to reach the £2 minimum donation.`);
    el('donate').disabled=sum<200 || !storageReady || Boolean(c.attempt);
    el('resume').classList.toggle('hidden',!c.attempt);
    el('raised').textContent=format(figures.amount); el('claimed').textContent=`${figures.approved} / ${n}`;
    el('completion').textContent=P.progress(figures.approved,n)+' complete';
    el('progress').style.width=(figures.approved/n*100)+'%';
    el('progress').parentElement.setAttribute('aria-valuenow',String(figures.approved/n*100));
    el('progress').parentElement.setAttribute('aria-valuetext',P.progress(figures.approved,n)+' of squares approved');
    const begun=c.claims.some(x=>x.status!=='released') || Boolean(c.attempt);
    el('changeChallenge').classList.toggle('hidden',begun);
    el('contactHelp').classList.add('hidden');
    const available=P.available(c,n), remaining=available.reduce((a,b)=>a+b,0);
    let nextNotice='';
    if(figures.approved===n) nextNotice='Challenge complete! Every square has been approved.';
    else if(remaining>0 && remaining<200 && !c.attempt) nextNotice=`Only ${format(remaining)} of squares is available, below the £2 minimum. Please check back if pending or reserved squares become available.`;
    else if(!available.length && figures.approved!==n) nextNotice='All squares are approved, pending or temporarily reserved. Further selection is unavailable until squares are released.';
    if(nextNotice || automaticNotice)message('campaignNotice',nextNotice);
    automaticNotice=nextNotice;
    el('selectionList').replaceChildren();
    for(const i of [...selected].sort((a,b)=>a-b)) {
      const b=document.createElement('button'); b.textContent=format(i)+' ×';
      b.setAttribute('aria-label','Remove '+format(i)); b.disabled=Boolean(c.attempt);
      b.onclick=()=>toggle(i); el('selectionList').append(b);
    }
    if(!selected.size) el('selectionList').textContent='No squares selected.';
    el('shuffle').disabled=!suggestionTarget || Boolean(c.attempt);
    for(const id of ['suggest','clear','donationValue','donor','donormessage']) el(id).disabled=Boolean(c.attempt);
    document.querySelectorAll('[data-bundle]').forEach(b=>b.disabled=Boolean(c.attempt));
    const box=el('dashboardCounts'); box.replaceChildren();
    for(const status of ['approved','pending','reserved','available']) {
      const item=document.createElement('div'), number=document.createElement('b'), label=document.createElement('span');
      number.textContent=figures[status]; label.textContent=status==='reserved'?'Temporarily reserved':status[0].toUpperCase()+status.slice(1);
      item.append(number,label); box.append(item);
    }
    el('dashboardProgress').textContent=`${figures.approved} of ${n} squares filled — ${P.progress(figures.approved,n)} complete`;
    renderQueue(); renderOwner(); updateClock();
  }
  function suggest(target) {
    refreshState();
    if(challenge().attempt) { warn('Resume or cancel the active checkout before changing your selection.'); return; }
    if(target===null || target<200) { warn('Enter a donation of at least £2.00, using no more than two decimal places.'); return; }
    const pool=P.available(challenge(),level*100), all=pool.reduce((a,b)=>a+b,0);
    if(target>all) { warn(`Only ${format(all)} is currently available. Your previous selection has been kept.`); return; }
    const picked=P.allocate(pool,target);
    if(!picked) { warn(`No available combination totals exactly ${format(target)}. Try another value or select squares manually. Your previous selection has been kept.`); return; }
    const previous=[...selected].join(',');
    let next=picked;
    if(suggestionTarget===target && previous===next.join(',')) {
      for(let i=0;i<5 && previous===next.join(',');i++) next=P.allocate(pool,target);
    }
    selected=new Set(next); suggestionTarget=target; el('donationValue').value=(target/100).toFixed(2);
    saveSelection(); warn(previous===next.join(',')?'The available amounts produced the same combination. You can edit it manually.':''); render();
  }
  function beginCheckout() {
    refreshState(); const c=challenge();
    if(c.attempt) { showCheckout(c.attempt); return; }
    if(!el('donor').value.trim()){warn('Please enter your name before continuing.');el('donor').focus();return;}
    if(totalSelection()<P.MINIMUM){warn('Select at least £2.00 before continuing.');return;}
    let attempt;
    if(!transaction(()=>{
      const ref=P.reference(db.references,()=>crypto.getRandomValues(new Uint32Array(1))[0]/4294967296);
      attempt=P.start(challenge(),[...selected],el('donor').value,el('donormessage').value,level*100,Date.now(),ref);
      db.references.push(ref);
    })) { render(); return; }
    message('warning',''); showCheckout(attempt); render();
  }
  function showCheckout(attempt) {
    checkoutAttempt={...attempt};
    el('checkoutAmount').textContent=format(attempt.amount); el('checkoutRef').textContent=attempt.ref;
    el('checkoutSquares').textContent=attempt.amounts.map(format).join(' · ');
    message('checkoutError',''); el('simulateReturn').disabled=false;
    el('checkout').showModal(); updateClock();
  }
  function updateClock() {
    if(!el('checkout').open || !checkoutAttempt) return;
    const remaining=Math.max(0,checkoutAttempt.expiresAt-Date.now());
    el('reservationClock').textContent=remaining ? `Reserved for ${Math.ceil(remaining/60000)} more minute${Math.ceil(remaining/60000)===1?'':'s'}.` : 'Reservation expired. Please review your selection.';
    el('simulateReturn').disabled=remaining===0;
    if(!remaining) message('checkoutError',`Reservation ${checkoutAttempt.ref} expired. Return to the challenge and review your selection. No claim was created.`);
  }
  function cancelCheckout() {
    if(!transaction(()=>{challenge().attempt=null;})) return;
    el('checkout').close(); checkoutAttempt=null; render();
    message('campaignNotice','Checkout cancelled. Your available squares and details have been kept for up to one hour.');
    el('donate').focus();
  }
  function finishCheckout() {
    if(!checkoutAttempt) return;
    el('simulateReturn').disabled=true;
    let claim;
    if(!transaction(()=>{
      claim=P.finish(challenge(),checkoutAttempt.ref,Date.now());
      challenge().selection=[]; challenge().donor=''; challenge().message='';
      db.receipt={...claim, challengeName:db.owner.name+"’s challenge", level};
    })) { message('checkoutError','The return could not be saved. Review the message on the challenge and try again.'); updateClock(); return; }
    selected.clear(); suggestionTarget=null; el('donor').value=''; el('donormessage').value='';
    el('checkout').close(); checkoutAttempt=null; render();
    history.pushState({receipt:true},'',location.pathname+'?thankyou=1'); showReceipt();
  }
  function showReceipt() {
    el('welcome').classList.add('hidden'); el('campaignMain').classList.add('hidden'); el('thankyou').classList.remove('hidden');
    const receipt=db.receipt;
    el('receiptPrivate').classList.toggle('hidden',!receipt);
    el('receiptChallenge').textContent=receipt?receipt.challengeName:'Thank you for supporting the Every Penny Challenge.';
    if(receipt) {
      el('receiptAmount').textContent=format(receipt.amount); el('receiptSquares').textContent=receipt.amounts.map(format).join(' · ');
      el('receiptRef').textContent=receipt.ref;
      const claim=Object.values(db.challenges).flatMap(c=>c.claims).find(c=>c.ref===receipt.ref);
      const status=claim?.status || 'pending';
      const statusText=el('receiptStatus');
      statusText.textContent=status==='pending'?'Claimed, awaiting approval. These squares do not count towards approved progress yet. No approval deadline is promised.':status==='approved'?'Approved. Thank you for your support.':'This claim has been released; its squares are available again.';
    }
    el('receiptNotice').textContent=receipt?'':'Detailed acknowledgements are available only in the original browser session. ';
    el('thankyou').focus(); window.scrollTo(0,0);
  }
  function dashboardNotice(text) {
    clearTimeout(noticeTimer); message('dashboardNotice',text);
    noticeTimer=setTimeout(()=>message('dashboardNotice',''),5000);
  }
  function reviewAction(ref,action,button) {
    if(!ownerMode) { dashboardNotice('Open the fundraiser controls first.'); return; }
    if(!confirm(action==='approved'?`Approve claim ${ref}?`:`Release claim ${ref}? Its squares will become available again.`)) return;
    button.disabled=true; button.textContent='Processing…';
    try {
      if(!transaction(()=>P.review(challenge(),ref,action))) { dashboardNotice('The action was not saved. No change was applied.'); return; }
      render(); dashboardNotice(`Claim ${ref} ${action==='approved'?'approved':'released'}.`);
    } finally { button.disabled=false; }
  }
  function renderQueue() {
    const root=el('queue'); root.replaceChildren();
    const c=challenge(), active=c.claims.filter(x=>x.status==='pending');
    if(c.attempt) {
      const reserved=document.createElement('div'); reserved.className='entry';
      reserved.textContent=`${c.attempt.ref} · ${c.attempt.amounts.length} squares temporarily reserved · ${format(c.attempt.amount)} · expires in ${Math.max(1,Math.ceil((c.attempt.expiresAt-Date.now())/60000))} minutes. Not a claim; cannot be approved.`;
      root.append(reserved);
    }
    for(const claim of active) {
      const entry=document.createElement('div'); entry.className='entry';
      const left=document.createElement('div'), title=document.createElement('b'), details=document.createElement('small');
      title.textContent=claim.donor+' · '+claim.ref;
      details.textContent=`${claim.amounts.length} squares · ${format(claim.amount)} · Awaiting approval`;
      left.append(title,details);
      if(claim.message) { const text=document.createElement('p'); text.textContent=claim.message; left.append(text); }
      const disclosure=document.createElement('details'), summary=document.createElement('summary'), amounts=document.createElement('p');
      summary.textContent='Review claimed squares'; amounts.className='amounts'; amounts.textContent=claim.amounts.map(format).join(' · ');
      disclosure.append(summary,amounts); left.append(disclosure);
      const buttons=document.createElement('div'); buttons.className='row';
      for(const [action,label] of [['approved','Approve claim'],['released','Release squares']]) {
        const b=document.createElement('button'); b.textContent=label;
        if(action==='released') b.className='release';
        b.onclick=()=>reviewAction(claim.ref,action,b); buttons.append(b);
      }
      entry.append(left,buttons); root.append(entry);
    }
    if(!active.length && !c.attempt) { const p=document.createElement('p'); p.className='note'; p.textContent='No pending claims or active reservations.'; root.append(p); }
  }
  function renderOwner() {
    el('adminPanel').classList.toggle('locked',!ownerMode); el('accessBox').classList.toggle('hidden',ownerMode);
    el('ownerBar').classList.toggle('hidden',!ownerMode); el('ownerEmailDisplay').textContent=db.owner?.email||'';
  }
  function enterChallenge() {
    ownerMode=false; el('welcome').classList.add('hidden'); el('thankyou').classList.add('hidden'); el('campaignMain').classList.remove('hidden');
    el('fundraiserInline').textContent=db.owner.name; el('fundraiserHeading').textContent=db.owner.name+"’s";
    refreshState(); el('donor').value=challenge().donor; el('donormessage').value=challenge().message;
    render(); window.scrollTo(0,0);
    if(!storageReady) message('campaignNotice','Session storage is unavailable. Checkout requires it so a claim cannot be lost.');
  }
  function setPick(value) {
    pickedLevel=value;
    document.querySelectorAll('[data-pick]').forEach(b=>{b.classList.toggle('chosen',+b.dataset.pick===value);b.setAttribute('aria-pressed',String(+b.dataset.pick===value));});
  }
  function cleanURL() { history.replaceState(null,'',location.pathname); }
  document.querySelectorAll('[data-pick]').forEach(b=>b.onclick=()=>setPick(+b.dataset.pick));
  document.querySelectorAll('[data-bundle]').forEach(b=>b.onclick=()=>suggest(+b.dataset.bundle));
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{
    view=b.dataset.view; document.querySelectorAll('[data-view]').forEach(x=>{x.classList.toggle('on',x===b);x.setAttribute('aria-pressed',String(x===b));}); render();
  });
  el('suggest').onclick=()=>suggest(P.parseMoney(el('donationValue').value));
  el('shuffle').onclick=()=>suggest(suggestionTarget);
  el('donationValue').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();suggest(P.parseMoney(event.target.value));}});
  el('clear').onclick=()=>{selected.clear();suggestionTarget=null;saveSelection();warn('');render();};
  for(const id of ['donor','donormessage']) el(id).addEventListener('input',()=>{
    challenge()[id==='donor'?'donor':'message']=el(id).value; challenge().updatedAt=Date.now();persist();
  });
  el('donate').onclick=beginCheckout;
  el('resume').onclick=()=>{refreshState();if(challenge().attempt)showCheckout(challenge().attempt);else render();};
  el('simulateReturn').onclick=finishCheckout; el('cancelCheckout').onclick=cancelCheckout;
  el('checkout').addEventListener('cancel',event=>{event.preventDefault();cancelCheckout();});
  el('startChallenge').onclick=()=>{
    const name=el('ownerName').value.trim(),email=el('ownerEmail').value.trim().toLowerCase();
    if(!name||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){el('signupError').textContent='Enter your first name and a valid email address.';return;}
    db.owner={name,email,level:pickedLevel};level=pickedLevel;el('signupError').textContent='';persist();cleanURL();enterChallenge();
  };
  el('changeChallenge').onclick=()=>{
    if(challenge().claims.some(c=>c.status!=='released')||challenge().attempt)return;
    setPick(level);el('campaignMain').classList.add('hidden');el('welcome').classList.remove('hidden');window.scrollTo(0,0);
  };
  el('ownerUnlock').onclick=()=>{ownerMode=true;renderOwner();};el('ownerLock').onclick=()=>{ownerMode=false;renderOwner();};
  el('reset').onclick=()=>{
    if(!ownerMode)return;
    if(!confirm('Reset all claims and selections for this challenge?'))return;
    if(!transaction(()=>{delete db.challenges[challengeKey()];db.receipt=null;}))return;
    selected.clear();el('donor').value='';el('donormessage').value='';message('campaignNotice','');render();dashboardNotice('This challenge has been reset.');
  };
  el('viewChallenge').onclick=()=>{history.pushState(null,'',location.pathname);if(db.owner)enterChallenge();else{el('thankyou').classList.add('hidden');el('welcome').classList.remove('hidden');}};
  async function copyText(text) {
    if(!navigator.clipboard)throw new Error('Clipboard access is unavailable in this browser.');
    await navigator.clipboard.writeText(text);
  }
  el('copyReference').onclick=async()=>{
    try { await copyText(db.receipt.ref);el('receiptNotice').textContent='Reference copied.'; }
    catch {el('receiptNotice').textContent='Copy was unavailable. You can select and copy the reference shown above.';}
  };
  el('shareChallenge').onclick=async()=>{
    const url=location.origin+location.pathname;
    try {
      if(navigator.share)await navigator.share({title:'Every Penny Challenge',url});
      else {await copyText(url);el('receiptNotice').textContent='Challenge link copied.';}
    }catch(error){if(error.name!=='AbortError')el('receiptNotice').textContent='Sharing was unavailable. Copy the challenge address from your browser.';}
  };
  window.addEventListener('popstate',()=>{if(new URLSearchParams(location.search).has('thankyou'))showReceipt();else if(db.owner)enterChallenge();else {el('thankyou').classList.add('hidden');el('campaignMain').classList.add('hidden');el('welcome').classList.remove('hidden');}});
  window.addEventListener('resize',()=>{if(db.owner&&view==='mosaic'&&!el('campaignMain').classList.contains('hidden'))artwork();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&db.owner)render();});
  // Local state has no network poll to fail. Refresh visible dashboard counts every minute.
  setInterval(()=>{if(!document.hidden&&db.owner)render();},60000);
  setInterval(()=>{if(!document.hidden&&el('checkout').open){const wasActive=Boolean(db.owner&&challenge().attempt);refreshState();if(wasActive&&!challenge().attempt)render();updateClock();}},1000);
  setPick(2);
  if(db.owner){level=[2,5,10].includes(db.owner.level)?db.owner.level:2;setPick(level);el('ownerName').value=db.owner.name;el('ownerEmail').value=db.owner.email;enterChallenge();}
  if(new URLSearchParams(location.search).has('thankyou'))showReceipt();
})();
