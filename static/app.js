// ═══════════════════════════════════════════════════════════════════
//  Zororo Phumulani — Digital Application Form  app.js  v3.0
//  CRITICAL: Keep in /static/app.js — DO NOT inline into HTML
//  (Cloudflare injects scripts into HTML that break inline JS)
//  Upload zones must remain <div> not <label> (breaks plan buttons)
// ═══════════════════════════════════════════════════════════════════

// ── PLAN DATA ────────────────────────────────────────────────────
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

// Province data for country cascade
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

// ── STATE ────────────────────────────────────────────────────────
let currentSlide = 1;
let children     = [];
let efmMembers   = [];
let spouseAdded  = false;
let selectedPlan = null;
let coverType    = 'single';
let sigMode      = 'digital';
let sigPhotoB64  = null;
let tcAcceptedAt = null;

// Signature canvas state
let drawing = false;
let sigCtx  = null;
let lastX = 0, lastY = 0;

// ── INIT ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // DOB max date: must be at least 18 years old
  const dobEl = document.getElementById('mm_dob');
  if (dobEl) {
    const max = new Date();
    max.setFullYear(max.getFullYear() - 18);
    dobEl.max = max.toISOString().split('T')[0];
    dobEl.addEventListener('change', () => showAge(dobEl.value, 'mm_age', 18, 65));
  }

  // Wire upload zones (MUST stay as div click triggers, not label)
  wireUpload('ficZone',      'fic_upload',      'fic_name');
  wireUpload('passportZone', 'passport_upload', 'passport_name');
  wireUpload('sigZone',      'sig_photo',       'sig_photo_name', true);

  // Other policy toggle
  const opYes = document.getElementById('op_yes');
  const opNo  = document.getElementById('op_no');
  if (opYes) {
    opYes.addEventListener('change', () => {
      document.getElementById('op_amt_wrap').style.display =
        opYes.checked ? 'block' : 'none';
    });
    opNo.addEventListener('change', () => {
      document.getElementById('op_amt_wrap').style.display = 'none';
    });
  }

  // Init signature canvas
  initCanvas();
});

// ── UPLOAD ZONE WIRING ────────────────────────────────────────────
function wireUpload(zoneId, inputId, nameId, isSig) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());

  input.addEventListener('change', function () {
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

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.style.borderColor = 'var(--mid)';
  });
  zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.style.borderColor = '';
    if (e.dataTransfer.files[0]) {
      // Create a DataTransfer to assign to input.files
      try {
        const dt = new DataTransfer();
        dt.items.add(e.dataTransfer.files[0]);
        input.files = dt.files;
        input.dispatchEvent(new Event('change'));
      } catch (_) {
        // Fallback: just show the name
        document.getElementById(nameId).textContent =
          '✓ ' + e.dataTransfer.files[0].name;
        zone.classList.add('uploaded');
      }
    }
  });
}

// ── AGE HELPERS ───────────────────────────────────────────────────
function calcAge(dobStr) {
  if (!dobStr) return 0;
  const today = new Date();
  const dob   = new Date(dobStr);
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age--;
  return age;
}

function showAge(dobStr, elId, minAge, maxAge) {
  const el = document.getElementById(elId);
  if (!el || !dobStr) return;
  const age = calcAge(dobStr);
  if (age < minAge || age > maxAge) {
    el.innerHTML = `<span class="age-err">⚠ Age: ${age} — must be ${minAge}–${maxAge}</span>`;
  } else {
    el.textContent = `Age: ${age}`;
  }
}

// ── COUNTRY CASCADE ───────────────────────────────────────────────
function onCountryChange() {
  const country = document.getElementById('mm_country').value;
  const wrap    = document.getElementById('province_wrap');
  const sel     = document.getElementById('mm_province');

  if (PROVINCES[country]) {
    sel.innerHTML = '<option value="">Select province</option>' +
      PROVINCES[country].map(p => `<option value="${p}">${p}</option>`).join('');
    wrap.style.display = 'block';
  } else {
    wrap.style.display = 'none';
    sel.innerHTML = '<option value="">Select province</option>';
  }
}

function onProvinceChange() { /* reserved for future suburb lookup */ }

// ── SLIDE NAVIGATION ─────────────────────────────────────────────
function nextSlide(from) {
  if (!validateSlide(from)) return;
  goTo(from + 1);
}
function prevSlide(from) { goTo(from - 1); }

