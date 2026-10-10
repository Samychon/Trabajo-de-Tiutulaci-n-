# Pruebas y validación de SIGMAT

Registro vivo de las pruebas determinantes del sistema, pensado como evidencia para la tesis. Cada prueba indica qué comprobó, cómo se ejecutó y qué **no** demuestra. Solo se incluyen resultados que se ejecutaron; lo pendiente está en la última sección.

Última actualización: 2026-10-05.

## 1. Alcance y metodología

**Entorno de las pruebas:** desarrollo local en Windows con WSL2 Ubuntu; PostgreSQL 16 y Redis en WSL; API FastAPI y frontend estático. No es un entorno de producción.

**Tipos de evidencia**

| Tipo | Qué prueba | Qué no prueba |
|---|---|---|
| Automatizada (`unittest`) | Reglas de negocio, permisos, validaciones y auditoría con base en memoria | Comportamiento con PostgreSQL ni red reales |
| Navegador con API simulada | Interfaz, flujo del usuario y peticiones que envía el cliente | Respuestas reales del servidor |
| End-to-end real | Navegador, API, PostgreSQL y Redis reales | Carga, ni otros equipos o redes |
| Auditoría de dependencias | Vulnerabilidades conocidas en paquetes declarados | Vulnerabilidades no publicadas |

**Cómo reproducir**

```powershell
# Pruebas automatizadas del backend
Push-Location backend; .\.venv\Scripts\python.exe -m unittest discover -s tests; Pop-Location

# Auditoría de dependencias (requiere pip-audit instalado en el venv)
Push-Location backend; .\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --progress-spinner off; Pop-Location
```

Para levantar los servicios, ver `docs/Inicializar servicio.md`.

## 2. Resumen de resultados

| Indicador | Resultado | Fecha |
|---|---|---|
| Pruebas automatizadas del backend | 45 de 45 aprobadas | 2026-10-05 |
| Auditoría de dependencias | Sin vulnerabilidades conocidas | 2026-10-07 |
| Exportación PDF real (navegador, API, PostgreSQL) | Aprobada | 2026-10-05 |
| Límite de exportaciones con Redis real | Aprobado | 2026-10-05 |
| Matriz de permisos por rol contra la API real | 60 de 60 comprobaciones aprobadas | 2026-10-05 |
| Ciclo de negocio completo contra la API real (movimientos, bajas, solicitudes) | 52 de 53 comprobaciones; 1 defecto de concurrencia hallado y corregido | 2026-10-05 |
| Concurrencia tras la corrección (8 peticiones simultáneas) | 1 éxito de 8 en autorizar y en devolver | 2026-10-05 |
| Generación de PDF con 5,000 movimientos | 11.03 s, 670,139 bytes | 2026-10-05 |
| Marcas de tiempo de la base de datos | Defecto hallado y corregido; filas nuevas con hora real | 2026-10-05 |
| Concurrencia en altas, desactivaciones y alertas | 2 defectos hallados y corregidos; invariante del último administrador verificada | 2026-10-05 |
| Migraciones desde base vacía y desde versión previa con datos | Aprobadas; esquema idéntico al de desarrollo y sin diferencias con los modelos | 2026-10-07 |
| Respaldo local restaurado en una base vacía | Conteos idénticos en las 18 tablas | 2026-10-07 |
| Recorrido de interfaz por rol, preferencias y ciclo de negocio | Aprobado; se corrigió un atajo de salida visible para el jefe de área | 2026-10-07 |

## 3. Pruebas determinantes

### P-01. Dependencia vulnerable en la autenticación JWT

- **Objetivo:** detectar vulnerabilidades conocidas en las dependencias del backend.
- **Método:** `pip-audit` sobre `requirements.txt`.
- **Hallazgo:** `ecdsa 0.19.2` (dependencia de `python-jose`) con el aviso PYSEC-2026-1325 / CVE-2024-23342, un ataque de temporización sobre firmas ECDSA P-256 para el que el proyecto upstream no planea corrección.
- **Análisis:** SIGMAT firma tokens con HS256, no con ECDSA, pero la dependencia seguía instalada sin necesidad.
- **Acción:** reemplazo de `python-jose` por `PyJWT`, con las mismas reglas de emisión y validación de tokens.
- **Resultado tras el cambio:** `pip-audit` reporta que no hay vulnerabilidades conocidas y las 7 pruebas de seguridad siguen aprobadas.
- **Limitación:** el resultado depende de la base de avisos vigente el 2026-10-04.

### P-02. Límite de exportaciones PDF por usuario (control de abuso)

