
var PLANS = {
  Premium:   {cover:45000, single:450,  family:540,  benefits:['Hearse and Mini Dome Casket','1 Return Air Ticket (Zimbabwe)','Grocery Allowance R4 500','Bus Benefit R5 400','Refreshments (bottled water, cash)']},
  Prestige:  {cover:75000, single:630,  family:720,  benefits:['Hearse and Standard Dome Casket','1 Return Air Ticket (Zimbabwe)','Grocery Allowance R7 200','Flowers','Bus Benefit R5 400']},
  Executive: {cover:90000, single:990,  family:1080, benefits:['Hearse and Royal Dome Casket','2 Return Air Tickets (Zimbabwe)','Grocery Allowance R10 800','Flowers','Bus Benefit R5 400']}
};
var EXT_OPTIONS = [
  {cover:2000, pm:60,  desc:'1 Tier Casket, R1 000 Chema Inyembezi, 2-Seater Transport'},
  {cover:3000, pm:80,  desc:'1 Tier Casket, R1 500 Chema Inyembezi, 6-Seater Transport'},
  {cover:4000, pm:110, desc:'2 Tier Casket, R2 000 Chema Inyembezi, 13-Seater Transport'},
  {cover:5000, pm:220, desc:'Std Dome Casket, R2 500 Chema, 13-Seater, Bus Benefit R3 000, Flight Option'}
];
var COUNTRY_CURR = {
  'South Africa':'R','Zimbabwe':'$','Zambia':'$','Botswana':'P','Namibia':'N$','Mozambique':'$',
  'Malawi':'$','Eswatini':'E','Lesotho':'L','Tanzania':'$','Kenya':'$','Nigeria':'NGN ',
  'Ghana':'GH ','United Kingdom':'GBP ','Germany':'EUR ','Netherlands':'EUR ','Belgium':'EUR ',
  'France':'EUR ','Portugal':'EUR ','Spain':'EUR ','Australia':'A$','New Zealand':'NZ$',
  'Canada':'C$','United States':'$'
};
var ST = {step:1, planName:null, planType:'single', deps:[]};
var payMethod = 'debit';

function calcAge(dob){ return dob ? Math.floor((Date.now()-new Date(dob))/(365.25*864e5)) : null; }
function gv(id){ var e=document.getElementById(id); return e ? e.value.trim() : ''; }
function fmt(n){ return 'R'+Math.round(n).toLocaleString('en-ZA'); }

window.addEventListener('load', function(){
  document.getElementById('dob').max = new Date().toISOString().split('T')[0];
});

function showAge(inp){
  var b=document.getElementById('ageBadge'), a=calcAge(inp.value);
  if(a===null){b.style.display='none';return;}
  b.style.display='inline-block';
  if(a<18||a>65){b.className='age-tag age-err';b.textContent='Age '+a+' - must be 18-65';}
  else{b.className='age-tag age-ok';b.textContent='Age '+a+' years';}
}

function onUpload(inp, lblId, zoneId){
  var f=inp.files[0]; if(!f) return;
  document.getElementById(lblId).textContent = f.name+' uploaded';
  document.getElementById(zoneId).className = 'upload-zone filled';
}

function setPlanType(type){
  ST.planType = type;
  document.getElementById('ptSingle').className = 'pt-btn'+(type==='single'?' sel':'');
  document.getElementById('ptFamily').className  = 'pt-btn'+(type==='family'?' sel':'');
  refreshPlanPrices();
  if(ST.planName) showPriceBox();
}

function refreshPlanPrices(){
  var names = ['Premium','Prestige','Executive'];
  for(var i=0;i<names.length;i++){
    var n=names[i], p=PLANS[n], pm=ST.planType==='family'?p.family:p.single;
    document.getElementById('pca_'+n).textContent = fmt(p.cover);
    document.getElementById('ppm_'+n).textContent = fmt(pm)+'/month';
  }
}

function selectPlan(name){
  ST.planName = name;
  var names = ['Premium','Prestige','Executive'];
  for(var i=0;i<names.length;i++){
    document.getElementById('pc_'+names[i]).className = 'pc'+(names[i]===name?' sel':'');
  }
  var plan = PLANS[name];
  document.getElementById('benTitle').textContent = name+' Plan - Included Benefits';
  var html = '';
  for(var j=0;j<plan.benefits.length;j++) html += '<div>&#10003; '+plan.benefits[j]+'</div>';
  document.getElementById('benList').innerHTML = html;
  document.getElementById('benefitsBox').style.display = 'block';
  showPriceBox();
}

