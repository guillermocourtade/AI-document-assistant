# RAG Evaluation Ground Truth — Manual Operativo de NovaTech Solutions

Este documento es **solo para uso interno de evaluación**. No debe cargarse al sistema RAG.
Corresponde al archivo `NovaTech_Manual_Operativo.docx` (convertir a PDF antes de indexar).

Distribución: 5 Direct · 5 Paraphrase · 5 Similar Sections · 4 Boundary Context · 3 Numeric Confusion · 3 Exact Identifier = 25 preguntas.

Nota sobre páginas: como pediste, todas las páginas se dejan como **POR COMPLETAR**. Complétalas manualmente después de exportar el .docx a PDF (abre el PDF y anota el número de página real de cada evidencia).

---

### Q01

**Pregunta:**
¿Cuántos días de anticipación debe dar un empleado que renuncia de forma voluntaria?

**Respuesta esperada:**
30 días de anticipación, por escrito.

**Sección:**
15.1 Renuncia voluntaria

**Página PDF esperada:** 13

**Evidencia:**
"debe presentar su aviso por escrito con al menos 30 días de anticipación a la fecha propuesta de salida"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q02

**Pregunta:**
¿A qué hora se ejecutan los backups incrementales?

**Respuesta esperada:**
Diariamente a las 23:00 horas.

**Sección:**
11.1 Backups incrementales

**Página PDF esperada:** 10

**Evidencia:**
"Los backups incrementales se ejecutan diariamente a las 23:00 horas"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q03

**Pregunta:**
¿Cuál es el tope diario de gasto en alimentos para un viaje nacional?

**Respuesta esperada:**
35 USD por día.

**Sección:**
5.1 Gastos en viajes nacionales

**Página PDF esperada:** 6

**Evidencia:**
"El tope diario para alimentos en viajes nacionales es de 35 USD por día"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q04

**Pregunta:**
¿Cuántas horas de capacitación anual son obligatorias para todo el personal?

**Respuesta esperada:**
16 horas al año.

**Sección:**
14. Capacitación y desarrollo

**Página PDF esperada:** 12

**Evidencia:**
"Todo empleado debe completar un mínimo de 16 horas de capacitación al año"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q05

**Pregunta:**
¿Cuál es el monto del estipendio único que reciben los empleados remotos para su oficina en casa?

**Respuesta esperada:**
300 USD.

**Sección:**
3. Trabajo remoto

**Página PDF esperada:** 4

**Evidencia:**
"recibe un estipendio único de 300 USD para la configuración de su oficina en casa"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q06

**Pregunta:**
¿Cuántos días de vacaciones al año recibe un empleado de tiempo completo?

**Respuesta esperada:**
20 días (el manual lo describe como "veinte jornadas de descanso remunerado por año").

**Sección:**
4. Vacaciones y ausencias

**Página PDF esperada:** 4

**Evidencia:**
"El personal de tiempo completo dispone de veinte jornadas de descanso remunerado por año"

**Dificultad:** Medium

**Categoría:** Paraphrase

---

### Q07

**Pregunta:**
¿Con cuánto tiempo de anticipación se debe reservar un viaje al extranjero?

**Respuesta esperada:**
Al menos 10 días hábiles antes de la fecha de salida.

**Sección:**
6.2 Viajes internacionales (política TRV-220)

**Página PDF esperada:** 7

**Evidencia:**
"Los viajes internacionales deben reservarse con al menos 10 días hábiles de anticipación"

**Dificultad:** Medium

**Categoría:** Paraphrase

---

### Q08

**Pregunta:**
¿Cuánto tiempo tiene un empleado para reportar sus gastos después de regresar de un viaje dentro del país?

**Respuesta esperada:**
7 días hábiles.

**Sección:**
5.1 Gastos en viajes nacionales

**Página PDF esperada:** 6

**Evidencia:**
"deben presentar su reporte de gastos... dentro de los siguientes 7 días hábiles posteriores a la fecha de regreso del viaje"

**Dificultad:** Medium

**Categoría:** Paraphrase

---

### Q09

**Pregunta:**
¿Cuál es la cantidad mínima de caracteres exigida para la contraseña de una cuenta de administrador?

**Respuesta esperada:**
16 caracteres.

**Sección:**
8.2 Contraseñas administrativas (política SEC-104)

**Página PDF esperada:** 8

**Evidencia:**
"Las contraseñas administrativas deben tener una longitud mínima de 16 caracteres"

**Dificultad:** Medium

