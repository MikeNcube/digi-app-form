// ═══════════════════════════════════════════════════════════════════
//  Zororo Phumulani — Digital Application Form  app.js  v4.0
//  CRITICAL: Keep in /static/app.js — DO NOT inline into HTML
//  Upload zones must remain <div> not <label> (breaks plan buttons)
//
//  v4 changes:
//  - FIC upload removed; passport/ID only
//  - Slide order: 1=Member, 2=Docs, 3=Plan, 4=Family, 5=Payment, 6=Decl, 7=Sign
//  - Currency converter on plan slide
//  - Income "prefer not to disclose" hides expenses/cash fields
// ═══════════════════════════════════════════════════════════════════

const PLANS = {
  premium:   { name: 'Premium',   cover: 45000, single: 450,  family: 540  },
  prestige:  { name: 'Prestige',  cover: 75000, single: 630,  family: 720  },
  executive: { name: 'Executive', cover: 90000, single: 990,  family: 1080 },
};
const EFM_TIERS = {
  t1: { cover: 2000,  premium: 60  },
  t2: { cover: 3000,  premium: 80  },
  t3: { cover: 4000,  premium: 110 },
  t4: { cover: 5000,  premium: 220 },
};
const FX_HINTS = {
  ZAR:'', USD:'18.20', GBP:'23.10', EUR:'19.80',
  AUD:'11.60', CAD:'13.40', ZWL:'0.05', BWP:'1.33', NAD:'1.00',
};
const PROVINCES = {
  ZA: ['Gauteng','Western Cape','KwaZulu-Natal','Eastern Cape','Limpopo',
       'Mpumalanga','North West','Free State','Northern Cape'],
  ZW: ['Harare','Bulawayo','Manicaland','Mashonaland Central','Mashonaland East',
       'Mashonaland West','Masvingo','Matabeleland North','Matabeleland South','Midlands'],
  ZM: ['Lusaka','Copperbelt','Southern','Eastern','Western','Northern','Luapula',
       'North-Western','Central','Muchinga'],
  BW: ['Central','Ghanzi','Kgalagadi','Kgatleng','Kweneng','North-East',
       'North-West','South-East','Southern'],
  MZ: ['Maputo','Gaza','Inhambane','Sofala','Manica','Tete','Zambézia',
       'Nampula','Niassa','Cabo Delgado'],
  MW: ['Blantyre','Lilongwe','Mzuzu','Zomba'],
  NA: ['Khomas','Erongo','Hardap','Karas','Kavango East','Kavango West',
       'Kunene','Ohangwena','Omaheke','Omusati','Oshana','Oshikoto','Otjozondjupa','Zambezi'],
};

let currentSlide=1, children=[], efmMembers=[], spouseAdded=false;
let selectedPlan=null, coverType='single', sigMode='digital';
let sigPhotoB64=null, tcAcceptedAt=null;
let drawing=false, sigCtx=null, lastX=0, lastY=0;

document.addEventListener('DOMContentLoaded', () => {
  const dobEl = document.getElementById('mm_dob');
  if (dobEl) {
    const max = new Date();
    max.setFullYear(max.getFullYear() - 18);
    dobEl.max = max.toISOString().split('T')[0];
    dobEl.addEventListener('change', () => showAge(dobEl.value, 'mm_age', 18, 65));
  }
  wireUpload('passportZone', 'passport_upload', 'passport_name');
  wireUpload('sigZone', 'sig_photo', 'sig_photo_name', true);
  const opYes = document.getElementById('op_yes');
  const opNo  = document.getElementById('op_no');
  if (opYes) {
    opYes.addEventListener('change', () => {
      document.getElementById('op_amt_wrap').style.display = opYes.checked ? 'block' : 'none';
    });
    opNo.addEventListener('change', () => {
      document.getElementById('op_amt_wrap').style.display = 'none';
    });
  }
  initCanvas();
});

function wireUpload(zoneId, inputId, nameId, isSig) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', function() {
    if (!this.files || !this.files[0]) return;
    const f = this.files[0];
    document.getElementById(nameId).textContent = '✓ ' + f.name;
    zone.classList.remove('upload-err');
    zone.classList.add('uploaded');
    if (isSig) {
      const reader = new FileReader();
      reader.onload = e => { sigPhotoB64 = e.target.result; };
      reader.readAsDataURL(f);
    }
  });
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor='var(--mid)'; });
  zone.addEventListener('dragleave', () => { zone.style.borderColor=''; });
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.style.borderColor='';
    if (e.dataTransfer.files[0]) {
      try {
        const dt = new DataTransfer();
        dt.items.add(e.dataTransfer.files[0]);
        input.files = dt.files;
        input.dispatchEvent(new Event('change'));
      } catch(_) {
        document.getElementById(nameId).textContent = '✓ ' + e.dataTransfer.files[0].name;
        zone.classList.add('uploaded');
      }
    }
  });
}