function showPriceBox(){
  if(!ST.planName) return;
  var p=PLANS[ST.planName], pm=ST.planType==='family'?p.family:p.single;
  document.getElementById('priceBox').style.display = 'flex';
  document.getElementById('pbCover').textContent = fmt(p.cover);
  document.getElementById('pbType').textContent  = ST.planType==='family'?'Family':'Single';
  document.getElementById('pbPm').textContent    = fmt(pm)+'/month';
}

function calcTotalPremium(){
  if(!ST.planName) return {base:0, ext:0, total:0};
  var plan=PLANS[ST.planName];
  var hasFamily = ST.deps.some(function(d){return d.type==='Spouse'||d.type==='Child';});
  var base = (hasFamily||ST.planType==='family') ? plan.family : plan.single;
  var ext  = 0;
  for(var i=0;i<ST.deps.length;i++) if(ST.deps[i].type==='Extended') ext+=ST.deps[i].pm;
  return {base:base, ext:ext, total:base+ext};
}

function setPayMethod(m){
  payMethod = m;
  document.getElementById('pmDebit').className  = 'pt-btn'+(m==='debit'?' sel':'');
  document.getElementById('pmOnline').className = 'pt-btn'+(m==='online'?' sel':'');
  document.getElementById('debitBox').style.display     = m==='debit'?'block':'none';
  document.getElementById('onlinePayBox').style.display = m==='online'?'block':'none';
}

function handleIncomeMode(){
  var v = gv('incomeMode');
  document.getElementById('incomeRangeBox').style.display = v==='range'?'block':'none';
  document.getElementById('incomeTypeBox').style.display  = v==='type'?'block':'none';
  if(v==='range') updateIncomeCurrency();
}

function updateIncomeCurrency(){
  var sym = COUNTRY_CURR[gv('country')] || 'R';
  var ranges = ['Below '+sym+'5,000',sym+'5,000 - '+sym+'10,000',sym+'10,000 - '+sym+'20,000',sym+'20,000 - '+sym+'40,000','Above '+sym+'40,000'];
  for(var i=1;i<=5;i++){
    var el=document.getElementById('ir'+i);
    if(el){el.textContent=ranges[i-1];el.value=ranges[i-1];}
  }
  var ti=document.getElementById('incomeAmount');
  if(ti) ti.placeholder='e.g. '+sym+'15 000';
}

function getGrossIncome(){
  var v = gv('incomeMode');
  if(v==='none'||!v) return 'Not disclosed';
  if(v==='range') return gv('incomeRange')||'Not specified';
  if(v==='type')  return gv('incomeAmount')||'Not specified';
  return 'Not disclosed';
}

function toggleDeclare(){
  var cb  = document.getElementById('declareCheck');
  var box = document.getElementById('declareBox');
  cb.checked = !cb.checked;
  box.style.borderColor = cb.checked ? 'var(--green)' : 'var(--border)';
  box.style.background  = cb.checked ? '#f0fdf4'      : 'var(--off)';
}

function addDep(type){
  var sc=0,cc=0,ec=0;
  for(var i=0;i<ST.deps.length;i++){
    if(ST.deps[i].type==='Spouse')   sc++;
    if(ST.deps[i].type==='Child')    cc++;
    if(ST.deps[i].type==='Extended') ec++;
  }
  if(type==='Spouse'  &&sc>=1){alert('Maximum 1 spouse.');return;}
  if(type==='Child'   &&cc>=6){alert('Maximum 6 children.');return;}
  if(type==='Extended'&&ec>=6){alert('Maximum 6 extended members.');return;}
  ST.deps.push({id:'d'+Date.now(),type:type,name:'',dob:'',relationship:'',isStudent:false,isDisabled:false,coverAmount:2000,pm:60});
  renderDeps();
}

function removeDep(id){
  var next=[];
  for(var i=0;i<ST.deps.length;i++) if(ST.deps[i].id!==id) next.push(ST.deps[i]);
  ST.deps=next; renderDeps();
}