function goTo(n) {
  document.getElementById('slide' + currentSlide).classList.remove('active');
  document.getElementById('slide' + n).classList.add('active');
  currentSlide = n;
  updateProgress(n);
  if (n === 7) buildReview();
  window.scrollTo(0, 0);
}

function updateProgress(n) {
  document.querySelectorAll('.step-tab').forEach(tab => {
    const s = parseInt(tab.dataset.step);
    tab.classList.remove('active', 'done');
    if (s === n)    tab.classList.add('active');
    else if (s < n) tab.classList.add('done');
  });
}

// ── VALIDATION ────────────────────────────────────────────────────
function validateSlide(n) {
  if (n === 1) return v1_mainMember();
  if (n === 2) return v2_documents();
  if (n === 3) return true;  // dependants optional
  if (n === 4) return v4_plan();
  if (n === 5) return v5_payment();
  if (n === 6) return v6_declarations();
  return true;
}

// Slide 1: Main member
function v1_mainMember() {
  let ok = true;
  const req = ['mm_first','mm_last','mm_dob','mm_gender','mm_nationality',
               'mm_phone','mm_email','mm_country','mm_postal','mm_address'];
  req.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (!el.value.trim()) { el.classList.add('err'); ok = false; }
    else el.classList.remove('err');
  });

  // Age must be ≥ 18
  const dob = document.getElementById('mm_dob').value;
  if (dob) {
    const age = calcAge(dob);
    if (age < 18) {
      document.getElementById('mm_dob').classList.add('err');
      document.getElementById('mm_age').innerHTML =
        '<span class="age-err">⚠ Main member must be at least 18 years old</span>';
      ok = false;
    } else if (age > 65) {
      document.getElementById('mm_dob').classList.add('err');
      document.getElementById('mm_age').innerHTML =
        '<span class="age-err">⚠ Maximum entry age is 65</span>';
      ok = false;
    }
  }

  // Province required for ZA, ZW, etc.
  const country = document.getElementById('mm_country').value;
  if (PROVINCES[country]) {
    const prov = document.getElementById('mm_province');
    if (!prov.value) { prov.classList.add('err'); ok = false; }
    else prov.classList.remove('err');
  }

  if (!ok) {
    alert('Please complete all required fields (marked with *) before continuing.');
  }
  return ok;
}

// Slide 2: Document uploads
function v2_documents() {
  const ficDone  = document.getElementById('ficZone').classList.contains('uploaded');
  const passDone = document.getElementById('passportZone').classList.contains('uploaded');
  const idNum    = document.getElementById('mm_id_number').value.trim();

  const errEl = document.getElementById('docs_err');

  if (!ficDone) document.getElementById('ficZone').classList.add('upload-err');
  if (!passDone) document.getElementById('passportZone').classList.add('upload-err');

  if (!ficDone || !passDone) {
    errEl.style.display = 'block';
    errEl.textContent = '⚠ Both the FIC document and Passport / ID copy are required.';
    return false;
  }
  if (!idNum) {
    document.getElementById('mm_id_number').classList.add('err');
    errEl.style.display = 'block';
    errEl.textContent = '⚠ Please enter your ID or Passport number.';
    return false;
  }
  errEl.style.display = 'none';
  return true;
}

// Slide 4: Plan selection + beneficiary
function v4_plan() {
  if (!selectedPlan) {
    alert('Please select a plan (Premium, Prestige, or Executive) before continuing.');
    return false;
  }
  const hasDeps = spouseAdded || children.length > 0;
  if (coverType === 'family' && !hasDeps) {
    document.getElementById('fam_warn').style.display = 'block';
    alert('Family cover requires at least one dependant (spouse or child). Please go back to step 3 and add a dependant, or switch to Single cover.');
    return false;
  }
  document.getElementById('fam_warn').style.display = 'none';

  // Beneficiary
  let ok = true;
  ['ben_first','ben_last','ben_phone','ben_rel'].forEach(id => {
    const el = document.getElementById(id);
    if (!el.value.trim()) { el.classList.add('err'); ok = false; }
    else el.classList.remove('err');
  });
  if (!ok) { alert('Please complete all beneficiary fields.'); return false; }
  return true;
}

// Slide 5: Payment
function v5_payment() {
  const method = document.querySelector('input[name="pm"]:checked').value;
  if (method === 'debit_order') {
    let ok = true;
    ['dob_holder','dob_contact','dob_bank','dob_branch',
     'dob_accnum','dob_acctype','dob_deductdate'].forEach(id => {
      const el = document.getElementById(id);
      if (!el.value.trim()) { el.classList.add('err'); ok = false; }
      else el.classList.remove('err');
    });
    if (!ok) { alert('Please complete all debit order fields.'); return false; }
  }
  return true;
}