function calcAge(dobStr) {
  if (!dobStr) return 0;
  const today=new Date(), dob=new Date(dobStr);
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m===0 && today.getDate() < dob.getDate())) age--;
  return age;
}

function showAge(dobStr, elId, minAge, maxAge) {
  const el = document.getElementById(elId);
  if (!el || !dobStr) return;
  const age = calcAge(dobStr);
  if (age < minAge || age > maxAge)
    el.innerHTML = `<span class="age-err">⚠ Age: ${age} — must be ${minAge}–${maxAge}</span>`;
  else el.textContent = `Age: ${age}`;
}

function onCountryChange() {
  const country = document.getElementById('mm_country').value;
  const wrap = document.getElementById('province_wrap');
  const sel = document.getElementById('mm_province');
  if (PROVINCES[country]) {
    sel.innerHTML = '<option value="">Select province</option>' +
      PROVINCES[country].map(p => `<option value="${p}">${p}</option>`).join('');
    wrap.style.display = 'block';
  } else {
    wrap.style.display = 'none';
    sel.innerHTML = '<option value="">Select province</option>';
  }
}
function onProvinceChange() {}

function nextSlide(from) { if (!validateSlide(from)) return; goTo(from+1); }
function prevSlide(from) { goTo(from-1); }
function goTo(n) {
  document.getElementById('slide'+currentSlide).classList.remove('active');
  document.getElementById('slide'+n).classList.add('active');
  currentSlide=n;
  updateProgress(n);
  if (n===7) buildReview();
  window.scrollTo(0,0);
}
function updateProgress(n) {
  document.querySelectorAll('.step-tab').forEach(tab => {
    const s=parseInt(tab.dataset.step);
    tab.classList.remove('active','done');
    if (s===n) tab.classList.add('active');
    else if (s<n) tab.classList.add('done');
  });
}

// Slide 3=Plan, 4=Family (optional)
function validateSlide(n) {
  if (n===1) return v1_mainMember();
  if (n===2) return v2_documents();
  if (n===3) return v3_plan();
  if (n===4) return true;
  if (n===5) return v5_payment();
  if (n===6) return v6_declarations();
  return true;
}

function v1_mainMember() {
  let ok=true;
  ['mm_first','mm_last','mm_dob','mm_gender','mm_nationality',
   'mm_phone','mm_email','mm_country','mm_postal','mm_address'].forEach(id => {
    const el=document.getElementById(id);
    if (!el) return;
    if (!el.value.trim()) { el.classList.add('err'); ok=false; }
    else el.classList.remove('err');
  });
  const dob=document.getElementById('mm_dob').value;
  if (dob) {
    const age=calcAge(dob);
    if (age<18) {
      document.getElementById('mm_dob').classList.add('err');
      document.getElementById('mm_age').innerHTML='<span class="age-err">⚠ Must be at least 18</span>';
      ok=false;
    } else if (age>65) {
      document.getElementById('mm_dob').classList.add('err');
      document.getElementById('mm_age').innerHTML='<span class="age-err">⚠ Maximum entry age is 65</span>';
      ok=false;
    }
  }
  const country=document.getElementById('mm_country').value;
  if (PROVINCES[country]) {
    const prov=document.getElementById('mm_province');
    if (!prov.value) { prov.classList.add('err'); ok=false; }
    else prov.classList.remove('err');
  }
  if (!ok) alert('Please complete all required fields before continuing.');
  return ok;
}

function v2_documents() {
  const passDone=document.getElementById('passportZone').classList.contains('uploaded');
  const idNum=document.getElementById('mm_id_number').value.trim();
  const errEl=document.getElementById('docs_err');
  if (!passDone) {
    document.getElementById('passportZone').classList.add('upload-err');
    errEl.style.display='block';
    errEl.textContent='⚠ Please upload your Passport or ID copy before continuing.';
    return false;
  }
  if (!idNum) {
    document.getElementById('mm_id_number').classList.add('err');
    errEl.style.display='block';
    errEl.textContent='⚠ Please enter your ID or Passport number.';
    return false;
  }
  errEl.style.display='none';
  return true;
}

function v3_plan() {
  if (!selectedPlan) {
    alert('Please select a plan before continuing.'); return false;
  }
  const hasDeps=spouseAdded||children.length>0;
  const warn=document.getElementById('fam_warn');
  if (warn) warn.style.display=(coverType==='family'&&!hasDeps)?'block':'none';
  let ok=true;
  ['ben_first','ben_last','ben_phone','ben_rel'].forEach(id => {
    const el=document.getElementById(id);
    if (!el.value.trim()) { el.classList.add('err'); ok=false; }
    else el.classList.remove('err');
  });
  if (!ok) { alert('Please complete all beneficiary fields.'); return false; }
  return true;
}