function renderDeps(){
  var list=document.getElementById('depList');
  list.innerHTML='';
  for(var i=0;i<ST.deps.length;i++) buildDepRow(ST.deps[i],list);
  var sc=0,cc=0,ec=0;
  for(var j=0;j<ST.deps.length;j++){
    if(ST.deps[j].type==='Spouse')   sc++;
    if(ST.deps[j].type==='Child')    cc++;
    if(ST.deps[j].type==='Extended') ec++;
  }
  document.getElementById('btnSpouse').disabled   = sc>=1;
  document.getElementById('btnChild').disabled    = cc>=6;
  document.getElementById('btnExtended').disabled = ec>=6;
  document.getElementById('extNote').style.display = ec>0?'block':'none';
}

function buildDepRow(d, container){
  var wrap=document.createElement('div'); wrap.className='dep-row';

  var hdr=document.createElement('div'); hdr.className='dep-header';
  var tag=document.createElement('span'); tag.className='dep-type-tag';
  tag.textContent=d.type==='Extended'?'Extended Family':d.type;
  var rm=document.createElement('button'); rm.type='button'; rm.className='btn-rm';
  rm.textContent='Remove';
  (function(did){rm.onclick=function(){removeDep(did);};})(d.id);
  hdr.appendChild(tag); hdr.appendChild(rm);

  var body=document.createElement('div'); body.className='dep-body';

  var nw=document.createElement('div');
  var nl=document.createElement('div'); nl.className='dep-lbl'; nl.textContent='Full Name *';
  var ni=document.createElement('input'); ni.type='text'; ni.className='dep-inp';
  ni.placeholder='Full name'; ni.value=d.name;
  (function(dep){ni.oninput=function(){dep.name=this.value;};})(d);
  nw.appendChild(nl); nw.appendChild(ni);

  var dw=document.createElement('div');
  var dl=document.createElement('div'); dl.className='dep-lbl'; dl.textContent='Date of Birth *';
  var di=document.createElement('input'); di.type='date'; di.className='dep-inp';
  di.max=new Date().toISOString().split('T')[0];
  if(d.dob) di.value=d.dob;
  var ageMsg=document.createElement('div'); ageMsg.className='dep-age-msg';
  (function(dep,msg){
    di.oninput=di.onchange=function(){
      dep.dob=this.value;
      var age=calcAge(this.value);
      if(age===null){msg.style.display='none';return;}
      msg.style.display='block';
      var ok=false;
      if(dep.type==='Spouse') ok=age>=18&&age<=65;
      else if(dep.type==='Extended') ok=age<90;
      else{var mx=(dep.isStudent||dep.isDisabled)?25:21; ok=age<=mx;}
      msg.style.background=ok?'#d1fae5':'#fee2e2';
      msg.style.color=ok?'#047857':'#dc2626';
      var label='';
      if(dep.type==='Spouse') label=ok?'Age '+age+' eligible':'Age '+age+' must be 18-65';
      else if(dep.type==='Extended') label=ok?'Age '+age+' eligible':'Age '+age+' must be under 90';
      else{var mx2=(dep.isStudent||dep.isDisabled)?25:21; label=ok?'Age '+age+' eligible':'Age '+age+' exceeds max '+mx2;}
      msg.textContent=label;
    };
  })(d,ageMsg);
  dw.appendChild(dl); dw.appendChild(di);
  body.appendChild(nw); body.appendChild(dw);

  if(d.type==='Extended'){
    var rw=document.createElement('div');
    var rl=document.createElement('div'); rl.className='dep-lbl'; rl.textContent='Relationship';
    var rs=document.createElement('select'); rs.className='dep-inp';
    var relOpts=['- Select -','Parent','Grandparent','Sibling','Aunt/Uncle','Cousin','In-law','Other'];
    for(var ri=0;ri<relOpts.length;ri++){
      var ro=document.createElement('option'); ro.value=ri===0?'':relOpts[ri]; ro.textContent=relOpts[ri]; rs.appendChild(ro);
    }
    if(d.relationship) rs.value=d.relationship;
    (function(dep){rs.onchange=function(){dep.relationship=this.value;};})(d);
    rw.appendChild(rl); rw.appendChild(rs);
    body.appendChild(rw);

    var cg=document.createElement('div'); cg.className='ext-cover-grid';
    for(var ei=0;ei<EXT_OPTIONS.length;ei++){
      (function(opt,dep){
        var btn=document.createElement('button'); btn.type='button';
        btn.className='ec-btn'+(dep.coverAmount===opt.cover?' sel':'');
        btn.innerHTML='<div class="ec-cover">R'+opt.cover.toLocaleString('en-ZA')+'</div><div class="ec-pm">R'+opt.pm+'/month</div><div class="ec-desc">'+opt.desc+'</div>';
        btn.onclick=function(){
          dep.coverAmount=opt.cover; dep.pm=opt.pm;
          var btns=cg.querySelectorAll('.ec-btn');
          for(var bi=0;bi<btns.length;bi++) btns[bi].className='ec-btn';
          btn.className='ec-btn sel';
        };
        cg.appendChild(btn);
      })(EXT_OPTIONS[ei],d);
    }
    body.appendChild(cg);
  }

  if(d.type==='Child'){
    var opts=document.createElement('div'); opts.className='dep-opts';
    function mkCk(lbl,field,dep2){
      var l=document.createElement('label'); l.className='ck';
      var cb=document.createElement('input'); cb.type='checkbox'; cb.checked=dep2[field];
      (function(f,dp,inp){cb.onchange=function(){dp[f]=this.checked;if(dp.dob)inp.oninput.call(inp);};})(field,dep2,di);
      var sp=document.createElement('span'); sp.textContent=' '+lbl;
      l.appendChild(cb); l.appendChild(sp); return l;
    }
    opts.appendChild(mkCk('Student (max 25)','isStudent',d));
    opts.appendChild(mkCk('Disabled (max 25)','isDisabled',d));
    body.appendChild(opts);
  }

  wrap.appendChild(hdr); wrap.appendChild(body); wrap.appendChild(ageMsg);
  container.appendChild(wrap);
}