// Slide 6: Declarations & T&C
function v6_declarations() {
  if (!document.getElementById('tc_popia').checked) {
    alert('Please accept the POPIA consent before continuing.');
    return false;
  }
  if (!document.getElementById('tc_terms').checked) {
    alert('Please read and accept the Terms & Conditions before continuing. Click the "Terms & Conditions" link to review them.');
    return false;
  }
  if (!document.getElementById('tc_fais').checked) {
    alert('Please accept the FAIS advice record declaration before continuing.');
    return false;
  }
  const income = document.getElementById('d_income');
  if (!income.value) {
    income.classList.add('err');
    alert('Please complete the gross monthly income field.');
    return false;
  }
  income.classList.remove('err');
  return true;
}

// ── COVER TYPE ────────────────────────────────────────────────────
function setCoverType(type) {
  coverType = type;
  const hasDeps = spouseAdded || children.length > 0;
  if (type === 'family' && !hasDeps) {
    document.getElementById('fam_warn').style.display = 'block';
  } else {
    document.getElementById('fam_warn').style.display = 'none';
  }
  updatePlanPrices();
}

function updatePlanPrices() {
  Object.keys(PLANS).forEach(key => {
    const price = coverType === 'family' ? PLANS[key].family : PLANS[key].single;
    const el = document.getElementById('pp_' + key);
    if (el) el.innerHTML = `R${price}<span class="plan-price-sm">/mo</span>`;
  });
  if (selectedPlan) recalcTotal();
}

// ── PLAN SELECTION ────────────────────────────────────────────────
function selPlan(key) {
  selectedPlan = key;
  document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('sel'));
  document.getElementById('pc_' + key).classList.add('sel');
  document.querySelector(`#pc_${key} input`).checked = true;
  document.getElementById('plan_total_wrap').style.display = 'block';
  recalcTotal();
}

function recalcTotal() {
  if (!selectedPlan) return;
  const base   = coverType === 'family' ? PLANS[selectedPlan].family : PLANS[selectedPlan].single;
  const efmPrem = efmMembers.reduce(
    (sum, e) => sum + (e.tier && EFM_TIERS[e.tier] ? EFM_TIERS[e.tier].premium : 0), 0);
  const total = base + efmPrem;
  document.getElementById('plan_total').textContent  = `R${total}`;
  document.getElementById('plan_detail').textContent =
    `${PLANS[selectedPlan].name} (${coverType}): R${base}` +
    (efmPrem ? ` + Extended family: R${efmPrem}` : '');
}

// ── SPOUSE ────────────────────────────────────────────────────────
function addSpouse() {
  if (spouseAdded) return;
  spouseAdded = true;
  const sec = document.getElementById('spouseSection');
  sec.innerHTML = `
    <div class="dep-card" id="spouseCard">
      <div class="dep-hdr">Spouse
        <button class="btn-rm" onclick="removeSpouse()">Remove</button>
      </div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label>
            <input type="text" id="sp_first" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label>
            <input type="text" id="sp_last" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="sp_dob" onchange="showAge(this.value,'sp_age',18,65)"/>
            <div class="age-disp" id="sp_age"></div></div>
          <div class="field"><label>Gender</label>
            <select id="sp_gender">
              <option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option>
            </select></div>
        </div>
        <div class="field"><label>ID / Passport Number</label>
          <input type="text" id="sp_id" placeholder="ID or Passport number"/></div>
      </div>
    </div>`;
}

function removeSpouse() {
  spouseAdded = false;
  document.getElementById('spouseSection').innerHTML =
    `<div class="dep-cnt">No spouse added.</div>
     <button class="btn-add" onclick="addSpouse()"><span>＋</span> Add Spouse</button>`;
}

// ── CHILDREN ──────────────────────────────────────────────────────
function addChild() {
  if (children.length >= 6) return;
  const id = 'ch' + Date.now();
  children.push({ id });
  renderChildren();
}

function removeChild(id) {
  children = children.filter(c => c.id !== id);
  renderChildren();
}

