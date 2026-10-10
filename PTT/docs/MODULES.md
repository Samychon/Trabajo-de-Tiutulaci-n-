# MODULES.md — Mapa de archivos del backend

> Documento vivo: cada vez que se cree, borre o modifique un archivo relevante del backend, este documento debe actualizarse en el mismo cambio.

## Raíz del repo
| Archivo | Qué hace |
|---|---|
| `docker-compose.yml` | Orquesta PostgreSQL, Redis, el backend y el servicio `backup` (respaldo automático) para desarrollo local. |
| `.gitignore` | Excluye entornos virtuales, `.env`, cachés y artefactos de build. |

## `backend/backup/` — continuidad de datos (disaster recovery)
| Archivo | Qué hace |
|---|---|
| `backup.sh` | Corre en bucle dentro del servicio `backup`: genera un `pg_dump` (formato custom) cada `BACKUP_INTERVAL_SECONDS` y borra los dumps más viejos que `BACKUP_RETENTION_DAYS`. Los archivos quedan en el volumen `backup_data`, separado del volumen de datos vivos (`db_data`). |
| `restore.sh` | Restaura un `.dump` sobre la BD (`pg_restore --clean --if-exists`); se ejecuta manualmente vía `docker compose exec backup sh /scripts/restore.sh /backups/<archivo>`. |

> Pendiente: copiar periódicamente el contenido de `backup_data` a un destino fuera del host (ej. `rclone` a un bucket en la nube) para cumplir la regla 3-2-1. Hoy el respaldo protege contra borrado accidental de datos/corrupción, pero no contra pérdida física del servidor si no se copia offsite.

## `backend/`
| Archivo | Qué hace |
|---|---|
| `requirements.txt` | Dependencias Python para API, JWT con PyJWT, límite distribuido con Redis y generación de reportes PDF con ReportLab. |
| `.env.example` | Plantilla de variables de entorno (nunca poner secretos reales aquí). |
| `Dockerfile` | Imagen del servicio backend (FastAPI + Uvicorn). |
| `alembic.ini` | Configuración de Alembic (migraciones de BD). |
| `alembic/env.py` | Conecta Alembic con `Settings` y el metadata de SQLAlchemy para autogenerar migraciones. |
| `alembic/script.py.mako` | Plantilla usada al generar nuevos archivos de migración. |
| `alembic/versions/` | Carpeta donde viven las migraciones generadas (`alembic revision --autogenerate`). |
| `alembic/versions/7af12c8d9e30_device_request_nonces.py` | Crea el registro persistente de nonces por dispositivo para evitar reenvios RFID. |
| `alembic/versions/c9416d23eab0_item_details.py` | Agrega ubicacion y especificaciones tecnicas a los articulos existentes sin alterar sus registros previos. |
| `alembic/versions/d84f6a20c13b_item_decommissions.py` | Crea el historial normalizado de bajas, relacionado univocamente con el articulo y el administrador. |
| `alembic/versions/e2b781af9c44_warehouse_request_rejection.py` | Agrega a las solicitudes el usuario, fecha y motivo de rechazo; downgrade reversible. |
| `alembic/versions/9c0d2a7e4b61_user_preferences.py` | Crea preferencias personales de reportes y alertas, con defaults y downgrade reversible. |
| `tests/test_security.py` | Pruebas de sesion en rutas sensibles, autenticacion WebSocket y rechazo de eventos RFID repetidos o alterados. |
| `tests/test_items.py` | Pruebas de validacion, roles, alta de articulos, auditoria y codigos duplicados. |
| `tests/test_movements.py` | Pruebas de referencias normalizadas, transiciones de prestamo/devolucion, permisos, auditoria y reintentos. |
| `tests/test_decommissions.py` | Pruebas de baja administrativa, historial relacional, contrasena, auditoria y bloqueo por movimientos activos. |
| `tests/test_users.py` | Pruebas de administracion de cuentas, preferencias aisladas por usuario, valores permitidos y respuestas sin hashes. |
| `tests/test_reports.py` | Pruebas de ventanas y métricas semanales/mensuales, resumen de solo lectura y exportación PDF con metadatos auditados. |
| `tests/test_requests.py` | Pruebas de alta, relaciones normalizadas, categorías, auditoría, aprobación/rechazo/envío, transiciones duplicadas y permisos. |