function v5_payment() {
  const method=document.querySelector('input[name="pm"]:checked').value;
  if (method==='debit_order') {
    let ok=true;
    ['dob_holder','dob_contact','dob_bank','dob_branch','dob_accnum','dob_acctype','dob_deductdate'].forEach(id => {
      const el=document.getElementById(id);
      if (!el.value.trim()) { el.classList.add('err'); ok=false; }
      else el.classList.remove('err');
    });
    if (!ok) { alert('Please complete all debit order fields.'); return false; }
  }
  return true;
}

function v6_declarations() {
  if (!document.getElementById('tc_popia').checked) {
    alert('Please accept the POPIA consent.'); return false;
  }
  if (!document.getElementById('tc_terms').checked) {
    alert('Please read and accept the Terms & Conditions.'); return false;
  }
  if (!document.getElementById('tc_fais').checked) {
    alert('Please accept the FAIS advice record declaration.'); return false;
  }
  const income=document.getElementById('d_income');
  if (!income.value) {
    income.classList.add('err');
    alert('Please complete the gross monthly income field.'); return false;
  }
  income.classList.remove('err');
  return true;
}

function onIncomeChange() {
  const val=document.getElementById('d_income').value;
  const wrap=document.getElementById('financial_detail_wrap');
  if (wrap) wrap.style.display=(val==='prefer_not')?'none':'block';
}

function setCoverType(type) {
  coverType=type;
  const hasDeps=spouseAdded||children.length>0;
  const warn=document.getElementById('fam_warn');
  if (warn) warn.style.display=(type==='family'&&!hasDeps)?'block':'none';
  updatePlanPrices();
}

function updatePlanPrices() {
  Object.keys(PLANS).forEach(key => {
    const price=coverType==='family'?PLANS[key].family:PLANS[key].single;
    const el=document.getElementById('pp_'+key);
    if (el) el.innerHTML=`R${price}<span class="plan-price-sm">/mo</span>`;
  });
  if (selectedPlan) recalcTotal();
}

function selPlan(key) {
  selectedPlan=key;
  document.querySelectorAll('.plan-card').forEach(c=>c.classList.remove('sel'));
  document.getElementById('pc_'+key).classList.add('sel');
  document.querySelector(`#pc_${key} input`).checked=true;
  document.getElementById('plan_total_wrap').style.display='block';
  recalcTotal();
}

function recalcTotal() {
  if (!selectedPlan) return;
  const base=coverType==='family'?PLANS[selectedPlan].family:PLANS[selectedPlan].single;
  const efmPrem=efmMembers.reduce((s,e)=>s+(e.tier&&EFM_TIERS[e.tier]?EFM_TIERS[e.tier].premium:0),0);
  const total=base+efmPrem;
  const el=document.getElementById('plan_total');
  const det=document.getElementById('plan_detail');
  if (el) el.textContent=`R${total}`;
  if (det) det.textContent=`${PLANS[selectedPlan].name} (${coverType}): R${base}`+(efmPrem?` + Ext. family: R${efmPrem}`:'');
  updateCurrencyDisplay();
}

