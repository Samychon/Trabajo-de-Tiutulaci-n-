let inventory=[];

let movements=[];
let movementOptions={users:[],locations:[]};

let alerts=[];

let decommissionHistory=[];

let users=[];
let availableRoles=[];
let reportPeriods=[];
let warehouseRequests=[];
let userPreferences={report_default_period:"week",alert_status_filter:"all",alert_type_filter:"all"};

let pendingAuthorization = null;
let pendingDecommission = null;
let pendingCheckoutPayload=null;
let pendingMovementId=null;

const sectionNames = {
  dashboard:"Inicio",inventario:"Inventario",salida:"Registrar salida",uso:"Herramientas en uso",bajas:"Bajas de inventario",movimientos:"Movimientos",alertas:"Historial de alertas",solicitudes:"Solicitudes de almacén",reportes:"Reportes",informacion:"Información",configuracion:"Configuración"
};
const connectedSections=new Set(["dashboard","inventario","salida","uso","bajas","movimientos","alertas","solicitudes","reportes","configuracion"]);

const localApiOrigin=location.port==="5173"?`${location.protocol}//${location.hostname}:8000`:location.origin;
const apiBaseUrl=window.SIGMAT_API_BASE_URL||`${localApiOrigin}/api/v1`;
const apiUrl=new URL(apiBaseUrl,location.origin);
const alertSocketUrl=window.SIGMAT_WS_URL||`${apiUrl.protocol==="https:"?"wss:":"ws:"}//${apiUrl.host}/ws/alerts`;
let accessToken=null;
let refreshToken=null;
let currentRole=null;
let currentUsername=null;
let currentUserId=null;
let sessionExpiresAt=0;
let sessionTimeout=null;
let sessionVersion=0;
let refreshPromise=null;
let alertSocket=null;
let alertReconnectTimer=null;