function renderChildren() {
  const list = document.getElementById('childList');
  list.innerHTML = '';
  children.forEach((ch, i) => {
    const d = document.createElement('div');
    d.className = 'dep-card';
    d.id = 'dep_' + ch.id;
    d.innerHTML = `
      <div class="dep-hdr">Child ${i + 1}
        <button class="btn-rm" onclick="removeChild('${ch.id}')">Remove</button>
      </div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label>
            <input type="text" id="${ch.id}_fn" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label>
            <input type="text" id="${ch.id}_ln" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="${ch.id}_dob"
              onchange="validateChildAge('${ch.id}')"/>
            <div class="age-disp" id="${ch.id}_age"></div></div>
          <div class="field"><label>Gender</label>
            <select id="${ch.id}_gender">
              <option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option>
            </select></div>
        </div>
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:4px">
          <label style="display:flex;align-items:center;gap:6px;font-size:.8rem;
                        font-weight:400;cursor:pointer">
            <input type="checkbox" id="${ch.id}_student"/>
            Full-time student (cover to age 25)
          </label>
          <label style="display:flex;align-items:center;gap:6px;font-size:.8rem;
                        font-weight:400;cursor:pointer">
            <input type="checkbox" id="${ch.id}_disabled"/>
            Disabled / special needs
          </label>
        </div>
      </div>`;
    list.appendChild(d);
  });
  document.getElementById('child_cnt').textContent =
    `${children.length} of 6 children added`;
  document.getElementById('addChildBtn').style.display =
    children.length >= 6 ? 'none' : 'flex';
}

function validateChildAge(id) {
  const dob      = document.getElementById(id + '_dob').value;
  const student  = document.getElementById(id + '_student').checked;
  const disabled = document.getElementById(id + '_disabled').checked;
  showAge(dob, id + '_age', 0, (student || disabled) ? 25 : 21);
}

// ── EXTENDED FAMILY ───────────────────────────────────────────────
function addEfm() {
  if (efmMembers.length >= 6) return;
  const id = 'ef' + Date.now();
  efmMembers.push({ id, tier: null });
  renderEfm();
}

function removeEfm(id) {
  efmMembers = efmMembers.filter(e => e.id !== id);
  recalcTotal();
  renderEfm();
}

function renderEfm() {
  const list = document.getElementById('efmList');
  list.innerHTML = '';
  efmMembers.forEach((efm, i) => {
    const d = document.createElement('div');
    d.className = 'dep-card';
    d.id = 'dep_' + efm.id;
    d.innerHTML = `
      <div class="dep-hdr">Extended Family Member ${i + 1}
        <button class="btn-rm" onclick="removeEfm('${efm.id}')">Remove</button>
      </div>
      <div class="dep-body">
        <div class="field-row">
          <div class="field"><label>First Name *</label>
            <input type="text" id="${efm.id}_fn" placeholder="First name"/></div>
          <div class="field"><label>Last Name *</label>
            <input type="text" id="${efm.id}_ln" placeholder="Last name"/></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Date of Birth *</label>
            <input type="date" id="${efm.id}_dob"
              onchange="showAge(this.value,'${efm.id}_age',0,89)"/>
            <div class="age-disp" id="${efm.id}_age"></div></div>
          <div class="field"><label>Relationship</label>
            <select id="${efm.id}_rel">
              <option value="">Select</option>
              <option>Parent</option><option>Sibling</option>
              <option>Grandparent</option><option>Uncle/Aunt</option>
              <option>Cousin</option><option>Other</option>
            </select></div>
        </div>
        <div class="field"><label>Select Cover Tier *</label>
          <div class="tier-grid" id="${efm.id}_tiers">
            <div class="tier-opt" id="${efm.id}_t1" onclick="selTier('${efm.id}','t1')">
              <div class="tier-cover">R2,000</div>
              <div class="tier-price">R60/mo</div>
              <div style="font-size:.65rem;color:var(--muted);margin-top:2px">1 Tier Casket</div>
            </div>
            <div class="tier-opt" id="${efm.id}_t2" onclick="selTier('${efm.id}','t2')">
              <div class="tier-cover">R3,000</div>
              <div class="tier-price">R80/mo</div>
              <div style="font-size:.65rem;color:var(--muted);margin-top:2px">1 Tier Casket</div>
            </div>
            <div class="tier-opt" id="${efm.id}_t3" onclick="selTier('${efm.id}','t3')">
              <div class="tier-cover">R4,000</div>
              <div class="tier-price">R110/mo</div>
              <div style="font-size:.65rem;color:var(--muted);margin-top:2px">2 Tier Casket</div>
            </div>
            <div class="tier-opt" id="${efm.id}_t4" onclick="selTier('${efm.id}','t4')">
              <div class="tier-cover">R5,000</div>
              <div class="tier-price">R220/mo</div>
              <div style="font-size:.65rem;color:var(--muted);margin-top:2px">Dome + Bus</div>
            </div>
          </div>
        </div>
      </div>`;
    list.appendChild(d);
  });
  document.getElementById('efm_cnt').textContent =
    `${efmMembers.length} of 6 extended family members added`;
  document.getElementById('addEfmBtn').style.display =
    efmMembers.length >= 6 ? 'none' : 'flex';
}