function buildReview(){
  var pm=calcTotalPremium(), plan=PLANS[ST.planName];
  var dob=gv('dob'), age=calcAge(dob);
  var idF=document.getElementById('idFile');
  document.getElementById('rvName').textContent    = gv('fullName')||'-';
  document.getElementById('rvDob').textContent     = dob||'-';
  document.getElementById('rvAge').textContent     = age!==null?age+' years':'-';
  document.getElementById('rvPhone').textContent   = gv('phone')||'-';
  document.getElementById('rvEmail').textContent   = gv('email')||'-';
  document.getElementById('rvCountry').textContent = gv('country')||'-';
  document.getElementById('rvAddress').textContent = gv('address')||'-';
  document.getElementById('rvId').textContent      = (idF&&idF.files[0])?idF.files[0].name:'Not uploaded';
  document.getElementById('rvBenName').textContent = (gv('benFirst')+' '+gv('benLast')).trim()||'-';
  document.getElementById('rvBenPhone').textContent= gv('benPhone')||'-';
  document.getElementById('rvBenRel').textContent  = gv('benRel')||'-';
  document.getElementById('rvPayMethod').textContent = payMethod==='online'?'Online Payment':'Debit Order';
  document.getElementById('rvBankRow').style.display  = payMethod==='debit'?'flex':'none';
  document.getElementById('rvAcctRow').style.display  = payMethod==='debit'?'flex':'none';
  document.getElementById('rvDeductRow').style.display= payMethod==='debit'?'flex':'none';
  document.getElementById('rvBank').textContent    = gv('bankName')||'-';
  document.getElementById('rvAcct').textContent    = gv('acctNumber')?(gv('acctType')+' ****'+gv('acctNumber').slice(-4)):'-';
  document.getElementById('rvDeduct').textContent  = gv('deductDate')||'-';
  document.getElementById('rvPlan').textContent    = ST.planName?ST.planName+' Plan':'-';
  document.getElementById('rvType').textContent    = ST.planType==='family'?'Family':'Single';
  document.getElementById('rvCover').textContent   = plan?fmt(plan.cover):'-';
  document.getElementById('rvBase').textContent    = fmt(pm.base)+'/month';
  document.getElementById('rvTotal').textContent   = fmt(pm.total)+'/month';
  var extRow=document.getElementById('rvExtRow');
  if(pm.ext>0){extRow.style.display='flex'; document.getElementById('rvExt').textContent=fmt(pm.ext)+'/month';}
  else extRow.style.display='none';
  var depSec=document.getElementById('rvDepSec');
  if(ST.deps.length>0){
    depSec.style.display='block';
    var html='';
    for(var i=0;i<ST.deps.length;i++){
      var dep=ST.deps[i], a=dep.dob?calcAge(dep.dob):null;
      var extra=dep.type==='Extended'?' - R'+dep.coverAmount.toLocaleString('en-ZA')+' cover, R'+dep.pm+'/m'+(dep.relationship?' ('+dep.relationship+')':''):((dep.isStudent?' Student':'')+(dep.isDisabled?' Disabled':''));
      html+='<div class="rv-r"><span>'+dep.type+'</span><strong>'+(dep.name||'unnamed')+(a!==null?', Age '+a:'')+extra+'</strong></div>';
    }
    document.getElementById('rvDeps').innerHTML=html;
  } else depSec.style.display='none';
}