- **Objetivo:** impedir que un usuario genere exportaciones sin límite.
- **Diseño:** contador atómico en Redis con ventana de 60 segundos; 5 exportaciones por usuario. Si Redis no responde, la exportación falla cerrada.
- **Evidencia automatizada:** la quinta petición se permite, la sexta devuelve `429` con `Retry-After`; con Redis caído devuelve `503`.
- **Evidencia real (2026-10-05):** siete peticiones consecutivas contra la API real devolvieron `200, 200, 200, 200, 200, 429, 429`.
- **Evidencia real, Redis apagado:** la API respondió `503` y no creó registros.
- **Limitación:** se probó con un solo usuario y un solo proceso; no se probó concurrencia entre varias instancias.

### P-03. Rango de fechas y zona horaria del reporte de movimientos

- **Objetivo:** que el reporte use fechas del calendario local, incluya ambos extremos y nunca exceda 12 meses.
- **Diseño:** el rango se interpreta en `America/Mexico_City` y se convierte a UTC para consultar.
- **Evidencia automatizada:** el rango del 2025-10-04 al 2026-10-03 se acepta y su inicio equivale a 06:00 UTC; el rango del 2025-10-04 al 2026-10-04 se rechaza con `422`; fechas invertidas también devuelven `422`.
- **Evidencia real (2026-10-05):** rango mayor a 12 meses y fechas invertidas devolvieron `422`.
- **Limitación:** las pruebas automatizadas usan una base en memoria.

### P-04. Descarga real del historial de movimientos en PDF

- **Objetivo:** comprobar el flujo completo desde la interfaz hasta la base de datos.
- **Método:** navegador automatizado inició sesión, abrió Reportes y descargó el PDF con el rango predeterminado de un mes.
- **Resultado:** respuesta `200`; tipo `application/pdf`; `Cache-Control: private, no-store`; `X-Content-Type-Options: nosniff`; archivo descargado de 2,412 bytes con nombre `sigmat-movimientos-<inicio>-<fin>.pdf`; sin errores de JavaScript.
- **Efectos en la base de datos:** un registro en `reports` sin ruta de archivo y una auditoría `report.export_movement_pdf`. El PDF no se conserva en el servidor.
- **Limitación:** el rango de la prueba no contenía muchos movimientos; no mide el rendimiento con volumen.

### P-05. Rechazo por falta de sesión

- **Evidencia real:** la exportación sin token devolvió `401`.
- **Limitación:** los tres roles pueden exportar reportes, por lo que el `403` de esta ruta no es aplicable; el control por rol se comprobó en las demás rutas (ver P-10).

### P-06. Tope de 5,000 movimientos por PDF

- **Objetivo:** proteger al servidor de consultas y archivos excesivos.
- **Evidencia automatizada:** con el tope reducido artificialmente a 1, un reporte con 2 movimientos devuelve `413` y **no** crea metadatos ni auditoría.
- **Evidencia real (2026-10-05):** con 5,001 movimientos en el rango la API devolvió `413` en 0.26 s y el número de metadatos de exportación no cambió (12 antes y después). Con 5,000 devolvió `200` (ver P-13).
- **Limitación:** los 5,001 movimientos eran filas sintéticas duplicadas de un mismo movimiento, creadas directamente en la base de datos y eliminadas al terminar; no representan una distribución real de datos.

### P-07. Renovación de sesión y almacenamiento de tokens

- **Objetivo:** verificar que el cliente renueva el token vencido sin exponerlo.
- **Método:** navegador con API simulada: la primera petición recibe `401`.
- **Resultado:** se renovó el token una sola vez, la petición se repitió con el token nuevo, el WebSocket se volvió a autenticar con el token rotado y `localStorage` quedó vacío (los tokens viven solo en memoria).
- **Limitación:** respuestas simuladas, no del servidor real.

### P-08. Preferencias por usuario

- **Objetivo:** guardar el periodo predeterminado de reportes y los filtros iniciales de alertas sin afectar permisos ni eventos.
- **Evidencia automatizada:** actualizar las preferencias de un usuario no cambia las de otro; valores inválidos se rechazan.
- **Evidencia en navegador (API simulada):** los valores cargan al iniciar sesión, se guardan con `PUT`, los filtros solo cambian las filas visibles y el contador global de alertas pendientes no cambia.
- **Limitación:** falta la prueba entre sesiones reales y cuentas distintas.

### P-09. Incidente de diagnóstico: error de CORS que ocultaba un fallo de base de datos