function selTier(efmId, tier) {
  efmMembers.find(e => e.id === efmId).tier = tier;
  ['t1','t2','t3','t4'].forEach(t => {
    const el = document.getElementById(efmId + '_' + t);
    if (el) el.classList.toggle('sel', t === tier);
  });
  recalcTotal();
}

// ── PAYMENT TOGGLE ────────────────────────────────────────────────
function switchPay(method) {
  document.getElementById('panel_debit').classList.toggle('active',  method === 'debit_order');
  document.getElementById('panel_online').classList.toggle('active', method === 'online_payment');
}

// ── CONSENT CHECKBOXES ────────────────────────────────────────────
function tglCheck(id) {
  const cb   = document.getElementById(id);
  const box  = document.getElementById('cbox_' + id);
  cb.checked = !cb.checked;
  if (cb.checked) {
    box.classList.add('on');
    if (id === 'tc_terms') tcAcceptedAt = new Date().toISOString();
  } else {
    box.classList.remove('on');
    if (id === 'tc_terms') tcAcceptedAt = null;
  }
}

// ── T&C MODAL ─────────────────────────────────────────────────────
function openTC(e) {
  if (e) e.preventDefault();
  document.getElementById('termsModal').style.display = 'block';
  document.body.style.overflow = 'hidden';
}

function closeTC() {
  document.getElementById('termsModal').style.display = 'none';
  document.body.style.overflow = '';
}

function acceptTCFromModal() {
  // Tick the T&C checkbox and record timestamp
  const cb  = document.getElementById('tc_terms');
  const box = document.getElementById('cbox_tc_terms');
  cb.checked    = true;
  tcAcceptedAt  = new Date().toISOString();
  box.classList.add('on');
  closeTC();
}

// ── SIGNATURE CANVAS ─────────────────────────────────────────────
function initCanvas() {
  const canvas = document.getElementById('sigCanvas');
  if (!canvas) return;
  sigCtx = canvas.getContext('2d');
  sigCtx.strokeStyle = '#0a1628';
  sigCtx.lineWidth   = 2.5;
  sigCtx.lineCap     = 'round';
  sigCtx.lineJoin    = 'round';

  const getPos = (c, ev) => {
    const r = c.getBoundingClientRect();
    return [
      (ev.clientX - r.left) * (c.width / r.width),
      (ev.clientY - r.top)  * (c.height / r.height),
    ];
  };

  canvas.addEventListener('mousedown', e => {
    drawing = true;
    [lastX, lastY] = getPos(canvas, e);
  });
  canvas.addEventListener('mousemove', e => {
    if (!drawing) return;
    const [x, y] = getPos(canvas, e);
    sigCtx.beginPath();
    sigCtx.moveTo(lastX, lastY);
    sigCtx.lineTo(x, y);
    sigCtx.stroke();
    [lastX, lastY] = [x, y];
  });
  canvas.addEventListener('mouseup',    () => { drawing = false; sigCtx.beginPath(); });
  canvas.addEventListener('mouseleave', () => { drawing = false; sigCtx.beginPath(); });

  canvas.addEventListener('touchstart', e => {
    e.preventDefault();
    drawing = true;
    [lastX, lastY] = getPos(canvas, e.touches[0]);
  }, { passive: false });
  canvas.addEventListener('touchmove', e => {
    e.preventDefault();
    if (!drawing) return;
    const [x, y] = getPos(canvas, e.touches[0]);
    sigCtx.beginPath();
    sigCtx.moveTo(lastX, lastY);
    sigCtx.lineTo(x, y);
    sigCtx.stroke();
    [lastX, lastY] = [x, y];
  }, { passive: false });
  canvas.addEventListener('touchend', () => { drawing = false; sigCtx.beginPath(); });
}

function clrSig() {
  const c = document.getElementById('sigCanvas');
  if (sigCtx) sigCtx.clearRect(0, 0, c.width, c.height);
}

