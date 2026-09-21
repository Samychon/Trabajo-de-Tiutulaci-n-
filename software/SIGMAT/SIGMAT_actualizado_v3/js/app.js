const inventory = [
  {code:"MOT-001",name:"Motor Eléctrico (Trifásico Industrial)",type:"Motor",status:"Disponible",location:"Almacén electromecánico",function:"Accionamiento de bombas y equipos rotativos.",specs:{tipo:"Corriente alterna, síncrono o de inducción",potencia:"100 CV (75 kW)",velocidad:"Aproximadamente 1,750 RPM a 60 Hz",modelo:"Motor industrial trifásico"}},
  {code:"TAL-001",name:"Taladro inalámbrico industrial",type:"Taladro",status:"En uso",location:"Almacén",function:"Perforación y atornillado en trabajos de mantenimiento.",specs:{tipo:"Herramienta portátil",potencia:"18 V",velocidad:"0–1,800 RPM",modelo:"Industrial"}},
  {code:"INS-001",name:"Multímetro digital",type:"Instrumento",status:"Disponible",location:"Almacén",function:"Medición de variables eléctricas durante mantenimiento.",specs:{tipo:"Instrumento de medición",potencia:"Alimentación interna",velocidad:"No aplica",modelo:"Digital"}},
  {code:"HER-001",name:"Juego de llaves combinadas",type:"Herramienta manual",status:"Disponible",location:"Almacén",function:"Apriete y aflojamiento de tornillería.",specs:{tipo:"Herramienta manual",potencia:"No aplica",velocidad:"No aplica",modelo:"Juego métrico"}},
  {code:"BOM-001",name:"Bomba centrífuga",type:"Bomba",status:"Mantenimiento",location:"Área de mantenimiento",function:"Impulsión y circulación de agua.",specs:{tipo:"Bomba centrífuga",potencia:"15 HP",velocidad:"3,450 RPM",modelo:"Horizontal"}}
];

let movements = [
  {id:"MOV-0001",code:"TAL-001",item:"Taladro inalámbrico industrial",responsible:"Carlos López",location:"Taller electromecánico",purpose:"Mantenimiento",authorizer:"Jefe de Área 1",exit:"18/09/2026 09:15",returnDate:"—",status:"En uso",start:new Date(2026,8,18,9,15)},
  {id:"MOV-0002",code:"INS-001",item:"Multímetro digital",responsible:"Ana Torres",location:"Área de control",purpose:"Diagnóstico",authorizer:"Jefe de Área 2",exit:"17/09/2026 10:20",returnDate:"17/09/2026 15:45",status:"Devuelto",start:new Date(2026,8,17,10,20)}
];

let alerts = [
  {date:"20/09/2026 11:42",event:"Salida no autorizada",item:"Taladro inalámbrico industrial",status:"Pendiente",admin:"—",action:"Revisar"},
  {date:"15/09/2026 14:18",event:"Artículo no reconocido",item:"Registro desconocido",status:"Resuelta",admin:"Administrador",action:"Evento revisado"}
];

let decommissionHistory = [
  {date:"05/09/2026 13:10",code:"HER-008",item:"Pinza de presión",reason:"Descomposición o daño irreparable",description:"Daño estructural que impide su uso seguro.",admin:"Administrador"}
];

let users = [
  {initials:"AD",name:"Administrador",role:"Administrador del sistema",status:"Activo"},
  {initials:"J1",name:"Jefe de Área 1",role:"Autorizador de salidas",status:"Activo"},
  {initials:"J2",name:"Jefe de Área 2",role:"Autorizador de salidas",status:"Activo"}
];

