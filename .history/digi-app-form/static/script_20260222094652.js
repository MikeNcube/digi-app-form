async function submitApp(){

  const consent = document.getElementById('consentCheck');
  if(!consent || !consent.checked){
    alert('Please accept the declaration.');
    return;
  }

  const SUPABASE_URL = "https://puidycccmzpawipmcqeb.supabase.co";
  const SUPABASE_ANON_KEY = "sb_publishable_labTvgdA1dNhrqTWpvSEbA_G05LWe6E";

  const g = id => document.getElementById(id)?.value?.trim() || '';
  const planRaw = g('plan_sel');

  if(!planRaw){
    alert('Please select a plan.');
    return;
  }

  const pts = planRaw.split('|');
  const policyNumber = `WWFP-${Date.now()}`;

  const payload = {
    tenant_id: "11111111-1111-1111-1111-111111111111", // MUST exist in DB
    policy_number: policyNumber,
    policy_type: pts[0] || null,
    policyholder_name: `${g('fname')} ${g('lname')}`.trim() || null,
    policyholder_dob: g('dob') || null,
    policyholder_id: g('id_number') || null,
    phone: g('phone') || null,
    email: g('email') || null,
    street: g('street') || null,
    city: g('city') || null,
    province: g('province') || null,
    postal_code: g('postal_code') || null,
    coverage_amount: pts[2] ? parseFloat(pts[2]) : null,
    premium_amount: pts[3] ? parseFloat(pts[3]) : null,
    has_spouse: document.getElementById('marriedSelect')?.value === 'yes',
    spouse_name: g('spouse_name') || null,
    spouse_dob: g('spouse_dob') || null,
    children: [],
    extended_family: []
  };

  try {

    const res = await fetch(`${SUPABASE_URL}/rest/v1/policies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
        'Prefer': 'return=representation'  // IMPORTANT: show real errors
      },
      body: JSON.stringify(payload)
    });

    const responseText = await res.text();

    if (!res.ok) {
      console.error("Supabase Error:", responseText);
      throw new Error(responseText);
    }

    console.log("Insert success:", responseText);

    document.getElementById('appForm').style.display = 'none';
    document.querySelector('.form-nav').style.display = 'none';
    document.getElementById('stepTrack').style.display = 'none';
    document.getElementById('successScreen').style.display = 'block';
    document.getElementById('policyRef').textContent = policyNumber;

  } catch (err) {
    alert("Submission failed: " + err.message);
  }
}