function setSig(mode) {
  sigMode = mode;
  ['digital','photo','typed'].forEach(m => {
    document.getElementById('sb_' + m).classList.toggle('active', m === mode);
    document.getElementById('sp_' + m).classList.toggle('active',  m === mode);
  });
}

function updateTyped() {
  const val = document.getElementById('typed_sig').value;
  document.getElementById('typed_preview').textContent = val;
}

function sigPhotoUploaded(input) {
  if (!input.files[0]) return;
  document.getElementById('sig_photo_name').textContent = '✓ ' + input.files[0].name;
  document.getElementById('sigZone').classList.add('uploaded');
  const reader = new FileReader();
  reader.onload = e => { sigPhotoB64 = e.target.result; };
  reader.readAsDataURL(input.files[0]);
}

// ── REVIEW BUILDER ────────────────────────────────────────────────
function buildReview() {
  const get = id => {
    const el = document.getElementById(id);
    return el ? (el.value || '—') : '—';
  };
  const countryEl = document.getElementById('mm_country');
  const countryTxt = countryEl && countryEl.options[countryEl.selectedIndex]
    ? countryEl.options[countryEl.selectedIndex].text : '—';

  let html = '';

  // Main member
  html += revSec('Main Member', [
    ['Full Name',         `${get('mm_first')} ${get('mm_last')}`],
    ['Date of Birth',     `${get('mm_dob')} (Age ${calcAge(get('mm_dob'))})`],
    ['Gender',            get('mm_gender')],
    ['Nationality',       get('mm_nationality')],
    ['ID / Passport No.', get('mm_id_number')],
    ['Contact',           get('mm_phone')],
    ['WhatsApp',          get('mm_whatsapp') || '(same as contact)'],
    ['Email',             get('mm_email')],
    ['Country',           countryTxt],
    ['Province',          get('mm_province')],
    ['Postal Code',       get('mm_postal')],
    ['Area / Suburb',     get('mm_area')],
    ['Address',           get('mm_address')],
  ]);

  // Documents
  const ficOk  = document.getElementById('ficZone').classList.contains('uploaded');
  const passOk = document.getElementById('passportZone').classList.contains('uploaded');
  html += revSec('Documents Uploaded', [
    ['FIC Document',      ficOk  ? '✓ Uploaded' : '✗ Not uploaded'],
    ['Passport / ID Copy',passOk ? '✓ Uploaded' : '✗ Not uploaded'],
  ]);

  // Dependants
  const depRows = [];
  if (spouseAdded) {
    const fn = (document.getElementById('sp_first') || {}).value || '—';
    const ln = (document.getElementById('sp_last')  || {}).value || '—';
    depRows.push(['Spouse', `${fn} ${ln}`]);
  }
  children.forEach((ch, i) => {
    const fn  = (document.getElementById(ch.id+'_fn')  || {}).value || '—';
    const ln  = (document.getElementById(ch.id+'_ln')  || {}).value || '—';
    const dob = (document.getElementById(ch.id+'_dob') || {}).value || '—';
    depRows.push([`Child ${i+1}`, `${fn} ${ln} · DOB: ${dob}`]);
  });
  efmMembers.forEach((efm, i) => {
    const fn   = (document.getElementById(efm.id+'_fn')  || {}).value || '—';
    const ln   = (document.getElementById(efm.id+'_ln')  || {}).value || '—';
    const tier = efm.tier
      ? `R${EFM_TIERS[efm.tier].cover} cover @ R${EFM_TIERS[efm.tier].premium}/mo`
      : 'No tier selected';
    depRows.push([`Ext. Family ${i+1}`, `${fn} ${ln} · ${tier}`]);
  });
  if (!depRows.length) depRows.push(['Dependants', 'None added']);
  html += revSec('Dependants', depRows);

  // Plan
  const pName   = selectedPlan ? PLANS[selectedPlan].name : '—';
  const pCover  = selectedPlan ? `R${PLANS[selectedPlan].cover.toLocaleString()}` : '—';
  const base    = selectedPlan ? (coverType==='family'
    ? PLANS[selectedPlan].family : PLANS[selectedPlan].single) : 0;
  const efmPrem = efmMembers.reduce(
    (s,e) => s + (e.tier && EFM_TIERS[e.tier] ? EFM_TIERS[e.tier].premium : 0), 0);
  html += revSec('Cover & Plan', [
    ['Plan',              pName],
    ['Cover Type',        coverType === 'family' ? 'Family' : 'Single'],
    ['Sum Insured',       pCover],
    ['Base Premium',      `R${base}/month`],
    ['Ext. Family Prem',  efmPrem ? `R${efmPrem}/month` : '—'],
    ['TOTAL PREMIUM',     `R${base + efmPrem}/month`],
  ]);

  // Beneficiary
  html += revSec('Beneficiary', [
    ['Name',         `${get('ben_first')} ${get('ben_last')}`],
    ['Contact',      get('ben_phone')],
    ['Relationship', get('ben_rel')],
  ]);

  // Payment
  const pm = document.querySelector('input[name="pm"]:checked');
  const pmv = pm ? pm.value : 'debit_order';
  if (pmv === 'debit_order') {
    html += revSec('Payment (Debit Order)', [
      ['Account Holder',   get('dob_holder')],
      ['Bank',             get('dob_bank')],
      ['Account Number',   get('dob_accnum')],
      ['Account Type',     get('dob_acctype')],
      ['Branch Code',      get('dob_branch')],
      ['Deduction Date',   get('dob_deductdate')],
      ['Commencement',     get('dob_commence')],
    ]);
  } else {
    html += revSec('Payment', [['Method', 'Online Payment via portal']]);
  }

  // Waiting periods
  html += `<div class="waiting-box">
    <strong>Waiting Periods:</strong> Accidental death — Immediate &nbsp;|&nbsp;
    Natural causes (family) — 3 months &nbsp;|&nbsp;
    Extended family — 6 months &nbsp;|&nbsp; Suicide — 12 months
  </div>`;

  // Premium total
  html += `<div class="prem-box" style="margin-top:14px">
    <div><div class="prem-label">Total Monthly Premium</div></div>
    <div class="prem-amount">R${base + efmPrem}</div>
  </div>`;

  document.getElementById('reviewContent').innerHTML = html;
}