function updateCurrencyDisplay() {
  const currSel=document.getElementById('currency_sel');
  const rateEl=document.getElementById('fx_rate');
  const hintEl=document.getElementById('fx_hint');
  const breakdown=document.getElementById('currency_breakdown');
  const rowsEl=document.getElementById('currency_rows');
  const titleEl=document.getElementById('currency_title');
  const convDisp=document.getElementById('converted_display');
  if (!currSel||!selectedPlan) return;
  const currency=currSel.value;
  if (currency==='ZAR') {
    if (rateEl) rateEl.value='';
    if (hintEl) hintEl.textContent='ZAR is the base currency — no conversion needed';
    if (breakdown) breakdown.style.display='none';
    if (convDisp) convDisp.textContent='';
    return;
  }
  if (hintEl) hintEl.textContent=FX_HINTS[currency]
    ?`Approx. rate: 1 ${currency} ≈ R${FX_HINTS[currency]} — enter current rate`
    :'Enter current exchange rate (ZAR per 1 unit)';
  const rate=parseFloat(rateEl?rateEl.value:'');
  if (!rate||rate<=0) {
    if (breakdown) breakdown.style.display='none';
    if (convDisp) convDisp.textContent='';
    return;
  }
  const base=coverType==='family'?PLANS[selectedPlan].family:PLANS[selectedPlan].single;
  const efmPrem=efmMembers.reduce((s,e)=>s+(e.tier&&EFM_TIERS[e.tier]?EFM_TIERS[e.tier].premium:0),0);
  const total=base+efmPrem;
  const sym=getCurrencySymbol(currency);
  const fmt=amt=>`${sym}${(amt/rate).toFixed(2)}`;
  const rows=[{label:`Base premium (${PLANS[selectedPlan].name} ${coverType})`,zar:base}];
  if (efmPrem) rows.push({label:'Extended family total',zar:efmPrem});
  rows.push({label:'TOTAL monthly premium',zar:total,bold:true});
  if (rowsEl) rowsEl.innerHTML=rows.map(r=>`
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:5px 0;border-bottom:1px solid #f0f0f0;
                ${r.bold?'font-weight:700;color:var(--navy);border-bottom:none':''}">
      <span style="color:${r.bold?'var(--navy)':'#555'};font-size:.82rem">${r.label}</span>
      <span style="font-size:.85rem">
        <span style="color:var(--muted);margin-right:10px">R${r.zar.toLocaleString()}</span>
        <span style="color:var(--navy);font-weight:600">${fmt(r.zar)}</span>
      </span>
    </div>`).join('');
  if (titleEl) titleEl.textContent=`Premium in ${currency} (rate: 1 ${currency} = R${rate})`;
  if (breakdown) breakdown.style.display='block';
  if (convDisp) convDisp.textContent=`≈ ${sym}${(total/rate).toFixed(2)} ${currency}/month`;
}

function getCurrencySymbol(code) {
  return {ZAR:'R',USD:'$',GBP:'£',EUR:'€',AUD:'A$',CAD:'C$',ZWL:'ZiG ',BWP:'P',NAD:'N$'}[code]||code+' ';
}

function addSpouse() {
  if (spouseAdded) return;
  spouseAdded=true;
  document.getElementById('spouseSection').innerHTML=`
    <div class="dep-card" id="spouseCard">
      <div class="dep-hdr">Spouse<button class="btn-rm" onclick="removeSpouse()">Remove</button></div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label><input type="text" id="sp_first" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label><input type="text" id="sp_last" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="sp_dob" onchange="showAge(this.value,'sp_age',18,65)"/>
            <div class="age-disp" id="sp_age"></div></div>
          <div class="field"><label>Gender</label>
            <select id="sp_gender"><option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option></select></div>
        </div>
        <div class="field"><label>ID / Passport Number</label>
          <input type="text" id="sp_id" placeholder="ID or Passport number"/></div>
      </div></div>`;
  const warn=document.getElementById('fam_warn');
  if (warn&&coverType==='family') warn.style.display='none';
}

function removeSpouse() {
  spouseAdded=false;
  document.getElementById('spouseSection').innerHTML=`
    <div class="dep-cnt">No spouse added.</div>
    <button class="btn-add" onclick="addSpouse()"><span>＋</span> Add Spouse</button>`;
}

function addChild() {
  if (children.length>=6) { alert('Maximum 6 children allowed.'); return; }
  const id='ch_'+Date.now();
  children.push({id});
  renderChildren();
  const warn=document.getElementById('fam_warn');
  if (warn&&coverType==='family') warn.style.display='none';
}
function removeChild(id) { children=children.filter(c=>c.id!==id); renderChildren(); }
function renderChildren() {
  const list=document.getElementById('childList');
  const cnt=document.getElementById('child_cnt');
  const btn=document.getElementById('addChildBtn');
  if (cnt) cnt.textContent=`${children.length} of 6 children added`;
  if (btn) btn.style.display=children.length>=6?'none':'';
  if (!list) return;
  list.innerHTML=children.map(ch=>`
    <div class="dep-card" id="${ch.id}">
      <div class="dep-hdr">Child<button class="btn-rm" onclick="removeChild('${ch.id}')">Remove</button></div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label><input type="text" id="${ch.id}_fn" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label><input type="text" id="${ch.id}_ln" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="${ch.id}_dob" onchange="validateChildAge('${ch.id}')"/>
            <div class="age-disp" id="${ch.id}_age"></div></div>
          <div class="field"><label>Gender</label>
            <select id="${ch.id}_gender"><option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option></select></div>
        </div>
        <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:4px">
          <label style="display:flex;align-items:center;gap:6px;font-size:.8rem;font-weight:400;cursor:pointer">
            <input type="checkbox" id="${ch.id}_student"/> Full-time student (extends to age 25)</label>
          <label style="display:flex;align-items:center;gap:6px;font-size:.8rem;font-weight:400;cursor:pointer">
            <input type="checkbox" id="${ch.id}_disabled"/> Physically/mentally disabled</label>
        </div>
      </div></div>`).join('');
}
function validateChildAge(id) {
  const dob=document.getElementById(id+'_dob').value;
  const s=document.getElementById(id+'_student')?.checked;
  const d=document.getElementById(id+'_disabled')?.checked;
  showAge(dob,id+'_age',0,(s||d)?25:21);
}