- **Síntoma:** el navegador mostraba un error de CORS y la pantalla de login rechazaba el acceso.
- **Verificación:** la configuración de CORS era correcta (preflight `200` con el origen permitido). El registro de la API mostró `500` porque no alcanzaba PostgreSQL desde Windows (`connection refused`); el navegador lo presentaba como CORS porque el error no incluía cabeceras.
- **Causa de fondo:** el reenvío de `localhost` entre Windows y WSL no era fiable para PostgreSQL ni Redis.
- **Acción:** ejecutar la API dentro de WSL, junto a sus dependencias.
- **Segundo hallazgo:** en WSL el login seguía con `500` por la incompatibilidad entre `passlib 1.7.4` y `bcrypt 5`. Se fijó `bcrypt>=4.0.1,<5` en `requirements.txt`.
- **Resultado:** login `200` en la API y en el navegador.
- **Lección para la tesis:** un error de CORS en el navegador puede ser un fallo del servidor; conviene revisar siempre el registro del backend.

### P-10. Matriz de permisos por rol contra la API real

- **Objetivo:** comprobar que cada rol solo accede a lo que le corresponde y que una cuenta desactivada pierde el acceso de inmediato.
- **Método:** script que creó dos cuentas temporales (`jefe_area` y `encargado_inventario`) con contraseñas aleatorias generadas en memoria, inició sesión con cada rol y llamó a 15 rutas con los tres roles. Para no modificar datos de negocio, las rutas de escritura se invocaron con identificadores inexistentes (`999999`) o cuerpos vacíos, de modo que el servidor decide el permiso antes de validar o actuar.
- **Interpretación de códigos:** `403` indica rol sin permiso; `404` o `422` indican que el rol sí tiene permiso y la petición falló después por validación o por no existir el recurso.
- **Resultado:** 60 comprobaciones, 0 fallos.

| Ruta | Administrador | Jefe de área | Encargado |
|---|---|---|---|
| Listar usuarios y roles | permitido | `403` | `403` |
| Historial de bajas | permitido | `403` | `403` |
| Aprobar, enviar o rechazar solicitudes | permitido | `403` | `403` |
| Resolver alertas | permitido | `403` | `403` |
| Crear o editar usuarios | permitido | `403` | `403` |
| Crear artículos | permitido | `403` | permitido |
| Crear solicitudes | permitido | `403` | permitido |
| Consultar reportes, solicitudes, alertas e inventario | permitido | permitido | permitido |

- **Sesión y tokens:** sin sesión devolvió `401`; con un token inválido, `401`.
- **Preferencias:** las del jefe se guardaron sin alterar las del encargado ni las del administrador; un periodo y un tipo de alerta inválidos devolvieron `422`.
- **Cuenta desactivada:** el administrador desactivó la cuenta y su token, que seguía vigente, devolvió `401` en la siguiente petición; un nuevo inicio de sesión también devolvió `401`. Esto confirma que el sistema revalida el estado del usuario en cada petición y no confía solo en el token.
- **Efectos en la base de datos:** 2 cuentas de prueba (quedaron inactivas), 2 auditorías `user.create` y 2 `user.deactivate`. No se tocaron inventario, movimientos ni solicitudes.
- **Limitación:** no se probó la ejecución real de las acciones de escritura permitidas, solo que el permiso se concede; esas acciones tienen sus propias pruebas automatizadas. Las rutas de movimientos se probaron aparte en P-11.

### P-11. Ciclo de negocio completo contra la API real

- **Objetivo:** comprobar el recorrido de un artículo y de una solicitud con datos reales en PostgreSQL, incluidos los rechazos y las transiciones inválidas.
- **Método:** script con dos cuentas temporales (jefe de área y encargado) y el administrador. Creó artículos de prueba y ejecutó 53 comprobaciones.
- **Movimientos (ciclo feliz):** crear artículo (`disponible`), crear salida (`pendiente de autorización`), autorizar con contraseña de jefe (`abierto`, artículo `en_uso`, autorizador registrado), devolver (`cerrado`, artículo `devuelta`) y volver a prestar el artículo devuelto.
- **Rechazos verificados:** salida duplicada `409`; contraseña incorrecta `403`; autorizar con credenciales de quien no es jefe `403`; huella (deshabilitada) `403`; el artículo no cambia de estado tras autorizaciones fallidas; autorizar un movimiento ya abierto `400`; prestar un artículo en uso o en baja `400`; devolver dos veces `409`; devolver un movimiento inexistente `404`; el jefe no puede crear salidas ni registrar devoluciones `403`.
- **Bajas:** con salida pendiente `409`; con artículo en uso `409`; por un encargado `403`; con contraseña de administrador incorrecta `403`; baja correcta `201`; repetida `409`; el artículo queda en `baja`.
- **Solicitudes:** crear, aprobar, enviar y rechazar con motivo (que se guarda); categoría inexistente `400`; cantidad cero o sin líneas `422`; rechazo sin motivo `422`; enviar una solicitud no aprobada, aprobar dos veces, rechazar una aprobada y aprobar una rechazada devuelven `409`; solicitud inexistente `404`.
- **Resultado:** 52 de 53 aprobadas; la falla se describe en P-12.
- **Efectos en la base de datos:** artículos y movimientos de prueba, solicitudes de prueba y 2 cuentas temporales (inactivas). No se eliminó ningún registro de auditoría.
- **Limitación:** los artículos y cuentas de prueba permanecen en la base de datos de desarrollo.