const reportData = {
  week:{outs:12,returns:9,incidents:1,average:"4 h 18 min",rows:[
    ["Lun–Dom · Semana actual",12,9,1,"Taladro inalámbrico"],
    ["Lun–Dom · Semana anterior",15,14,0,"Multímetro digital"],
    ["Lun–Dom · Hace 2 semanas",10,8,1,"Juego de llaves"]
  ]},
  month:{outs:48,returns:42,incidents:3,average:"4 h 41 min",rows:[
    ["Septiembre 2026",48,42,3,"Taladro inalámbrico"],
    ["Agosto 2026",52,50,1,"Multímetro digital"],
    ["Julio 2026",45,43,2,"Motor eléctrico"]
  ]}
};

let pendingAuthorization = null;
let pendingAddItem = null;
let pendingDecommission = null;

const sectionNames = {
  dashboard:"Inicio",inventario:"Inventario",salida:"Registrar salida",uso:"Herramientas en uso",bajas:"Bajas de inventario",movimientos:"Movimientos",alertas:"Historial de alertas",reportes:"Reportes",informacion:"Información",configuracion:"Configuración"
};

// LOGIN
document.getElementById("login-form").addEventListener("submit",e=>{
  e.preventDefault();
  const user=document.getElementById("login-user").value.trim();
  const pass=document.getElementById("login-password").value;
  if(user==="admin"&&pass==="admin123"){
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    renderAll(); updateDate();
  }else document.getElementById("login-error").classList.remove("hidden");
});

document.getElementById("logout-btn").addEventListener("click",()=>{
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
});

// NAVEGACIÓN
document.querySelectorAll(".nav-item").forEach(btn=>btn.addEventListener("click",()=>showSection(btn.dataset.section)));
document.querySelectorAll("[data-go]").forEach(btn=>btn.addEventListener("click",()=>showSection(btn.dataset.go)));
document.getElementById("brand-home").addEventListener("click",()=>showSection("dashboard"));
document.getElementById("alerts-shortcut").addEventListener("click",()=>showSection("alertas"));

function showSection(section){
  document.querySelectorAll(".content-section").forEach(s=>s.classList.remove("active-section"));
  document.getElementById(`section-${section}`).classList.add("active-section");
  document.querySelectorAll(".nav-item").forEach(n=>n.classList.toggle("active",n.dataset.section===section));
  document.getElementById("page-title").textContent=sectionNames[section];
  window.scrollTo({top:0,behavior:"smooth"});
}

// INVENTARIO Y FILTROS
function statusTag(status){
  const cls=status==="Disponible"||status==="Devuelto"?"green":status==="En uso"?"orange":status==="Baja"?"red":"gray";
  return `<span class="tag ${cls}">${status}</span>`;
}

function renderInventory(list=inventory){
  const body=document.getElementById("inventory-body");
  body.innerHTML=list.map(item=>`<tr>
    <td><strong>${item.code}</strong></td><td>${item.name}</td><td>${item.type}</td><td>${statusTag(item.status)}</td><td>${item.location}</td><td>${item.function}</td>
    <td><div class="action-group"><button class="action-btn" onclick="showItem('${item.code}')">Ver ficha</button>${item.status!=="Baja"?`<button class="action-btn danger-action" onclick="prepareDecommission('${item.code}')">Dar de baja</button>`:""}</div></td>
  </tr>`).join("") || `<tr><td colspan="7">No hay artículos que coincidan con los filtros.</td></tr>`;
  refreshLocationFilter();
  renderDecommissionOptions();
}

function refreshLocationFilter(){
  const select=document.getElementById("inventory-location-filter");
  const current=select.value;
  const locations=[...new Set(inventory.map(i=>i.location).filter(Boolean))].sort();
  select.innerHTML='<option value="todos">Todas</option>'+locations.map(l=>`<option>${l}</option>`).join("");
  if([...select.options].some(o=>o.value===current))select.value=current;
}