function addEfm() {
  if (efmMembers.length>=6) { alert('Maximum 6 extended family members.'); return; }
  const id='efm_'+Date.now();
  efmMembers.push({id,tier:null});
  renderEfm();
}
function removeEfm(id) { efmMembers=efmMembers.filter(e=>e.id!==id); renderEfm(); recalcTotal(); }
function renderEfm() {
  const list=document.getElementById('efmList');
  const cnt=document.getElementById('efm_cnt');
  const btn=document.getElementById('addEfmBtn');
  if (cnt) cnt.textContent=`${efmMembers.length} of 6 extended family members added`;
  if (btn) btn.style.display=efmMembers.length>=6?'none':'';
  if (!list) return;
  list.innerHTML=efmMembers.map(efm=>`
    <div class="dep-card" id="${efm.id}">
      <div class="dep-hdr">Extended Family Member
        <button class="btn-rm" onclick="removeEfm('${efm.id}')">Remove</button></div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label><input type="text" id="${efm.id}_fn" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label><input type="text" id="${efm.id}_ln" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="${efm.id}_dob" onchange="showAge(this.value,'${efm.id}_age',0,90)"/>
            <div class="age-disp" id="${efm.id}_age"></div></div>
          <div class="field"><label>Relationship</label>
            <input type="text" id="${efm.id}_rel" placeholder="e.g. Parent, Sibling"/></div>
        </div>
        <div class="sec-label" style="margin:10px 0 8px;font-size:.78rem">Select Cover Tier</div>
        <div class="tier-grid">
          ${['t1','t2','t3','t4'].map(t=>`
            <div class="tier-card ${efm.tier===t?'sel':''}" id="${efm.id}_${t}"
                 onclick="selTier('${efm.id}','${t}')">
              <div class="tier-cover">R${EFM_TIERS[t].cover.toLocaleString()}</div>
              <div class="tier-prem">R${EFM_TIERS[t].premium}/mo</div>
            </div>`).join('')}
        </div>
      </div></div>`).join('');
}
function selTier(efmId, tier) {
  const efm=efmMembers.find(e=>e.id===efmId);
  if (efm) {
    efm.tier=tier;
    const card=document.getElementById(efmId);
    if (card) {
      card.querySelectorAll('.tier-card').forEach(tc=>tc.classList.remove('sel'));
      document.getElementById(efmId+'_'+tier)?.classList.add('sel');
    }
    recalcTotal();
  }
}

function switchPay(method) {
  document.getElementById('panel_debit').classList.toggle('active',method==='debit_order');
  document.getElementById('panel_online').classList.toggle('active',method==='online_payment');
}

function tglCheck(id) {
  const el=document.getElementById(id);
  const box=document.getElementById('box_'+id);
  if (!el) return;
  el.checked=!el.checked;
  if (box) { box.classList.toggle('chk-checked',el.checked); box.textContent=el.checked?'✓':''; }
  if (id==='tc_terms'&&el.checked&&!tcAcceptedAt) tcAcceptedAt=new Date().toISOString();
}

function openTC(e) {
  if (e) e.preventDefault();
  document.getElementById('termsModal').style.display='flex';
  document.body.style.overflow='hidden';
  const c=document.getElementById('tcContent');
  if (c) c.scrollTop=0;
}
function closeTC() {
  document.getElementById('termsModal').style.display='none';
  document.body.style.overflow='';
}
function acceptTCFromModal() {
  const cb=document.getElementById('tc_terms');
  const box=document.getElementById('box_tc_terms');
  if (cb) cb.checked=true;
  if (box) { box.classList.add('chk-checked'); box.textContent='✓'; }
  if (!tcAcceptedAt) tcAcceptedAt=new Date().toISOString();
  closeTC();
}