function revSec(title, rows) {
  let h = `<div class="rev-sec">
    <div class="rev-sec-title">${title}</div>`;
  rows.forEach(([k, v]) => {
    h += `<div class="rev-row">
      <span class="rev-k">${k}</span>
      <span class="rev-v">${v || '—'}</span>
    </div>`;
  });
  return h + '</div>';
}

// ── COLLECT DATA ──────────────────────────────────────────────────
function collectData() {
  const get = id => { const el = document.getElementById(id); return el ? el.value : ''; };
  const chk = id => { const el = document.getElementById(id); return el ? el.checked : false; };

  const countryEl  = document.getElementById('mm_country');
  const countryTxt = countryEl && countryEl.options[countryEl.selectedIndex]
    ? countryEl.options[countryEl.selectedIndex].text : '';

  const notifs = [];
  if (chk('notif_sms'))      notifs.push('sms');
  if (chk('notif_email'))    notifs.push('email');
  if (chk('notif_whatsapp')) notifs.push('whatsapp');
  if (chk('notif_tel'))      notifs.push('telephone');

  const spouseInfo = spouseAdded ? {
    first_name: get('sp_first'), last_name: get('sp_last'),
    dob:        get('sp_dob'),   gender:    get('sp_gender'),
    id_number:  get('sp_id'),
  } : null;

  const childrenInfo = children.map(ch => ({
    first_name: get(ch.id+'_fn'), last_name: get(ch.id+'_ln'),
    dob:        get(ch.id+'_dob'), gender: get(ch.id+'_gender'),
    student:    chk(ch.id+'_student'),
    disabled:   chk(ch.id+'_disabled'),
  }));

  const efmInfo = efmMembers.map(efm => ({
    first_name:   get(efm.id+'_fn'), last_name: get(efm.id+'_ln'),
    dob:          get(efm.id+'_dob'), relationship: get(efm.id+'_rel'),
    tier:         efm.tier,
    cover:        efm.tier && EFM_TIERS[efm.tier] ? EFM_TIERS[efm.tier].cover   : 0,
    premium:      efm.tier && EFM_TIERS[efm.tier] ? EFM_TIERS[efm.tier].premium : 0,
  }));

  const plan   = selectedPlan ? PLANS[selectedPlan] : null;
  const base   = plan ? (coverType==='family' ? plan.family : plan.single) : 0;
  const efmPr  = efmMembers.reduce(
    (s,e) => s + (e.tier && EFM_TIERS[e.tier] ? EFM_TIERS[e.tier].premium : 0), 0);

  // Build signature data
  let sigData = null;
  if (sigMode === 'digital') {
    const c = document.getElementById('sigCanvas');
    sigData = { type: 'digital', data: c.toDataURL('image/png') };
  } else if (sigMode === 'typed') {
    sigData = { type: 'typed', name: get('typed_sig') };
  } else if (sigMode === 'photo' && sigPhotoB64) {
    sigData = { type: 'photo', data: sigPhotoB64 };
  }

  return {
    main_member: {
      first_name:   get('mm_first'),
      last_name:    get('mm_last'),
      dob:          get('mm_dob'),
      gender:       get('mm_gender'),
      nationality:  get('mm_nationality'),
      id_number:    get('mm_id_number'),
      phone:        get('mm_phone'),
      whatsapp:     get('mm_whatsapp') || get('mm_phone'),
      email:        get('mm_email'),
      country:      countryTxt,
      country_code: get('mm_country'),
      province:     get('mm_province'),
      postal_code:  get('mm_postal'),
      area_code:    get('mm_area'),
      address:      get('mm_address'),
    },
    spouse:          spouseInfo,
    children:        childrenInfo,
    extended_family: efmInfo,
    plan:            selectedPlan  || '',
    plan_name:       plan ? plan.name : '',
    cover_type:      coverType,
    cover_amount:    plan ? plan.cover : 0,
    base_premium:    base,
    efm_premium:     efmPr,
    total_premium:   base + efmPr,
    beneficiary: {
      first_name:   get('ben_first'),
      last_name:    get('ben_last'),
      phone:        get('ben_phone'),
      relationship: get('ben_rel'),
    },
    payment_method: (document.querySelector('input[name="pm"]:checked') || {}).value || 'debit_order',
    debit_order: {
      account_holder:         get('dob_holder'),
      account_holder_contact: get('dob_contact'),
      bank:                   get('dob_bank'),
      branch_code:            get('dob_branch'),
      account_number:         get('dob_accnum'),
      account_type:           get('dob_acctype'),
      deduction_date:         get('dob_deductdate'),
      commencement_date:      get('dob_commence'),
    },
    declarations: {
      has_other_policy:    chk('op_yes'),
      other_policy_amount: get('op_amount'),
      is_replacement:      chk('rp_yes'),
      income_range:        get('d_income'),
      num_dependants:      get('d_numdeps'),
      monthly_expenses:    get('d_expenses'),
      available_cash:      get('d_cash'),
      notifications:       notifs,
    },
    agent: {
      name:        get('ag_name'),
      phone:       get('ag_phone'),
      team_leader: get('ag_leader'),
      province:    get('ag_province'),
    },
    signature:          sigData,
    popia_consent:      chk('tc_popia'),
    terms_accepted:     chk('tc_terms'),
    terms_accepted_at:  tcAcceptedAt || new Date().toISOString(),
    fais_accepted:      chk('tc_fais'),
    fic_uploaded:       document.getElementById('ficZone').classList.contains('uploaded'),
    passport_uploaded:  document.getElementById('passportZone').classList.contains('uploaded'),
    submission_timestamp: new Date().toISOString(),
  };
}