function endSession(){
  sessionVersion++;
  refreshPromise=null;
  accessToken=null;refreshToken=null;currentRole=null;currentUsername=null;currentUserId=null;sessionExpiresAt=0;clearTimeout(sessionTimeout);
  clearTimeout(alertReconnectTimer);alertReconnectTimer=null;
  if(alertSocket){alertSocket.close();alertSocket=null;}
  document.getElementById("add-item-btn").disabled=true;
  inventory=[];
  movements=[];
  alerts=[];
  decommissionHistory=[];
  users=[];availableRoles=[];
  reportPeriods=[];
  warehouseRequests=[];
  userPreferences={report_default_period:"week",alert_status_filter:"all",alert_type_filter:"all"};
  document.getElementById("alert-status-filter").value="all";
  document.getElementById("alert-type-filter").value="all";
  movementOptions={users:[],locations:[]};
  pendingCheckoutPayload=null;pendingMovementId=null;pendingDecommission=null;
  pendingAuthorizationTarget=null;
  pendingDecommission=null;
  document.getElementById("login-form").reset();
  document.getElementById("inventory-body").replaceChildren();
  document.getElementById("movement-body").replaceChildren();
  document.getElementById("use-body").replaceChildren();
  document.getElementById("alert-body").replaceChildren();
  document.getElementById("decommission-history-body").replaceChildren();
  document.getElementById("warehouse-request-body").replaceChildren();
  document.getElementById("warehouse-request-lines").replaceChildren();
  document.getElementById("alert-count").textContent="0";
  document.getElementById("stat-alerts").textContent="0";
  document.getElementById("alerts-shortcut").disabled=true;
  document.getElementById("dashboard-movements").textContent="Inicia sesión para consultar movimientos.";
  document.getElementById("modal").classList.add("hidden");
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

function applyRoleAccess(){
  const canRegisterExit=["administrador","encargado_inventario"].includes(currentRole);
  document.getElementById("add-item-btn").disabled=!( ["administrador","encargado_inventario"].includes(currentRole));
  document.querySelector('[data-section="salida"]').disabled=!canRegisterExit;
  document.querySelectorAll('[data-go="salida"]').forEach(button=>button.disabled=!canRegisterExit);
  document.querySelector('[data-section="bajas"]').disabled=currentRole!=="administrador";
  document.querySelector('[data-section="configuracion"]').disabled=currentRole!=="administrador";
  document.querySelector('[data-section="reportes"]').disabled=!( ["administrador","jefe_area","encargado_inventario"].includes(currentRole));
  document.getElementById("warehouse-request-compose").classList.toggle("hidden",!( ["administrador","encargado_inventario"].includes(currentRole)));
  document.getElementById("alerts-shortcut").disabled=false;
}

function setSessionTokens(tokens){
  accessToken=tokens.access_token;
  refreshToken=tokens.refresh_token;
  const encodedClaims=accessToken.split(".")[1].replace(/-/g,"+").replace(/_/g,"/");
  const claims=JSON.parse(atob(encodedClaims.padEnd(Math.ceil(encodedClaims.length/4)*4,"=")));
  sessionExpiresAt=claims.exp*1000;
  currentRole=claims.role;
  currentUsername=claims.sub;
  clearTimeout(sessionTimeout);
  sessionTimeout=setTimeout(()=>{refreshSession().catch(()=>{});},Math.max(0,sessionExpiresAt-Date.now()-60000));
  applyRoleAccess();
  if(alertSocket)alertSocket.close();
}

async function refreshSession(){
  if(refreshPromise)return refreshPromise;
  if(!refreshToken){endSession();return false;}
  const version=sessionVersion;
  const currentRefresh=refreshToken;
  const pending=(async()=>{
    try{
      const response=await fetch(`${apiBaseUrl}/auth/refresh`,{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({refresh_token:currentRefresh})
      });
      if(!response.ok){if(version===sessionVersion)endSession();return false;}
      const tokens=await response.json();
      if(version!==sessionVersion)return false;
      setSessionTokens(tokens);
      return true;
    }catch{
      if(version===sessionVersion)endSession();
      return false;
    }
  })();
  refreshPromise=pending;
  try{return await pending;}
  finally{if(refreshPromise===pending)refreshPromise=null;}
}

async function apiFetch(url,options={}){
  const requestSessionVersion=sessionVersion;
  const requestAccessToken=accessToken;
  const send=()=>{
    const headers=new Headers(options.headers||{});
    if(accessToken)headers.set("Authorization",`Bearer ${accessToken}`);
    return fetch(url,{...options,headers});
  };
  let response=await send();
  if(requestSessionVersion!==sessionVersion)throw new Error("Session changed");
  if(response.status!==401)return response;
  if(accessToken&&accessToken!==requestAccessToken){
    response=await send();
    if(requestSessionVersion!==sessionVersion)throw new Error("Session changed");
    if(response.status===401)endSession();
    return response;
  }
  if(!refreshToken||!(await refreshSession())){
    if(requestSessionVersion===sessionVersion&&accessToken)endSession();
    return response;
  }
  if(requestSessionVersion!==sessionVersion)throw new Error("Session changed");
  response=await send();
  if(requestSessionVersion!==sessionVersion)throw new Error("Session changed");
  if(response.status===401)endSession();
  return response;
}

async function loadInventory(token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/items`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Inventory unavailable");
  const items=await response.json();
  const statuses={disponible:"Disponible",en_uso:"En uso",devuelta:"Devuelta",baja:"Baja"};
  inventory=items.map(item=>({
    id:item.id,code:item.code,name:item.name,category_id:item.category_id,category_name:item.category_name,type:item.category_name||(item.type==="herramienta"?"Herramienta":"Material"),
    status:statuses[item.status]||item.status,location:item.location_name||"No registrada",function:item.description||"No registrada",
    specs:item.specs||{tipo:"",potencia:"",velocidad:"",modelo:""}
  }));
}

async function loadMovementOptions(token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/movements/options`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Movement options unavailable");
  movementOptions=await response.json();
  renderCheckoutOptions();
}

async function loadMovements(token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/movements`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Movements unavailable");
  const entries=await response.json();
  const statuses={pending_authorization:"Pendiente de autorización",open:"En uso",closed:"Devuelto"};
  movements=entries.map(movement=>({
    apiId:movement.id,itemId:movement.item_id,id:`MOV-${String(movement.id).padStart(4,"0")}`,code:movement.item_code,item:movement.item_name,
    responsible:movement.responsible_name,authorizer:movement.authorizer_name||"Pendiente",
    location:movement.location_name,purpose:movement.purpose,
    exit:formatDateTime(movement.checkout_at),returnDate:formatDateTime(movement.checkin_at),
    status:statuses[movement.status]||movement.status,start:movement.checkout_at
  }));
}

async function loadAlerts(token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/alerts`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Alerts unavailable");
  const entries=await response.json();
  const types={salida_no_autorizada:"Salida no autorizada",falla_dispositivo:"Falla de dispositivo",manipulacion_sensor:"Manipulación de sensor"};
  const statuses={activa:"Pendiente",resuelta:"Resuelta"};
  alerts=entries.map(alert=>({
    id:alert.id,date:formatDateTime(alert.triggered_at),event:types[alert.type]||alert.type,
    item:alert.item_name||alert.device_uid||"Evento de sistema",
    status:statuses[alert.status]||alert.status,admin:alert.resolved_by_name||"—",
    notes:alert.resolution_notes||"",resolvedAt:formatDateTime(alert.resolved_at),type:alert.type,rawStatus:alert.status
  }));
}

async function loadDecommissions(token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/items/decommissions`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Decommission history unavailable");
  const entries=await response.json();
  decommissionHistory=entries.map(entry=>({
    date:formatDateTime(entry.decommissioned_at),code:entry.item_code,item:entry.item_name,
    reason:entry.reason,description:entry.description+(entry.notes?` · ${entry.notes}`:""),admin:entry.administrator_name
  }));
}

async function loadUsersAndRoles(token=accessToken){
  const [userResponse,roleResponse]=await Promise.all([
  apiFetch(`${apiBaseUrl}/users`),apiFetch(`${apiBaseUrl}/users/roles`)
  ]);
  if(userResponse.status===401||roleResponse.status===401){endSession();throw new Error("Session expired");}
  if(userResponse.status===403||roleResponse.status===403)throw new Error("Administrator role required");
  if(!userResponse.ok||!roleResponse.ok)throw new Error("User administration unavailable");
  users=await userResponse.json();availableRoles=await roleResponse.json();
}

async function loadReports(period="week",token=accessToken){
  const response=await apiFetch(`${apiBaseUrl}/reports/summary?period=${encodeURIComponent(period)}`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Report summary unavailable");
  const summary=await response.json();
  reportPeriods=summary.periods;
  renderReports();
}

function connectAlertSocket(){
  if(!accessToken||alertSocket)return;
  const socket=new WebSocket(alertSocketUrl);
  alertSocket=socket;
  socket.addEventListener("open",()=>{
    if(accessToken&&alertSocket===socket)socket.send(accessToken);
  });
  socket.addEventListener("message",event=>{
    try{
      const message=JSON.parse(event.data);
      if(message.type==="alert")loadAlerts().then(renderAlerts).catch(()=>{});
    }catch{}
  });
  socket.addEventListener("close",()=>{
    if(alertSocket===socket)alertSocket=null;
    if(accessToken)alertReconnectTimer=setTimeout(connectAlertSocket,3000);
  });
}

function formatDateTime(value){
  return value?new Date(value).toLocaleString("es-MX",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",hour12:false}):"—";
}

async function loadWarehouseRequests(){
  const response=await apiFetch(`${apiBaseUrl}/requests`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("Requests unavailable");
  warehouseRequests=await response.json();
  renderWarehouseRequests();
}

function addWarehouseRequestLine(){
  const container=document.getElementById("warehouse-request-lines");
  const line=document.createElement("div");
  line.className="request-item-row form-grid";
  const categories=[...new Map(inventory.filter(item=>item.category_id!=null).map(item=>[item.category_id,item.category_name])).entries()]
    .sort((first,second)=>String(first[1]).localeCompare(String(second[1]),"es"));
  line.innerHTML=`<div><label>Categoría</label><select name="category_id"><option value="">Sin categoría</option>${categories.map(([id,name])=>`<option value="${id}">${escapeHtml(name)}</option>`).join("")}</select></div><div><label>Descripción</label><input name="description" required maxlength="300" autocomplete="off"></div><div><label>Cantidad</label><input name="quantity" type="number" min="1" max="10000" step="1" value="1" required></div><button type="button" class="action-btn danger-action" data-remove-request-line aria-label="Quitar línea">Quitar</button>`;
  container.appendChild(line);
  line.querySelector("[data-remove-request-line]").addEventListener("click",()=>{
    if(container.children.length>1)line.remove();
  });
  updateRequestLineButtons();
}

function updateRequestLineButtons(){
  const lines=document.querySelectorAll("#warehouse-request-lines .request-item-row");
  lines.forEach(line=>line.querySelector("[data-remove-request-line]").disabled=lines.length===1);
}

function renderWarehouseRequests(){
  const body=document.getElementById("warehouse-request-body");
  body.innerHTML=warehouseRequests.map(request=>{
    const statusLabels={pendiente:"Pendiente",aprobada:"Aprobada",rechazada:"Rechazada",enviada:"Enviada"};
    const itemList=request.items.map(item=>`<li>${escapeHtml(item.description)}${item.category_name?` · ${escapeHtml(item.category_name)}`:""} × ${item.quantity}</li>`).join("");
    const decision=["aprobada","enviada"].includes(request.status)?`Aprobó ${escapeHtml(request.approver_name||"Administrador")}`:request.status==="rechazada"?`Rechazó ${escapeHtml(request.rejecter_name||"Administrador")}<br><small>${escapeHtml(request.rejection_reason||"")}</small>`:"Sin decisión";
    const actions=currentRole==="administrador"&&request.status==="pendiente"?`<div class="action-group"><button class="action-btn" data-request-action="approve" data-request-id="${request.id}">Aprobar</button><button class="action-btn danger-action" data-request-action="reject" data-request-id="${request.id}">Rechazar</button></div>`:currentRole==="administrador"&&request.status==="aprobada"?`<button class="action-btn" data-request-action="send" data-request-id="${request.id}">Marcar enviada</button>`:"—";
    return `<tr><td>${formatDateTime(request.created_at)}</td><td>${escapeHtml(request.requester_name)}</td><td><ul class="request-item-list">${itemList}</ul></td><td>${statusTag(statusLabels[request.status]||request.status)}</td><td>${decision}</td><td>${actions}</td></tr>`;
  }).join("")||`<tr><td colspan="6">No hay solicitudes registradas.</td></tr>`;
}

async function submitWarehouseDecision(requestId,action,reason=""){
  const payload=action==="reject"?{reason}:undefined;
  const response=await apiFetch(`${apiBaseUrl}/requests/${requestId}/${action}`,{
    method:"POST",headers:payload?{"Content-Type":"application/json"}:{},body:payload?JSON.stringify(payload):undefined
  });
  if(response.status===401){endSession();return false;}
  if(response.status===403){toast("Solo un administrador puede procesar solicitudes.",true);return false;}
  if(response.status===404){toast("La solicitud ya no está disponible.",true);return false;}
  if(response.status===409){toast("La solicitud ya fue procesada.",true);await loadWarehouseRequests();return false;}
  if(!response.ok){toast("No se pudo procesar la solicitud.",true);return false;}
  await loadWarehouseRequests();
  toast(action==="approve"?"Solicitud aprobada y auditada.":action==="reject"?"Solicitud rechazada y auditada.":"Solicitud marcada como enviada y auditada.");
  return true;
}

document.getElementById("add-request-line").addEventListener("click",addWarehouseRequestLine);
document.getElementById("warehouse-request-form").addEventListener("submit",async event=>{
  event.preventDefault();
  if(!( ["administrador","encargado_inventario"].includes(currentRole)))return;
  const form=event.currentTarget;
  const submit=form.querySelector('button[type="submit"]');
  const items=[...form.querySelectorAll(".request-item-row")].map(line=>{
    const categoryId=line.querySelector('[name="category_id"]').value;
    return {category_id:categoryId?Number(categoryId):null,description:line.querySelector('[name="description"]').value.trim(),quantity:Number(line.querySelector('[name="quantity"]').value)};
  });
  submit.disabled=true;
  try{
    const response=await apiFetch(`${apiBaseUrl}/requests`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items})});
    if(response.status===401){endSession();return;}
    if(response.status===403){toast("Su rol no puede crear solicitudes.",true);return;}
    if(response.status===400||response.status===422){toast("Revise las categorías, descripciones y cantidades.",true);return;}
    if(!response.ok){toast("No se pudo registrar la solicitud.",true);return;}
    form.reset();document.getElementById("warehouse-request-lines").replaceChildren();addWarehouseRequestLine();
    await loadWarehouseRequests();toast("Solicitud registrada y auditada.");
  }catch(error){if(error.message!=="Session expired")toast("No se pudo conectar con el servidor.",true);}
  finally{submit.disabled=false;}
});
document.getElementById("warehouse-request-body").addEventListener("click",event=>{
  const button=event.target.closest("[data-request-action]");
  if(!button||currentRole!=="administrador")return;
  const requestId=Number(button.dataset.requestId);
  if(button.dataset.requestAction==="approve"){
    openModal("Aprobar solicitud",`<form id="approve-request-form" class="form-grid"><p class="modal-help full-row">La decisión quedará registrada en la auditoría.</p><div class="full-row form-actions"><button type="submit" class="btn btn-primary">Confirmar aprobación</button></div></form>`);
    document.getElementById("approve-request-form").addEventListener("submit",async submitEvent=>{
      submitEvent.preventDefault();const submit=submitEvent.currentTarget.querySelector('button[type="submit"]');submit.disabled=true;
      try{if(await submitWarehouseDecision(requestId,"approve"))closeModal();}catch{toast("No se pudo conectar con el servidor.",true);}finally{submit.disabled=false;}
    });
    return;
  }
  if(button.dataset.requestAction==="send"){
    openModal("Marcar solicitud como enviada",`<form id="send-request-form" class="form-grid"><p class="modal-help full-row">Confirme que el pedido aprobado fue enviado al área solicitante.</p><div class="full-row form-actions"><button type="submit" class="btn btn-primary">Confirmar envío</button></div></form>`);
    document.getElementById("send-request-form").addEventListener("submit",async submitEvent=>{
      submitEvent.preventDefault();const submit=submitEvent.currentTarget.querySelector('button[type="submit"]');submit.disabled=true;
      try{if(await submitWarehouseDecision(requestId,"send"))closeModal();}catch{toast("No se pudo conectar con el servidor.",true);}finally{submit.disabled=false;}
    });
    return;
  }
  openModal("Rechazar solicitud",`<form id="reject-request-form" class="form-grid"><div class="full-row"><label for="request-rejection-reason">Motivo del rechazo</label><textarea id="request-rejection-reason" required maxlength="500" rows="4"></textarea></div><div class="full-row form-actions"><button type="submit" class="btn btn-danger">Confirmar rechazo</button></div></form>`);
  document.getElementById("reject-request-form").addEventListener("submit",async submitEvent=>{
    submitEvent.preventDefault();const submit=submitEvent.currentTarget.querySelector('button[type="submit"]');submit.disabled=true;
    try{if(await submitWarehouseDecision(requestId,"reject",document.getElementById("request-rejection-reason").value.trim()))closeModal();}catch{toast("No se pudo conectar con el servidor.",true);}finally{submit.disabled=false;}
  });
});

function applyUserPreferences(){
  document.getElementById("alert-status-filter").value=userPreferences.alert_status_filter;
  document.getElementById("alert-type-filter").value=userPreferences.alert_type_filter;
  document.querySelectorAll(".period-btn").forEach(button=>{
    button.classList.toggle("active",button.dataset.period===userPreferences.report_default_period);
  });
}

async function loadUserPreferences(){
  const response=await apiFetch(`${apiBaseUrl}/users/me/preferences`);
  if(response.status===401){endSession();throw new Error("Session expired");}
  if(!response.ok)throw new Error("User preferences unavailable");
  userPreferences=await response.json();
  applyUserPreferences();
}

document.getElementById("user-preferences-btn").addEventListener("click",()=>{
  openModal("Preferencias personales",`<form id="user-preferences-form" class="form-grid"><div class="full-row"><label for="preference-report-period">Periodo predeterminado de reportes</label><select id="preference-report-period"><option value="week">Semanal</option><option value="month">Mensual</option></select></div><div class="full-row"><label for="preference-alert-status">Filtro inicial de alertas por estado</label><select id="preference-alert-status"><option value="all">Todos</option><option value="activa">Pendientes</option><option value="resuelta">Resueltas</option></select></div><div class="full-row"><label for="preference-alert-type">Filtro inicial de alertas por tipo</label><select id="preference-alert-type"><option value="all">Todos los tipos</option><option value="salida_no_autorizada">Salida no autorizada</option><option value="falla_dispositivo">Falla de dispositivo</option><option value="manipulacion_sensor">Manipulación de sensor</option></select></div><div class="full-row form-actions"><button type="submit" class="btn btn-primary">Guardar preferencias</button></div></form>`);
  document.getElementById("preference-report-period").value=userPreferences.report_default_period;
  document.getElementById("preference-alert-status").value=userPreferences.alert_status_filter;
  document.getElementById("preference-alert-type").value=userPreferences.alert_type_filter;
  document.getElementById("user-preferences-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    const payload={
      report_default_period:document.getElementById("preference-report-period").value,
      alert_status_filter:document.getElementById("preference-alert-status").value,
      alert_type_filter:document.getElementById("preference-alert-type").value,
    };
    try{
      const response=await apiFetch(`${apiBaseUrl}/users/me/preferences`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      if(response.status===401){endSession();return;}
      if(!response.ok){toast("No se pudieron guardar las preferencias.",true);return;}
      userPreferences=await response.json();applyUserPreferences();renderAlerts();closeModal();
      if(document.getElementById("section-reportes").classList.contains("active-section")){
        await loadReports(userPreferences.report_default_period).catch(()=>{});
      }
      toast("Preferencias guardadas en tu cuenta.");
    }catch(error){if(error.message!=="Session expired")toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
});

document.getElementById("alert-status-filter").addEventListener("change",renderAlerts);
document.getElementById("alert-type-filter").addEventListener("change",renderAlerts);

// LOGIN
document.getElementById("login-form").addEventListener("submit",async e=>{
  e.preventDefault();
  const user=document.getElementById("login-user").value.trim();
  const passwordInput=document.getElementById("login-password");
  const submit=e.target.querySelector('button[type="submit"]');
  const error=document.getElementById("login-error");
  submit.disabled=true;error.classList.add("hidden");
  try{
    const response=await fetch(`${apiBaseUrl}/auth/token`,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({username:user,password:passwordInput.value})});
    if(!response.ok)throw new Error("Login failed");
    const tokens=await response.json();
    sessionVersion++;
    setSessionTokens(tokens);
    const profile=await apiFetch(`${apiBaseUrl}/users/me`);
    if(!profile.ok)throw new Error("Session validation failed");
    await loadInventory();
    await loadMovementOptions();
    await loadMovements();
    await loadAlerts();
    await loadUserPreferences();
    await loadWarehouseRequests();
    if(currentRole==="administrador")await loadDecommissions();
    if(currentRole==="administrador")await loadUsersAndRoles();
    const profileData=await profile.json();
    currentUserId=profileData.id;
    document.querySelector(".admin-user strong").textContent=profileData.full_name;
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    connectAlertSocket();
    renderAll(); updateDate();
  }catch{
    endSession();error.classList.remove("hidden");
  }finally{
    passwordInput.value="";submit.disabled=false;
  }
});

document.getElementById("logout-btn").addEventListener("click",endSession);
document.addEventListener("visibilitychange",()=>{
  if(!document.hidden&&accessToken&&Date.now()>=sessionExpiresAt-60000)refreshSession();
});

// NAVEGACIÓN
document.querySelectorAll(".nav-item").forEach(btn=>{
  if(!connectedSections.has(btn.dataset.section)){btn.disabled=true;btn.title="Pendiente de integración";}
});
document.querySelector('[data-section="salida"]').disabled=true;
document.querySelector('[data-section="bajas"]').disabled=true;
document.querySelector('[data-section="configuracion"]').disabled=true;
document.querySelector('[data-section="reportes"]').disabled=true;
document.querySelectorAll("[data-go]").forEach(btn=>{
  if(!connectedSections.has(btn.dataset.go)){btn.disabled=true;btn.title="Pendiente de integración";}
});
document.getElementById("alerts-shortcut").disabled=true;
document.getElementById("alerts-shortcut").title="Pendiente de integración";
document.querySelectorAll(".nav-item").forEach(btn=>btn.addEventListener("click",()=>showSection(btn.dataset.section)));
document.querySelectorAll("[data-go]").forEach(btn=>btn.addEventListener("click",()=>showSection(btn.dataset.go)));
document.getElementById("brand-home").addEventListener("click",()=>showSection("dashboard"));
document.getElementById("alerts-shortcut").addEventListener("click",()=>showSection("alertas"));

function showSection(section){
  if(!connectedSections.has(section)||!accessToken)return;
  if(section==="salida"&&!( ["administrador","encargado_inventario"].includes(currentRole)))return;
  if(section==="bajas"&&currentRole!=="administrador")return;
  if(section==="configuracion"&&currentRole!=="administrador")return;
  if(section==="reportes"&&!(["administrador","jefe_area","encargado_inventario"].includes(currentRole)))return;
  if(section==="configuracion")loadUsersAndRoles().then(renderUsers).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudo cargar la administración de usuarios.",true);
  });
  if(section==="inventario")loadInventory().then(()=>{renderInventory();updateStats();}).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudo actualizar el inventario.",true);
  });
  if(section==="salida")Promise.all([loadInventory(),loadMovementOptions()]).then(()=>renderInventory()).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudieron cargar las opciones de salida.",true);
  });
  if(section==="movimientos"||section==="uso")loadMovements().then(()=>{renderMovements();renderInUse();}).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudo actualizar el historial de movimientos.",true);
  });
  if(section==="alertas")loadAlerts().then(renderAlerts).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudieron cargar las alertas.",true);
  });
  if(section==="solicitudes")Promise.all([loadInventory(),loadWarehouseRequests()]).then(()=>{
    renderWarehouseRequests();
    if(["administrador","encargado_inventario"].includes(currentRole)&&!document.querySelector("#warehouse-request-lines .request-item-row"))addWarehouseRequestLine();
  }).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudieron cargar las solicitudes.",true);
  });
  if(section==="bajas")Promise.all([loadInventory(),loadMovements(),loadDecommissions()]).then(()=>{
    renderInventory();renderDecommissionOptions();renderDecommissionHistory();updateStats();
  }).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudo cargar el historial de bajas.",true);
  });
  if(section==="reportes")Promise.all([
    loadInventory(),loadMovementOptions(),loadReports(document.querySelector(".period-btn.active")?.dataset.period||"week")
  ]).then(renderMovementReportOptions).catch(error=>{
    if(error.message!=="Session expired")toast("No se pudieron cargar las opciones de reportes.",true);
  });
  document.querySelectorAll(".content-section").forEach(s=>s.classList.remove("active-section"));
  document.getElementById(`section-${section}`).classList.add("active-section");
  document.querySelectorAll(".nav-item").forEach(n=>n.classList.toggle("active",n.dataset.section===section));
  document.getElementById("page-title").textContent=sectionNames[section];
  window.scrollTo({top:0,behavior:"smooth"});
}

// INVENTARIO Y FILTROS
function escapeHtml(value){
  return String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]);
}
function statusTag(status){
  const cls=status==="Disponible"||status==="Devuelta"||status==="Devuelto"||status==="Aprobada"||status==="Enviada"?"green":status==="En uso"||status==="Pendiente"?"orange":status==="Baja"||status==="Rechazada"?"red":"gray";
  return `<span class="tag ${cls}">${escapeHtml(status)}</span>`;
}

function renderInventory(list=inventory){
  const body=document.getElementById("inventory-body");
  body.innerHTML=list.map(item=>`<tr>
    <td><strong>${escapeHtml(item.code)}</strong></td><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.type)}</td><td>${statusTag(item.status)}</td><td>${escapeHtml(item.location)}</td><td>${escapeHtml(item.function)}</td>
    <td><button class="action-btn" data-item-code="${escapeHtml(item.code)}">Ver ficha</button></td>
  </tr>`).join("") || `<tr><td colspan="7">No hay artículos que coincidan con los filtros.</td></tr>`;
  refreshLocationFilter();
  refreshTypeFilter();
}
document.getElementById("inventory-body").addEventListener("click",event=>{
  const button=event.target.closest("[data-item-code]");
  if(button)showItem(button.dataset.itemCode);
});

function refreshLocationFilter(){
  const select=document.getElementById("inventory-location-filter");
  const current=select.value;
  const locations=[...new Set(inventory.map(i=>i.location).filter(Boolean))].sort();
  select.innerHTML='<option value="todos">Todas</option>'+locations.map(l=>`<option>${escapeHtml(l)}</option>`).join("");
  if([...select.options].some(o=>o.value===current))select.value=current;
}

function refreshTypeFilter(){
  const select=document.getElementById("inventory-type-filter");
  const current=select.value;
  const types=[...new Set(inventory.map(item=>item.type))].sort();
  select.innerHTML='<option value="todos">Todos</option>'+types.map(type=>`<option>${escapeHtml(type)}</option>`).join("");
  if([...select.options].some(option=>option.value===current))select.value=current;
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
    <div><span>Artículo</span><strong>${escapeHtml(item.name)}</strong></div><div><span>Tipo</span><strong>${escapeHtml(item.type)}</strong></div><div><span>Estado</span><strong>${escapeHtml(item.status)}</strong></div><div><span>Ubicación</span><strong>${escapeHtml(item.location)}</strong></div><div><span>Función</span><strong>${escapeHtml(item.function)}</strong></div><div><span>Tipo / descripción</span><strong>${escapeHtml(item.specs.tipo||"No registrado")}</strong></div><div><span>Potencia / capacidad</span><strong>${escapeHtml(item.specs.potencia||"No registrado")}</strong></div><div><span>Velocidad / rango</span><strong>${escapeHtml(item.specs.velocidad||"No registrado")}</strong></div><div><span>Modelo</span><strong>${escapeHtml(item.specs.modelo||"No registrado")}</strong></div>
  </div>`);
}