function filterInventory(){
  const q=document.getElementById("inventory-search").value.toLowerCase();
  const status=document.getElementById("inventory-status-filter").value;
  const type=document.getElementById("inventory-type-filter").value;
  const location=document.getElementById("inventory-location-filter").value;
  renderInventory(inventory.filter(i=>{
    const text=[i.code,i.name,i.type,i.location,i.function].join(" ").toLowerCase();
    return text.includes(q)&&(status==="todos"||i.status===status)&&(type==="todos"||i.type===type)&&(location==="todos"||i.location===location);
  }));
}
["inventory-search","inventory-status-filter","inventory-type-filter","inventory-location-filter"].forEach(id=>document.getElementById(id).addEventListener(id==="inventory-search"?"input":"change",filterInventory));
document.getElementById("clear-inventory-filters").addEventListener("click",()=>{
  document.getElementById("inventory-search").value="";document.getElementById("inventory-status-filter").value="todos";document.getElementById("inventory-type-filter").value="todos";document.getElementById("inventory-location-filter").value="todos";renderInventory();
});

function showItem(code){
  const item=inventory.find(i=>i.code===code); if(!item)return;
  openModal(`Ficha de ${item.code}`,`<div class="modal-detail">
    <div><span>Artículo</span><strong>${item.name}</strong></div><div><span>Tipo</span><strong>${item.type}</strong></div><div><span>Estado</span><strong>${item.status}</strong></div><div><span>Ubicación</span><strong>${item.location}</strong></div><div><span>Función</span><strong>${item.function}</strong></div><div><span>Tipo / descripción</span><strong>${item.specs.tipo}</strong></div><div><span>Potencia / capacidad</span><strong>${item.specs.potencia}</strong></div><div><span>Velocidad / rango</span><strong>${item.specs.velocidad}</strong></div><div><span>Modelo</span><strong>${item.specs.modelo}</strong></div>
  </div>`);
}

// ALTA DE ARTÍCULO CON CÓDIGO AUTOMÁTICO
const prefixMap={Motor:"MOT",Bomba:"BOM",Taladro:"TAL","Herramienta manual":"HER",Instrumento:"INS",Equipo:"EQU",Material:"MAT",Otro:"ART"};
function generateCodeByType(type){
  const prefix=prefixMap[type]||"ART";
  const used=inventory.filter(i=>i.code.startsWith(prefix+"-")).map(i=>Number(i.code.split("-")[1])||0);
  const next=(used.length?Math.max(...used):0)+1;
  return `${prefix}-${String(next).padStart(3,"0")}`;
}

document.getElementById("add-item-btn").addEventListener("click",()=>{
  openModal("Agregar artículo",`<form id="add-item-form" class="form-grid">
    <div><label>Tipo de artículo</label><select id="new-item-type" required><option>Motor</option><option>Bomba</option><option>Taladro</option><option>Herramienta manual</option><option>Instrumento</option><option>Equipo</option><option>Material</option><option>Otro</option></select></div>
    <div><label>Código asignado</label><input id="new-item-code" readonly></div>
    <div class="full-row"><label>Nombre</label><input id="new-item-name" required placeholder="Nombre del artículo"></div>
    <div><label>Ubicación</label><input id="new-item-location" required value="Almacén"></div><div><label>Modelo</label><input id="new-item-model" placeholder="Opcional"></div>
    <div><label>Tipo / descripción</label><input id="new-item-spec-type" placeholder="Descripción técnica"></div><div><label>Potencia / capacidad</label><input id="new-item-power" placeholder="Si aplica"></div>
    <div><label>Velocidad / rango</label><input id="new-item-speed" placeholder="Si aplica"></div><div><label>Estado inicial</label><input value="Disponible" readonly></div>
    <div class="full-row"><label>Función</label><textarea id="new-item-function" required placeholder="¿Para qué se utiliza?"></textarea></div>
    <div class="full-row authorization-box compact"><div><span class="auth-icon">✓</span><div><strong>Autorización administrativa</strong><p>Al guardar se solicitará validación automática. También puede utilizarse contraseña.</p></div></div><button type="button" class="btn btn-secondary" id="new-item-password">Usar contraseña</button></div>
    <div class="full-row form-actions"><button class="btn btn-primary" type="submit">Guardar artículo</button></div>
  </form>`);
  const typeSel=document.getElementById("new-item-type");
  const updateCode=()=>document.getElementById("new-item-code").value=generateCodeByType(typeSel.value);
  typeSel.addEventListener("change",updateCode);updateCode();
  document.getElementById("new-item-password").addEventListener("click",()=>openPasswordAuthorization("add-item"));
  document.getElementById("add-item-form").addEventListener("submit",e=>{
    e.preventDefault(); pendingAddItem=collectNewItem(); requestAutomaticAuthorization("add-item");
  });
});

