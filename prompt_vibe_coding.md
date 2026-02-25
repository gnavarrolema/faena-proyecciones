### 🐔 PROMPT MAESTRO PARA VIBE CODING: Web App "Proyección de Faena"

**🎯 CONTEXTO DEL PROYECTO**
Eres un desarrollador full-stack experto y un ingeniero de software proactivo. Debes construir desde cero una web app de planificación de faena avícola ("Proyección de Faena") que replica con exactitud la lógica y cálculos de una hoja de cálculo Excel (pestaña "PROYEC1"). La app automatizará la carga de la oferta de granjas de engorde (pasada cada martes/jueves) y la planificación de retiros según peso, edad y demanda comercial (ej. 30k a 35k pollos diarios).
La app debe correr en **Google Cloud Run**, persistir datos en **PostgreSQL (Cloud SQL)** y generar exportables en **Google Cloud Storage** para mantener los costos bajos. Se requiere además integrar un pipeline completo de **CI/CD usando GitHub Actions**.

**📐 ARQUITECTURA OBJETIVO**
*   **Frontend:** React (Vite) + TypeScript + TailwindCSS. Grilla interactiva editable tipo Excel.
*   **Backend:** Python con FastAPI (REST API), SQLAlchemy (Async), autenticación JWT.
*   **Base de datos:** PostgreSQL en Google Cloud SQL (Tier micro).
*   **Almacenamiento:** Google Cloud Storage para guardar PDFs y Excels exportados.
*   **Infraestructura:** Contenedores en Google Cloud Run.
*   **CI/CD:** GitHub Actions (Build -> Test -> Docker Push -> Deploy Cloud Run).

**🧮 MODELO DE DATOS Y PARÁMETROS GLOBALES**
**Lote de granja (Tabla principal de Oferta):**
`granja` (string), `lote_numero` (int), `semana` (int), `cantidad_pollos` (int), `sexo` ("M", "H" o null para sin sexar), `edad_actual` (días), `peso_actual` (kg), `fecha_inicio_retiro` (date), `pollos_lunes` a `pollos_sabado` (int, editables directamente en la UI).

**Parámetros globales (Editables por el usuario, afectan toda la proyección):**
*   `ganancia_diaria_macho`: 0.09 kg (90 gr)
*   `ganancia_diaria_hembra`: 0.079 kg (79 gr)
*   `rendimiento_faena`: 0.87 (87%)
*   `kg_por_caja`: 20.0 kg
*   `edad_ideal_macho`: 40 días
*   `edad_ideal_hembra`: 44 días
*   `edad_ideal_sin_sexar`: 42 días
*   `medio_dia_ganancia`: 0.5 (aplica a la ganancia diaria)

**📊 RUTINAS Y LÓGICA DE CÁLCULO ESTRICTA (CRÍTICO)**
Tu tarea es implementar exactamente estas lógicas matemáticas en el backend y refrescarlas en el front:

1.  **Diferencia de edad ideal de retiro:**
    `Diferencia = Edad al momento del retiro - Edad Ideal (según sexo)`.
    *(M = 40, H = 44, Sin sexar = 42).*
2.  **Peso de pollo vivo al momento del retiro:**
    `Días extra = Edad al momento de retiro - Edad Actual - 1`
    `Medio día extra = Ganancia diaria (según sexo) * 0.5`
    `Peso = (Días extra * Ganancia diaria) + Peso Actual + Medio día extra`
    *(⚠️ Nota: Si el pollo no está sexado, aplicar un descuento del 4% multiplicando todo el resultado final por 0.96).*
3.  **Diferencia de edad ideal de retiro promedio:**
    Se calcula como un porcentaje/promedio ponderado del día:
    `SUMPRODUCT(Cantidad de pollos * Diferencia de edad ideal) / SUM(Cantidad de pollos del día)`.
4.  **Peso promedio diario de Pollo vivo el día del retiro:**
    Promedio ponderado del día: `SUMPRODUCT(Cantidad de pollos * Peso vivo) / SUM(Cantidad de pollos del día)`.