### P-12. Defecto de concurrencia al autorizar una salida (hallado y corregido)

- **Hallazgo:** al enviar 3 solicitudes simultáneas para autorizar el mismo movimiento, las 3 devolvieron `200`. La bitácora mostró **3 auditorías** `movement.authorize` para ese movimiento; según el código, cada autorización exitosa reescribe la fecha de salida.
- **Causa:** la autorización leía el movimiento y el artículo sin bloquear las filas, a diferencia de crear y devolver, que ya usaban `SELECT ... FOR UPDATE`. Dos peticiones simultáneas veían ambas el estado `pendiente` antes de que alguna lo cambiara.
- **Por qué las pruebas automatizadas no lo detectaron:** usaban una base en memoria y una sola petición a la vez; solo una carrera real contra PostgreSQL lo expone.
- **Corrección:** bloquear las filas del movimiento y del artículo durante la autorización, sin cambiar los códigos de respuesta. Se añadió una prueba automatizada de regresión (la suite pasó de 40 a 41 pruebas).
- **Verificación tras la corrección:** 8 autorizaciones simultáneas devolvieron un `200` y siete `400`; 8 devoluciones simultáneas, un `200` y siete `409`. La bitácora de ese movimiento tiene exactamente una autorización, una creación y una devolución.
- **Evidencia comparativa:** movimiento 11 (antes) con 3 autorizaciones; movimiento 12 (después) con 1.
- **Pruebas de concurrencia sin defecto:** 3 salidas simultáneas sobre un mismo artículo crearon solo una; 3 devoluciones simultáneas aplicaron solo una; 3 aprobaciones simultáneas de una solicitud aplicaron solo una.
- **Lección para la tesis:** las condiciones de carrera exigen pruebas concurrentes contra la base de datos real; las pruebas unitarias con una base en memoria no las detectan.
- **Limitación:** el movimiento 11 conserva su historial duplicado como registro del defecto; no se alteró la bitácora.

### P-13. Rendimiento del PDF de movimientos con volumen

- **Objetivo:** medir cuánto tarda y pesa el PDF al aumentar el número de movimientos, y comprobar el límite en vivo.
- **Método:** se insertaron filas sintéticas (copias de un movimiento) hasta alcanzar el número indicado dentro del rango de fechas, se descargó el PDF por la API y se midió el tiempo total de la petición. Las filas se eliminaron al terminar.

| Movimientos | Resultado | Tiempo | Tamaño |
|---|---|---|---|
| 100 | `200` | 0.21 s | 15,573 bytes |
| 1,000 | `200` | 1.73 s | 135,177 bytes |
| 5,000 | `200` | 11.03 s | 670,139 bytes |
| 5,001 | `413` | 0.26 s | sin archivo |

- **Interpretación:** el tiempo crece de forma aproximadamente lineal con el número de filas (unos 2 ms por movimiento). El máximo permitido tarda unos 11 s, aceptable para una descarga bajo demanda. El rechazo por exceso es casi inmediato porque la consulta se detiene en 5,001 filas.
- **Efectos en la base de datos:** 3 metadatos y 3 auditorías por las exportaciones exitosas; el `413` no creó ninguno.
- **Limitación:** una sola ejecución por tamaño, un solo usuario, servidor local sin otras cargas y filas repetidas; no es una prueba de carga con usuarios concurrentes ni establece un límite de capacidad.

### P-14. Defecto: marcas de tiempo congeladas en la base de datos (hallado y corregido)