## `backend/app/`
| Archivo | Qué hace |
|---|---|
| `main.py` | Punto de entrada FastAPI: CORS, router `/api/v1`, WebSocket `/ws/alerts` con origen permitido y access token como primer mensaje, `/health`. |

### `app/core/` — configuración y seguridad transversal
| Archivo | Qué hace |
|---|---|
| `config.py` | Carga `Settings` desde variables de entorno (`pydantic-settings`): BD, JWT, clave de cifrado de secretos de dispositivo, CORS, Redis. |
| `security.py` | Hash/verify de contraseñas (bcrypt), JWT con PyJWT, cifrado Fernet y mensaje canonico para HMAC de eventos IoT (identidad, hora, nonce, metodo, ruta y SHA-256 del cuerpo). |
| `zero_trust.py` | Dependencia `verify_device_request`: exige `X-Device-Id`, `X-Timestamp`, `X-Nonce` y `X-Signature`; verifica HMAC y registra un nonce unico por dispositivo para impedir replay. |

### `app/db/` — acceso a datos
| Archivo | Qué hace |
|---|---|
| `session.py` | Engine de SQLAlchemy, `SessionLocal` y `Base` declarativa. |
| `base.py` | Importa todos los modelos en un solo módulo para que Alembic detecte el metadata completo. |

### `app/models/` — entidades de dominio (SQLAlchemy ORM)
| Archivo | Qué hace |
|---|---|
| `role.py` | Roles del sistema (`administrador`, `jefe_area`, `encargado_inventario`). |
| `user.py` | Usuarios de la app, vinculados a un rol. |
| `user_preferences.py` | Periodo predeterminado de reportes y filtros iniciales de alertas, asociados uno-a-uno con el usuario. |
| `biometric_template.py` | Referencia (no la huella cruda) al template biométrico enrolado en un dispositivo lector. |
| `item.py` | `Category` e `Item` (herramienta/material): codigo, tag RFID, categoria, ubicacion, especificaciones tecnicas y estado. |
| `location.py` | Ubicaciones/áreas donde se usa el material. |
| `movement.py` | Movimiento de salida/devolución: responsable, autorizador, ubicación, propósito, método de autorización, timestamps y duración calculada. |
| `alert.py` | Alertas de salida no autorizada u otras fallas, con flujo de resolución (quién y cómo la desactivó). |
| `device.py` | Dispositivos de hardware con secreto HMAC cifrado y estado, y nonces consumidos de peticiones firmadas. |
| `rfid_event.py` | Eventos crudos de paso por RFID (entrada/salida), enlazados a un movimiento cuando corresponde. |
| `warehouse_request.py` | Solicitudes de reabastecimiento y líneas normalizadas; conserva referencias de aprobación/rechazo y motivo. |
| `report.py` | Metadatos de reportes periódicos generados. |
| `audit_log.py` | Bitácora de auditoría append-only de toda acción sensible (principio Zero Trust de trazabilidad total). |

### `app/schemas/` — contratos Pydantic (API)
| Archivo | Qué hace |
|---|---|
| `auth.py` | `Token`, `TokenRefreshRequest`, `MovementAuthorizationRequest` (huella o password del jefe). |
| `user.py` | `UserCreate` / `UserRead` sin hashes, `RoleRead` y confirmación administrativa para activar/desactivar cuentas. |
| `preferences.py` | Contratos de lectura/actualizacion de preferencias personales con opciones estrictamente validadas. |
| `item.py` | `ItemCreate` / `ItemRead` y ficha tecnica validada; codigo opcional al crear y generado en backend cuando se omite. |
| `movement.py` | `MovementCreate`, `MovementRead` con etiquetas relacionadas y opciones autenticadas para responsables y ubicaciones. |
| `decommission.py` | Solicitud y respuesta de baja con límites de entrada y etiquetas derivadas de relaciones ORM. |
| `report.py` | Resumen de tres periodos calculado desde movimientos y alertas existentes; no persiste agregados. |
| `alert.py` | `AlertRead` / `AlertDeactivateRequest`. |
| `device.py` | Registro de dispositivos y payloads de eventos RFID/biométricos entrantes. |
| `warehouse_request.py` | Validación de líneas y motivo de rechazo; lectura con etiquetas derivadas de relaciones ORM. |

