$vmIp = Read-Host "Pega aquí la Public IPv4 address de la VM Oracle"
Test-NetConnection -ComputerName $vmIp -Port 22# Roadmap de SIGMAT

Actualizado: 2026-10-07

## Objetivo

Completar el MVP y preparar SIGMAT para su publicacion en Internet, manteniendo los datos del negocio en almacenamiento persistente del servidor. PostgreSQL conserva los datos; Redis se usa para controles temporales y coordinacion. El entorno local actual usa PostgreSQL nativo en WSL y Redis local; Docker Compose define una alternativa de contenedores. Ninguno es una publicacion de produccion.

## Alcance congelado (2026-10-07)

Todas las funciones del MVP estan implementadas y probadas (fases 1 y 2 completas). Desde esta fecha el alcance esta **congelado**: no se agregan tareas nuevas, solo se cierran las de esta lista.

**Cierre del MVP (4 tareas)**

- [x] **Cierre 1. Migraciones desde una base vacia:** crear una base nueva, aplicar todas las migraciones, sembrar el administrador y comprobar que la API y el esquema quedan correctos. Es lo que hara una instalacion nueva del cliente.
- [x] **Cierre 2. Recorrido en el navegador por rol:** administrador, jefe de area y encargado de inventario recorren sus pantallas; incluye preferencias entre sesiones y que no queden controles falsamente habilitados.
- [x] **Cierre 3. Restauracion de respaldo local:** generar un respaldo, restaurarlo en una base vacia y comparar conteos de tablas.
- [x] **Cierre 4. Revision transversal de seguridad y cierre documental:** lista de verificacion aprobada; secretos, credenciales de desarrollo, CORS, cabeceras y dependencias revisados. La regla global de `pg_hba.conf` se retiró y verificó (P-19).

**Reglas del congelamiento**

- Un hallazgo nuevo solo entra si bloquea una de las 4 tareas o es un defecto de seguridad o de integridad de datos; lo demas se anota en la seccion de pospuestos.
- Todo lo que depende de hardware, de un servidor con dominio o de una decision institucional queda fuera del MVP y se retoma al contar con ese recurso.

## Estado implementado

- [x] Inventario, movimientos, bajas, alertas, reportes y administracion de usuarios conectados al backend.
- [x] Preferencias por usuario: periodo predeterminado de reportes y filtros iniciales de alertas, persistidos en PostgreSQL y aislados de permisos.
- [x] Solicitudes de almacen: alta, historial, aprobacion, rechazo con motivo y transicion a enviada; cambios auditados.
- [x] Reporte semanal/mensual en PDF con acceso por rol, auditoria, proteccion contra cache y `nosniff`.
- [x] Limite compartido de 5 exportaciones PDF por usuario cada 60 segundos con Redis; responde `429` al excederlo y falla cerrado con `503` si Redis no esta disponible.
- [x] Promedio de uso calculado en SQL, sin cargar todos los movimientos cerrados en memoria.
- [x] JWT con PyJWT; `pip-audit` no encontro vulnerabilidades conocidas en las dependencias declaradas al 2026-10-07 (P-19).
- [x] Docker Compose define PostgreSQL con volumen persistente, servicio de respaldo local con retencion y Redis interno; en el entorno de desarrollo actual PostgreSQL y Redis corren nativamente en WSL.

## Fase 1: Cerrar decisiones del MVP

- [x] Preferencias independientes por usuario, persistidas en PostgreSQL; no cambian permisos ni politicas globales.
- [x] Primera version de Preferencias: periodo predeterminado de reportes y filtros iniciales de alertas; estos filtros no suprimen eventos ni su auditoria.
- [x] PDF para historial de movimientos, no una fotografia estatica del inventario.
- [x] PDF bajo demanda y sin conservar el archivo; PostgreSQL conserva metadatos de exportacion y auditoria.
- [x] Rango seleccionable de hasta 12 meses por descarga; periodos menores, incluido un mes, siguen permitidos.
- [x] Contenido propuesto: identificador y fechas del movimiento, articulo/categoria, responsable, autorizador, ubicacion, proposito y estado.
- [x] Filtros propuestos: fechas, estado, articulo/categoria, ubicacion y responsable.
- [x] Regla provisional: PDF generado bajo demanda y no conservado; no hay borrado automatico de movimientos, metadatos ni auditorias mientras SIGMAT sea la unica fuente.
- [ ] (Externo, no bloquea el cierre tecnico) Validar con Archivo/Juridico de OAPAS la clasificacion documental y el plazo definitivo de movimientos, metadatos de reportes y bitacora de auditoria. No implementar purga automatica antes de esa validacion.