// ALTA DE ARTÍCULO CON CÓDIGO AUTOMÁTICO
document.getElementById("add-item-btn").addEventListener("click",()=>{
  openModal("Agregar artículo",`<form id="add-item-form" class="form-grid">
    <div><label>Tipo de artículo</label><select id="new-item-type" required><option>Motor</option><option>Bomba</option><option>Taladro</option><option>Herramienta manual</option><option>Instrumento</option><option>Equipo</option><option>Material</option><option>Otro</option></select></div>
    <div><label>Código asignado</label><input value="Al guardar" readonly></div>
    <div class="full-row"><label>Nombre</label><input id="new-item-name" required placeholder="Nombre del artículo"></div>
    <div><label>Ubicación</label><input id="new-item-location" required value="Almacén"></div><div><label>Modelo</label><input id="new-item-model" placeholder="Opcional"></div>
    <div><label>Tipo / descripción</label><input id="new-item-spec-type" placeholder="Descripción técnica"></div><div><label>Potencia / capacidad</label><input id="new-item-power" placeholder="Si aplica"></div>
    <div><label>Velocidad / rango</label><input id="new-item-speed" placeholder="Si aplica"></div><div><label>Estado inicial</label><input value="Disponible" readonly></div>
    <div class="full-row"><label>Función</label><textarea id="new-item-function" required placeholder="¿Para qué se utiliza?"></textarea></div>
    <div class="full-row form-actions"><button class="btn btn-primary" type="submit">Guardar artículo</button></div>
  </form>`);
  document.getElementById("add-item-form").addEventListener("submit",async e=>{
    e.preventDefault();
    const button=e.target.querySelector('button[type="submit"]');
    button.disabled=true;
    try{
      const response=await apiFetch(`${apiBaseUrl}/items`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(collectNewItem())
      });
      if(response.status===401){endSession();return;}
      if(response.status===403)return toast("No tiene permiso para agregar artículos.",true);
      if(response.status===409)return toast("El código, categoría o ubicación ya existen. Intente de nuevo.",true);
      if(!response.ok)return toast("No se pudo registrar el artículo. Revise los datos.",true);
      const saved=await response.json();
      closeModal();
      try{await loadInventory();renderAll();}
      catch{toast("Artículo guardado, pero no se pudo actualizar la lista.",true);return;}
      toast(`Artículo ${saved.code} agregado.`);
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
});

function collectNewItem(){
  const category=document.getElementById("new-item-type").value;
  return {type:category==="Material"?"material":"herramienta",category_name:category,name:document.getElementById("new-item-name").value.trim(),location_name:document.getElementById("new-item-location").value.trim(),description:document.getElementById("new-item-function").value.trim(),specs:{tipo:document.getElementById("new-item-spec-type").value.trim(),potencia:document.getElementById("new-item-power").value.trim(),velocidad:document.getElementById("new-item-speed").value.trim(),modelo:document.getElementById("new-item-model").value.trim()}};
}

// REGISTRAR SALIDA
function renderCheckoutOptions(){
  const itemSelect=document.getElementById("checkout-item-id");
  const selectedItem=itemSelect.value;
  itemSelect.innerHTML='<option value="">Selecciona un artículo...</option>'+inventory.filter(item=>["Disponible","Devuelta"].includes(item.status)).map(item=>`<option value="${item.id}">${escapeHtml(item.code)} — ${escapeHtml(item.name)} (${escapeHtml(item.status)})</option>`).join("");
  if([...itemSelect.options].some(option=>option.value===selectedItem))itemSelect.value=selectedItem;
  const responsibleSelect=document.getElementById("checkout-responsible-id");
  responsibleSelect.innerHTML='<option value="">Selecciona un usuario...</option>'+movementOptions.users.map(user=>`<option value="${user.id}">${escapeHtml(user.name)}</option>`).join("");
  const locationSelect=document.getElementById("checkout-location-id");
  locationSelect.innerHTML='<option value="">Selecciona una ubicación...</option>'+movementOptions.locations.map(location=>`<option value="${location.id}">${escapeHtml(location.name)}</option>`).join("");
}
document.getElementById("checkout-item-id").addEventListener("change",fillCheckout);
function fillCheckout(){
  const item=inventory.find(candidate=>String(candidate.id)===document.getElementById("checkout-item-id").value);
  document.getElementById("checkout-item").value=item?item.name:""; document.getElementById("checkout-status").value=item?item.status:"";
  if(!item)document.getElementById("checkout-status").value="";
}
document.getElementById("checkout-form").addEventListener("submit",e=>{
  e.preventDefault();
  const item=inventory.find(i=>String(i.id)===document.getElementById("checkout-item-id").value);
  if(!item)return toast("Ingrese un código válido.",true);
  if(!["Disponible","Devuelta"].includes(item.status))return toast("El artículo no está disponible.",true);
  pendingCheckoutPayload={item_id:item.id,responsible_user_id:Number(document.getElementById("checkout-responsible-id").value),location_id:Number(document.getElementById("checkout-location-id").value),purpose:document.getElementById("checkout-purpose").value.trim()};
  pendingMovementId=null;
  openPasswordAuthorization("checkout");
});

// BAJAS
function renderDecommissionOptions(){
  const select=document.getElementById("decommission-item");
  const selected=select.value;
  const activeItemIds=new Set(movements.filter(movement=>["Pendiente de autorización","En uso"].includes(movement.status)).map(movement=>movement.itemId));
  select.innerHTML='<option value="">Seleccione un artículo...</option>'+inventory.filter(item=>item.status!=="Baja"&&!activeItemIds.has(item.id)).map(item=>`<option value="${item.id}">${escapeHtml(item.code)} — ${escapeHtml(item.name)} (${escapeHtml(item.status)})</option>`).join("");
  if([...select.options].some(option=>option.value===selected))select.value=selected;
}
function prepareDecommission(code){
  showSection("bajas"); renderDecommissionOptions();
  const item=inventory.find(entry=>entry.code===code);
  if(item)document.getElementById("decommission-item").value=String(item.id);
}
document.getElementById("decommission-form").addEventListener("submit",e=>{
  e.preventDefault();
  const item=inventory.find(entry=>String(entry.id)===document.getElementById("decommission-item").value);
  if(!item)return toast("Seleccione un artículo válido.",true);
  if(item.status==="Baja")return toast("El artículo ya está dado de baja.",true);
  if(movements.some(movement=>movement.itemId===item.id&&["En uso","Pendiente de autorización"].includes(movement.status)))return toast("El artículo tiene un movimiento pendiente o abierto.",true);
  pendingDecommission={itemId:item.id,code:item.code,name:item.name,reason:document.getElementById("decommission-reason").value,description:document.getElementById("decommission-description").value.trim(),notes:document.getElementById("decommission-notes").value.trim()};
  openModal("Confirmar baja",`<form id="decommission-confirm-form" class="form-grid"><p class="modal-help full-row">Se conservarán el artículo y sus movimientos anteriores. Confirma la baja con la contraseña de la sesión administrativa.</p><div class="full-row"><strong>${escapeHtml(item.code)} — ${escapeHtml(item.name)}</strong></div><div class="full-row"><label for="decommission-confirm-password">Contraseña del administrador</label><input id="decommission-confirm-password" type="password" required autocomplete="current-password"></div><div class="full-row form-actions"><button class="btn btn-danger" type="submit">Confirmar baja</button></div></form>`);
  document.getElementById("decommission-confirm-form").addEventListener("submit",submitDecommission);
});
async function submitDecommission(event){
  event.preventDefault();
  if(!pendingDecommission||currentRole!=="administrador")return;
  const button=event.target.querySelector('button[type="submit"]');button.disabled=true;
  try{
    const response=await apiFetch(`${apiBaseUrl}/items/${pendingDecommission.itemId}/decommission`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({reason:pendingDecommission.reason,description:pendingDecommission.description,notes:pendingDecommission.notes||null,confirmation_password:document.getElementById("decommission-confirm-password").value})
    });
    if(response.status===401){endSession();return;}
    if(response.status===403){toast("Contraseña incorrecta o sesión sin permisos administrativos.",true);return;}
    if(response.status===409){toast("No se puede dar de baja: ya existe una baja o hay movimientos pendientes/abiertos.",true);return;}
    if(!response.ok){toast("No se pudo registrar la baja. Revise los datos.",true);return;}
    closeModal();document.getElementById("decommission-form").reset();pendingDecommission=null;
    await Promise.all([loadInventory(),loadMovements(),loadDecommissions()]);
    renderAll();renderDecommissionOptions();renderDecommissionHistory();
    toast("Baja registrada y auditada.");
  }catch{toast("No se pudo conectar con el servidor.",true);}
  finally{button.disabled=false;}
}
function renderDecommissionHistory(){
  document.getElementById("decommission-history-body").innerHTML=decommissionHistory.map(h=>`<tr><td>${escapeHtml(h.date)}</td><td>${escapeHtml(h.code)}</td><td>${escapeHtml(h.item)}</td><td>${escapeHtml(h.reason)}</td><td>${escapeHtml(h.description)}</td><td>${escapeHtml(h.admin)}</td></tr>`).join("")||`<tr><td colspan="6">Sin bajas registradas.</td></tr>`;
}

// Los formularios pendientes no deben simular autorizaciones en el navegador.
function requestAutomaticAuthorization(){toast("Operación pendiente de integración.",true);}
let pendingAuthorizationTarget=null;
function openPasswordAuthorization(target){
  if(target!=="checkout"&&target!=="pending-movement"){toast("Operación pendiente de integración.",true);return;}
  if(target==="checkout"&&!pendingCheckoutPayload)return toast("Complete primero los datos de la salida.",true);
  if(target==="pending-movement"&&!pendingMovementId)return toast("No hay un movimiento pendiente seleccionado.",true);
  pendingAuthorizationTarget=target;
  document.getElementById("auth-user").value="";
  document.getElementById("auth-password").value="";
  document.getElementById("auth-modal-help").textContent="Un jefe de área debe ingresar sus credenciales para autorizar esta salida.";
  document.getElementById("password-modal-close").disabled=Boolean(pendingMovementId);
  document.getElementById("password-modal").classList.remove("hidden");
}
document.getElementById("password-modal-close").addEventListener("click",()=>{
  if(pendingMovementId)return;
  pendingCheckoutPayload=null;pendingAuthorizationTarget=null;
  document.getElementById("password-modal").classList.add("hidden");
});
document.getElementById("password-confirm-btn").addEventListener("click",async()=>{
  const isNewCheckout=pendingAuthorizationTarget==="checkout";
  const isPendingCheckout=pendingAuthorizationTarget==="pending-movement";
  if((!isNewCheckout&&!isPendingCheckout)||(isNewCheckout&&!pendingCheckoutPayload))return;
  const username=document.getElementById("auth-user").value.trim();
  const password=document.getElementById("auth-password").value;
  if(!username||!password)return toast("Ingrese usuario y contraseña del jefe de área.",true);
  const button=document.getElementById("password-confirm-btn");
  button.disabled=true;
  try{
    if(!pendingMovementId&&isNewCheckout){
      const created=await apiFetch(`${apiBaseUrl}/movements`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(pendingCheckoutPayload)
      });
      if(created.status===401){endSession();return;}
      if(created.status===403){toast("Su rol no puede registrar salidas.",true);return;}
      if(created.status===409){toast("El artículo ya tiene una salida pendiente.",true);return;}
      if(!created.ok){toast("No se pudo registrar la salida. Revise los datos.",true);return;}
      pendingMovementId=(await created.json()).id;
      document.getElementById("password-modal-close").disabled=true;
    }
    const authorized=await apiFetch(`${apiBaseUrl}/movements/${pendingMovementId}/authorize`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({method:"password",username,password})
    });
    if(authorized.status===401){endSession();return;}
    if(authorized.status===403){toast("Credenciales inválidas o el usuario no es jefe de área. Puede reintentar.",true);return;}
    if(!authorized.ok){toast("El movimiento quedó pendiente; no se autorizó la salida.",true);return;}
    document.getElementById("password-modal").classList.add("hidden");
    document.getElementById("password-modal-close").disabled=false;
    document.getElementById("checkout-form").reset();
    document.getElementById("checkout-item").value="";
    document.getElementById("checkout-status").value="";
    pendingCheckoutPayload=null;pendingMovementId=null;pendingAuthorizationTarget=null;
    await Promise.all([loadInventory(),loadMovements()]);
    renderAll();showSection("movimientos");
    toast("Salida registrada y autorizada.");
  }catch{toast("No se pudo conectar con el servidor. El movimiento puede seguir pendiente.",true);}
  finally{button.disabled=false;}
});