function initCanvas() {
  const canvas=document.getElementById('sigCanvas');
  if (!canvas) return;
  sigCtx=canvas.getContext('2d');
  sigCtx.strokeStyle='#0a1628'; sigCtx.lineWidth=2;
  sigCtx.lineCap='round'; sigCtx.lineJoin='round';
  const getPos=e=>{ const r=canvas.getBoundingClientRect(),src=e.touches?e.touches[0]:e;
    return {x:src.clientX-r.left,y:src.clientY-r.top}; };
  const startDraw=e=>{ e.preventDefault(); drawing=true; const p=getPos(e); lastX=p.x; lastY=p.y;
    sigCtx.beginPath(); sigCtx.moveTo(lastX,lastY); };
  const draw=e=>{ if(!drawing)return; e.preventDefault(); const p=getPos(e);
    sigCtx.lineTo(p.x,p.y); sigCtx.stroke(); lastX=p.x; lastY=p.y; };
  const endDraw=()=>{ drawing=false; };
  canvas.addEventListener('mousedown',startDraw);
  canvas.addEventListener('mousemove',draw);
  canvas.addEventListener('mouseup',endDraw);
  canvas.addEventListener('mouseleave',endDraw);
  canvas.addEventListener('touchstart',startDraw,{passive:false});
  canvas.addEventListener('touchmove',draw,{passive:false});
  canvas.addEventListener('touchend',endDraw);
}
function clrSig() {
  if (sigCtx) { const c=document.getElementById('sigCanvas'); sigCtx.clearRect(0,0,c.width,c.height); }
}
function setSig(mode) {
  sigMode=mode;
  ['panel_sig_digital','panel_sig_photo','panel_sig_typed'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.style.display='none';
  });
  const panelMap={digital:'panel_sig_digital',photo:'panel_sig_photo',typed:'panel_sig_typed'};
  const panel=document.getElementById(panelMap[mode]);
  if (panel) panel.style.display='block';
  document.querySelectorAll('.sig-opt-btn').forEach(b=>b.classList.remove('active'));
  const ab=document.getElementById('sigbtn_'+mode);
  if (ab) ab.classList.add('active');
}
function updateTyped() {
  const val=document.getElementById('typed_sig')?.value||'';
  const prev=document.getElementById('typed_preview');
  if (prev) prev.textContent=val||'Your name will appear here';
}
function sigPhotoUploaded(input) {
  if (input.files&&input.files[0]) {
    const reader=new FileReader();
    reader.onload=e=>{ sigPhotoB64=e.target.result; };
    reader.readAsDataURL(input.files[0]);
  }
}

function buildReview() {
  const get=id=>{ const el=document.getElementById(id); return el?el.value:''; };
  let html='';
  html+=revSec('Main Member',[
    ['Name',`${get('mm_first')} ${get('mm_last')}`],
    ['Date of Birth',get('mm_dob')],['Gender',get('mm_gender')],
    ['Nationality',get('mm_nationality')],['ID/Passport',get('mm_id_number')],
    ['Phone',get('mm_phone')],['WhatsApp',get('mm_whatsapp')||get('mm_phone')],
    ['Email',get('mm_email')],['Address',`${get('mm_address')}, ${get('mm_area')||''} ${get('mm_postal')}`],
    ['Country',get('mm_country')],['Province',get('mm_province')],
  ]);
  const pName=selectedPlan?PLANS[selectedPlan].name:'—';
  const pCover=selectedPlan?`R${PLANS[selectedPlan].cover.toLocaleString()}`:'—';
  const base=selectedPlan?(coverType==='family'?PLANS[selectedPlan].family:PLANS[selectedPlan].single):0;
  const efmPrem=efmMembers.reduce((s,e)=>s+(e.tier&&EFM_TIERS[e.tier]?EFM_TIERS[e.tier].premium:0),0);
  const total=base+efmPrem;
  const currSel=document.getElementById('currency_sel');
  const rateEl=document.getElementById('fx_rate');
  const currency=currSel?currSel.value:'ZAR';
  const fxRate=rateEl?parseFloat(rateEl.value):0;
  const totalDisplay=(currency!=='ZAR'&&fxRate>0)
    ?`R${total} (≈ ${getCurrencySymbol(currency)}${(total/fxRate).toFixed(2)} ${currency})`
    :`R${total}`;
  html+=revSec('Cover & Plan',[
    ['Plan',pName],['Cover Type',coverType==='family'?'Family':'Single'],
    ['Sum Insured',pCover],['Base Premium',`R${base}/month`],
    ['Ext. Family Prem',efmPrem?`R${efmPrem}/month`:'—'],
    ['TOTAL PREMIUM',`${totalDisplay}/month`],
  ]);
  const depRows=[];
  if (spouseAdded) {
    const fn=(document.getElementById('sp_first')||{}).value||'—';
    const ln=(document.getElementById('sp_last')||{}).value||'—';
    depRows.push(['Spouse',`${fn} ${ln}`]);
  }
  children.forEach((ch,i)=>{
    const fn=(document.getElementById(ch.id+'_fn')||{}).value||'—';
    const ln=(document.getElementById(ch.id+'_ln')||{}).value||'—';
    const dob=(document.getElementById(ch.id+'_dob')||{}).value||'—';
    depRows.push([`Child ${i+1}`,`${fn} ${ln} · DOB: ${dob}`]);
  });
  efmMembers.forEach((efm,i)=>{
    const fn=(document.getElementById(efm.id+'_fn')||{}).value||'—';
    const ln=(document.getElementById(efm.id+'_ln')||{}).value||'—';
    const tier=efm.tier?`R${EFM_TIERS[efm.tier].cover} cover @ R${EFM_TIERS[efm.tier].premium}/mo`:'No tier selected';
    depRows.push([`Ext. Family ${i+1}`,`${fn} ${ln} · ${tier}`]);
  });
  if (!depRows.length) depRows.push(['Dependants','None added']);
  html+=revSec('Family & Dependants',depRows);
  html+=revSec('Beneficiary',[
    ['Name',`${get('ben_first')} ${get('ben_last')}`],
    ['Contact',get('ben_phone')],['Relationship',get('ben_rel')],
  ]);
  const pm=document.querySelector('input[name="pm"]:checked');
  const pmv=pm?pm.value:'debit_order';
  if (pmv==='debit_order') {
    html+=revSec('Payment (Debit Order)',[
      ['Account Holder',get('dob_holder')],['Bank',get('dob_bank')],
      ['Account Number',get('dob_accnum')],['Account Type',get('dob_acctype')],
      ['Branch Code',get('dob_branch')],['Deduction Date',get('dob_deductdate')],
      ['Commencement',get('dob_commence')],
    ]);
  } else {
    html+=revSec('Payment',[['Method','Online Payment via portal']]);
  }
  html+=`<div class="waiting-box"><strong>Waiting Periods:</strong>
    Accidental death — Immediate &nbsp;|&nbsp; Natural causes (family) — 3 months &nbsp;|&nbsp;
    Extended family — 6 months &nbsp;|&nbsp; Suicide — 12 months</div>`;
  html+=`<div class="prem-box" style="margin-top:14px">
    <div><div class="prem-label">Total Monthly Premium</div>
    ${(currency!=='ZAR'&&fxRate>0)?`<div style="font-size:.75rem;color:rgba(255,255,255,.6);margin-top:2px">
      ≈ ${getCurrencySymbol(currency)}${(total/fxRate).toFixed(2)} ${currency}/month</div>`:''}
    </div><div class="prem-amount">R${total}</div></div>`;
  document.getElementById('reviewContent').innerHTML=html;
}