function validate(){
  if(ST.step===1){
    if(!gv('fullName'))  {alert('Please enter your full name.');return false;}
    if(!gv('dob'))       {alert('Please enter your date of birth.');return false;}
    var a=calcAge(gv('dob')); if(a<18||a>65){alert('Age '+a+' is outside 18-65.');return false;}
    if(!gv('phone'))     {alert('Please enter your phone number.');return false;}
    if(!gv('email'))     {alert('Please enter your email address.');return false;}
    if(!gv('country'))   {alert('Please select your country of residence.');return false;}
    if(!gv('address'))   {alert('Please enter your residential address.');return false;}
    if(!ST.planName)     {alert('Please select a plan.');return false;}
  }
  if(ST.step===2){
    for(var i=0;i<ST.deps.length;i++){
      var d=ST.deps[i];
      if(!d.name.trim()){alert('Please enter a name for each member.');return false;}
      if(!d.dob){alert('Please enter date of birth for '+(d.name||'member'));return false;}
      var da=calcAge(d.dob);
      if(d.type==='Spouse'&&(da<18||da>65)){alert('Spouse "'+d.name+'" age '+da+' must be 18-65.');return false;}
      if(d.type==='Child'){var mx=(d.isStudent||d.isDisabled)?25:21;if(da>mx){alert('Child "'+d.name+'" age '+da+' exceeds max '+mx);return false;}}
      if(d.type==='Extended'&&da>=90){alert('Extended member "'+d.name+'" must be under 90.');return false;}
    }
  }
  if(ST.step===3){
    if(!gv('benFirst')){alert('Please enter beneficiary first name.');return false;}
    if(!gv('benLast')) {alert('Please enter beneficiary last name.');return false;}
    if(!gv('benPhone')){alert('Please enter beneficiary phone number.');return false;}
    if(!gv('benRel'))  {alert('Please select beneficiary relationship.');return false;}
  }
  if(ST.step===4&&payMethod==='debit'){
    if(!gv('bankName'))  {alert('Please select your bank.');return false;}
    if(!gv('acctHolder')){alert('Please enter account holder name.');return false;}
    if(!gv('acctNumber')){alert('Please enter your account number.');return false;}
    if(!gv('acctType'))  {alert('Please select account type.');return false;}
    if(!gv('deductDate')){alert('Please select deduction date.');return false;}
  }
  if(ST.step===5){
    if(!document.getElementById('declareCheck').checked){alert('Please accept the declaration to continue.');return false;}
  }
  return true;
}

var META={
  1:{title:'Step 1: Principal Member Details',   sub:'Personal information and plan selection',    num:'01'},
  2:{title:'Step 2: Add Dependants',              sub:'Spouse, children and extended family',       num:'02'},
  3:{title:'Step 3: Beneficiary Details',         sub:'Who receives the payout',                   num:'03'},
  4:{title:'Step 4: Payment Details',             sub:'Monthly premium collection',                num:'04'},
  5:{title:'Step 5: Declarations',                sub:'Needs analysis and authorisation',          num:'05'},
  6:{title:'Step 6: Review and Confirm',          sub:'Verify all details before submitting',      num:'06'}
};

function goNext(){if(!validate())return; if(ST.step===5)buildReview(); setStep(ST.step+1);}
function goPrev(){setStep(ST.step-1);}

