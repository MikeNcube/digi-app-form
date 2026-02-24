/**
 * Zororo Phumulani â€” Worldwide Funeral Plan
 * app.js | Complete Logic Engine v2.0
 * Pricing Â· Currency Â· Age validation Â· Dynamic members Â· Review builder
 */

''use strict'';

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  CONSTANTS  (mirrors backend â€” single source of truth)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
const PLANS = {
  Premium:   { cover: 45000, single: 450,  family: 540,  label: ''Premium Plan''   },
  Prestige:  { cover: 75000, single: 630,  family: 720,  label: ''Prestige Plan''  },
  Executive: { cover: 90000, single: 990,  family: 1080, label: ''Executive Plan'' },
};

const EXT_COVER = { 2000: 60, 3000: 80, 4000: 110, 5000: 220 };

const FX = { ZAR: 1.0, USD: 0.054, EUR: 0.050 };
const SYM = { ZAR: ''R'', USD: ''$'', EUR: ''â‚¬'' };

const REGIONS = {
  ZAR: [''Gauteng'',''Western Cape'',''Eastern Cape'',''KwaZulu-Natal'',
        ''Limpopo'',''Mpumalanga'',''North West'',''Northern Cape'',''Free State''],
  USD: [''Zimbabwe'',''Zambia'',''Botswana'',''Namibia'',''Mozambique'',
        ''Malawi'',''Tanzania'',''Angola'',''DRC'',''Eswatini''],
  EUR: [''United Kingdom'',''Germany'',''Netherlands'',''Belgium'',
        ''France'',''Portugal'',''Spain'',''Other EU''],
};

