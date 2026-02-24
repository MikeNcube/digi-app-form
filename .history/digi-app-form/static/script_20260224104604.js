let currentStep = 0;
let extendedMembers = [];

const exchangeRates = {
    SA: 1,
    SADC: 0.055,
    EU: 0.05
};

const plans = {
    Premium: { cover: 45000, Family: 540, Single: 450 },
    Prestige: { cover: 75000, Family: 720 },
    Executive: { cover: 90000, Family: 1080, Single: 990 }
};

function nextStep() {
    document.querySelectorAll(".step")[currentStep].classList.remove("active");
    currentStep++;
    document.querySelectorAll(".step")[currentStep].classList.add("active");
    if(currentStep === 3) buildReview();
}

function addExtended() {
    if(extendedMembers.length >= 6) return alert("Max 6 extended members");

    let name = prompt("Name");
    let age = parseInt(prompt("Age"));

    if(age >= 90) return alert("Must be under 90");

    let cover = prompt("Cover (2000,3000,4000,5000)");

    const pricing = {2000:60,3000:80,4000:110,5000:220};

    if(!pricing[cover]) return alert("Invalid cover");

    extendedMembers.push({
        name, age, cover, premium: pricing[cover]
    });

    renderExtended();
}

function renderExtended(){
    let container = document.getElementById("extendedList");
    container.innerHTML = "";
    extendedMembers.forEach(m => {
        container.innerHTML += `<p>${m.name} - R${m.premium}</p>`;
    });
}

function buildReview(){
    let plan = document.getElementById("plan").value;
    let type = document.getElementById("type").value;
    let region = document.getElementById("region").value;

    let basePremium = plans[plan][type];
    let baseCover = plans[plan].cover;

    let extTotal = extendedMembers.reduce((a,b)=>a+b.premium,0);
    let total = basePremium + extTotal;

    let rate = exchangeRates[region];

    document.getElementById("review").innerHTML = `
        <p>Base Premium: ${convert(total-extTotal, rate, region)}</p>
        <p>Extended Premium: ${convert(extTotal, rate, region)}</p>
        <p>Total Premium: <b>${convert(total, rate, region)}</b></p>
        <p>Cover: ${convert(baseCover, rate, region)}</p>
    `;
}

function convert(amount, rate, region){
    let currency = region === "SA" ? "ZAR" : region === "SADC" ? "USD" : "EUR";
    return (amount * rate).toFixed(2) + " " + currency;
}

async function submitApp(){
    let payload = {
        name: document.getElementById("fullName").value,
        dob: document.getElementById("dob").value,
        plan: document.getElementById("plan").value,
        type: document.getElementById("type").value,
        extendedMembers
    };

    let formData = new FormData();
    formData.append("payload", JSON.stringify(payload));

    const res = await fetch("/submit", {
        method:"POST",
        body: formData
    });

    const data = await res.json();
    alert(data.message);
}