- **Hallazgo:** al revisar la estructura de la tabla de alertas, el valor por defecto de `triggered_at` era una fecha fija (`2026-09-13 23:10:42`) y no la hora actual. La misma fecha aparecía en 13 columnas de 11 tablas. Los datos lo confirmaron: las 49 auditorías, los 5 movimientos, los 12 reportes y las 3 solicitudes tenían exactamente el mismo instante, aunque la hora real era `2026-10-05 23:21`.
- **Causa:** los modelos y la migración inicial declaraban el valor por defecto como el **texto** `"now()"`. PostgreSQL lo evaluó una sola vez al crear la tabla y lo guardó como constante; lo correcto es la función SQL `now()`. Además, `updated_at` usaba `datetime.utcnow`, una hora sin zona horaria sobre una columna con zona horaria.
- **Impacto:** la bitácora de auditoría no registraba cuándo ocurrió cada acción, lo que invalida su valor de trazabilidad. También afectaba funciones: el PDF de movimientos filtra por `created_at`, por lo que una salida creada hoy y aún sin autorizar no aparecía en el rango correcto.
- **Por qué no se detectó antes:** las pruebas automatizadas usan una base en memoria y asignan las fechas a mano; ninguna comprobó la fecha que genera la base real.
- **Corrección:** los 11 modelos usan `func.now()`, `updated_at` usa `onupdate=func.now()`, y una migración (`b3f4a8c21d57`) cambia el valor por defecto de las 13 columnas sin modificar filas existentes.
- **Verificación en la base real:** las 13 columnas muestran `now()`. Una prueba creando usuario, artículo y movimiento produjo marcas de `23:28:22`, a segundos de la hora real; las auditorías tienen instantes distintos y ordenados, y `updated_at` del usuario cambió al desactivarlo.
- **Prueba de regresión:** una prueba automatizada recorre todas las columnas de fecha de todos los modelos y falla si alguna usa texto como valor por defecto (la suite pasó de 41 a 42 pruebas). Se comprobó que la verificación distingue el valor antiguo (texto) del corregido.
- **Limitación y datos históricos:** las filas anteriores a la corrección conservan la fecha falsa y no es posible reconstruir su hora real: 49 auditorías, 5 movimientos, 12 reportes, 3 solicitudes, 5 artículos, 8 usuarios y 1 baja. No se modificaron, porque la bitácora es de solo agregar. Todas son datos de prueba de desarrollo; en un entorno real esto exigiría una nota de integridad.
- **Lección para la tesis:** un defecto de configuración del esquema pasó todas las pruebas unitarias; solo inspeccionar la base de datos real lo expuso. Conviene verificar también que los datos generados por el motor sean los esperados.

### P-15. Concurrencia en altas de artículos, desactivación de usuarios y resolución de alertas

- **Objetivo:** extender a las demás escrituras la prueba que reveló el defecto de P-12. Antes de probar se revisó el código y se anotaron tres sospechas: (1) “buscar y crear” de categoría y ubicación en el alta de artículos, (2) la auditoría del alta registrada fuera de la transacción del artículo y (3) la regla de al menos un administrador activo, que cuenta antes de actuar.
- **Método:** peticiones simultáneas contra la API y PostgreSQL reales, con cuentas temporales y comprobación directa de la base de datos.

| Escenario | Antes de corregir | Después de corregir |
|---|---|---|
| 8 altas con el mismo código | 1 creada, 7 `409`; una sola fila | igual |
| 8 altas válidas con categoría y ubicación nuevas | 1 creada, **7 `409` erróneos**; 1 categoría y 1 ubicación | 8 creadas; 1 categoría, 1 ubicación, 8 auditorías |
| 2 administradores se desactivan entre sí a la vez | 1 `200` y **1 `500`** (interbloqueo) | `200` + `200`, sin error, en 6 rondas |
| 2 únicos administradores se desactivan entre sí | no probado | `200` + `409`; queda exactamente 1 activo |
| 6 resoluciones simultáneas de una alerta | 1 `200`, 5 `400`; 1 auditoría | igual |

