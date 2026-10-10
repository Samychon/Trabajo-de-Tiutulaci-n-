# Tecnologias y componentes implementados en el proyecto

## 1. Descripcion general

El proyecto consiste en un sistema backend para el control y monitoreo de inventario mediante RFID, lectores biometricos, codigos de barras o QR, dispositivos IoT, alertas, solicitudes de reabastecimiento y reportes.

El backend centraliza la informacion del inventario, valida usuarios y dispositivos, controla permisos y registra las operaciones realizadas.

## 2. Herramientas de desarrollo

### IDE

- Visual Studio Code.
- Terminal integrada de VS Code.
- Extensiones para Python.
- Extensiones para SQL y Markdown.
- Herramientas de depuracion y navegacion de codigo.

### Control de versiones

- Git.
- Repositorio remoto para almacenar el codigo.
- Archivo `.gitignore` para excluir entornos virtuales, archivos `.env`, caches y archivos temporales.

## 3. Lenguajes utilizados

### Python

Se utiliza como lenguaje principal para el backend, la API, la seguridad, el acceso a la base de datos, los modelos ORM, los servicios de negocio, las migraciones y los scripts de inicializacion.

### SQL

Se utiliza para crear usuarios y bases de datos PostgreSQL, consultar informacion, definir tablas, establecer relaciones e indices y administrar permisos.

### Bash

Se utiliza dentro de WSL2 para instalar PostgreSQL, iniciar servicios, revisar puertos, ejecutar respaldos y restaurar bases de datos.

### PowerShell

Se utiliza en Windows para crear entornos virtuales, instalar dependencias, ejecutar migraciones, iniciar el backend y realizar pruebas HTTP.

### YAML

Se utiliza en `docker-compose.yml` para definir servicios, puertos, volumenes y variables de contenedores.

### Markdown

Se utiliza para la documentacion tecnica, el manual de instalacion, el mapa de modulos y la documentacion de la tesis.

## 4. Framework y servidor web

### FastAPI

FastAPI es el framework principal del backend. Permite crear endpoints HTTP, validar datos, generar documentacion OpenAPI, implementar dependencias de seguridad y crear WebSockets.

Endpoints principales:

- `/health`
- `/docs`
- `/api/v1/auth/token`
- `/api/v1/users`
- `/api/v1/items`
- `/api/v1/movements`
- `/api/v1/alerts`
- `/api/v1/devices`
- `/api/v1/requests`
- `/api/v1/reports`
- `/ws/alerts`

### Uvicorn

Uvicorn se utiliza como servidor ASGI para ejecutar FastAPI.

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

## 5. Arquitectura del backend

El backend utiliza una arquitectura por capas:

- Configuracion.
- Seguridad.
- Acceso a datos.
- Modelos.
- Esquemas.
- API.
- Servicios.
- Comunicacion en tiempo real.

### Configuracion

`backend/app/core/config.py` administra la URL de PostgreSQL, las claves de seguridad, los origenes CORS, Redis y el ambiente de ejecucion.

### Base de datos

`backend/app/db/session.py` crea el engine y las sesiones de SQLAlchemy. `backend/app/db/base.py` registra todos los modelos para que Alembic detecte el metadata completo.

### Modelos

Los modelos representan las tablas de PostgreSQL mediante SQLAlchemy.

### Esquemas

Los esquemas Pydantic definen y validan los datos recibidos y enviados por la API.

### Servicios

Los servicios contienen logica reutilizable, como el registro de auditoria y la creacion de alertas.

### API

Los endpoints se agrupan bajo `/api/v1`. El versionamiento permite evolucionar la API sin romper clientes existentes.

## 6. Base de datos

### PostgreSQL

PostgreSQL es el sistema gestor de base de datos relacional utilizado.

Caracteristicas implementadas:

- Claves primarias.
- Claves foraneas.
- Restricciones de unicidad.
- Indices.
- Enumeraciones.
- Relaciones entre entidades.
- Fechas con zona horaria.
- Campos JSON.
- Control de estados.

Configuracion utilizada:

```text
Usuario: ipi2_user
Base de datos: ipi2_inventario
Puerto: 5432
```

### SQLAlchemy

SQLAlchemy se utiliza como ORM para trabajar con objetos Python y mantener las relaciones entre los modelos.

Beneficios:

- Consultas parametrizadas.
- Menor riesgo de inyeccion SQL.
- Relaciones entre modelos.
- Reutilizacion de sesiones.
- Integracion con Alembic.

### Alembic

Alembic controla la evolucion de la estructura de la base de datos.

```powershell
python -m alembic upgrade head
```

```powershell
python -m alembic revision --autogenerate -m "esquema inicial"
```

### Entidades principales