function collectNewItem(){
  return {code:document.getElementById("new-item-code").value,type:document.getElementById("new-item-type").value,name:document.getElementById("new-item-name").value.trim(),status:"Disponible",location:document.getElementById("new-item-location").value.trim(),function:document.getElementById("new-item-function").value.trim(),specs:{tipo:document.getElementById("new-item-spec-type").value.trim()||"No especificado",potencia:document.getElementById("new-item-power").value.trim()||"No especificado",velocidad:document.getElementById("new-item-speed").value.trim()||"No especificado",modelo:document.getElementById("new-item-model").value.trim()||"No especificado"}};
}
function completeAddItem(authorizer){
  if(!pendingAddItem)return;
  inventory.push(pendingAddItem); closeModal(); renderAll(); toast(`Artículo ${pendingAddItem.code} agregado. Autorizó: ${authorizer}`); pendingAddItem=null;
}

// REGISTRAR SALIDA
document.getElementById("checkout-code").addEventListener("change",fillCheckout);
document.getElementById("checkout-code").addEventListener("blur",fillCheckout);
function fillCheckout(){
  const code=document.getElementById("checkout-code").value.trim().toUpperCase(); const item=inventory.find(i=>i.code===code);
  document.getElementById("checkout-item").value=item?item.name:""; document.getElementById("checkout-status").value=item?item.status:"";
  if(code&&!item)toast("El código no está registrado.",true);
}
document.getElementById("checkout-password-btn").addEventListener("click",()=>openPasswordAuthorization("checkout"));
document.getElementById("checkout-form").addEventListener("submit",e=>{
  e.preventDefault();
  const item=inventory.find(i=>i.code===document.getElementById("checkout-code").value.trim().toUpperCase());
  if(!item)return toast("Ingrese un código válido.",true);
  if(item.status!=="Disponible")return toast("El artículo no está disponible.",true);
  pendingAuthorization={type:"checkout",item,responsible:document.getElementById("checkout-responsible").value.trim(),location:document.getElementById("checkout-location").value.trim(),purpose:document.getElementById("checkout-purpose").value.trim()};
  requestAutomaticAuthorization("checkout");
});
function completeCheckout(authorizer){
  if(!pendingAuthorization||pendingAuthorization.type!=="checkout")return;
  const p=pendingAuthorization; const dt=nowString();
  movements.unshift({id:`MOV-${String(movements.length+1).padStart(4,"0")}`,code:p.item.code,item:p.item.name,responsible:p.responsible,location:p.location,purpose:p.purpose,authorizer,exit:dt,returnDate:"—",status:"En uso",start:new Date()});
  p.item.status="En uso"; document.getElementById("checkout-form").reset(); document.getElementById("authorization-result").classList.add("hidden"); pendingAuthorization=null; renderAll(); toast("Salida registrada correctamente."); showSection("movimientos");
}