- **Defecto A (alta de artículos):** con una categoría o ubicación nueva, varias peticiones válidas buscaban el nombre, no lo encontraban y todas intentaban crearlo; la restricción única de la base de datos protegió la integridad, pero el usuario recibía un `409 ya registrado` sin haber repetido nada. Corrección: creación tolerante a carreras (se intenta en un punto de guardado y, si otra petición ganó, se reutiliza su fila). Además, la auditoría `item.create` se escribe ahora en la misma transacción del artículo, como en las demás rutas; antes un fallo entre ambos pasos podía dejar un artículo sin auditoría.
- **Defecto B (desactivación):** dos administradores desactivándose entre sí producían un interbloqueo en PostgreSQL al registrar la auditoría (cada petición bloqueaba su objetivo y necesitaba leer la fila del otro). Una de las dos respondía `500`. La integridad se mantenía (nunca quedó sin administradores) porque la base abortó una transacción, pero el usuario veía un error. Corrección: bloquear siempre las filas de los administradores en el mismo orden antes de actuar, de modo que las peticiones se serialicen.
- **Pruebas automatizadas añadidas:** tres (creación tolerante a carreras, reutilización de filas existentes y auditoría en la misma transacción); la suite pasó de 42 a 45.
- **Efectos en la base de datos:** artículos, categorías, ubicaciones, una alerta y cuentas temporales de prueba; todas las cuentas quedaron inactivas.
- **Intervención directa en la base de datos:** para probar la regla del último administrador fue necesario desactivar temporalmente a `admin` mediante la API. Al terminar, `admin` se reactivó con una instrucción SQL directa, que **no genera auditoría**; por eso esa reactivación no aparece en la bitácora. En un entorno real se haría con el endpoint de reactivación.
- **Limitación:** la corrección del interbloqueo se verificó en vivo (6 rondas sin error) pero no tiene prueba automatizada, porque el interbloqueo solo ocurre con transacciones reales en PostgreSQL. Tampoco se probó la reactivación simultánea de usuarios.
- **Lección para la tesis:** las restricciones de la base de datos garantizan la integridad, pero no la experiencia del usuario; una carrera puede dejar los datos correctos y devolver errores falsos.
- **Lección para la tesis:** revisar el código antes de probar permitió formular hipótesis concretas y verificarlas, en lugar de probar al azar.

### P-16. Migraciones desde una base vacía y desde una versión previa con datos

- **Objetivo:** comprobar que una instalación nueva (lo que hará el cliente) produce el esquema correcto y que actualizar una base con datos no los pierde.
- **Método:** base PostgreSQL 16 temporal y vacía (`ipi2_migracion_prueba`), seleccionada con la variable `DATABASE_URL` sin tocar el `.env`; la base de desarrollo no se modificó.

| Comprobación | Resultado |
|---|---|
| `alembic upgrade head` desde cero | 7 migraciones aplicadas en orden, sin errores; revisión `b3f4a8c21d57` |
| `alembic check` (esquema contra modelos) | Sin diferencias |
| Comparación con la base de desarrollo (columnas, valores por defecto, restricciones, índices) | 199 elementos en cada una; 0 diferencias |
| Columnas de fecha con `now()` | 13 de 13 |
| Seed del administrador, ejecutado dos veces | Crea 3 roles y 1 usuario; la segunda ejecución no duplica |
| Contraseña inicial del seed | Valida la correcta y rechaza una incorrecta; `created_at` coincide con la hora real |
| Actualización desde la revisión inicial con datos (3 roles, 1 usuario, 1 categoría, 1 ubicación, 2 artículos, 1 movimiento, 1 auditoría) | Conteos idénticos antes y después; valores de los artículos intactos |
| Fila insertada después de actualizar | Recibe la hora real; la fila anterior conserva su fecha congelada |

- **Efectos:** la base temporal se eliminó al terminar, junto con los scripts temporales.
- **Limitaciones:** la prueba de actualización usó pocos datos sintéticos y solo desde la primera revisión; no se midió el tiempo con volúmenes grandes ni se probó la reversión (`downgrade`, que en la última migración es intencionalmente vacío). El inicio de sesión se verificó comprobando el hash del seed, no mediante una API levantada contra la base nueva.
- **Observación:** las filas anteriores a la migración `b3f4a8c21d57` conservan la fecha congelada del defecto de P-14; la migración corrige las filas futuras, no reconstruye las pasadas.
- **Lección para la tesis:** comparar el esquema de una instalación nueva contra el de la base en uso detecta diferencias acumuladas durante el desarrollo que las pruebas unitarias, con base en memoria, no ven.


### P-17. Restauración de respaldo local

- **Objetivo:** comprobar que un respaldo local puede restaurarse en una base PostgreSQL vacía y conserva los registros de todas las tablas.
- **Método:** `pg_dump -F c` de `ipi2_inventario`; restauración de una sola ejecución con `backend/backup/restore.sh` en una base temporal vacía, creada con un nombre único. Se comparó el conteo de cada tabla pública de origen y destino.