**Categoría:** Paraphrase

---

### Q10

**Pregunta:**
¿Con qué múltiplo se paga el tiempo extra trabajado en fin de semana?

**Respuesta esperada:**
Al doble (2x) de la tarifa horaria ordinaria.

**Sección:**
2. Horarios y asistencia

**Página PDF esperada:** 3

**Evidencia:**
"las horas extra realizadas en sábado, domingo o días festivos oficiales se compensan al doble (2x) de la tarifa horaria ordinaria"

**Dificultad:** Medium

**Categoría:** Paraphrase

---

### Q11

**Pregunta:**
¿Cuál es el tope de gasto en hospedaje por noche en un viaje internacional?

**Respuesta esperada:**
200 USD por noche (distinto de los 120 USD de los viajes nacionales).

**Sección:**
5.2 Gastos en viajes internacionales

**Página PDF esperada:** 6

**Evidencia:**
"el tope por noche de hospedaje es de 200 USD"

**Dificultad:** Hard

**Categoría:** Similar Sections

---

### Q12

**Pregunta:**
¿Cada cuántos días debe renovarse una contraseña administrativa?

**Respuesta esperada:**
Cada 30 días (distinto de los 90 días de las contraseñas de usuario estándar).

**Sección:**
8.2 Contraseñas administrativas (política SEC-104)

**Página PDF esperada:** 8

**Evidencia:**
"deben renovarse cada 30 días"

**Dificultad:** Hard

**Categoría:** Similar Sections

---

### Q13

**Pregunta:**
¿En qué plazo debe verificarse la integridad de un backup completo mediante una prueba de restauración?

**Respuesta esperada:**
Dentro de las 72 horas posteriores a su ejecución.

**Sección:**
11.2 Backups completos

**Página PDF esperada:** 11

**Evidencia:**
"debe validar la integridad de cada backup completo dentro de las 72 horas posteriores a su ejecución"

**Dificultad:** Hard

**Categoría:** Similar Sections

---

### Q14

**Pregunta:**
¿Cuántos días a la semana puede trabajar remoto un empleado que ya terminó su periodo de prueba?

**Respuesta esperada:**
Hasta 3 días por semana (distinto del máximo de 1 día durante el periodo de prueba).

**Sección:**
3.2 Empleados confirmados

**Página PDF esperada:** 4

**Evidencia:**
"puede solicitar trabajar de forma remota hasta tres días por semana"

**Dificultad:** Hard

**Categoría:** Similar Sections

---

### Q15

**Pregunta:**
¿En cuánto tiempo debe notificarse al CISO un incidente de seguridad de severidad crítica?

**Respuesta esperada:**
Dentro de los siguientes 15 minutos posteriores a la detección (distinto de las 24 horas para un incidente normal).

**Sección:**
9.2 Incidentes de severidad crítica (política SEC-110)

**Página PDF esperada:** 9

**Evidencia:**
"deberá completarse dentro de los siguientes 15 minutos posteriores a la detección del incidente"

**Dificultad:** Hard

**Categoría:** Similar Sections

---

### Q16

**Pregunta:**
¿Qué debe hacer el responsable inmediatamente después de que ocurre un incidente de severidad crítica?

**Respuesta esperada:**
Iniciar de inmediato el protocolo de escalamiento definido en la política SEC-110, sin esperar aprobación previa del gerente.

**Sección:**
9.2 Incidentes de severidad crítica (política SEC-110)

**Página PDF esperada:** 9

**Evidencia:**
"el responsable deberá iniciar inmediatamente el protocolo de escalamiento definido en la política SEC-110"

**Dificultad:** Hard

**Categoría:** Boundary Context

---

### Q17

**Pregunta:**
Después de ejecutar un backup completo, ¿qué debe hacer el equipo de Infraestructura y en cuánto tiempo?

**Respuesta esperada:**
Validar la integridad del backup mediante una prueba de restauración parcial, dentro de las 72 horas posteriores a su ejecución.

**Sección:**
11.2 Backups completos

**Página PDF esperada:** 11

**Evidencia:**
"El equipo de Infraestructura debe validar la integridad de cada backup completo dentro de las 72 horas posteriores a su ejecución, mediante una prueba de restauración parcial"

**Dificultad:** Hard

**Categoría:** Boundary Context

---

### Q18

**Pregunta:**
Cuando un empleado deja la compañía, ¿quién debe notificar a Recursos Humanos y cuándo?