// BAJAS
function renderDecommissionOptions(){
  const select=document.getElementById("decommission-item");
  select.innerHTML=inventory.filter(i=>i.status!=="Baja").map(i=>`<option value="${i.code}">${i.code} — ${i.name} (${i.status})</option>`).join("");
}
function prepareDecommission(code){
  showSection("bajas"); renderDecommissionOptions(); document.getElementById("decommission-item").value=code;
}
document.getElementById("decommission-password-btn").addEventListener("click",()=>openPasswordAuthorization("decommission"));
document.getElementById("decommission-form").addEventListener("submit",e=>{
  e.preventDefault(); const item=inventory.find(i=>i.code===document.getElementById("decommission-item").value);
  if(!item)return; if(item.status==="En uso")return toast("El artículo está en uso y no puede darse de baja.",true);
  pendingDecommission={item,reason:document.getElementById("decommission-reason").value,description:document.getElementById("decommission-description").value.trim(),notes:document.getElementById("decommission-notes").value.trim()};
  requestAutomaticAuthorization("decommission");
});
function completeDecommission(authorizer){
  if(!pendingDecommission)return; const p=pendingDecommission;
  p.item.status="Baja"; p.item.location="Fuera de inventario";
  decommissionHistory.unshift({date:nowString(),code:p.item.code,item:p.item.name,reason:p.reason,description:p.description+(p.notes?` · ${p.notes}`:""),admin:authorizer});
  document.getElementById("decommission-form").reset(); document.getElementById("decommission-auth-result").classList.add("hidden"); pendingDecommission=null; renderAll(); toast("Baja registrada y conservada en el historial.");
}
function renderDecommissionHistory(){
  document.getElementById("decommission-history-body").innerHTML=decommissionHistory.map(h=>`<tr><td>${h.date}</td><td>${h.code}</td><td>${h.item}</td><td>${h.reason}</td><td>${h.description}</td><td>${h.admin}</td></tr>`).join("")||`<tr><td colspan="6">Sin bajas registradas.</td></tr>`;
}

// AUTORIZACIÓN AUTOMÁTICA + CONTRASEÑA
function requestAutomaticAuthorization(target){
  pendingAuthorizationTarget=target;
  document.getElementById("authorization-overlay").classList.remove("hidden");
  setTimeout(()=>{
    document.getElementById("authorization-overlay").classList.add("hidden");
    if(target==="checkout"){
      const el=document.getElementById("authorization-result"); el.classList.remove("hidden"); el.innerHTML='<div class="auth-success">✓ Autorización validada automáticamente por Jefe de Área 1.</div>'; completeCheckout("Jefe de Área 1");
    }else if(target==="add-item") completeAddItem("Administrador");
    else if(target==="decommission"){
      const el=document.getElementById("decommission-auth-result"); el.classList.remove("hidden"); el.innerHTML='<div class="auth-success">✓ Autorización administrativa validada.</div>'; completeDecommission("Administrador");
    }
  },900);
}
let pendingAuthorizationTarget=null;
function openPasswordAuthorization(target){pendingAuthorizationTarget=target;document.getElementById("auth-password").value="";document.getElementById("password-modal").classList.remove("hidden");}
document.getElementById("password-modal-close").addEventListener("click",()=>document.getElementById("password-modal").classList.add("hidden"));
document.getElementById("password-confirm-btn").addEventListener("click",()=>{
  const user=document.getElementById("auth-user").value.trim(),pass=document.getElementById("auth-password").value;
  if(user!=="admin"||pass!=="admin123")return toast("Credenciales incorrectas.",true);
  document.getElementById("password-modal").classList.add("hidden");
  if(pendingAuthorizationTarget==="checkout"){
    const item=inventory.find(i=>i.code===document.getElementById("checkout-code").value.trim().toUpperCase());
    if(!item||item.status!=="Disponible")return toast("No hay una salida válida para autorizar.",true);
    pendingAuthorization={type:"checkout",item,responsible:document.getElementById("checkout-responsible").value.trim(),location:document.getElementById("checkout-location").value.trim(),purpose:document.getElementById("checkout-purpose").value.trim()}; completeCheckout("Jefe autorizado por contraseña");
  }else if(pendingAuthorizationTarget==="add-item"){
    if(!pendingAddItem)pendingAddItem=collectNewItem(); completeAddItem("Administrador por contraseña");
  }else if(pendingAuthorizationTarget==="decommission"){
    if(!pendingDecommission){const item=inventory.find(i=>i.code===document.getElementById("decommission-item").value);pendingDecommission={item,reason:document.getElementById("decommission-reason").value,description:document.getElementById("decommission-description").value.trim(),notes:document.getElementById("decommission-notes").value.trim()};} completeDecommission("Administrador por contraseña");
  }
});