const TOTAL_STEPS = 7;

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  STATE
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
const STATE = {
  step:      1,
  currency:  ''ZAR'',
  plan:      null,
  hasSpouse: false,
  children:  [],    // { id, name, dob, isStudent, isDisabled, proofFile }
  extended:  [],    // { id, name, dob, coverAmount }
  uploadedDocs: {}, // policy_id â†’ doc list (after creation)
  policyId:  null,
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  DOM HELPERS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const fmt = (n, cur = STATE.currency) =>
  `${SYM[cur]}${Math.round(n * FX[cur]).toLocaleString(''en-ZA'')}`;

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  INIT
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
document.addEventListener(''DOMContentLoaded'', () => {
  bindCurrency();
  bindSpouseToggle();
  bindPlanCards();
  renderProvince();
  renderExtCovers();
  updateStep(1);
  updatePriceSummary();
});

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  STEP NAVIGATION
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function goNext() {
  if (!validateStep(STATE.step)) return;
  if (STATE.step === TOTAL_STEPS - 1) buildReview();
  updateStep(STATE.step + 1);
}

function goPrev() {
  updateStep(STATE.step - 1);
}

function updateStep(n) {
  STATE.step = Math.min(Math.max(n, 1), TOTAL_STEPS);
  // hide all slides
  $$(''.slide'').forEach(s => s.classList.remove(''active''));
  const slide = $(`[data-step="${STATE.step}"]`);
  if (slide) slide.classList.add(''active'');
  // progress bar
  const fill = $(''#stepFill'');
  if (fill) fill.style.width = `${((STATE.step - 1) / (TOTAL_STEPS - 1)) * 100}%`;
  // step dots
  $$(''.s-step'').forEach((el, i) => {
    el.classList.remove(''active'', ''done'');
    if (i + 1 === STATE.step) el.classList.add(''active'');
    if (i + 1 <  STATE.step) el.classList.add(''done'');
  });
  // header
  const meta = STEP_META[STATE.step];
  if (meta) {
    const t = $(''#cardTitle''); const s = $(''#cardSub'');
    if (t) t.textContent = meta.title;
    if (s) s.textContent = meta.sub;
    const n2 = $(''#ctrNum'');
    if (n2) n2.textContent = String(STATE.step).padStart(2, ''0'');
  }
  // nav buttons
  const prev   = $(''#prevBtn'');
  const next   = $(''#nextBtn'');
  const submit = $(''#submitBtn'');
  if (prev)   prev.style.display   = STATE.step === 1 ? ''none'' : ''inline-flex'';
  if (next)   next.style.display   = STATE.step === TOTAL_STEPS ? ''none'' : ''inline-flex'';
  if (submit) submit.style.display = STATE.step === TOTAL_STEPS ? ''inline-flex'' : ''none'';

  window.scrollTo({ top: 0, behavior: ''smooth'' });
}

const STEP_META = {
  1: { title: ''Main Member Details'',        sub: ''Personal information of the primary policyholder'' },
  2: { title: ''Spouse Details'',             sub: ''Optional â€” spouse must be 18â€“65 years of age'' },
  3: { title: ''Children'',                   sub: ''Add up to 6 children â€” age limits apply'' },
  4: { title: ''Extended Family'',            sub: ''Add up to 6 extended members â€” must be under 90'' },
  5: { title: ''Coverage Plan & Location'',   sub: ''Select your plan and region for currency'' },
  6: { title: ''Review Your Application'',    sub: ''Verify all details â€” go back to edit anything'' },
  7: { title: ''Declaration & Consent'',      sub: ''Read and accept the terms to submit'' },
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  VALIDATION PER STEP
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function validateStep(step) {
  switch (step) {
    case 1: return validateMainMember();
    case 2: return validateSpouse();
    case 3: return validateChildren();
    case 4: return validateExtended();
    case 5: return validatePlan();
    default: return true;
  }
}

function validateMainMember() {
  const fname = $(''#fname'')?.value.trim();
  const lname = $(''#lname'')?.value.trim();
  const dob   = $(''#dob'')?.value;
  const phone = $(''#phone'')?.value.trim();
  const email = $(''#email'')?.value.trim();
  if (!fname) return alert(''Please enter your first name.''), false;
  if (!lname) return alert(''Please enter your last name.''), false;
  if (!dob)   return alert(''Please enter your date of birth.''), false;
  const a = ageFromDob(dob);
  if (a < 18 || a > 65) return alert(`Main member age (${a}) must be between 18 and 65.`), false;
  if (!phone) return alert(''Please enter a phone number.''), false;
  if (!email) return alert(''Please enter an email address.''), false;
  return true;
}

function validateSpouse() {
  if (!STATE.hasSpouse) return true;
  const sname = $(''#spouse_name'')?.value.trim();
  const sdob  = $(''#spouse_dob'')?.value;
  if (!sname) return alert(''Please enter spouse full name.''), false;
  if (!sdob)  return alert(''Please enter spouse date of birth.''), false;
  const sa = ageFromDob(sdob);
  if (sa < 18 || sa > 65) return alert(`Spouse age (${sa}) must be 18â€“65.`), false;
  return true;
}

function validateChildren() {
  for (const ch of STATE.children) {
    if (!ch.name.trim()) return alert(''Please enter a name for each child.''), false;
    if (!ch.dob)         return alert(`Please enter date of birth for child: ${ch.name}`), false;
    const ca  = ageFromDob(ch.dob);
    const max = (ch.isStudent || ch.isDisabled) ? 25 : 21;
    if (ca > max) {
      return alert(`Child "${ch.name}" is ${ca} years old â€” maximum is ${max} for ${ch.isStudent ? ''students'' : ch.isDisabled ? ''disabled'' : ''children''}.`), false;
    }
    if ((ch.isStudent || ch.isDisabled) && !ch.proofFile) {
      return alert(`Please upload proof for "${ch.name}" (student/disability certificate).`), false;
    }
  }
  return true;
}

function validateExtended() {
  for (const ex of STATE.extended) {
    if (!ex.name.trim()) return alert(''Please enter a name for each extended member.''), false;
    if (!ex.dob)         return alert(`Please enter DOB for: ${ex.name}`), false;
    const ea = ageFromDob(ex.dob);
    if (ea >= 90) return alert(`Extended member "${ex.name}" is ${ea} â€” must be under 90.`), false;
    if (!ex.coverAmount) return alert(`Please select cover amount for: ${ex.name}`), false;
  }
  return true;
}

function validatePlan() {
  if (!STATE.plan) return alert(''Please select a coverage plan.''), false;
  return true;
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  AGE HELPERS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function ageFromDob(dobStr) {
  if (!dobStr) return 0;
  return Math.floor((Date.now() - new Date(dobStr)) / (365.25 * 24 * 3600 * 1000));
}

function checkChildAge(input, childId) {
  const ch  = STATE.children.find(c => c.id === childId);
  if (!ch || !input.value) return;
  ch.dob    = input.value;
  const age = ageFromDob(input.value);
  const max = (ch.isStudent || ch.isDisabled) ? 25 : 21;
  const warn = input.closest(''.dep-row'')?.querySelector(''.age-warn'');
  if (warn) {
    if (age > max) {
      warn.textContent = `âš  Age ${age} exceeds max ${max}`;
      warn.style.display = ''block'';
    } else {
      warn.style.display = ''none'';
    }
  }
}

function checkExtAge(input, extId) {
  const ex = STATE.extended.find(e => e.id === extId);
  if (!ex || !input.value) return;
  ex.dob    = input.value;
  const age = ageFromDob(input.value);
  const warn = input.closest(''.dep-row'')?.querySelector(''.age-warn'');
  if (warn) {
    if (age >= 90) {
      warn.textContent = `âš  Age ${age} â€” must be under 90`;
      warn.style.display = ''block'';
    } else {
      warn.style.display = ''none'';
    }
  }
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  CURRENCY
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function bindCurrency() {
  const sel = $(''#currencySelect'');
  if (!sel) return;
  sel.addEventListener(''change'', function () {
    STATE.currency = this.value;
    renderProvince();
    updatePriceSummary();
  });
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  PROVINCE / REGION
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function renderProvince() {
  const sel = $(''#province'');
  if (!sel) return;
  const list = REGIONS[STATE.currency] || REGIONS.ZAR;
  sel.innerHTML = `<option value="">Select ${STATE.currency === ''ZAR'' ? ''province'' : ''country''}...</option>`
    + list.map(r => `<option value="${r}">${r}</option>`).join('''');
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  SPOUSE
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function bindSpouseToggle() {
  const sel = $(''#marriedSelect'');
  if (!sel) return;
  sel.addEventListener(''change'', function () {
    STATE.hasSpouse = this.value === ''yes'';
    const fields = $(''#spouseFields'');
    if (fields) fields.style.display = STATE.hasSpouse ? ''block'' : ''none'';
    updatePriceSummary();
  });
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  CHILDREN
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function addChild() {
  if (STATE.children.length >= 6) return alert(''Maximum 6 children allowed.'');
  const id  = ''ch_'' + Date.now();
  const obj = { id, name: '''', dob: null, isStudent: false, isDisabled: false, proofFile: null };
  STATE.children.push(obj);
  renderChildren();
}

function removeChild(id) {
  STATE.children = STATE.children.filter(c => c.id !== id);
  renderChildren();
  updatePriceSummary();
}

function renderChildren() {
  const list = $(''#childrenList'');
  if (!list) return;
  list.innerHTML = STATE.children.map(ch => `
    <div class="dep-row" data-id="${ch.id}">
      <div class="dep-fields">
        <div class="dep-row-top">
          <input type="text"   class="dep-name" placeholder="Child''s full name"
                 value="${ch.name}" onchange="updateChild(''${ch.id}'',''name'',this.value)">
          <input type="date"   class="dep-dob"
                 value="${ch.dob || ''''}"
                 onchange="updateChild(''${ch.id}'',''dob'',this.value);checkChildAge(this,''${ch.id}'')">
          <button type="button" class="btn-rm" onclick="removeChild(''${ch.id}'')">âœ•</button>
        </div>
        <div class="dep-options">
          <label class="chk-lbl">
            <input type="checkbox" ${ch.isStudent ? ''checked'' : ''''}
                   onchange="updateChild(''${ch.id}'',''isStudent'',this.checked);renderChildren()">
            Student (up to 25)
          </label>
          <label class="chk-lbl">
            <input type="checkbox" ${ch.isDisabled ? ''checked'' : ''''}
                   onchange="updateChild(''${ch.id}'',''isDisabled'',this.checked);renderChildren()">
            Disabled (up to 25)
          </label>
          ${(ch.isStudent || ch.isDisabled) ? `
          <label class="upload-sm">
            <span>${ch.proofFile ? ''âœ“ '' + ch.proofFile.name : ''ðŸ“Ž Upload proof certificate''}</span>
            <input type="file" accept=".pdf,.jpg,.jpeg,.png"
                   onchange="updateChild(''${ch.id}'',''proofFile'',this.files[0]);renderChildren()">
          </label>` : ''''}
        </div>
        <div class="age-warn" style="display:none"></div>
      </div>
    </div>
  `).join('''');
  updatePriceSummary();
}

function updateChild(id, field, value) {
  const ch = STATE.children.find(c => c.id === id);
  if (ch) ch[field] = value;
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  EXTENDED FAMILY
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function renderExtCovers() {
  // Used when building each ext row''s select
}

function addExtended() {
  if (STATE.extended.length >= 6) return alert(''Maximum 6 extended members allowed.'');
  const id  = ''ex_'' + Date.now();
  STATE.extended.push({ id, name: '''', dob: null, coverAmount: 2000 });
  renderExtended();
}

function removeExtended(id) {
  STATE.extended = STATE.extended.filter(e => e.id !== id);
  renderExtended();
  updatePriceSummary();
}

function renderExtended() {
  const list = $(''#extList'');
  if (!list) return;
  const coverOptions = Object.entries(EXT_COVER)
    .map(([cov, pm]) =>
      `<option value="${cov}">${fmt(+cov)} cover â€” ${fmt(pm)}/month</option>`
    ).join('''');

  list.innerHTML = STATE.extended.map(ex => `
    <div class="dep-row" data-id="${ex.id}">
      <div class="dep-fields">
        <div class="dep-row-top">
          <input type="text"  class="dep-name" placeholder="Full name"
                 value="${ex.name}" onchange="updateExt(''${ex.id}'',''name'',this.value)">
          <input type="date"  class="dep-dob"
                 value="${ex.dob || ''''}"
                 onchange="updateExt(''${ex.id}'',''dob'',this.value);checkExtAge(this,''${ex.id}'')">
          <select onchange="updateExt(''${ex.id}'',''coverAmount'',+this.value);updatePriceSummary()">
            ${coverOptions}
          </select>
          <button type="button" class="btn-rm" onclick="removeExtended(''${ex.id}'')">âœ•</button>
        </div>
        <div class="age-warn" style="display:none"></div>
      </div>
    </div>
  `).join('''');
  // restore selected values
  STATE.extended.forEach(ex => {
    const row = list.querySelector(`[data-id="${ex.id}"]`);
    if (!row) return;
    const sel = row.querySelector(''select'');
    if (sel) sel.value = String(ex.coverAmount);
  });
  updatePriceSummary();
}

function updateExt(id, field, value) {
  const ex = STATE.extended.find(e => e.id === id);
  if (ex) ex[field] = value;
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  PLAN SELECTION
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function bindPlanCards() {
  document.addEventListener(''click'', e => {
    const card = e.target.closest(''.plan-card'');
    if (!card) return;
    $$(''.plan-card'').forEach(c => c.classList.remove(''sel''));
    card.classList.add(''sel'');
    STATE.plan = card.dataset.plan;
    updatePriceSummary();
  });
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  PRICING ENGINE
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function computePricing() {
  if (!STATE.plan) return null;
  const plan    = PLANS[STATE.plan];
  const rate    = FX[STATE.currency];
  const hasFamily = STATE.hasSpouse || STATE.children.length > 0;
  const base    = hasFamily ? plan.family : plan.single;
  const extPm   = STATE.extended.reduce((s, e) => s + (EXT_COVER[e.coverAmount] || 60), 0);
  const total   = base + extPm;
  return {
    cover:    Math.round(plan.cover * rate),
    base:     Math.round(base  * rate),
    extPm:    Math.round(extPm * rate),
    total:    Math.round(total * rate),
    currency: STATE.currency,
  };
}

function updatePriceSummary() {
  const p = computePricing();
  if (!p) return;
  const els = {
    coverAmt:  $(''#summCover''),
    basePm:    $(''#summBase''),
    extPm:     $(''#summExt''),
    totalPm:   $(''#summTotal''),
  };
  if (els.coverAmt) els.coverAmt.textContent = fmt(p.cover / FX[STATE.currency]);
  if (els.basePm)   els.basePm.textContent   = fmt(p.base  / FX[STATE.currency]);
  if (els.extPm)    els.extPm.textContent    = fmt(p.extPm / FX[STATE.currency]);
  if (els.totalPm)  els.totalPm.textContent  = fmt(p.total / FX[STATE.currency]);

  // update plan card prices for current currency
  $$(''.plan-card'').forEach(card => {
    const pl = PLANS[card.dataset.plan];
    if (!pl) return;
    const cvr = card.querySelector(''.p-amt'');
    const si  = card.querySelector(''.p-single'');
    const fa  = card.querySelector(''.p-family'');
    if (cvr) cvr.textContent = fmt(pl.cover);
    if (si)  si.textContent  = `${SYM[STATE.currency]}${Math.round(pl.single * FX[STATE.currency]).toLocaleString()} single`;
    if (fa)  fa.textContent  = `${SYM[STATE.currency]}${Math.round(pl.family * FX[STATE.currency]).toLocaleString()} family`;
  });
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  REVIEW BUILDER
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function buildReview() {
  const pricing = computePricing();
  const area    = $(''#reviewArea'');
  if (!area || !pricing) return;

  const g = id => document.getElementById(id)?.value?.trim() || ''â€”'';
  const hasFamily = STATE.hasSpouse || STATE.children.length > 0;

  area.innerHTML = `
    <div class="rv-box">
      <h4>Main Member</h4>
      <div class="rv-main">${g(''fname'')} ${g(''lname'')}</div>
      <div class="rv-sub">DOB: ${g(''dob'')} Â· Age: ${ageFromDob(g(''dob''))}</div>
      <div class="rv-sub">${g(''phone'')} Â· ${g(''email'')}</div>
    </div>

    <div class="rv-box">
      <h4>Spouse</h4>
      ${STATE.hasSpouse
        ? `<div class="rv-main">${g(''spouse_name'')}</div>
           <div class="rv-sub">DOB: ${g(''spouse_dob'')} Â· Age: ${ageFromDob(g(''spouse_dob''))}</div>`
        : `<div class="rv-sub muted">No spouse added</div>`}
    </div>

    <div class="rv-box">
      <h4>Children (${STATE.children.length})</h4>
      ${STATE.children.length === 0
        ? `<div class="rv-sub muted">No children added</div>`
        : STATE.children.map(ch =>
            `<div class="rv-sub">
              <strong>${ch.name}</strong> â€” Age ${ageFromDob(ch.dob)}
              ${ch.isStudent ? '' Â· Student'' : ''''}
              ${ch.isDisabled ? '' Â· Disabled'' : ''''}
              ${ch.proofFile ? ` Â· <span class="tag-ok">Proof âœ“</span>` : ''''}
            </div>`
          ).join('''')}
    </div>

    <div class="rv-box">
      <h4>Extended Family (${STATE.extended.length})</h4>
      ${STATE.extended.length === 0
        ? `<div class="rv-sub muted">No extended members added</div>`
        : STATE.extended.map(ex =>
            `<div class="rv-sub">
              <strong>${ex.name}</strong> â€” Age ${ageFromDob(ex.dob)}
              Â· Cover ${fmt(ex.coverAmount)}
              Â· <span class="tag-pm">${fmt(EXT_COVER[ex.coverAmount])}/month</span>
            </div>`
          ).join('''')}
    </div>

    <div class="rv-box">
      <h4>Address</h4>
      <div class="rv-main">${g(''street'')}</div>
      <div class="rv-sub">${g(''city'')}, ${g(''province'')} Â· ${g(''postal_code'')}</div>
    </div>

    <div class="rv-box span2 gold-top">
      <h4>Coverage Plan â€” Premium Breakdown</h4>
      <div class="rv-main">${PLANS[STATE.plan]?.label || ''â€”''}</div>
      <div class="rv-pricing">
        <div class="rv-row"><span>Cover Amount</span><strong>${fmt(pricing.cover / FX[STATE.currency])}</strong></div>
        <div class="rv-row"><span>${hasFamily ? ''Family'' : ''Single''} Premium</span><strong>${fmt(pricing.base / FX[STATE.currency])}/month</strong></div>
        ${pricing.extPm > 0
          ? `<div class="rv-row"><span>Extended Member Premiums</span><strong>${fmt(pricing.extPm / FX[STATE.currency])}/month</strong></div>`
          : ''''}
        <div class="rv-row total-row"><span>Total Monthly Premium</span><strong>${fmt(pricing.total / FX[STATE.currency])}/month</strong></div>
        ${STATE.currency !== ''ZAR''
          ? `<div class="rv-row sub-row"><span>Displayed in ${STATE.currency} (1 ZAR = ${FX[STATE.currency]} ${STATE.currency})</span></div>`
          : ''''}
      </div>
    </div>
  `;
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  FILE UPLOAD HELPER (ID doc)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function onFile(input, labelId, zoneId) {
  const f = input.files[0];
  if (!f) return;
  const lbl  = document.getElementById(labelId);
  const zone = document.getElementById(zoneId);
  if (lbl)  lbl.textContent = ''âœ“ '' + f.name;
  if (zone) zone.classList.add(''filled'');
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  SUBMIT
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async function submitApp() {
  const btn = $(''#submitBtn'');
  if (!$(''#consentCheck'')?.checked) return alert(''Please accept the declaration to proceed.'');

  // Build payload
  const g = id => document.getElementById(id)?.value?.trim() || '''';
  const pricing   = computePricing();
  const polNum    = ''WWFP-'' + Date.now();

  const payload = {
    policy_number:     polNum,
    policy_type:       STATE.plan,
    currency:          STATE.currency,
    policyholder_name: `${g(''fname'')} ${g(''lname'')}`,
    policyholder_dob:  g(''dob''),
    phone:             g(''phone''),
    email:             g(''email''),
    street:            g(''street''),
    city:              g(''city''),
    province:          g(''province''),
    postal_code:       g(''postal_code''),
    has_spouse:        STATE.hasSpouse,
    spouse_name:       STATE.hasSpouse ? g(''spouse_name'') : null,
    spouse_dob:        STATE.hasSpouse ? g(''spouse_dob'')  : null,
    children:          STATE.children.map(ch => ({
      name:        ch.name,
      dob:         ch.dob,
      is_student:  ch.isStudent,
      is_disabled: ch.isDisabled,
    })),
    extended_family: STATE.extended.map(ex => ({
      name:         ex.name,
      dob:          ex.dob,
      cover_amount: ex.coverAmount,
      premium:      EXT_COVER[ex.coverAmount] || 60,
    })),
    source: ''digital_form'',
  };

  try {
    btn.innerHTML = ''âŒ› Submittingâ€¦'';
    btn.disabled  = true;

    const res  = await fetch(''/api/v1/policies'', {
      method:  ''POST'',
      headers: { ''Content-Type'': ''application/json'' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(Array.isArray(data.detail)
      ? data.detail.join(''\n'') : data.detail || ''Server error'');

    STATE.policyId = data.policy_id;

    // Upload ID doc if selected
    const idFile = $(''#id_upload'')?.files[0];
    if (idFile) await uploadDoc(STATE.policyId, ''id'', idFile);

    // Upload child proofs
    for (const ch of STATE.children) {
      if (ch.proofFile) await uploadDoc(STATE.policyId, ''student_proof'', ch.proofFile);
    }

    showSuccess(data.policy_number, pricing);
  } catch (err) {
    alert(''Submission failed:\n'' + err.message);
  } finally {
    btn.innerHTML = ''Submit Application âœ“'';
    btn.disabled  = false;
  }
}

async function uploadDoc(policyId, docType, file) {
  const fd = new FormData();
  fd.append(''policy_id'',     policyId);
  fd.append(''document_type'', docType);
  fd.append(''file'',          file);
  try {
    await fetch(''/api/v1/documents/upload'', { method: ''POST'', body: fd });
  } catch (e) {
    console.warn(''Doc upload failed:'', e);
  }
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  SUCCESS SCREEN
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
function showSuccess(policyNumber, pricing) {
  const form  = $(''#appForm'');
  const nav   = $(''.form-nav'');
  const track = $(''#stepTrack'');
  const succ  = $(''#successScreen'');
  if (form)  form.style.display  = ''none'';
  if (nav)   nav.style.display   = ''none'';
  if (track) track.style.display = ''none'';
  if (succ)  succ.style.display  = ''block'';

  const ref = $(''#policyRef'');
  if (ref) ref.textContent = policyNumber;

  const pm = $(''#successPremium'');
  if (pm && pricing)
    pm.textContent = `Total monthly premium: ${fmt(pricing.total / FX[STATE.currency])} ${STATE.currency}`;

  document.querySelector(''.form-card'')?.scrollIntoView({ behavior: ''smooth'', block: ''start'' });
}