function revSec(title, rows) {
  let h=`<div class="rev-sec"><div class="rev-sec-title">${title}</div>`;
  rows.forEach(([k,v])=>{
    h+=`<div class="rev-row"><span class="rev-k">${k}</span><span class="rev-v">${v||'—'}</span></div>`;
  });
  return h+'</div>';
}

function collectData() {
  const get=id=>{ const el=document.getElementById(id); return el?el.value:''; };
  const chk=id=>{ const el=document.getElementById(id); return el?el.checked:false; };
  const countryEl=document.getElementById('mm_country');
  const countryTxt=countryEl&&countryEl.options[countryEl.selectedIndex]
    ?countryEl.options[countryEl.selectedIndex].text:'';
  const notifs=[];
  if(chk('notif_sms'))notifs.push('sms');
  if(chk('notif_email'))notifs.push('email');
  if(chk('notif_whatsapp'))notifs.push('whatsapp');
  if(chk('notif_tel'))notifs.push('telephone');
  const spouseInfo=spouseAdded?{
    first_name:get('sp_first'),last_name:get('sp_last'),
    dob:get('sp_dob'),gender:get('sp_gender'),id_number:get('sp_id'),
  }:null;
  const childrenInfo=children.map(ch=>({
    first_name:get(ch.id+'_fn'),last_name:get(ch.id+'_ln'),
    dob:get(ch.id+'_dob'),gender:get(ch.id+'_gender'),
    student:chk(ch.id+'_student'),disabled:chk(ch.id+'_disabled'),
  }));
  const efmInfo=efmMembers.map(efm=>({
    first_name:get(efm.id+'_fn'),last_name:get(efm.id+'_ln'),
    dob:get(efm.id+'_dob'),relationship:get(efm.id+'_rel'),
    tier:efm.tier,
    cover:efm.tier&&EFM_TIERS[efm.tier]?EFM_TIERS[efm.tier].cover:0,
    premium:efm.tier&&EFM_TIERS[efm.tier]?EFM_TIERS[efm.tier].premium:0,
  }));
  const plan=selectedPlan?PLANS[selectedPlan]:null;
  const base=plan?(coverType==='family'?plan.family:plan.single):0;
  const efmPr=efmMembers.reduce((s,e)=>s+(e.tier&&EFM_TIERS[e.tier]?EFM_TIERS[e.tier].premium:0),0);
  const currSel=document.getElementById('currency_sel');
  const rateEl=document.getElementById('fx_rate');
  const currency=currSel?currSel.value:'ZAR';
  const fxRate=rateEl?parseFloat(rateEl.value)||null:null;
  let sigData=null;
  if (sigMode==='digital') {
    const c=document.getElementById('sigCanvas');
    sigData={type:'digital',data:c.toDataURL('image/png')};
  } else if (sigMode==='typed') {
    sigData={type:'typed',name:get('typed_sig')};
  } else if (sigMode==='photo'&&sigPhotoB64) {
    sigData={type:'photo',data:sigPhotoB64};
  }
  return {
    main_member:{
      first_name:get('mm_first'),last_name:get('mm_last'),dob:get('mm_dob'),
      gender:get('mm_gender'),nationality:get('mm_nationality'),id_number:get('mm_id_number'),
      phone:get('mm_phone'),whatsapp:get('mm_whatsapp')||get('mm_phone'),email:get('mm_email'),
      country:countryTxt,country_code:get('mm_country'),province:get('mm_province'),
      postal_code:get('mm_postal'),area_code:get('mm_area'),address:get('mm_address'),
    },
    spouse:spouseInfo,children:childrenInfo,extended_family:efmInfo,
    plan:selectedPlan||'',plan_name:plan?plan.name:'',cover_type:coverType,
    cover_amount:plan?plan.cover:0,base_premium:base,efm_premium:efmPr,total_premium:base+efmPr,
    display_currency:currency,fx_rate:fxRate,
    beneficiary:{first_name:get('ben_first'),last_name:get('ben_last'),
      phone:get('ben_phone'),relationship:get('ben_rel')},
    payment_method:(document.querySelector('input[name="pm"]:checked')||{}).value||'debit_order',
    debit_order:{account_holder:get('dob_holder'),account_holder_contact:get('dob_contact'),
      bank:get('dob_bank'),branch_code:get('dob_branch'),account_number:get('dob_accnum'),
      account_type:get('dob_acctype'),deduction_date:get('dob_deductdate'),
      commencement_date:get('dob_commence')},
    declarations:{has_other_policy:chk('op_yes'),other_policy_amount:get('op_amount'),
      is_replacement:chk('rp_yes'),income_range:get('d_income'),num_dependants:get('d_numdeps'),
      monthly_expenses:get('d_expenses'),available_cash:get('d_cash'),notifications:notifs},
    agent:{name:get('ag_name'),phone:get('ag_phone'),team_leader:get('ag_leader'),province:get('ag_province')},
    signature:sigData,popia_consent:chk('tc_popia'),terms_accepted:chk('tc_terms'),
    terms_accepted_at:tcAcceptedAt||new Date().toISOString(),fais_accepted:chk('tc_fais'),
    fic_uploaded:false,
    passport_uploaded:document.getElementById('passportZone').classList.contains('uploaded'),
    submission_timestamp:new Date().toISOString(),
  };
}