**Criterio de salida:** decisiones aprobadas y criterios de aceptacion escritos antes de implementar.

## Fase 2: Completar las funciones aprobadas

- [x] Implementar Preferencias por usuario: periodo predeterminado de reportes y filtros iniciales de alertas.
- [x] Implementar endpoint y descarga PDF bajo demanda del historial de movimientos, con el contenido, filtros y limite de 12 meses acordados; no guardar una copia del archivo.
- [x] Mantener la bitacora de auditoria como fuente tecnica; el PDF es auxiliar y no la sustituye. La exportacion guarda metadatos y auditoria.
- [x] Limitar cada PDF a 5,000 movimientos; si se excede, responder `413` sin truncar ni crear metadatos de exportacion.

**Criterio de salida:** cada funcion cumple sus criterios, permisos por rol y auditoria esperada; no quedan controles de interfaz falsamente habilitados.

## Fase 3: Validacion de aceptacion

- [x] **[Cierre 2]** Probar desde navegador los flujos por rol: inventario, movimientos, usuarios, solicitudes, alertas y reportes; ciclo de movimiento completo (P-18).
- [x] **[Cierre 2]** Verificar preferencias por usuario entre sesiones y cuentas, incluyendo valores inválidos y persistencia después de volver a iniciar sesión (P-18).
- [x] Verificadas respuestas 401/403/409, transiciones invalidas, auditoria y validacion de entrada contra la API real (cubierto por P-10, P-11 y P-15).
- [x] Probar en backend y navegador simulado el PDF: filtros, fechas inclusivas, rango maximo de 12 meses, cabeceras, descarga y limite de 5,000 movimientos.
- [x] Ejecutado end-to-end contra la API y PostgreSQL reales (2026-10-05): descarga desde el navegador `200` con cabeceras de seguridad, auditoria y metadato sin ruta de archivo; `401` sin sesion, `422` por rango mayor a 12 meses o fechas invertidas, `503` con Redis apagado y `429` a la sexta descarga por minuto; los rechazos no crearon registros.
- [x] Verificado contra la API real (2026-10-05) el control de acceso por rol en 15 rutas con los tres roles, `401` sin sesion o con token invalido, y que una cuenta desactivada pierde el acceso aunque su token siga vigente (60 de 60 comprobaciones; ver `docs/PRUEBAS_Y_VALIDACION.md`).
- [x] Verificado contra la API real `413` a los 5,001 movimientos sin crear metadatos (2026-10-05).
- [x] Ciclo de negocio completo contra la API real (movimientos, bajas y solicitudes, 53 comprobaciones). Hallo un defecto de concurrencia al autorizar salidas, ya corregido con bloqueo de filas y prueba de regresion (ver P-12 en `docs/PRUEBAS_Y_VALIDACION.md`).
- [x] Corregido defecto de marcas de tiempo congeladas en 13 columnas (la auditoria no registraba la hora real); migracion `b3f4a8c21d57` y prueba de regresion (ver P-14 en `docs/PRUEBAS_Y_VALIDACION.md`).
- [x] Decidido el tratamiento de registros con fecha falsa: en esta base de desarrollo no se reconstruyen y se documentan como limitacion (P-14); una instalacion nueva parte de la migracion corregida.
- [x] Probada la concurrencia en altas de articulos, desactivacion de usuarios y resolucion de alertas (2026-10-05): dos defectos corregidos (errores falsos al crear categoria o ubicacion nuevas e interbloqueo al desactivarse dos administradores a la vez) y verificado que siempre queda un administrador activo (P-15).
- [ ] (Pospuesto) Probar concurrencia en la reactivacion simultanea de usuarios y en las rutas de dispositivos y eventos RFID. Motivo: la reactivacion usa el mismo bloqueo de filas ya verificado en la desactivacion; las rutas RFID requieren hardware.
- [ ] (Pospuesto) Retirar de la base de desarrollo los registros de exportacion de prueba solo cuando exista una politica de retencion aprobada; no borrar auditoria manualmente.
- [x] **[Cierre 1]** Validar migraciones desde una base vacia y desde una version previa con datos conservados.
- [x] Prueba de carga basica de un solo usuario (2026-10-05): el PDF de 5,000 movimientos tarda unos 11 s.
- [ ] (Pospuesto) Prueba de carga con usuarios concurrentes y revision de recursos del servidor. Motivo: requiere un entorno comparable al de produccion; la limitacion queda registrada en P-13.

