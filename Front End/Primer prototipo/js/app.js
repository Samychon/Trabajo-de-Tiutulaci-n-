// ============================================================
// SIGMAT - Prototipo frontend
// La información de este archivo es simulada.
// Posteriormente se conectará con Python/PostgreSQL/ESP32.
// ============================================================

const inventory = [
    { code: "TAL-001", rfid: "RFID-A83F21", name: "Taladro inalámbrico", type: "Herramienta", status: "En uso", location: "Almacén", responsible: "Carlos López" },
    { code: "TAL-002", rfid: "RFID-B1287C", name: "Taladro de impacto", type: "Herramienta", status: "Disponible", location: "Almacén" },
    { code: "MUL-001", rfid: "RFID-C9812A", name: "Multímetro digital", type: "Instrumento", status: "Disponible", location: "Almacén" },
    { code: "LLA-001", rfid: "RFID-D44210", name: "Juego de llaves", type: "Herramienta", status: "Disponible", location: "Almacén" },
    { code: "CAB-001", rfid: "RFID-E1029F", name: "Cable de control", type: "Material", status: "Mantenimiento", location: "Almacén" },
    { code: "SOL-001", rfid: "RFID-F81220", name: "Estación de soldadura", type: "Equipo", status: "Disponible", location: "Almacén" }
];

let movements = [
    { id: "MOV-0001", code: "TAL-001", item: "Taladro inalámbrico", responsible: "Carlos López", authorizer: "Jefe de Área 1", exit: "13/09/2026 09:15", returnDate: "—", status: "En uso" },
    { id: "MOV-0002", code: "MUL-001", item: "Multímetro digital", responsible: "Ana Torres", authorizer: "Jefe de Área 2", exit: "12/09/2026 10:20", returnDate: "12/09/2026 15:45", status: "Devuelto" },
    { id: "MOV-0003", code: "LLA-001", item: "Juego de llaves", responsible: "Luis García", authorizer: "Jefe de Área 1", exit: "11/09/2026 08:05", returnDate: "11/09/2026 12:10", status: "Devuelto" }
];

let alerts = [
    { date: "13/09/2026 11:42", event: "Salida no autorizada", item: "Taladro inalámbrico", status: "Pendiente", admin: "—", action: "Revisar" },
    { date: "08/09/2026 14:18", event: "RFID no registrado", item: "Etiqueta desconocida", status: "Resuelta", admin: "Administrador", action: "Regularizada" }
];

let fingerprintAuthorized = false;

// ---------- LOGIN ----------
document.getElementById("login-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const user = document.getElementById("login-user").value.trim();
    const password = document.getElementById("login-password").value;

    if (user === "admin" && password === "admin123") {
        document.getElementById("login-screen").classList.add("hidden");
        document.getElementById("app").classList.remove("hidden");
        updateDate();
        renderAll();
        toast("Sesión iniciada correctamente.");
    } else {
        document.getElementById("login-error").classList.remove("hidden");
    }
});

document.getElementById("logout-btn").addEventListener("click", () => {
    document.getElementById("app").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
    document.getElementById("login-form").reset();
});

// ---------- NAVEGACIÓN ----------
const sectionNames = {
    dashboard: "Inicio",
    inventario: "Inventario",
    salida: "Registrar salida",
    uso: "Herramientas en uso",
    movimientos: "Historial de movimientos",
    alertas: "Historial de alertas",
    usuarios: "Usuarios",
    reportes: "Reportes",
    configuracion: "Configuración"
};

document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
});

document.querySelectorAll("[data-go]").forEach(btn => {
    btn.addEventListener("click", () => showSection(btn.dataset.go));
});