5.  **Peso de faenado:**
    `Peso Faenado = Peso pollo vivo * rendimiento_faena (0.87)`.
6.  **Calibre Promedio (Pollos/Cajón):**
    `Calibre = kg_por_caja (20) / Peso de faenado`. *(El resultado indica cuántos pollos entran en una caja).*
7.  **Cajas:**
    `Cajas producidas = Cantidad de pollos faenados / Calibre Promedio`
    *(⚠️ Solo contar de lotes asignados en un día en específico).*
8.  **Calibre Promedio (Pollos/Cajón) Promedio diario:**
    Promedio ponderado: `SUMPRODUCT(Cantidad pollos * Calibre) / SUM(Cantidad de pollos del día)`.
9.  **Pollos/Día Faena y Ventas:**
    Suma simple de todos los pollos configurados (editables) para ese día específico de la semana entre todos los lotes. Debe rondar los 30.000 a 35.000 pollos/día y mostrar un totalizador.
10. **PRODUCCIÓN CAJAS SEMANALES:**
    `Total Pollos Faena+Ventas Semana / Calibre Promedio Ponderado Semanal`.
11. **Pollos Faena+Ventas/Semana:**
    Suma estática de la cantidad de pollos cargada para la semana (Suma de Lunes a Sábado). Al destino "Sofía" se le restan 10.000 fijos de ese total general (o una constante editable).
12. **PROMEDIO EDADES SEMANAL:**
    Promedio de edades de fin de retiro de todos los lotes de la faena semanal. *(Excluir lotes donde no haya ingreso de pollos).*

**🖥️ REQUERIMIENTOS DEL FRONTEND (UI/UX)**
1. **Grilla tipo Excel Dinámica:** Celdas para `Lunes`, `Martes`, `Miércoles`, `Jueves`, `Viernes` y `Sábado` deben ser inputs numéricos rápidos de editar. Los valores calculados deben actualizarse reactivamente (debounce).
2. **Alertas visuales de edad (Semáforo):**
   *   🟢 **Verde:** Diferencia de edad entre -2 a +2 días.
   *   🟡 **Amarillo:** -5 a -3 o +3 a +5 días.
   *   🔴 **Rojo:** Diferencia es < -5 o > +5 días.
3. **Pega de datos (Paste):** Soporte para copiar de un Excel (columnas A a G de la "Oferta") y pegar directamente en la tabla web para crear nuevos lotes (FarmBatch) de forma masiva super fluida.
4. **Resumen y Panel Diario/Semanal:** Una fila inferiror de "Totales" para mostrar las *Cajas producidas semanales*, y el dashboard con los *Calibres promedios ponderados*.

**⚙️ INFRAESTRUCTURA & CI/CD**
*   **Docker:** Escribe `Dockerfile` para el backend (Python) y el frontend (Nginx multietapa). Así como un `docker-compose.yml` para desarrollo en local.
*   **GitHub Actions:** Crea 2 workflows:
    *   `ci.yml`: Ejecuta unit tests (pytest en lógica matemática) al crear PR a main.
    *   `cd.yml`: Hace Push al *Google Artifact Registry* y actualiza el *Google Cloud Run* en cada Push a main.
*   **Archivos:** Integrar Google Cloud Storage con una clase `gcs_service.py` que suba los excels y de una URL de descarga mediante Signed URLs o publicas.

**✅ TESTS Y OBLIGACIONES DEL DESARROLLADOR**
Escribe una suite extensa de tests (`pytest` en `app/tests/test_calculations.py`) probando meticulosamente todas las 12 lógicas enumeradas con valores de borde y escenarios con pollos "sin sexar". 
Tu entrega principal de este prompt inicial será inicializar la estructura base y darme el Motor de Cálculo Completo de Backend en Python, el Schema y Modelo SQLAlchemy. Luego pasaremos al frontend.