// MOVIMIENTOS Y USO
function renderMovements(){
  const q=document.getElementById("movement-search").value.toLowerCase(); const f=document.getElementById("movement-status-filter").value;
  const list=movements.filter(m=>[m.id,m.code,m.item,m.responsible,m.authorizer].join(" ").toLowerCase().includes(q)&&(f==="todos"||m.status===f));
  document.getElementById("movement-body").innerHTML=list.map(m=>`<tr><td><strong>${escapeHtml(m.id)}</strong></td><td>${escapeHtml(m.code)}</td><td>${escapeHtml(m.item)}</td><td>${escapeHtml(m.responsible)}</td><td>${escapeHtml(m.authorizer)}</td><td>${escapeHtml(m.exit)}</td><td>${escapeHtml(m.returnDate)}</td><td>${statusTag(m.status)}${m.status==="Pendiente de autorización"&&["administrador","encargado_inventario","jefe_area"].includes(currentRole)?` <button class="action-btn" data-authorize-movement="${m.apiId}">Autorizar</button>`:""}</td></tr>`).join("")||`<tr><td colspan="8">No hay movimientos que coincidan con los filtros.</td></tr>`;
  document.getElementById("dashboard-movements").innerHTML=movements.slice(0,4).map(m=>`<div><strong>${escapeHtml(m.item)}</strong>${statusTag(m.status)}<small>${escapeHtml(m.responsible)} · ${escapeHtml(m.exit)}</small></div>`).join("")||"No hay movimientos registrados.";
}
document.getElementById("movement-body").addEventListener("click",event=>{
  const button=event.target.closest("[data-authorize-movement]");
  if(!button)return;
  pendingMovementId=Number(button.dataset.authorizeMovement);
  pendingCheckoutPayload=null;
  openPasswordAuthorization("pending-movement");
});
document.getElementById("movement-search").addEventListener("input",renderMovements);document.getElementById("movement-status-filter").addEventListener("change",renderMovements);
function renderInUse(){
  const current=movements.filter(m=>m.status==="En uso");
  document.getElementById("use-body").innerHTML=current.map(m=>`<tr><td>${escapeHtml(m.code)}</td><td>${escapeHtml(m.item)}</td><td>${escapeHtml(m.responsible)}</td><td>${escapeHtml(m.location)}</td><td>${escapeHtml(m.exit)}</td><td>${elapsed(m.start)}</td><td>${statusTag(m.status)}</td><td>${["administrador","encargado_inventario"].includes(currentRole)?`<button class="action-btn" data-return-movement="${m.apiId}">Registrar devolución</button>`:"—"}</td></tr>`).join("")||`<tr><td colspan="8">No hay herramientas en uso.</td></tr>`;
}
document.getElementById("use-body").addEventListener("click",event=>{
  const button=event.target.closest("[data-return-movement]");
  if(!button)return;
  const movement=movements.find(entry=>entry.apiId===Number(button.dataset.returnMovement));
  if(!movement)return;
  openModal("Confirmar devolución",`<p class="modal-help">¿Confirmas la devolución de ${escapeHtml(movement.code)} · ${escapeHtml(movement.item)}? El artículo volverá a estar disponible y la acción quedará auditada.</p><button class="btn btn-primary" data-confirm-return="${movement.apiId}">Confirmar devolución</button>`);
});
document.getElementById("modal-content").addEventListener("click",async event=>{
  const button=event.target.closest("[data-confirm-return]");
  if(!button)return;
  const movementId=Number(button.dataset.confirmReturn);
  button.disabled=true;
  try{
    const response=await apiFetch(`${apiBaseUrl}/movements/${movementId}/return`,{method:"POST"});
    if(response.status===401){endSession();return;}
    if(response.status===403){toast("Su rol no puede registrar devoluciones.",true);return;}
    if(response.status===409){toast("El movimiento ya fue cerrado o el artículo cambió de estado.",true);await Promise.all([loadInventory(),loadMovements()]);renderAll();closeModal();return;}
    if(!response.ok){toast("No se pudo registrar la devolución.",true);return;}
    closeModal();
    await Promise.all([loadInventory(),loadMovements()]);
    renderAll();
    toast("Devolución registrada; artículo disponible.");
  }catch{toast("No se pudo conectar con el servidor.",true);}
  finally{button.disabled=false;}
});
function elapsed(start){const ms=Math.max(0,Date.now()-new Date(start).getTime()),h=Math.floor(ms/3600000),min=Math.floor((ms%3600000)/60000);return `${h} h ${min} min`;}