**Criterio de salida:** pruebas automatizadas y pruebas de navegador aprobadas; riesgos restantes registrados y aceptados.

## Fase 4: Resiliencia y operacion

- [x] **[Cierre 3]** Probar una restauracion de respaldo local: generar un respaldo, restaurarlo en una base vacia y comparar conteos de tablas.

**Resto de la fase: pospuesto hasta contar con un servidor.** Las tareas siguientes dependen del entorno de produccion.

- [ ] Copiar los respaldos fuera del host y probar periodicamente una restauracion. El volumen local actual no protege ante perdida del equipo.
- [ ] Definir monitorizacion, alertas operativas, retencion de logs y procedimiento de respuesta a incidentes.
- [ ] Definir limite de memoria y politica de Redis para produccion. Las claves de limite expiran a los 60 segundos; si Redis queda sin memoria, el endpoint debe seguir fallando cerrado.
- [ ] Si se ejecutaran varias instancias del backend, mover WebSocket/pub-sub a Redis; hoy las conexiones viven en memoria de una sola instancia.

**Criterio de salida:** respaldo restaurable, salud de servicios observable y comportamiento ante caidas documentado.

## Fase 5: Integracion fisica

**Fuera del alcance del MVP:** se retoma al disponer del hardware.

- [ ] Integrar RFID cuando esten disponibles los lectores y el entorno de prueba.
- [ ] Integrar biometria con hardware real, prueba de autenticidad del lector y manejo seguro de plantillas; no almacenar imagenes crudas de huellas.
- [ ] Probar TLS, autenticacion de dispositivo, proteccion contra replay, desconexion y auditoria con los equipos reales.

**Bloqueo:** requiere adquisicion y disponibilidad del hardware elegido (por ejemplo AS608 + ESP32 para prototipo).

## Fase 6: Publicacion en Internet

**Fuera del alcance del MVP:** lista de verificacion para publicar SIGMAT en Oracle Cloud con servidor y dominio.

### Despliegue en Oracle Cloud

- [ ] Confirmar region, disponibilidad y recursos de la VM Always Free; revisar consumo y posibles cargos en la consola.
- [ ] Crear una VM Linux con acceso SSH por llave; permitir solo SSH restringido y trafico web por 80/443 en Oracle Cloud y en el firewall del sistema. No exponer PostgreSQL, Redis ni los puertos de desarrollo.
- [ ] Preparar Docker Compose para produccion: retirar el montaje de codigo de desarrollo y mantener PostgreSQL y Redis accesibles solo desde la red privada de contenedores.
- [ ] Configurar Nginx como proxy inverso: servir el frontend estatico, dirigir `/api/v1` a FastAPI y `/ws/alerts` al WebSocket.
- [ ] Configurar DNS y HTTPS para el dominio; establecer CORS con el origen HTTPS real.
- [ ] Configurar secretos unicos de produccion y `ENVIRONMENT=production`; no reutilizar valores de ejemplo ni incluir secretos en el repositorio.
- [ ] Resolver la cuenta semilla: eliminar la contrasena fija de desarrollo y crear una cuenta administradora con credenciales seguras antes de abrir el acceso publico.
- [ ] Aplicar migraciones, inicializar roles y validar salud, inicio de sesion, API y alertas en tiempo real.
- [ ] Guardar respaldos fuera de la VM y probar una restauracion; verificar que los datos persisten tras reiniciar la instancia.
- [ ] Hacer una prueba final desde Internet y confirmar que solo esten publicos el sitio y HTTPS, y que la aplicacion vuelva a funcionar despues de reiniciar la VM.

**Criterio de salida:** dominio HTTPS activo, datos persistentes y restaurables, servicios internos no expuestos y checklist de lanzamiento firmado.

## Definicion de terminado

Una tarea se marca completa cuando tiene criterios de aceptacion, pruebas aprobadas, permisos y auditoria verificados, documentacion actualizada y ningun secreto incluido en el repositorio. Las tareas bloqueadas por hardware o proveedor deben permanecer identificadas como bloqueadas, no como terminadas.

## Mantenimiento del roadmap

- Si una tarea se pospone, registrar el motivo, la dependencia o decision que la bloquea y el siguiente paso para retomarla.
- Marcar una tarea completa solo cuando el cambio exista y su validacion correspondiente haya pasado.
- Al ejecutar una prueba determinante, registrar su resultado en `docs/PRUEBAS_Y_VALIDACION.md` y mover ahi el punto correspondiente de sus pendientes.
- Mantener este archivo como fuente unica de pendientes; no duplicar listas de trabajo en otras guias.