- `roles`
- `users`
- `categories`
- `locations`
- `items`
- `devices`
- `biometric_templates`
- `movements`
- `alerts`
- `rfid_events`
- `warehouse_requests`
- `warehouse_request_items`
- `reports`
- `audit_logs`

## 7. Inventario

El sistema permite administrar herramientas y materiales, categorias, codigos internos, tags RFID, estados, ubicaciones, descripciones y fotografias o URLs asociadas.

El alta desde la interfaz envia categoria, ubicacion, descripcion funcional y especificaciones tecnicas al backend. El backend asigna el codigo si se omite, valida permisos y unicidad, conserva los datos en PostgreSQL y audita la creacion. El frontend integra inventario, movimientos, bajas, alertas, reportes PDF, solicitudes de almacén y administración de usuarios.

Las bajas conservan la fila de inventario y sus movimientos. Un registro uno-a-uno almacena motivo, descripción, notas, fecha y administrador; la clave foránea mantiene la relación sin copiar nombre o código del artículo. La operación valida reautenticación administrativa y ausencia de movimientos pendientes/abiertos, y confirma el cambio de estado junto con la auditoría en una transacción.

La administración de usuarios permite al administrador consultar cuentas activas y roles registrados y crear usuarios con contraseña inicial validada. Las contraseñas se guardan hasheadas con bcrypt, no aparecen en las respuestas y el alta queda auditada junto con su registro.

El administrador puede editar los datos y el rol de otros usuarios y restablecer su contraseña con validaciones y auditoría. La desactivación y reactivación son lógicas (`is_active`): conservan referencias históricas, exigen reautenticación y registran cada cambio en auditoría.

Los indicadores semanales y mensuales se calculan bajo demanda desde movimientos y alertas normalizados: salidas, devoluciones, incidentes, promedio de uso y artículo más utilizado, junto con dos periodos comparativos. Se puede descargar un PDF autenticado; su metadato y auditoría se guardan, pero el archivo se genera en memoria y no se conserva en el servidor. No se almacenan copias agregadas que puedan divergir de las tablas fuente.

Estados de los articulos:

- Disponible.
- En uso.
- Devuelta.
- Baja.

La busqueda puede realizarse por codigo o tag RFID.

## 8. Control de movimientos

Un movimiento representa la salida o devolucion de un articulo. Registra el articulo, usuario responsable, usuario autorizador, ubicacion, proposito, metodo de autorizacion, fechas y estado.

La interfaz permite seleccionar articulos disponibles o devueltos, usuarios activos y ubicaciones registradas; el backend valida referencias y evita salidas pendientes duplicadas. La salida se crea pendiente y solo pasa a abierta/en uso tras la autenticacion por contraseña de un jefe de area. Para devolver, un administrador o encargado cierra el movimiento abierto y el articulo pasa a estado `devuelta`, que sigue siendo elegible para un nuevo prestamo. Cada transicion y su auditoria se confirman en la misma transaccion; las relaciones se conservan por claves foraneas, sin duplicar nombres en el movimiento. El historial y los articulos en uso se consultan desde la API. El cierre RFID sigue contemplado para la integracion fisica futura.

Estados:

- Pendiente de autorizacion.
- Abierto.
- Cerrado.

Metodos de autorizacion:

- Contrasena.
- Huella digital.

## 9. Usuarios y roles

El sistema utiliza control de acceso basado en roles.

Roles principales:

- `administrador`
- `jefe_area`
- `encargado_inventario`

Funciones relacionadas:

- Crear usuarios.
- Consultar el usuario actual.
- Validar que el usuario este activo.
- Restringir operaciones segun el rol.
- Autorizar movimientos.
- Resolver alertas.
- Aprobar solicitudes.

## 10. Autenticacion

### Contrasenas

Las contrasenas no se almacenan en texto plano. Se utiliza Passlib con bcrypt para generar hashes irreversibles y verificar credenciales.

### JWT

El sistema utiliza JSON Web Tokens para autenticacion.

Se generan access tokens y refresh tokens con identidad del usuario, rol, tipo de token, fecha de emision y fecha de expiracion.

El backend valida el token en cada endpoint protegido.

El frontend conserva access y refresh tokens solo en memoria, renueva el access token antes de su expiracion y repite una solicitud una sola vez ante un `401` cuando la renovacion es valida. El WebSocket de alertas se vuelve a autenticar con el access token rotado.

## 11. Modelo Zero Trust

El sistema aplica el principio de no confiar automaticamente y verificar siempre.

No se confia unicamente en la red local, la direccion IP, el dispositivo, el lector biometrico o una sesion anterior.

Controles incluidos:

- Usuario autenticado.
- Usuario activo.
- Rol autorizado.
- Token valido.
- Dispositivo registrado.
- Dispositivo activo.
- Firma HMAC correcta.
- Timestamp valido.
- Prevencion de ataques de repeticion.
- Auditoria de acciones sensibles.

