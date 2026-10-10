# Recomendación de hardware biométrico para la tesis

## Contexto

El proyecto ya está diseñado bajo un modelo de seguridad orientado a zero trust, con autenticación basada en JWT, control por roles, validación de usuarios activos, auditoría y firma de dispositivos. Por ello, la decisión de hardware no debe enfocarse solo en costo, sino en cómo se integra dentro de la cadena de confianza del sistema.

## Recomendación principal para tesis

### Sensor recomendado: Adafruit AS608 + ESP32

Es la mejor opción para un trabajo académico o de titulación si se busca equilibrio entre costo, aprendizaje y demostrabilidad técnica.

### Motivos

- Es muy económica en comparación con lectores industriales.
- Permite demostrar claramente la integración de hardware con backend.
- Encaja con el modelo de datos actual (`BiometricTemplate` y `sensor_slot_id`); la autorizacion por huella esta deshabilitada hasta integrar prueba firmada y verificable del lector.
- No exige licencias ni ecosistemas cerrados.
- Es ideal para un prototipo funcional y un demostrador de tesis.

## ¿Se degrada la ciberseguridad?

No necesariamente, siempre que la seguridad se mantenga en el backend y no se confíe ciegamente en el sensor.

El riesgo real no es que el hardware sea barato, sino que se haga una integración débil, por ejemplo:

- aceptar tráfico del sensor sin autenticar el dispositivo,
- no cifrar la comunicación,
- guardar imágenes de huella en lugar de plantillas,
- no validar roles ni sesiones en el backend,
- confiar en el lector como autoridad absoluta.

Eso sí sería una mala práctica en ciberseguridad.

## Modelo recomendado de seguridad

Para una solución económica y académica, la arquitectura debería respetar estas reglas:

1. El ESP32 debe identificarse con un ID único del dispositivo.
2. La comunicación con el backend debe ir sobre TLS.
3. El payload del sensor debe estar firmado o autenticado antes de llegar al servidor.
4. El backend debe validar siempre:
   - usuario activo,
   - rol permitido,
   - token JWT válido,
   - dispositivo autenticado,
   - timestamp dentro de la ventana de tolerancia,
   - flujo de operación válido.
5. Los templates biométricos deben almacenarse de forma segura y no deben guardarse imágenes crudas de huellas.
6. Todo intento de autenticación debe quedar registrado en auditoría.

## Diferencia entre prototipo y producción

### Para tesis / prototipo
AS608 + ESP32 es una excelente decisión:

- bajo costo,
- aprendizaje práctico,
- demostración técnica sólida,
- fácil de integrar con FastAPI.

### Para producción
Sería recomendable migrar a lectores más robustos, como modelos de la línea ZKTeco o similares, porque aportan:

- mejores garantías de hardware,
- mayor robustez operativa,
- mejor soporte industrial,
- mayor estabilidad en entornos críticos.

## Recomendación final

Para este trabajo de titulación, la mejor decisión es:

- Adafruit AS608
- ESP32
- backend FastAPI con validación centralizada
- zero trust aplicado en la capa del servidor
- integración segura con plantillas biométricas y auditoría

Esto mantiene un enfoque académico fuerte, práctico y alineado con ciberseguridad sin caer en costos innecesarios.

## Conclusión

La elección del hardware no debe ser el punto débil del diseño si el backend mantiene la autoridad de validación. El AS608 no “degrada” la seguridad del proyecto por sí solo; la seguridad se degrada cuando el sistema confía demasiado en el dispositivo o no valida correctamente la cadena completa.

Por lo tanto, para la tesis esta es la opción más recomendable: AS608 + ESP32, siempre con controles de seguridad bien implementados en FastAPI.