| Tabla | Filas (origen/restauración) | Tabla | Filas (origen/restauración) |
|---|---:|---|---:|
| `alembic_version` | 1 / 1 | `alerts` | 2 / 2 |
| `audit_logs` | 102 / 102 | `biometric_templates` | 0 / 0 |
| `categories` | 3 / 3 | `device_request_nonces` | 0 / 0 |
| `devices` | 0 / 0 | `item_decommissions` | 1 / 1 |
| `items` | 17 / 17 | `locations` | 4 / 4 |
| `movements` | 6 / 6 | `reports` | 12 / 12 |
| `rfid_events` | 0 / 0 | `roles` | 3 / 3 |
| `user_preferences` | 1 / 1 | `users` | 27 / 27 |
| `warehouse_request_items` | 5 / 5 | `warehouse_requests` | 3 / 3 |

- **Resultado:** conteos idénticos en las 18 tablas; restauración completada sin errores.
- **Efectos:** la base temporal y el archivo `.dump` se eliminaron; la base de desarrollo no se modificó.
- **Limitación:** valida respaldo lógico y restauración local, no copias fuera del equipo, pérdida física del host, recuperación en producción ni restauración con volúmenes grandes.

### P-18. Recorrido de interfaz por rol y ciclo de negocio

- **Objetivo:** recorrer los flujos de navegador de administrador, jefe de área y encargado; comprobar permisos, preferencias y que los controles de cada rol coincidan con la autorización real.
- **Método:** frontend en `http://localhost:5173/`, API, PostgreSQL y Redis locales. Se crearon por la interfaz dos cuentas temporales (una por cada rol no administrador) y se recorrieron inventario, movimientos, solicitudes, alertas y reportes.

| Comprobación | Resultado |
|---|---|
| Acceso y pantallas por rol | Inicio correcto para los tres roles; las pantallas de inventario, movimientos, solicitudes, alertas e informes cargaron sin respuestas `4xx` |
| Permisos de jefe de área | No puede acceder a bajas, configuración ni crear solicitudes; al inicio el menú bloqueaba la salida, pero el atajo del panel seguía habilitado |
| Corrección del atajo de salida | Atajo deshabilitado por rol y transición de sección protegida; incluso habilitando el botón en el cliente, el jefe permanece en Inicio |
| Permisos de encargado | Puede agregar artículos y registrar salidas/devoluciones; bajas y configuración deshabilitadas; formulario de solicitud visible |
| Preferencias | El administrador guardó `month / resuelta / falla_dispositivo`; los valores persistieron tras cerrar e iniciar sesión. Jefe y encargado conservaron `week / all / all` |
| Valores inválidos | `report_default_period=year` rechazado con `422`; tras volver a iniciar sesión las preferencias válidas seguían intactas |
| Ciclo de movimiento en navegador | Salida creada (`201`), autorizada por el jefe (`200`) y devuelta por el encargado (`200`); movimiento `10008` quedó `CLOSED` |
| Solicitud en navegador | Solicitud `4` creada (`201`), aprobada (`200`) y marcada enviada (`200`); estado final `ENVIADA` |
| Datos estáticos del panel | Se quitó la tarjeta de estados de integración codificados en HTML, que mostraba como pendientes funciones conectadas al backend |
| Preferencias generales | La pestaña permanece deshabilitada y marcada como pendiente de integración |

- **Efectos en la base de datos:** cuentas `qa_cierre2_jefe_20261007` y `qa_cierre2_enc_20261007` creadas y luego desactivadas, no eliminadas; movimiento `10008` y solicitud `4` de prueba, con auditoría conservada. El artículo `2` quedó en `DEVUELTA` (estado que permite volver a prestarlo). Las preferencias del administrador se restauraron a `week / all / all`; no se modificaron alertas.
- **Observación de entorno:** el sitio debe abrirse con `localhost`; `127.0.0.1` no está en `ALLOWED_ORIGINS` y el navegador bloqueó el login por CORS.
- **Limitación:** durante este recorrido se comprobaron las vistas de reportes y alertas, pero no se descargó otro PDF ni se cambió el estado de alertas. La descarga real de PDF ya está cubierta por P-04.

### P-19. Revisión transversal de seguridad y configuración