La ingesta RFID ahora firma tambien el metodo, la ruta y el hash del cuerpo y registra un nonce unico por dispositivo para rechazar eventos repetidos. Las autorizaciones biometrica y WebSocket requieren controles adicionales antes de aceptarse.

## 12. Seguridad de dispositivos

Los dispositivos utilizan los encabezados:

```text
X-Device-Id
X-Timestamp
X-Nonce
X-Signature
```

El backend valida que el dispositivo exista y este activo, que el timestamp sea reciente y que la firma HMAC cubra identidad, timestamp, nonce, metodo, ruta y hash SHA-256 del cuerpo. Un nonce repetido se rechaza mediante una restriccion unica en PostgreSQL. El lector debe actualizarse a este contrato antes de enviar eventos.

Los secretos de los dispositivos se almacenan cifrados mediante Fernet.

## 13. Seguridad biometrica

El sistema no esta disenado para almacenar imagenes crudas de huellas digitales. Utiliza una referencia a una plantilla biometrica en la tabla `biometric_templates`.

La tabla relaciona el usuario, el dispositivo lector, el identificador de posicion de la plantilla, su estado y la fecha de enrolamiento.

La validacion biometrica debe mantener la autoridad final en el backend.

Actualmente las solicitudes de autorizacion por huella se rechazan hasta contar con una prueba autenticada del dispositivo asociada a la operacion; sigue disponible la autorizacion por contrasena de un usuario activo con el rol correspondiente.

## 14. Hardware recomendado

La recomendacion para el prototipo de tesis es:

- Sensor biometrico AS608.
- Controlador ESP32.
- Lector RFID.
- Buzzer o indicador de alerta.
- Lector de codigo de barras o QR como componente opcional.

Esta recomendacion es para la integracion futura del prototipo. El hardware fisico todavia debe conectarse y probarse con el backend.

### Integracion propuesta

```text
Sensor biometrico
        |
      ESP32
        |
 Comunicacion segura
        |
 Backend FastAPI
        |
 PostgreSQL
```

El backend debe validar la identidad del dispositivo, la firma del mensaje, el usuario, el rol, la sesion y la operacion solicitada.

## 15. RFID

El sistema contempla eventos RFID para registrar entradas, salidas, tag leido, dispositivo utilizado, fecha y hora, movimiento relacionado, payload original y estado de procesamiento.

Los eventos se almacenan en `rfid_events` y su ingesta esta protegida por la validacion Zero Trust del dispositivo.

## 16. Alertas

El sistema contempla alertas para salidas no autorizadas, fallas de dispositivos y manipulacion de sensores.

Estados:

- Activa.
- Resuelta.

Una alerta puede asociarse con un articulo, movimiento, dispositivo, usuario que la resolvio, metodo de desactivacion y notas de resolucion.

## 17. WebSocket y tiempo real

Se implemento un canal WebSocket para alertas:

```text
/ws/alerts
```

Su objetivo es transmitir alertas al cliente en tiempo real. El gestor actual funciona en memoria para una instancia del backend. Para escalar a varias instancias se recomienda Redis Pub/Sub.

El cliente debe conectarse desde un origen permitido y enviar un access token valido como primer mensaje en cinco segundos; las conexiones no autenticadas no reciben alertas.

## 18. Redis

Redis esta contemplado en la infraestructura mediante:

```env
REDIS_URL=redis://localhost:6379/0
```

Puede utilizarse para publicar alertas, comunicar varias instancias, manejar sesiones temporales, crear colas y distribuir eventos en tiempo real.

## 19. Auditoria

Las operaciones sensibles se registran en `audit_logs`.

La auditoria puede incluir:

- Usuario.
- Dispositivo.
- Accion.
- Entidad afectada.
- Identificador de entidad.
- Direccion IP.
- Detalles en formato JSON.
- Fecha y hora.

Esto proporciona trazabilidad, evidencia para auditoria y apoyo para investigaciones de incidentes.

## 20. CORS

El backend configura CORS para controlar que frontend puede realizar solicitudes.

```env
ALLOWED_ORIGINS=["http://localhost:5173"]
```

En produccion se deben especificar unicamente dominios autorizados.

## 21. Variables de entorno

Las variables sensibles se almacenan en `.env` y no deben publicarse.

```env
DATABASE_URL=postgresql+psycopg2://ipi2_user:<contrasena-unica-generada>@localhost:5432/ipi2_inventario
JWT_SECRET_KEY=<clave-secreta>
DEVICE_SECRET_ENCRYPTION_KEY=<clave-fernet>
ALLOWED_ORIGINS=["http://localhost:5173"]
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=development
```

Nunca se deben publicar contrasenas reales, claves JWT, claves Fernet, secretos HMAC, tokens o credenciales de produccion.

## 22. Entorno de ejecucion

### Windows