### `app/api/` — capa HTTP
| Archivo | Qué hace |
|---|---|
| `deps.py` | `get_db`, `get_current_user` (revalida el usuario en BD en cada request), `require_roles(...)`. |
| `v1/router.py` | Agrega todos los routers de `v1/endpoints/` bajo `/api/v1`. |
| `v1/endpoints/auth.py` | Login (`/auth/token`) y refresh de tokens. |
| `v1/endpoints/users.py` | Alta, listado, catálogo de roles, edición y activación/desactivación admin-only; preferencias autenticadas limitadas a la cuenta actual. |
| `v1/endpoints/items.py` | Alta de articulos, listado y busqueda; baja admin-only con reautenticacion, bloqueo de movimientos activos, historial normalizado y auditoria atomica. |
| `v1/endpoints/movements.py` | Opciones e historial autenticados; creación, autorización por jefe y devolución para administrador/encargado. Valida referencias y estados, permite volver a prestar artículos `devuelta`, evita salidas/devoluciones duplicadas y guarda cada transición junto con su auditoría en una transacción; rechaza huellas hasta contar con prueba firmada del lector. |
| `v1/endpoints/alerts.py` | Listado de alertas y desactivacion por contrasena (solo administrador autenticado); huella temporalmente deshabilitada. |
| `v1/endpoints/devices.py` | Alta de dispositivos (admin) e ingesta de eventos RFID protegida con `verify_device_request` (Zero Trust). |
| `v1/endpoints/requests.py` | Alta y listado autenticados; aprobación/rechazo admin-only y envío desde aprobada, con transiciones y auditoría atómicas. |
| `v1/endpoints/reports.py` | Resumen semanal/mensual y PDF del historial de movimientos por rol; filtra por fechas, estado, artículo/categoría, ubicación y responsable; limita 12 meses y 5,000 movimientos, guarda metadatos/auditoría y no almacena el PDF. |

### `app/services/` — lógica de negocio reutilizable
| Archivo | Qué hace |
|---|---|
| `audit_service.py` | `record_audit(...)`: escribe entradas inmutables en `audit_logs`; admite compartir la transacción de una operación crítica. |
| `rate_limit_service.py` | Limite atomico compartido en Redis para exportaciones PDF; falla cerrado cuando Redis no esta disponible. |
| `alert_service.py` | `raise_unauthorized_exit_alert(...)`: crea la alerta y la transmite en vivo por WebSocket. |

### `app/ws/` — tiempo real
| Archivo | Qué hace |
|---|---|
| `connection_manager.py` | Registra solo conexiones WebSocket ya autenticadas, en memoria (single-instance); Redis pub/sub sigue pendiente. |

## Contrato de seguridad para clientes

- Un cliente de `/ws/alerts` debe abrir la conexion desde un origen en `ALLOWED_ORIGINS` y enviar su JWT de acceso como **primer mensaje** en un maximo de 5 segundos. Si falla, el servidor cierra con codigo 1008; el token no debe ir en la URL.
- Para `POST /api/v1/devices/events/rfid`, generar `X-Nonce` con 16 bytes aleatorios expresados como 32 caracteres hexadecimales minusculos. Firmar con HMAC-SHA256 y el secreto del dispositivo el mensaje `device_id.timestamp.nonce.METHOD./ruta.sha256_hex(cuerpo_crudo)`. Usar la ruta real `/api/v1/devices/events/rfid`, `METHOD=POST`, timestamp Unix en segundos y el cuerpo JSON exactamente como se transmite. Enviar el resultado hexadecimal en `X-Signature` junto con `X-Device-Id`, `X-Timestamp` y `X-Nonce`. No reutilizar un nonce; aplicar la migracion antes de conectar lectores.

---

## Convenciones para mantener este archivo
1. Todo archivo nuevo bajo `backend/` se agrega a la tabla correspondiente en el mismo commit/cambio.
2. Si un archivo cambia de responsabilidad (no solo detalles internos), se actualiza su descripción.
3. Si un archivo se elimina, se borra su fila.
4. Las carpetas nuevas (ej. `frontend/` de Alejandro) se documentan en un archivo `MODULES.md` propio de esa carpeta, o se agrega una sección nueva aquí si aplica al backend.
