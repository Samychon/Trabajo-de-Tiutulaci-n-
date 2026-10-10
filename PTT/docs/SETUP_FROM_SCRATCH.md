# Arranque de la base de datos desde cero en una nueva computadora

## Objetivo

Esta guía explica cómo levantar la base de datos del proyecto en una nueva máquina desde cero, usando la misma configuración que validamos en este entorno: Windows + WSL2 + PostgreSQL.

## Requisitos previos

- Windows 11
- WSL2 habilitado
- Ubuntu o Debian dentro de WSL
- Git
- Python 3.12 o 3.14
- acceso a internet para instalar dependencias

## 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd <carpeta-del-proyecto>
```

## 2. Abrir WSL y crear el entorno de PostgreSQL

Ejecuta estas instrucciones desde WSL:

```bash
sudo apt update -y
sudo apt install -y postgresql postgresql-contrib
```

Luego inicia el servicio:

```bash
sudo service postgresql start
```

Verifica el estado:

```bash
pg_lsclusters
```

Debe aparecer un clúster PostgreSQL en línea en el puerto 5432.

## 3. Crear usuario y base de datos del proyecto

Desde WSL:

```bash
sudo -u postgres psql
```

Genera una contraseña única para esta instalación:

```bash
openssl rand -hex 24
```

Dentro de PostgreSQL, crea el usuario y define su contraseña de forma interactiva:

```sql
CREATE ROLE ipi2_user LOGIN;
\password ipi2_user
CREATE DATABASE ipi2_inventario OWNER ipi2_user;
\q
```

## 4. Asegurar acceso desde localhost

La API corre dentro de WSL y se conecta a PostgreSQL por `localhost`; no hace falta exponer PostgreSQL a la red.

Edita el archivo principal de PostgreSQL:

```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
```

Busca la línea:

```conf
listen_addresses = 'localhost'
```

Mantén PostgreSQL limitado a loopback. En `pg_hba.conf`, permite solo conexiones locales con SCRAM:

```conf
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
```

Guarda y reinicia PostgreSQL:

```bash
sudo service postgresql restart
```

Verifica que esté escuchando en el puerto 5432:

```bash
ss -tlnp | grep 5432
```

## 5. Preparar el backend local en WSL

Desde WSL, entra a la carpeta `backend` del repositorio y crea el entorno virtual:

```bash
cd /mnt/c/ruta/al/proyecto/backend
python3 -m venv /home/$USER/.venvs/sigmat
source /home/$USER/.venvs/sigmat/bin/activate
python -m pip install -r requirements.txt
```

El entorno probado en esta máquina es `/home/samu/.venvs/sigmat`. La interfaz estática puede servirse desde Windows; el API y PostgreSQL deben quedar en WSL para conectarse por `localhost`.

## 6. Configurar las variables de entorno

Desde `backend`, copia `.env.example` a `.env`. El archivo `.env` está ignorado por Git. Sustituye la contraseña de la base por el valor aleatorio generado arriba y genera claves propias para JWT y Fernet:

```bash
cp .env.example .env
openssl rand -hex 32
/home/$USER/.venvs/sigmat/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

No reutilices valores del ejemplo ni publiques las claves generadas. La contraseña hexadecimal se puede colocar directamente en el URL de PostgreSQL.

Para usar Docker Compose, copia también el `.env.example` de la raíz a `.env` y configura `POSTGRES_PASSWORD` con la contraseña única. Compose publica sus puertos solo en `127.0.0.1` y comparte esa variable con PostgreSQL, la API y el respaldo.

## 7. Crear la base de datos con Alembic

Desde la carpeta `backend` en WSL:

```bash
/home/$USER/.venvs/sigmat/bin/python -m alembic upgrade head
```

Si la migración aún no existe, primero genera la estructura desde el modelo:

```bash
/home/$USER/.venvs/sigmat/bin/python -m alembic revision --autogenerate -m "esquema inicial"
/home/$USER/.venvs/sigmat/bin/python -m alembic upgrade head
```

## 8. Sembrar datos base

Se recomienda crear roles y usuario administrador inicial:

```bash
/home/$USER/.venvs/sigmat/bin/python -m app.seed
```

Esto deja el usuario principal disponible para autenticación:

- usuario: `admin`
- contraseña: `Admin123!`

Esta contraseña es únicamente para desarrollo local. Cámbiala antes de dar acceso a otra persona o red y nunca la uses en una publicación.

## 9. Levantar el backend

```bash
cd /mnt/c/ruta/al/proyecto/backend
/home/$USER/.venvs/sigmat/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verifica salud sin incluir credenciales en la línea de comandos:

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

Debe responder `200`. El inicio de sesión se prueba desde la interfaz en `http://localhost:5173/`.

Para probar el frontend desde la raiz del proyecto, en otra terminal ejecuta:

```powershell
.\backend\.venv\Scripts\python.exe Frontend\serve.py
```

Abre `http://localhost:5173/`. Este servidor local solo expone el HTML, CSS y JS publicos; no uses `python -m http.server` en la raiz porque podria publicar `backend/.env`. El frontend usa `/auth/token`, `/users`, `/items`, `/movements`, `/alerts` y `/reports/summary` del backend en `http://localhost:8000`. Inicio, Inventario, administración de usuarios (alta/edición/desactivación/reactivación), altas y bajas, ciclo de salida/autorizacion/devolucion, alertas, reportes, solicitudes de almacen e historial están conectados. Las preferencias por usuario guardan el periodo predeterminado de reportes y los filtros iniciales de alertas sin modificar permisos ni suprimir eventos. Las salidas requieren una cuenta activa de jefe de área para la autorización por contraseña.

En un despliegue detrás de proxy inverso, el frontend usa por defecto el mismo origen para la API y el WebSocket. El proxy debe enviar `/api/v1/` a FastAPI y admitir WebSocket en `/ws/alerts`; con HTTPS, debe conservar la conexión WebSocket segura (`wss`). En desarrollo local con el frontend en el puerto `5173`, el cliente conserva el API en el puerto `8000`. Configura `ALLOWED_ORIGINS` en el backend con el origen HTTPS exacto antes de exponerlo.

El usuario inicial es solo para desarrollo: cambia su contrasena antes de exponer el servicio a otras personas o redes. Los access y refresh tokens del navegador se guardan solo en memoria; el access se renueva automáticamente durante la sesión, solicitudes simultáneas comparten una sola renovación y cada petición se reintenta una vez. Se cierra la sesión al vencer/rechazarse el refresh token. Al recargar la página se solicita un nuevo inicio de sesión.

## 10. Verificar Swagger

Abre en el navegador:

```text
http://localhost:8000/docs
```

## 11. Recomendación importante

Cuando la base de datos se levanta en otra máquina, lo más importante es:

- instalar PostgreSQL dentro de WSL,
- revisar que el servicio esté activo,
- recrear el usuario y la base del proyecto,
- ejecutar las migraciones,
- sembrar los datos base,
- y verificar el login antes de seguir desarrollando.

## 12. Resumen rápido

Comandos clave:

```bash
sudo service postgresql start
sudo -u postgres psql
CREATE ROLE ipi2_user LOGIN;
\password ipi2_user
CREATE DATABASE ipi2_inventario OWNER ipi2_user;
```

```bash
cd /mnt/c/ruta/al/proyecto/backend
source /home/$USER/.venvs/sigmat/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Observación final

Esta ruta fue validada para este proyecto y resulta robusta para una tesis o un entorno de desarrollo compartido, porque evita depender de Docker y funciona bien con el flujo real de Windows + WSL2 + PostgreSQL.