Se utiliza como sistema operativo principal para desarrollo.

### WSL2

WSL2 permite ejecutar un entorno Linux dentro de Windows. Se utilizo para ejecutar Ubuntu, instalar PostgreSQL, administrar servicios y revisar puertos.

### PostgreSQL en WSL2

El backend se conecta desde Windows mediante `localhost:5432`.

Comandos utilizados:

```bash
sudo apt update -y
sudo apt install -y postgresql postgresql-contrib
sudo service postgresql start
pg_lsclusters
```

## 23. Entorno virtual de Python

El entorno virtual aisla las dependencias del proyecto de las instalaciones globales de Python.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 24. Docker

El proyecto contiene `docker-compose.yml` y `backend/Dockerfile`.

Docker Compose define servicios para PostgreSQL, Redis, backend y respaldos. El Dockerfile instala automaticamente las dependencias mediante:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```

Sin embargo, durante la validacion real se utilizo Windows, WSL2, PostgreSQL nativo dentro de WSL2 y un entorno virtual local de Python. Docker esta preparado en el proyecto, pero no fue la ruta principal de las pruebas finales.

## 25. Respaldos y recuperacion

El proyecto contempla `pg_dump`, respaldos periodicos, retencion de respaldos y restauracion mediante `pg_restore`.

Scripts relacionados:

- `backend/backup/backup.sh`
- `backend/backup/restore.sh`

La estrategia 3-2-1 todavia requiere copiar los respaldos a una ubicacion externa o a la nube.

## 26. Inicializacion de datos

El archivo `backend/app/seed.py` crea los roles y el usuario administrador inicial.

```powershell
python -m app.seed
```

## 27. Pruebas realizadas

Se validaron los siguientes procesos:

- Importacion del backend.
- Arranque de FastAPI.
- Endpoint `/health`.
- Documentacion Swagger.
- Inicio de sesion.
- Generacion de tokens.
- Creacion de articulos.
- Consulta de articulos.
- Creacion de movimientos.
- Autorizacion de movimientos.
- Consulta autenticada del historial de movimientos.
- Prevencion de salidas pendientes duplicadas.
- Creacion de solicitudes de almacen.
- Aprobacion de solicitudes.
- Conexion con PostgreSQL.
- Aplicacion de migraciones.
- Ejecucion del seed.
- Verificacion de contrasenas.
- Compatibilidad de bcrypt.

Respuestas esperadas:

- `200 OK` para operaciones exitosas.
- `201 Created` para creacion de recursos.
- `401 Unauthorized` para autenticacion invalida.
- Errores de validacion para datos incorrectos.

## 28. Problemas tecnicos resueltos

### Docker bloqueado

La politica organizacional no permitio utilizar Docker Desktop como ruta principal. Se utilizo PostgreSQL dentro de WSL2 y Python desde un entorno virtual local.

### Acceso a PostgreSQL

Se configuro el servicio, el usuario, la base de datos y el acceso TCP/IP para permitir la conexion desde Windows.

### Conflicto entre Passlib y bcrypt

Se resolvio fijando una version compatible:

```powershell
python -m pip install --upgrade bcrypt==4.0.1
```

### Relaciones de SQLAlchemy

Se corrigio el registro de modelos para que SQLAlchemy conociera todas las entidades antes de inicializar las relaciones.

### Conexion a PostgreSQL

Se verificaron el servicio activo, el puerto 5432, la configuracion TCP/IP, el usuario, la base de datos y las credenciales.

## 29. Estado del proyecto

### Implementado y validado

- Backend FastAPI.
- Autenticacion JWT.
- Contrasenas con bcrypt.
- Roles y usuarios.
- Inventario.
- Movimientos.
- Solicitudes de almacen.
- PostgreSQL.
- SQLAlchemy.
- Alembic.
- Auditoria.
- Alertas.
- WebSocket.
- Registro de dispositivos.
- Validacion Zero Trust.
- Eventos RFID.
- Migracion inicial.
- Seed de datos.

### Preparado o contemplado

- Integracion fisica con AS608.
- Integracion fisica con ESP32.
- Implementacion completa del frontend.
- Redis Pub/Sub para multiples instancias.
- Respaldo externo en la nube.
- Despliegue productivo.
- Endurecimiento adicional de infraestructura.

## 30. Conclusiones para la tesis

El proyecto integra conocimientos de ingenieria de software, desarrollo backend, programacion en Python, APIs REST, bases de datos relacionales, SQL, ORM, migraciones, seguridad informatica, Zero Trust, criptografia, IoT, RFID, biometria, automatizacion, administracion de sistemas, documentacion tecnica y pruebas de integracion.

La arquitectura separa la logica de negocio, la seguridad, los dispositivos y la persistencia de datos. Esto facilita la ampliacion futura del sistema y proporciona una base tecnica documentada para la investigacion de tesis.