// ALERTAS
function renderAlerts(){
  const statusFilter=document.getElementById("alert-status-filter").value;
  const typeFilter=document.getElementById("alert-type-filter").value;
  const filteredAlerts=alerts.filter(alert=>(statusFilter==="all"||alert.rawStatus===statusFilter)&&(typeFilter==="all"||alert.type===typeFilter));
  document.getElementById("alert-body").innerHTML=filteredAlerts.map(alert=>`<tr><td>${escapeHtml(alert.date)}</td><td><strong>${escapeHtml(alert.event)}</strong></td><td>${escapeHtml(alert.item)}</td><td>${alert.status==="Pendiente"?'<span class="tag red">Pendiente</span>':'<span class="tag green">Resuelta</span>'}</td><td>${escapeHtml(alert.admin)}</td><td>${alert.status==="Pendiente"&&currentRole==="administrador"?`<button class="action-btn" data-resolve-alert="${alert.id}">Atender</button>`:alert.status==="Resuelta"?escapeHtml(alert.notes||alert.resolvedAt):"—"}</td></tr>`).join("")||`<tr><td colspan="6">No hay alertas para los filtros seleccionados.</td></tr>`;
  const count=alerts.filter(alert=>alert.status==="Pendiente").length;
  document.getElementById("alert-count").textContent=count;
  document.getElementById("stat-alerts").textContent=count;
}
document.getElementById("alert-body").addEventListener("click",event=>{
  const button=event.target.closest("[data-resolve-alert]");
  if(button)resolveAlert(Number(button.dataset.resolveAlert));
});
function resolveAlert(alertId){
  const alert=alerts.find(entry=>entry.id===alertId);
  if(!alert||alert.status!=="Pendiente"||currentRole!=="administrador")return;
  openModal("Atender alerta",`<form id="alert-resolution-form" class="form-grid"><p class="modal-help full-row">${escapeHtml(alert.event)} · ${escapeHtml(alert.item)}. Confirma la resolución con la contraseña de tu sesión administrativa.</p><div class="full-row"><label for="alert-resolution-notes">Notas de resolución</label><textarea id="alert-resolution-notes" maxlength="500" placeholder="Describe la revisión realizada"></textarea></div><div class="full-row"><label for="alert-resolution-password">Contraseña del administrador</label><input id="alert-resolution-password" type="password" required autocomplete="current-password"></div><div class="full-row form-actions"><button class="btn btn-primary" type="submit">Resolver alerta</button></div></form>`);
  document.getElementById("alert-resolution-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const form=event.target;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    try{
      const response=await apiFetch(`${apiBaseUrl}/alerts/${alertId}/deactivate`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({method:"dashboard",username:currentUsername,password:document.getElementById("alert-resolution-password").value,resolution_notes:document.getElementById("alert-resolution-notes").value.trim()||null})
      });
      if(response.status===401){endSession();return;}
      if(response.status===403){toast("La contraseña no corresponde a un administrador activo.",true);return;}
      if(response.status===409||response.status===400){toast("La alerta ya fue resuelta o no está disponible.",true);await loadAlerts();renderAlerts();closeModal();return;}
      if(!response.ok){toast("No se pudo resolver la alerta.",true);return;}
      closeModal();await loadAlerts();renderAlerts();toast("Alerta resuelta y auditada.");
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
}