function setStep(n){
  ST.step=Math.max(1,Math.min(6,n));
  for(var i=1;i<=6;i++){
    var el=document.getElementById('s'+i);
    if(!el) continue;
    el.style.display=(i===ST.step)?'block':'none';
    if(i===ST.step) el.classList.add('active'); else el.classList.remove('active');
  }
  var m=META[ST.step];
  document.getElementById('cardTitle').textContent=m.title;
  document.getElementById('cardSub').textContent=m.sub;
  document.getElementById('cardNum').textContent=m.num;
  document.getElementById('navInfo').textContent='Step '+ST.step+' of 6';
  document.getElementById('prevBtn').style.display   = ST.step>1?'inline-flex':'none';
  document.getElementById('nextBtn').style.display   = ST.step<6?'inline-flex':'none';
  document.getElementById('submitBtn').style.display = ST.step===6?'inline-flex':'none';
  var items=document.querySelectorAll('.si');
  for(var j=0;j<items.length;j++){
    items[j].classList.remove('active','done');
    if(j+1===ST.step) items[j].classList.add('active');
    if(j+1< ST.step)  items[j].classList.add('done');
  }
  document.getElementById('progFill').style.width=Math.round((ST.step-1)/5*100)+'%';
  window.scrollTo({top:0,behavior:'smooth'});
}

function submitApp(){
  var btn=document.getElementById('submitBtn');
  var pm=calcTotalPremium(), plan=PLANS[ST.planName];
  var polNum='WWFP-'+Date.now();
  var children=[], extended=[];
  for(var i=0;i<ST.deps.length;i++){
    var d=ST.deps[i];
    if(d.type==='Child')    children.push({name:d.name,dob:d.dob,is_student:d.isStudent,is_disabled:d.isDisabled});
    if(d.type==='Extended') extended.push({name:d.name,dob:d.dob,relationship:d.relationship,cover_amount:d.coverAmount,premium:d.pm});
  }
  var spouse=null;
  for(var k=0;k<ST.deps.length;k++) if(ST.deps[k].type==='Spouse'){spouse=ST.deps[k];break;}
  var payload={
    policy_number:polNum, policy_type:ST.planName, currency:'ZAR', plan_type:ST.planType,
    policyholder_name:gv('fullName'), policyholder_dob:gv('dob'),
    phone:gv('phone'), email:gv('email'),
    street:gv('address'), city:'', province:gv('country'), postal_code:'', country:gv('country'),
    has_spouse:spouse!==null,
    spouse_name:spouse?spouse.name:null, spouse_dob:spouse?spouse.dob:null,
    children:children, extended_family:extended,
    beneficiary_name:gv('benFirst')+' '+gv('benLast'),
    beneficiary_phone:gv('benPhone'), beneficiary_relationship:gv('benRel'),
    bank_name:gv('bankName'), account_holder:gv('acctHolder'),
    account_number:gv('acctNumber'), account_type:gv('acctType'),
    branch_code:gv('branchCode'), deduction_date:gv('deductDate'),
    agent_name:gv('agentName'), agent_phone:gv('agentPhone'),
    has_other_policies:gv('otherPolicies')==='yes',
    gross_income:getGrossIncome(),
    payment_method:payMethod,
    replacing_policy:gv('replacingPolicy')==='yes',
    source:'digital_form'
  };
  btn.textContent='Submitting...'; btn.disabled=true;
  fetch('/api/v1/policies',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
  }).then(function(res){
    return res.json().then(function(d){return{ok:res.ok,data:d};});
  }).then(function(r){
    if(!r.ok) throw new Error(Array.isArray(r.data.detail)?r.data.detail.join('\n'):r.data.detail||'Server error');
    document.getElementById('appForm').style.display='none';
    document.getElementById('succScreen').style.display='block';
    document.querySelector('.cf').style.display='none';
    document.getElementById('prog').style.display='none';
    document.getElementById('cardTitle').textContent='Application Complete';
    document.getElementById('cardSub').textContent='Thank you - your policy is being processed';
    document.getElementById('cardNum').textContent='OK';
    document.getElementById('polRef').textContent=r.data.policy_number||polNum;
    document.getElementById('spm').textContent=fmt(pm.total)+'/month';
    document.getElementById('scov').textContent=plan?fmt(plan.cover):'-';
    window.scrollTo({top:0,behavior:'smooth'});
  }).catch(function(err){
    alert('Submission failed:\n'+err.message);
    btn.textContent='Submit Application'; btn.disabled=false;
  });
}

refreshPlanPrices();