- **Objetivo:** revisar secretos, credenciales de desarrollo, CORS, exposición local de servicios, cabeceras de reportes y vulnerabilidades conocidas en dependencias; actualizar las guías operativas.
- **Comprobaciones aprobadas:**
	- `backend/.env` está ignorado por Git y no está rastreado; no se imprimieron sus valores.
	- Se eliminó la contraseña compartida de PostgreSQL de configuración, Compose y ejemplos. `DATABASE_URL` es obligatorio y los ejemplos contienen marcadores, no secretos; la contraseña semilla de desarrollo se documenta por separado abajo.
	- Compose exige `POSTGRES_PASSWORD`, publica puertos solo en `127.0.0.1` y `docker compose config --quiet` pasó con una variable temporal. No se iniciaron contenedores.
	- CORS y WebSocket limitan el origen a `http://localhost:5173`; login funciona con `localhost` y el origen `127.0.0.1` es rechazado.
	- Las descargas PDF mantienen `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff` (P-04 y pruebas automatizadas).
	- `pip-audit -r backend/requirements.txt`: sin vulnerabilidades conocidas (2026-10-07).
	- Las guías de instalación y operación describen contraseñas únicas, el secreto local ignorado, el API en WSL/loopback y la contraseña semilla solo para desarrollo.
- **Hallazgo corregido:** PostgreSQL escuchaba en todas las interfaces. Se aplicó `ALTER SYSTEM SET listen_addresses = 'localhost'` y se reinició el servicio; `ss` confirma solo `127.0.0.1:5432`. `pg_isready`, login del navegador y carga de reportes respondieron correctamente después del reinicio.
- **Regla global retirada:** se eliminó `host all all 0.0.0.0/0 md5` de `/etc/postgresql/16/main/pg_hba.conf`. `pg_reload_conf()` devolvió `t` y `pg_hba_file_rules` no encontró reglas con dirección `0.0.0.0`; la verificación de conectividad de PostgreSQL y API se completó el 2026-10-09.
- **Credencial semilla:** el código conserva `admin / Admin123!` para inicialización de desarrollo. La guía la identifica como tal y exige cambiarla antes de dar acceso a otras personas o publicar el servicio; no hay despliegue de producción en este cierre.
- **Limitación:** la auditoría de dependencias cubre únicamente las declaradas; no sustituye un análisis del sistema operativo ni una revisión en un despliegue con dominio y HTTPS.

## 4. Controles de seguridad con evidencia

| Control | Evidencia disponible |
|---|---|
| Autenticación obligatoria en rutas de reportes | Automatizada y real (`401`) |
| Control de acceso por rol | Automatizada y real (matriz de 60 comprobaciones, P-10) |
| Integridad ante peticiones simultáneas (autorizar, devolver, aprobar) | Real: una sola se aplica de 8 simultáneas (P-12) |
| Tope de tamaño de exportación | Automatizada y real: `413` a los 5,001 movimientos (P-06, P-13) |
| Marca de tiempo correcta en la bitácora de auditoría | Real, solo para filas posteriores a la corrección (P-14) |
| Siempre queda al menos un administrador activo, incluso con desactivaciones simultáneas | Real (P-15) |
| Auditoría de alta de artículos dentro de la misma transacción | Automatizada y real (P-15) |
| Revalidación del usuario en cada petición | Real: token vigente de cuenta desactivada devuelve `401` (P-10) |
| Instalación nueva reproducible (migraciones + seed) y sin diferencias con los modelos | Real (P-16) |
| Respaldo local restaurable con conteos conservados | Real en PostgreSQL (P-17); no valida copia externa |
| Navegación por rol sin atajos a secciones restringidas | Real en navegador (P-18) |
| Auditoría atómica de exportaciones | Automatizada y real |
| Límite de frecuencia con falla cerrada | Automatizada y real |
| Cabeceras de protección en descargas | Automatizada y real |
| Tokens solo en memoria | Navegador con API simulada |
| Dependencias sin vulnerabilidades conocidas | Auditoría 2026-10-07 (P-19) |
| PostgreSQL no expuesto fuera de loopback | Real, listener limitado a loopback y sin regla host global en `pg_hba.conf` (P-19) |
| Respuestas sin almacenar el PDF | Real: `file_url` vacío |

## 5. Pruebas pendientes

- Prueba de carga con usuarios concurrentes (P-13 midió un solo usuario).
- Concurrencia en reactivación simultánea de usuarios y en las rutas de dispositivos y eventos RFID.
- Pruebas con hardware RFID y biométrico (depende de disponer del equipo).
- Pruebas en un entorno desplegado con dominio y HTTPS.

## 6. Plantilla para registrar una prueba nueva

```markdown
### P-XX. Título

- **Objetivo:**
- **Método:** (automatizada, navegador simulado o end-to-end real)
- **Resultado:** (valores observados, no suposiciones)
- **Efectos en la base de datos:**
- **Limitación:** (qué no demuestra)
```

Reglas: registrar solo resultados observados, anotar la fecha, y mover cada punto de la sección 5 a la sección 3 cuando se ejecute.