// MOVIMIENTOS Y USO
function renderMovements(){
  const q=document.getElementById("movement-search").value.toLowerCase(); const f=document.getElementById("movement-status-filter").value;
  const list=movements.filter(m=>[m.id,m.code,m.item,m.responsible,m.authorizer].join(" ").toLowerCase().includes(q)&&(f==="todos"||m.status===f));
  document.getElementById("movement-body").innerHTML=list.map(m=>`<tr><td><strong>${m.id}</strong></td><td>${m.code}</td><td>${m.item}</td><td>${m.responsible}</td><td>${m.authorizer}</td><td>${m.exit}</td><td>${m.returnDate}</td><td>${statusTag(m.status)}</td></tr>`).join("");
  document.getElementById("dashboard-movements").innerHTML=movements.slice(0,4).map(m=>`<div><strong>${m.item}</strong>${statusTag(m.status)}<small>${m.responsible} · ${m.exit}</small></div>`).join("");
}
document.getElementById("movement-search").addEventListener("input",renderMovements);document.getElementById("movement-status-filter").addEventListener("change",renderMovements);
function renderInUse(){
  const current=movements.filter(m=>m.status==="En uso");
  document.getElementById("use-body").innerHTML=current.map(m=>`<tr><td>${m.code}</td><td>${m.item}</td><td>${m.responsible}</td><td>${m.location}</td><td>${m.exit}</td><td>${elapsed(m.start)}</td><td>${statusTag(m.status)}</td></tr>`).join("")||`<tr><td colspan="7">No hay herramientas en uso.</td></tr>`;
}
function elapsed(start){const ms=Math.max(0,Date.now()-new Date(start).getTime()),h=Math.floor(ms/3600000),min=Math.floor((ms%3600000)/60000);return `${h} h ${min} min`;}

// ALERTAS
function renderAlerts(){
  document.getElementById("alert-body").innerHTML=alerts.map((a,index)=>`<tr><td>${a.date}</td><td><strong>${a.event}</strong></td><td>${a.item}</td><td>${a.status==="Pendiente"?'<span class="tag red">Pendiente</span>':'<span class="tag green">Resuelta</span>'}</td><td>${a.admin}</td><td>${a.status==="Pendiente"?`<button class="btn btn-danger" onclick="resolveAlert(${index})">Atender</button>`:`<span class="tag green">${a.action}</span>`}</td></tr>`).join("");
  const count=alerts.filter(a=>a.status==="Pendiente").length; document.getElementById("alert-count").textContent=count; document.getElementById("stat-alerts").textContent=count;
}
function resolveAlert(index){openModal("Atender alerta",`<p class="modal-help">Confirme la atención del incidente. Se solicitará autorización por contraseña.</p><button class="btn btn-danger full" onclick="authorizeAlert(${index})">Continuar</button>`)}
function authorizeAlert(index){closeModal(); pendingAuthorizationTarget=`alert:${index}`; openPasswordAuthorization(`alert:${index}`);}
// intercepta alertas en confirmación de contraseña
const originalPasswordHandler=document.getElementById("password-confirm-btn").onclick;
document.getElementById("password-confirm-btn").addEventListener("click",()=>{
  if(!pendingAuthorizationTarget||!pendingAuthorizationTarget.startsWith("alert:"))return;
  const user=document.getElementById("auth-user").value.trim(),pass=document.getElementById("auth-password").value;if(user!=="admin"||pass!=="admin123")return;
  const index=Number(pendingAuthorizationTarget.split(":")[1]);alerts[index].status="Resuelta";alerts[index].admin="Administrador";alerts[index].action="Evento atendido";document.getElementById("password-modal").classList.add("hidden");renderAlerts();toast("Alerta atendida correctamente.");pendingAuthorizationTarget=null;
});

