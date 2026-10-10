# Inicializar servicio

Guía para levantar SIGMAT en desarrollo local cualquier día. Los comandos están probados en este equipo (Windows + WSL2 Ubuntu).

## Arquitectura en ejecución

| Entidad | Dónde corre | Puerto |
|---|---|---|
| PostgreSQL | WSL (Ubuntu), loopback | 5432 |
| Redis (límite de exportaciones PDF) | WSL (Ubuntu), loopback | 6379 |
| API FastAPI | **WSL**, venv `/home/samu/.venvs/sigmat`, loopback | 8000 |
| Frontend estático | Windows, `Frontend\serve.py`, loopback | 5173 |

La API corre dentro de WSL porque el backend de Windows puede recibir `connection refused` al conectar con PostgreSQL y Redis por `localhost`. Dentro de WSL esa conexión es local y estable.

## Orden de arranque

Respeta el orden: base de datos y Redis primero, después la API y al final el frontend.

### 1. Confirmar que los puertos están libres

Abre PowerShell en la raíz del proyecto:

```powershell
Get-NetTCPConnection -LocalPort 5173,8000 -State Listen -ErrorAction SilentlyContinue
```

Si devuelve filas, ya hay un proceso activo; no abras otro. Cierra el anterior con `Ctrl+C` en su terminal.

### 2. Iniciar PostgreSQL y Redis

```powershell
wsl -d Ubuntu -u root -- service postgresql start
wsl -d Ubuntu -u root -- service redis-server start
wsl -d Ubuntu -u root -- pg_isready -h localhost -p 5432
```

Debe responder `localhost:5432 - accepting connections`.

### 3. Aplicar migraciones (solo si hubo cambios del esquema)

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/H634046/OneDrive - Honeywell/PTT/backend'; /home/samu/.venvs/sigmat/bin/python -m alembic upgrade head"
```

Es seguro repetirlo: si la base ya está al día no cambia nada.

### 4. Iniciar la API

En una terminal dedicada, déjala abierta:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/H634046/OneDrive - Honeywell/PTT/backend'; exec /home/samu/.venvs/sigmat/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
```

Debe mostrar `Application startup complete`.

### 5. Iniciar el frontend

En otra terminal, desde la raíz del proyecto:

```powershell
.\backend\.venv\Scripts\python.exe Frontend\serve.py
```

No muestra mensaje de arranque; es normal. No uses `python -m http.server` en la raíz: publicaría `backend/.env`.

### 6. Abrir la aplicación

`http://localhost:5173/`

Usuario de desarrollo: `admin`. Cambia esa contraseña antes de exponer el servicio a otras personas o redes.

## Verificación rápida

Ejecuta esto una vez que todo esté arriba; los tres códigos esperados son `200`:

```powershell
(Invoke-WebRequest http://localhost:5173/ -UseBasicParsing).StatusCode
(Invoke-WebRequest http://localhost:8000/health -UseBasicParsing).StatusCode
wsl -d Ubuntu -u root -- systemctl is-active postgresql redis-server
```

Los dos servicios deben responder `active`. También puedes revisar `http://localhost:8000/docs`.

## Apagar al terminar

1. `Ctrl+C` en la terminal de la API y en la del frontend.
2. Opcional, para liberar memoria:

```powershell
wsl -d Ubuntu -u root -- service redis-server stop
wsl -d Ubuntu -u root -- service postgresql stop
```

Detener PostgreSQL **no borra datos**. Redis solo guarda contadores temporales de 60 segundos, así que perder su contenido no afecta al negocio.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| El login muestra "No se pudo iniciar sesión" y la consola del navegador dice **CORS** | La API devolvió `500` y el navegador lo presenta como CORS | Revisa la terminal de la API; casi siempre es la base de datos apagada. Repite el paso 2 |
| `connection refused` al puerto 5432 | PostgreSQL no arrancó o la API corre en Windows | Repite el paso 2 y arranca la API desde WSL (paso 4) |
| Login con `500` y error de `bcrypt` | `bcrypt` 5 es incompatible con `passlib` | `wsl -d Ubuntu -- /home/samu/.venvs/sigmat/bin/pip install "bcrypt>=4.0.1,<5"` |
| El puerto 8000 o 5173 está ocupado | Hay un proceso anterior vivo | Cierra la terminal anterior con `Ctrl+C`; no inicies una segunda instancia |
| Descargar un PDF devuelve `503` | Redis apagado: la exportación falla cerrada a propósito | `wsl -d Ubuntu -u root -- service redis-server start` |
| Descargar un PDF devuelve `429` | Más de 5 exportaciones por minuto del mismo usuario | Espera el tiempo indicado en `Retry-After` |
| El PDF devuelve `413` | El filtro incluye más de 5,000 movimientos | Reduce el rango de fechas o agrega filtros |
| `ModuleNotFoundError` al iniciar la API | Faltan dependencias en el venv de WSL | Ver "Actualizar dependencias" |
| Error CORS al abrir SIGMAT con `127.0.0.1` | El origen autorizado de desarrollo es `http://localhost:5173` | Abre `http://localhost:5173/`; no amplíes CORS para resolverlo |

## Actualizar dependencias

Cuando cambie `backend/requirements.txt`, actualiza el venv de WSL, que es el que usa la API:

```powershell
wsl -d Ubuntu -- bash -lc "/home/samu/.venvs/sigmat/bin/pip install -r '/mnt/c/Users/H634046/OneDrive - Honeywell/PTT/backend/requirements.txt'"
```

## Si hay que recrear el entorno de WSL

Solo si `/home/samu/.venvs/sigmat` se pierde:

```powershell
wsl -d Ubuntu -u root -- apt-get install -y python3.12-venv
wsl -d Ubuntu -- bash -lc "mkdir -p /home/samu/.venvs && python3 -m venv /home/samu/.venvs/sigmat"
```

Después instala las dependencias como en la sección anterior. Para crear PostgreSQL y la base desde cero consulta `docs/SETUP_FROM_SCRATCH.md`.

## Reglas de seguridad

- `backend/.env` contiene secretos locales. No lo imprimas, no lo compartas y no lo subas al repositorio.
- Las credenciales semilla (`admin` / `Admin123!`) son solo de desarrollo; cámbialas antes de habilitar acceso a otras personas o redes.
- Mantén Redis y PostgreSQL sin exponer a Internet; la API escucha solo en `127.0.0.1`.
- Docker Compose requiere `POSTGRES_PASSWORD` en el `.env` de la raíz; los puertos publicados se limitan a `127.0.0.1`.
- No borres filas de movimientos, reportes ni auditoría para "limpiar" pruebas. Mientras SIGMAT sea la única fuente de esos registros no hay purga automática.