function showSection(section) {
    document.querySelectorAll(".content-section").forEach(s => s.classList.remove("active-section"));
    document.getElementById(`section-${section}`).classList.add("active-section");

    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    const nav = document.querySelector(`.nav-item[data-section="${section}"]`);
    if (nav) nav.classList.add("active");

    document.getElementById("page-title").textContent = sectionNames[section];
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- INVENTARIO ----------
function renderInventory(list = inventory) {
    const body = document.getElementById("inventory-body");

    body.innerHTML = list.map(item => `
        <tr>
            <td><strong>${item.code}</strong></td>
            <td>${item.rfid}</td>
            <td>${item.name}</td>
            <td>${item.type}</td>
            <td>${statusTag(item.status)}</td>
            <td>${item.location}</td>
            <td><button class="action-btn" onclick="showItem('${item.code}')">Ver</button></td>
        </tr>
    `).join("");
}

function statusTag(status) {
    const cls = status === "Disponible" || status === "Devuelto" ? "green" :
                status === "En uso" ? "orange" : "red";
    return `<span class="tag ${cls}">${status}</span>`;
}

document.getElementById("inventory-search").addEventListener("input", filterInventory);
document.getElementById("inventory-filter").addEventListener("change", filterInventory);

function filterInventory() {
    const q = document.getElementById("inventory-search").value.toLowerCase();
    const filter = document.getElementById("inventory-filter").value;

    const filtered = inventory.filter(item => {
        const matchesText = [item.code, item.rfid, item.name, item.type].some(v => v.toLowerCase().includes(q));
        const matchesFilter = filter === "todos" || item.status === filter;
        return matchesText && matchesFilter;
    });

    renderInventory(filtered);
}

function showItem(code) {
    const item = inventory.find(i => i.code === code);
    if (!item) return;

    openModal(`Artículo ${item.code}`, `
        <div class="modal-detail">
            <div><span>Nombre</span><strong>${item.name}</strong></div>
            <div><span>Código</span><strong>${item.code}</strong></div>
            <div><span>RFID</span><strong>${item.rfid}</strong></div>
            <div><span>Tipo</span><strong>${item.type}</strong></div>
            <div><span>Estado</span><strong>${item.status}</strong></div>
            <div><span>Ubicación</span><strong>${item.location}</strong></div>
            <div><span>Responsable</span><strong>${item.responsible || "—"}</strong></div>
        </div>
    `);
}

// ---------- SALIDA ----------
document.getElementById("simulate-scan").addEventListener("click", () => {
    const code = document.getElementById("checkout-code").value.trim().toUpperCase() || "TAL-001";
    document.getElementById("checkout-code").value = code;

    const item = inventory.find(i => i.code === code);

    if (!item) {
        toast("Código no registrado en el inventario.", true);
        return;
    }

    document.getElementById("checkout-item").value = item.name;
    document.getElementById("checkout-rfid").value = item.rfid;
    toast(`Código detectado: ${item.code}`);
});

document.getElementById("checkout-code").addEventListener("change", () => {
    const item = inventory.find(i => i.code === document.getElementById("checkout-code").value.trim().toUpperCase());
    if (item) {
        document.getElementById("checkout-item").value = item.name;
        document.getElementById("checkout-rfid").value = item.rfid;
    }
});

document.getElementById("fingerprint-btn").addEventListener("click", () => {
    const result = document.getElementById("authorization-result");
    result.classList.remove("hidden");
    result.innerHTML = `<div class="auth-success">✓ Huella reconocida. Autorización concedida por <strong>Jefe de Área 1</strong>.</div>`;
    fingerprintAuthorized = true;
    toast("Autorización biométrica aceptada.");
});

document.getElementById("checkout-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const code = document.getElementById("checkout-code").value.trim().toUpperCase();
    const item = inventory.find(i => i.code === code);

    if (!item) {
        toast("Primero debe identificar una herramienta válida.", true);
        return;
    }

    if (item.status !== "Disponible") {
        toast("La herramienta no está disponible.", true);
        return;
    }

    if (!fingerprintAuthorized) {
        toast("Se requiere autorización del jefe mediante huella.", true);
        return;
    }

    const now = new Date();
    const dateTime = formatDateTime(now);

    const newMovement = {
        id: `MOV-${String(movements.length + 1).padStart(4, "0")}`,
        code: item.code,
        item: item.name,
        responsible: document.getElementById("checkout-responsible").value,
        authorizer: "Jefe de Área 1",
        exit: dateTime,
        returnDate: "—",
        status: "En uso"
    };

    movements.unshift(newMovement);
    item.status = "En uso";
    item.responsible = newMovement.responsible;

    fingerprintAuthorized = false;
    document.getElementById("checkout-form").reset();
    document.getElementById("checkout-item").value = "";
    document.getElementById("checkout-rfid").value = "";
    document.getElementById("authorization-result").classList.add("hidden");

    renderAll();
    toast(`Salida registrada correctamente: ${item.name}`);
    showSection("movimientos");
});

// ---------- MOVIMIENTOS ----------
function renderMovements() {
    document.getElementById("movement-body").innerHTML = movements.map(m => `
        <tr>
            <td><strong>${m.id}</strong></td>
            <td>${m.code}</td>
            <td>${m.item}</td>
            <td>${m.responsible}</td>
            <td>${m.authorizer}</td>
            <td>${m.exit}</td>
            <td>${m.returnDate}</td>
            <td>${statusTag(m.status)}</td>
        </tr>
    `).join("");

    document.getElementById("dashboard-movements").innerHTML = movements.slice(0, 4).map(m => `
        <div>
            <strong>${m.item}</strong>
            <span>${statusTag(m.status)}</span>
            <small>${m.responsible} · ${m.exit}</small>
        </div>
    `).join("");
}

document.getElementById("movement-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll("#movement-body tr").forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
    });
});