// REPORTES
document.querySelectorAll(".period-btn").forEach(btn=>btn.addEventListener("click",()=>{
  document.querySelectorAll(".period-btn").forEach(button=>button.classList.remove("active"));
  btn.classList.add("active");
  loadReports(btn.dataset.period).catch(error=>{if(error.message!=="Session expired")toast("No se pudieron calcular los reportes.",true);});
}));

function localDateValue(value){
  return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,"0")}-${String(value.getDate()).padStart(2,"0")}`;
}

function initializeMovementReportDates(){
  const startInput=document.getElementById("movement-report-start");
  const endInput=document.getElementById("movement-report-end");
  if(startInput.value&&endInput.value)return;
  const end=new Date();
  const startMonth=end.getMonth()-1;
  const startYear=end.getFullYear()+Math.floor(startMonth/12);
  const normalizedMonth=(startMonth+12)%12;
  const startDay=Math.min(end.getDate(),new Date(startYear,normalizedMonth+1,0).getDate());
  startInput.value=localDateValue(new Date(startYear,normalizedMonth,startDay));
  endInput.value=localDateValue(end);
}

function renderMovementReportOptions(){
  const update=(id,placeholder,options)=>{
    const select=document.getElementById(id);
    const selected=select.value;
    select.innerHTML=`<option value="">${placeholder}</option>`+options.map(option=>`<option value="${option.id}">${escapeHtml(option.label)}</option>`).join("");
    if(options.some(option=>String(option.id)===selected))select.value=selected;
  };
  const items=[...inventory].sort((first,second)=>first.name.localeCompare(second.name,"es"))
    .map(item=>({id:item.id,label:`${item.name} · ${item.code}`}));
  const categories=[...new Map(inventory.filter(item=>item.category_id!=null)
    .map(item=>[item.category_id,item.category_name])).entries()]
    .sort((first,second)=>String(first[1]).localeCompare(String(second[1]),"es"))
    .map(([id,label])=>({id,label}));
  const locations=[...movementOptions.locations].sort((first,second)=>first.name.localeCompare(second.name,"es"))
    .map(location=>({id:location.id,label:location.name}));
  const responsibles=[...movementOptions.users].sort((first,second)=>first.name.localeCompare(second.name,"es"))
    .map(user=>({id:user.id,label:user.name}));
  update("movement-report-item","Todos",items);
  update("movement-report-category","Todas",categories);
  update("movement-report-location","Todas",locations);
  update("movement-report-responsible","Todos",responsibles);
  initializeMovementReportDates();
}

document.getElementById("download-report-btn").addEventListener("click",async event=>{
  const button=event.currentTarget;
  button.disabled=true;
  const period=document.querySelector(".period-btn.active")?.dataset.period||"week";
  try{
    const response=await apiFetch(`${apiBaseUrl}/reports/summary/pdf?period=${encodeURIComponent(period)}`);
    if(response.status===401){endSession();return;}
    if(response.status===403){toast("Su rol no puede descargar reportes.",true);return;}
    if(!response.ok){toast("No se pudo generar el PDF.",true);return;}
    const fileUrl=URL.createObjectURL(await response.blob());
    const download=document.createElement("a");
    download.href=fileUrl;download.download=`sigmat-reporte-${period}-${new Date().toISOString().slice(0,10)}.pdf`;
    document.body.appendChild(download);download.click();download.remove();URL.revokeObjectURL(fileUrl);
    toast("Reporte PDF generado y auditado.");
  }catch(error){if(error.message!=="Session expired")toast("No se pudo conectar con el servidor.",true);}
  finally{button.disabled=false;}
});
document.getElementById("movement-report-form").addEventListener("submit",async event=>{
  event.preventDefault();
  const form=event.currentTarget;
  const button=form.querySelector('button[type="submit"]');
  const params=new URLSearchParams({
    start_date:document.getElementById("movement-report-start").value,
    end_date:document.getElementById("movement-report-end").value,
  });
  const filters={
    status:document.getElementById("movement-report-status").value,
    item_id:document.getElementById("movement-report-item").value,
    category_id:document.getElementById("movement-report-category").value,
    location_id:document.getElementById("movement-report-location").value,
    responsible_user_id:document.getElementById("movement-report-responsible").value,
  };
  Object.entries(filters).forEach(([key,value])=>{if(value)params.set(key,value);});
  button.disabled=true;
  try{
    const response=await apiFetch(`${apiBaseUrl}/reports/movements/pdf?${params}`);
    if(response.status===401){endSession();return;}
    if(response.status===403){toast("Su rol no puede descargar reportes.",true);return;}
    if(response.status===422){const problem=await response.json().catch(()=>({}));toast(problem.detail||"Revise el rango de fechas y los filtros.",true);return;}
    if(response.status===429){toast("Se alcanzó el límite de exportaciones; intente más tarde.",true);return;}
    if(response.status===503){toast("El servicio de reportes no está disponible temporalmente.",true);return;}
    if(!response.ok){toast("No se pudo generar el historial PDF.",true);return;}
    const fileUrl=URL.createObjectURL(await response.blob());
    const download=document.createElement("a");
    download.href=fileUrl;download.download=`sigmat-movimientos-${document.getElementById("movement-report-start").value}-${document.getElementById("movement-report-end").value}.pdf`;
    document.body.appendChild(download);download.click();download.remove();setTimeout(()=>URL.revokeObjectURL(fileUrl),1000);
    toast("Historial PDF generado y auditado.");
  }catch(error){if(error.message!=="Session expired")toast("No se pudo conectar con el servidor.",true);}
  finally{button.disabled=false;}
});
function renderReports(){
  const current=reportPeriods[0];
  document.getElementById("report-outs").textContent=current?.checkouts??0;
  document.getElementById("report-returns").textContent=current?.returns??0;
  document.getElementById("report-incidents").textContent=current?.incidents??0;
  const seconds=current?.average_usage_seconds;
  document.getElementById("report-average").textContent=seconds==null?"—":`${Math.floor(seconds/3600)} h ${Math.floor((seconds%3600)/60)} min`;
  const period=document.querySelector(".period-btn.active")?.dataset.period||"week";
  const label=period==="week"?"Ventana semanal":"Ventana mensual";
  ["report-outs-label","report-returns-label","report-incidents-label","report-average-label"].forEach(id=>document.getElementById(id).textContent=label);
  document.getElementById("report-table-title").textContent=period==="week"?"Comparativo de semanas":"Comparativo de meses";
  document.getElementById("report-table-body").innerHTML=reportPeriods.map(row=>`<tr><td>${escapeHtml(row.label)}</td><td>${row.checkouts}</td><td>${row.returns}</td><td>${row.incidents}</td><td>${escapeHtml(row.most_used_item||"—")}</td></tr>`).join("")||`<tr><td colspan="5">No hay datos para los periodos seleccionados.</td></tr>`;
}

// CONFIGURACIÓN / USUARIOS
document.querySelectorAll(".settings-tab").forEach(tab=>tab.addEventListener("click",()=>{
  if(tab.disabled)return;
  document.querySelectorAll(".settings-tab").forEach(t=>t.classList.remove("active"));document.querySelectorAll(".config-tab-content").forEach(c=>c.classList.remove("active"));tab.classList.add("active");document.getElementById(`config-tab-${tab.dataset.configTab}`).classList.add("active");
}));
function renderUsers(){
  document.getElementById("users-grid").innerHTML=users.map(user=>{
    const initials=user.full_name.split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase();
    const accountAction=user.is_active
      ?user.id!==currentUserId?`<button class="action-btn danger-action" data-deactivate-user="${user.id}">Desactivar</button>`:""
      :`<button class="action-btn" data-reactivate-user="${user.id}">Reactivar</button>`;
    return `<article class="person-card"><div class="avatar">${escapeHtml(initials)}</div><h3>${escapeHtml(user.full_name)}</h3><p>${escapeHtml(user.username)} · ${escapeHtml(user.role_name)}</p><span class="tag ${user.is_active?"green":"gray"}">${user.is_active?"Activo":"Inactivo"}</span><div class="action-group"><button class="action-btn" data-edit-user="${user.id}">Editar</button>${accountAction}</div></article>`;
  }).join("")||`<p>No hay usuarios registrados.</p>`;
}
document.getElementById("users-grid").addEventListener("click",event=>{
  const editButton=event.target.closest("[data-edit-user]");
  const deactivateButton=event.target.closest("[data-deactivate-user]");
  const reactivateButton=event.target.closest("[data-reactivate-user]");
  if(editButton){openEditUser(Number(editButton.dataset.editUser));return;}
  if(deactivateButton)openDeactivateUser(Number(deactivateButton.dataset.deactivateUser));
  if(reactivateButton)openReactivateUser(Number(reactivateButton.dataset.reactivateUser));
});
function openEditUser(userId){
  const user=users.find(entry=>entry.id===userId);
  if(!user||currentRole!=="administrador")return;
  const isCurrentUser=user.id===currentUserId;
  openModal("Editar usuario",`<form id="edit-user-form" class="form-grid"><div><label for="edit-user-username">Usuario</label><input id="edit-user-username" value="${escapeHtml(user.username)}" ${isCurrentUser?"readonly":""} required minlength="3" maxlength="50"></div><div><label for="edit-user-name">Nombre completo</label><input id="edit-user-name" value="${escapeHtml(user.full_name)}" required maxlength="150"></div><div class="full-row"><label for="edit-user-email">Correo</label><input id="edit-user-email" type="email" value="${escapeHtml(user.email)}" required maxlength="120"></div><div><label for="edit-user-password">Nueva contraseña</label><input id="edit-user-password" type="password" minlength="12" maxlength="128" autocomplete="new-password"></div><div><label for="edit-user-role">Rol</label><select id="edit-user-role" ${isCurrentUser?"disabled":""}>${availableRoles.map(role=>`<option value="${role.id}" ${role.id===user.role_id?"selected":""}>${escapeHtml(role.description||role.name)} · ${escapeHtml(role.name)}</option>`).join("")}</select></div><div class="full-row form-actions"><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form>`);
  document.getElementById("edit-user-form").addEventListener("submit",async event=>{
    event.preventDefault();const form=event.target;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    const payload={username:document.getElementById("edit-user-username").value.trim(),full_name:document.getElementById("edit-user-name").value.trim(),email:document.getElementById("edit-user-email").value.trim()};
    if(!isCurrentUser)payload.role_id=Number(document.getElementById("edit-user-role").value);
    const password=document.getElementById("edit-user-password").value;
    if(password)payload.password=password;
    try{
      const response=await apiFetch(`${apiBaseUrl}/users/${userId}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      if(response.status===401){endSession();return;}
      if(response.status===403){toast("Solo un administrador puede editar usuarios.",true);return;}
      if(response.status===409){toast("No se pudo editar: username o correo duplicado, o cambio propio no permitido.",true);return;}
      if(response.status===422){toast("Revise los campos y la longitud de la nueva contraseña.",true);return;}
      if(!response.ok){toast("No se pudo actualizar el usuario.",true);return;}
      closeModal();await loadUsersAndRoles();renderUsers();toast("Usuario actualizado y auditado.");
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
}
function openDeactivateUser(userId){
  const user=users.find(entry=>entry.id===userId);
  if(!user||!user.is_active||user.id===currentUserId||currentRole!=="administrador")return;
  openModal("Desactivar usuario",`<form id="deactivate-user-form" class="form-grid"><p class="modal-help full-row">La cuenta de ${escapeHtml(user.full_name)} dejará de iniciar sesión. Sus movimientos y auditorías se conservarán.</p><div class="full-row"><label for="deactivate-user-password">Contraseña del administrador</label><input id="deactivate-user-password" type="password" autocomplete="current-password" required></div><div class="full-row form-actions"><button class="btn btn-danger" type="submit">Desactivar cuenta</button></div></form>`);
  document.getElementById("deactivate-user-form").addEventListener("submit",async event=>{
    event.preventDefault();const form=event.target;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    try{
      const response=await apiFetch(`${apiBaseUrl}/users/${userId}/deactivate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmation_password:document.getElementById("deactivate-user-password").value})});
      if(response.status===401){endSession();return;}
      if(response.status===403){toast("Contraseña incorrecta o sesión sin permisos administrativos.",true);return;}
      if(response.status===409){toast("No se pudo desactivar: la cuenta ya está inactiva o debe permanecer activa.",true);return;}
      if(!response.ok){toast("No se pudo desactivar el usuario.",true);return;}
      closeModal();await loadUsersAndRoles();renderUsers();toast("Usuario desactivado; su historial se conserva.");
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
}
function openReactivateUser(userId){
  const user=users.find(entry=>entry.id===userId);
  if(!user||user.is_active||currentRole!=="administrador")return;
  openModal("Reactivar usuario",`<form id="reactivate-user-form" class="form-grid"><p class="modal-help full-row">La cuenta de ${escapeHtml(user.full_name)} podrá volver a iniciar sesión. Sus referencias históricas se conservan.</p><div class="full-row"><label for="reactivate-user-password">Contraseña del administrador</label><input id="reactivate-user-password" type="password" autocomplete="current-password" required></div><div class="full-row form-actions"><button class="btn btn-primary" type="submit">Reactivar cuenta</button></div></form>`);
  document.getElementById("reactivate-user-form").addEventListener("submit",async event=>{
    event.preventDefault();const form=event.target;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    try{
      const response=await apiFetch(`${apiBaseUrl}/users/${userId}/reactivate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmation_password:document.getElementById("reactivate-user-password").value})});
      if(response.status===401){endSession();return;}
      if(response.status===403){toast("Contraseña incorrecta o sesión sin permisos administrativos.",true);return;}
      if(response.status===404){toast("No se encontró la cuenta.",true);return;}
      if(response.status===409){toast("La cuenta ya está activa.",true);return;}
      if(!response.ok){toast("No se pudo reactivar el usuario.",true);return;}
      closeModal();await loadUsersAndRoles();renderUsers();toast("Usuario reactivado y auditado.");
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
}
document.getElementById("new-user-btn").addEventListener("click",()=>{
  if(currentRole!=="administrador")return;
  openModal("Nuevo usuario",`<form id="new-user-form" class="form-grid"><div><label for="new-user-username">Usuario</label><input id="new-user-username" required minlength="3" maxlength="50" autocomplete="username"></div><div><label for="new-user-name">Nombre completo</label><input id="new-user-name" required maxlength="150" autocomplete="name"></div><div class="full-row"><label for="new-user-email">Correo</label><input id="new-user-email" type="email" required maxlength="120" autocomplete="email"></div><div><label for="new-user-password">Contraseña inicial</label><input id="new-user-password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></div><div><label for="new-user-role">Rol</label><select id="new-user-role" required><option value="">Selecciona un rol...</option>${availableRoles.map(role=>`<option value="${role.id}">${escapeHtml(role.description||role.name)} · ${escapeHtml(role.name)}</option>`).join("")}</select></div><div class="full-row form-actions"><button class="btn btn-primary" type="submit">Crear usuario</button></div></form>`);
  document.getElementById("new-user-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const form=event.target;const button=form.querySelector('button[type="submit"]');button.disabled=true;
    try{
      const response=await apiFetch(`${apiBaseUrl}/users`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          username:document.getElementById("new-user-username").value.trim(),
          full_name:document.getElementById("new-user-name").value.trim(),
          email:document.getElementById("new-user-email").value.trim(),
          password:document.getElementById("new-user-password").value,
          role_id:Number(document.getElementById("new-user-role").value)
        })
      });
      if(response.status===401){endSession();return;}
      if(response.status===403){toast("Solo un administrador puede crear usuarios.",true);return;}
      if(response.status===409){toast("El usuario o el correo ya están registrados.",true);return;}
      if(response.status===422){toast("Revise los datos y la longitud de la contraseña.",true);return;}
      if(!response.ok){toast("No se pudo crear el usuario.",true);return;}
      form.reset();closeModal();await loadUsersAndRoles();renderUsers();toast("Usuario creado y auditado.");
    }catch{toast("No se pudo conectar con el servidor.",true);}
    finally{button.disabled=false;}
  });
});