**Respuesta esperada:**
El gerente directo, el mismo día en que se confirme la salida del empleado.

**Sección:**
15.2 Terminación con causa

**Página PDF esperada:** 13

**Evidencia:**
"el gerente directo deberá notificar formalmente al equipo de Recursos Humanos el mismo día en que se confirme la salida"

**Dificultad:** Hard

**Categoría:** Boundary Context

---

### Q19

**Pregunta:**
¿Qué debe activar un empleado antes de acceder a los sistemas internos de la compañía cuando trabaja de forma remota?

**Respuesta esperada:**
La VPN corporativa (requisito de la política REM-018).

**Sección:**
3. Trabajo remoto

**Página PDF esperada:** 4

**Evidencia:**
"la VPN corporativa debe activarse obligatoriamente antes de acceder a cualquier sistema interno de la compañía"

**Dificultad:** Medium

**Categoría:** Boundary Context

---

### Q20

**Pregunta:**
¿En cuántas horas deben revocarse los accesos a sistemas críticos después de que se confirma la terminación laboral de un empleado?

**Respuesta esperada:**
24 horas (distinto de las 72 horas para accesos no críticos).

**Sección:**
15.3 Revocación de accesos (política HR-045)

**Página PDF esperada:** 13

**Evidencia:**
"los accesos a sistemas críticos deben revocarse dentro de las 24 horas siguientes a la confirmación de la terminación laboral"

**Dificultad:** Hard

**Categoría:** Numeric Confusion

---

### Q21

**Pregunta:**
¿En cuántas horas debe responder un proveedor a una solicitud de auditoría de seguridad?

**Respuesta esperada:**
48 horas.

**Sección:**
12. Proveedores y terceros

**Página PDF esperada:** 11

**Evidencia:**
"el proveedor debe responder formalmente a dicha solicitud dentro de un plazo de 48 horas"

**Dificultad:** Medium

**Categoría:** Numeric Confusion

---

### Q22

**Pregunta:**
¿Cuál es el RTO (Recovery Time Objective) para los sistemas Tier 1 según el plan de continuidad de negocio?

**Respuesta esperada:**
4 horas (distinto de las 24 horas de los sistemas Tier 2).

**Sección:**
16.1 Sistemas Tier 1 (críticos)

**Página PDF esperada:** 14

**Evidencia:**
"el objetivo de tiempo de recuperación (Recovery Time Objective, RTO) es de 4 horas"

**Dificultad:** Hard

**Categoría:** Numeric Confusion

---

### Q23

**Pregunta:**
¿Qué formulario debe utilizarse para solicitar un periodo de vacaciones de más de cinco días?

**Respuesta esperada:**
FORM-B22.

**Sección:**
4. Vacaciones y ausencias

**Página PDF esperada:** 5

**Evidencia:**
"deben presentarse mediante el formulario FORM-B22 con al menos diez días hábiles de anticipación"

**Dificultad:** Easy

**Categoría:** Exact Identifier

---

### Q24

**Pregunta:**
¿Qué código de política regula la longitud mínima y el almacenamiento de las contraseñas administrativas?

**Respuesta esperada:**
SEC-104.

**Sección:**
8.2 Contraseñas administrativas (política SEC-104)

**Página PDF esperada:** 8

**Evidencia:**
"Contraseñas administrativas (política SEC-104)"

**Dificultad:** Easy

**Categoría:** Exact Identifier

---

### Q25

**Pregunta:**
¿Qué código de política aplica específicamente a los viajes internacionales de la compañía?

**Respuesta esperada:**
TRV-220.

**Sección:**
6.2 Viajes internacionales (política TRV-220)

**Página PDF esperada:** 7

**Evidencia:**
"Viajes internacionales (política TRV-220)"

**Dificultad:** Easy

**Categoría:** Exact Identifier

---

## Notas de consistencia (verificado)

- Todos los números monetarios, de días y de horas citados arriba coinciden literalmente con el texto del manual.
- Los pares de "secciones similares" usados (gastos nacional/internacional, contraseñas normal/administrativa, backups incremental/completo, remoto en prueba/confirmado, incidente normal/crítico) tienen reglas explícitamente distintas y no contradictorias.
- Los identificadores (FORM-B22, FORM-X17, SEC-104, SEC-110, TRV-115, TRV-220, REM-018, HR-045, DPO-500, PROV-030, ASIS-010) aparecen exactamente igual en el manual y en este documento.
- Ninguna pregunta depende de información que no esté en el manual.