// ---------- EN USO ----------
function renderInUse() {
    const current = movements.filter(m => m.status === "En uso");
    document.getElementById("use-body").innerHTML = current.map(m => `
        <tr>
            <td>${m.code}</td>
            <td>${m.item}</td>
            <td>${m.responsible}</td>
            <td>Área de trabajo</td>
            <td>${m.exit}</td>
            <td>En curso</td>
            <td>${statusTag("En uso")}</td>
        </tr>
    `).join("") || `<tr><td colspan="7">No hay herramientas actualmente en uso.</td></tr>`;
}

// ---------- ALERTAS ----------
function renderAlerts() {
    document.getElementById("alert-body").innerHTML = alerts.map((a, index) => `
        <tr>
            <td>${a.date}</td>
            <td><strong>${a.event}</strong></td>
            <td>${a.item}</td>
            <td>${statusTag(a.status === "Pendiente" ? "En uso" : "Devuelto").replace("En uso", a.status)}</td>
            <td>${a.admin}</td>
            <td>
                ${a.status === "Pendiente"
                    ? `<button class="btn btn-danger" onclick="resolveAlert(${index})">Atender</button>`
                    : `<span class="tag green">${a.action}</span>`}
            </td>
        </tr>
    `).join("");
}

function resolveAlert(index) {
    openModal("Atender alerta", `
        <p style="margin-bottom:15px;color:#6b7785;">Para apagar la alarma y regularizar el evento se requiere autenticación del administrador.</p>
        <div class="form-grid">
            <div><label>Usuario administrador</label><input id="alert-admin-user" value="admin"></div>
            <div><label>Contraseña</label><input id="alert-admin-pass" type="password" placeholder="••••••••"></div>
            <div class="full-row"><button class="btn btn-primary full" onclick="confirmAlert(${index})">Autorizar y apagar alarma</button></div>
        </div>
    `);
}

function confirmAlert(index) {
    const pass = document.getElementById("alert-admin-pass").value;

    if (pass !== "admin123") {
        toast("Credenciales incorrectas.", true);
        return;
    }

    alerts[index].status = "Resuelta";
    alerts[index].admin = "Administrador";
    alerts[index].action = "Alarma apagada / evento revisado";
    closeModal();
    renderAlerts();
    updateStats();
    toast("Alarma desactivada y alerta resuelta.");
}

// ---------- MODAL ----------
function openModal(title, content) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-content").innerHTML = content;
    document.getElementById("modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("modal").classList.add("hidden");
}

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal").addEventListener("click", e => {
    if (e.target.id === "modal") closeModal();
});

// ---------- STATS ----------
function updateStats() {
    const total = inventory.length;
    const inUse = inventory.filter(i => i.status === "En uso").length;
    const available = inventory.filter(i => i.status === "Disponible").length;
    const pendingAlerts = alerts.filter(a => a.status === "Pendiente").length;

    document.getElementById("stat-total").textContent = total;
    document.getElementById("stat-use").textContent = inUse;
    document.getElementById("stat-available").textContent = available;
    document.getElementById("stat-alerts").textContent = pendingAlerts;
}

// ---------- UTILIDADES ----------
function formatDateTime(date) {
    const d = String(date.getDate()).padStart(2, "0");
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const y = date.getFullYear();
    const h = String(date.getHours()).padStart(2, "0");
    const min = String(date.getMinutes()).padStart(2, "0");
    return `${d}/${m}/${y} ${h}:${min}`;
}

function updateDate() {
    const now = new Date();
    document.getElementById("current-date").textContent =
        now.toLocaleDateString("es-MX", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function toast(message, error = false) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = `${error ? "⚠️ " : "✓ "}${message}`;
    document.getElementById("toast-container").appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

function renderAll() {
    renderInventory();
    renderMovements();
    renderInUse();
    renderAlerts();
    updateStats();
}

document.getElementById("add-item-btn").addEventListener("click", () => {
    openModal("Agregar artículo", `
        <div class="form-grid">
            <div><label>Código</label><input placeholder="Ej. TAL-003"></div>
            <div><label>RFID</label><input placeholder="Ej. RFID-XXXXXX"></div>
            <div><label>Nombre</label><input placeholder="Nombre del artículo"></div>
            <div><label>Tipo</label><select><option>Herramienta</option><option>Material</option><option>Equipo</option><option>Instrumento</option></select></div>
            <div class="full-row"><button class="btn btn-primary full" onclick="closeModal(); toast('Formulario de alta preparado para conexión con la base de datos.')">Guardar artículo</button></div>
        </div>
    `);
});

document.querySelectorAll(".setting-btn").forEach(btn => {
    btn.addEventListener("click", () => toast("Módulo preparado para integración con hardware real."));
});

updateDate();