async function submitApp() {
  if (sigMode==='digital') {
    const c=document.getElementById('sigCanvas');
    const blank=document.createElement('canvas');
    blank.width=c.width; blank.height=c.height;
    if (c.toDataURL()===blank.toDataURL()) { alert('Please provide a drawn signature.'); return; }
  } else if (sigMode==='typed') {
    if (!document.getElementById('typed_sig').value.trim()) {
      alert('Please type your full legal name as your signature.'); return;
    }
  } else if (sigMode==='photo'&&!sigPhotoB64) {
    alert('Please upload a photo of your signature.'); return;
  }
  const btn=document.getElementById('submitBtn');
  btn.disabled=true; btn.textContent='Submitting…';
  try {
    const payload=collectData();
    const res=await fetch('/api/v1/policies',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),
    });
    if (!res.ok) {
      const err=await res.json().catch(()=>({detail:'Unknown error'}));
      throw new Error(err.detail||`Server error ${res.status}`);
    }
    const result=await res.json();
    showSuccess(result.policy_number);
  } catch(err) {
    alert(`Submission failed: ${err.message}\n\nPlease check your connection and try again.`);
    btn.disabled=false; btn.textContent='✓ Submit Application';
  }
}

function showSuccess(polNum) {
  document.getElementById('formWrap').style.display='none';
  document.querySelector('.progress-wrap').style.display='none';
  document.getElementById('successScreen').style.display='block';
  document.getElementById('sucPolNum').textContent=polNum;
  window.scrollTo(0,0);
}