// REPORTES
document.querySelectorAll(".period-btn").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll(".period-btn").forEach(b=>b.classList.remove("active"));btn.classList.add("active");renderReports(btn.dataset.period)}));
function renderReports(period="week"){
  const d=reportData[period],label=period==="week"?"Esta semana":"Este mes";
  document.getElementById("report-outs").textContent=d.outs;document.getElementById("report-returns").textContent=d.returns;document.getElementById("report-incidents").textContent=d.incidents;document.getElementById("report-average").textContent=d.average;
  ["report-outs-label","report-returns-label","report-incidents-label","report-average-label"].forEach(id=>document.getElementById(id).textContent=label);
  document.getElementById("report-table-title").textContent=period==="week"?"Resumen semanal":"Resumen mensual";
  document.getElementById("report-table-body").innerHTML=d.rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td>${r[4]}</td></tr>`).join("");
}

// CONFIGURACIÓN / USUARIOS
document.querySelectorAll(".settings-tab").forEach(tab=>tab.addEventListener("click",()=>{
  document.querySelectorAll(".settings-tab").forEach(t=>t.classList.remove("active"));document.querySelectorAll(".config-tab-content").forEach(c=>c.classList.remove("active"));tab.classList.add("active");document.getElementById(`config-tab-${tab.dataset.configTab}`).classList.add("active");
}));
function renderUsers(){document.getElementById("users-grid").innerHTML=users.map(u=>`<article class="person-card"><div class="avatar">${u.initials}</div><h3>${u.name}</h3><p>${u.role}</p><span class="tag green">${u.status}</span></article>`).join("")}
document.getElementById("new-user-btn").addEventListener("click",()=>openModal("Nuevo usuario",`<form id="new-user-form" class="form-grid"><div class="full-row"><label>Nombre</label><input id="new-user-name" required></div><div><label>Iniciales</label><input id="new-user-initials" maxlength="3" required></div><div><label>Rol</label><select id="new-user-role"><option>Autorizador de salidas</option><option>Administrador del sistema</option><option>Consulta</option></select></div><div class="full-row form-actions"><button class="btn btn-primary">Guardar usuario</button></div></form>`));
document.addEventListener("submit",e=>{if(e.target.id!=="new-user-form")return;e.preventDefault();users.push({initials:document.getElementById("new-user-initials").value.toUpperCase(),name:document.getElementById("new-user-name").value.trim(),role:document.getElementById("new-user-role").value,status:"Activo"});closeModal();renderUsers();toast("Usuario agregado.")});

// MODALES Y UTILIDADES
function openModal(title,content){document.getElementById("modal-title").textContent=title;document.getElementById("modal-content").innerHTML=content;document.getElementById("modal").classList.remove("hidden")}
function closeModal(){document.getElementById("modal").classList.add("hidden")}
document.getElementById("modal-close").addEventListener("click",closeModal);document.getElementById("modal").addEventListener("click",e=>{if(e.target.id==="modal")closeModal()});
function updateStats(){document.getElementById("stat-total").textContent=inventory.filter(i=>i.status!=="Baja").length;document.getElementById("stat-use").textContent=inventory.filter(i=>i.status==="En uso").length;document.getElementById("stat-available").textContent=inventory.filter(i=>i.status==="Disponible").length;}
function updateDate(){document.getElementById("current-date").textContent=new Date().toLocaleDateString("es-MX",{weekday:"long",day:"numeric",month:"long",year:"numeric"})}
function nowString(){return new Date().toLocaleString("es-MX",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",hour12:false})}
function toast(message,error=false){const t=document.createElement("div");t.className=`toast${error?" error":""}`;t.textContent=(error?"⚠ ":"✓ ")+message;document.getElementById("toast-container").appendChild(t);setTimeout(()=>t.remove(),3200)}
function renderAll(){renderInventory();renderMovements();renderInUse();renderAlerts();renderDecommissionHistory();renderReports(document.querySelector(".period-btn.active")?.dataset.period||"week");renderUsers();updateStats();}

updateDate();