// MODALES Y UTILIDADES
function openModal(title,content){document.getElementById("modal-title").textContent=title;document.getElementById("modal-content").innerHTML=content;document.getElementById("modal").classList.remove("hidden")}
function closeModal(){document.getElementById("modal").classList.add("hidden")}
document.getElementById("modal-close").addEventListener("click",closeModal);document.getElementById("modal").addEventListener("click",e=>{if(e.target.id==="modal")closeModal()});
function updateStats(){document.getElementById("stat-total").textContent=inventory.filter(i=>i.status!=="Baja").length;document.getElementById("stat-use").textContent=inventory.filter(i=>i.status==="En uso").length;document.getElementById("stat-available").textContent=inventory.filter(i=>["Disponible","Devuelta"].includes(i.status)).length;}
function updateDate(){document.getElementById("current-date").textContent=new Date().toLocaleDateString("es-MX",{weekday:"long",day:"numeric",month:"long",year:"numeric"})}
function nowString(){return new Date().toLocaleString("es-MX",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",hour12:false})}
function toast(message,error=false){const t=document.createElement("div");t.className=`toast${error?" error":""}`;t.textContent=(error?"⚠ ":"✓ ")+message;document.getElementById("toast-container").appendChild(t);setTimeout(()=>t.remove(),3200)}
function renderAll(){renderInventory();renderMovements();renderInUse();renderAlerts();renderDecommissionHistory();updateStats();}

updateDate();