// ── SUBMIT ────────────────────────────────────────────────────────
async function submitApp() {
  // Validate signature
  if (sigMode === 'digital') {
    const c     = document.getElementById('sigCanvas');
    const blank = document.createElement('canvas');
    blank.width = c.width; blank.height = c.height;
    if (c.toDataURL() === blank.toDataURL()) {
      alert('Please provide a drawn signature before submitting.');
      return;
    }
  } else if (sigMode === 'typed') {
    if (!document.getElementById('typed_sig').value.trim()) {
      alert('Please type your full legal name as your signature before submitting.');
      return;
    }
  } else if (sigMode === 'photo' && !sigPhotoB64) {
    alert('Please upload a photo of your signature before submitting.');
    return;
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled    = true;
  btn.textContent = 'Submitting…';

  try {
    const payload = collectData();
    const res = await fetch('/api/v1/policies', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const result = await res.json();
    showSuccess(result.policy_number);
  } catch (err) {
    alert(`Submission failed: ${err.message}\n\nPlease check your connection and try again.`);
    btn.disabled    = false;
    btn.textContent = '✓ Submit Application';
  }
}

function showSuccess(polNum) {
  document.getElementById('formWrap').style.display        = 'none';
  document.querySelector('.progress-wrap').style.display   = 'none';
  document.getElementById('successScreen').style.display   = 'block';
  document.getElementById('sucPolNum').textContent         = polNum;
  window.scrollTo(0, 0);
}
