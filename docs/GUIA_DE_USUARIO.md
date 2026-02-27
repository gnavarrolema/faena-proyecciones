# 📖 Guía de Usuario — ProyecFaena

## Proyección de Faena Avícola

**Versión:** 1.0  
**Última actualización:** Febrero 2026

---

## Índice

1. [¿Qué es ProyecFaena?](#1-qué-es-proyecfaena)
2. [Requisitos previos](#2-requisitos-previos)
3. [Acceso al sistema](#3-acceso-al-sistema)
   - 3.1 [Página de inicio](#31-página-de-inicio)
   - 3.2 [Iniciar sesión](#32-iniciar-sesión)
4. [Pantalla principal — Navegación](#4-pantalla-principal--navegación)
5. [Cargar Oferta (Pestaña "Cargar Oferta")](#5-cargar-oferta)
   - 5.1 [Formato del archivo Excel](#51-formato-del-archivo-excel)
   - 5.2 [Pasos para cargar la oferta](#52-pasos-para-cargar-la-oferta)
   - 5.3 [Advertencia de sobreescritura](#53-advertencia-de-sobreescritura)
6. [Ver Oferta (Pestaña "Oferta")](#6-ver-oferta)
   - 6.1 [Resumen estadístico](#61-resumen-estadístico)
   - 6.2 [Generar Proyección](#62-generar-proyección)
   - 6.3 [Resumen por Granja](#63-resumen-por-granja)
   - 6.4 [Tabla de Oferta Completa](#64-tabla-de-oferta-completa)
7. [Proyección de Faena (Pestaña "Proyección")](#7-proyección-de-faena)
   - 7.1 [Indicadores semanales](#71-indicadores-semanales)
   - 7.2 [Ajuste con Oferta del Martes](#72-ajuste-con-oferta-del-martes)
   - 7.3 [Lotes no asignados](#73-lotes-no-asignados)
   - 7.4 [Lotes fuera de rango](#74-lotes-fuera-de-rango)
   - 7.5 [Vista por Día (Cards)](#75-vista-por-día-cards)
   - 7.6 [Vista Tabla](#76-vista-tabla)
   - 7.7 [Mover un lote a otro día](#77-mover-un-lote-a-otro-día)
   - 7.8 [Eliminar un lote](#78-eliminar-un-lote)
8. [Resumen Semanal (Pestaña "Resumen")](#8-resumen-semanal)
   - 8.1 [Resumen Diario](#81-resumen-diario)
   - 8.2 [Distribución por Granja](#82-distribución-por-granja)
   - 8.3 [Cobertura de la Oferta](#83-cobertura-de-la-oferta)
9. [Parámetros de Cálculo (Pestaña "Parámetros")](#9-parámetros-de-cálculo)
   - 9.1 [Secciones de parámetros](#91-secciones-de-parámetros)
   - 9.2 [Guardar cambios](#92-guardar-cambios)
10. [Exportación a PDF](#10-exportación-a-pdf)
11. [Semáforo de edades](#11-semáforo-de-edades)
12. [Flujo de trabajo recomendado](#12-flujo-de-trabajo-recomendado)
13. [Glosario de términos](#13-glosario-de-términos)
14. [Preguntas frecuentes](#14-preguntas-frecuentes)
15. [Solución de problemas](#15-solución-de-problemas)

---

## 1. ¿Qué es ProyecFaena?

**ProyecFaena** es una aplicación web de planificación de faena avícola. Permite:

- **Cargar la oferta** de granjas de engorde recibida cada jueves (y ajustarla con la oferta del martes).
- **Generar automáticamente** la proyección semanal de retiro de pollos, distribuyéndolos de lunes a sábado según peso, edad y demanda (objetivo ~30.000 a 35.000 pollos/día).
- **Ajustar manualmente** la distribución moviendo lotes entre días.
- **Visualizar indicadores clave** como peso promedio, calibre, cajas producidas y diferencia de edad ideal.
- **Exportar reportes** en formato PDF.

La aplicación automatiza los cálculos que tradicionalmente se realizaban en una hoja de Excel, ofreciendo precisión, velocidad y trazabilidad.

---

## 2. Requisitos previos

| Requisito | Detalle |
|---|---|
| **Navegador** | Google Chrome, Microsoft Edge, Firefox o Safari (versión actual) |
| **Conexión** | Acceso a la red donde está desplegado el servidor |
| **Archivo Excel** | Formato `.xlsx` o `.xls` con la oferta de granjas (ver sección 5.1) |
| **Credenciales** | Usuario y contraseña proporcionados por el administrador |

---

## 3. Acceso al sistema

### 3.1 Página de inicio

Al ingresar a la URL de la aplicación, verá la **Landing Page** con información general del sistema. Desde aquí puede hacer clic en:

- **"Iniciar Sesión"** (esquina superior derecha)
- **"Comenzar Ahora"** (botón central)

Ambos lo llevan a la pantalla de login.

### 3.2 Iniciar sesión

1. Ingrese su **Usuario** en el primer campo.
2. Ingrese su **Contraseña** en el segundo campo.
3. Haga clic en **"Ingresar"**.

Si los datos son correctos, verá el mensaje "¡Bienvenido!" y será redirigido a la pantalla principal de la aplicación.

> **Nota:** La sesión permanece activa por 7 días. Si el token expira, será redirigido automáticamente al login.

> **Credenciales por defecto (desarrollo):** Usuario: `admin` / Contraseña: `admin123`. En producción, el administrador le proporcionará sus credenciales.

---

## 4. Pantalla principal — Navegación

Una vez autenticado, la pantalla principal muestra una **barra de navegación superior** con 5 pestañas:

| Pestaña | Ícono | Función |
|---|---|---|
| **Cargar Oferta** | 📁 | Subir el archivo Excel con la oferta de granjas |
| **Oferta** | 📋 | Ver los lotes cargados y generar la proyección |
| **Proyección** | 📊 | Ver y ajustar la distribución diaria de lotes |
| **Resumen** | 📈 | Dashboard con totales diarios y semanales |
| **Parámetros** | ⚙️ | Configurar los valores de cálculo (ganancias, edades, rendimientos) |

En el extremo derecho de la barra hay un botón **"Salir"** para cerrar sesión.

> **Tip:** Al ingresar, la aplicación detecta automáticamente si ya hay datos cargados y lo lleva a la pestaña más relevante (Proyección si ya existe, Oferta si hay datos, o Cargar Oferta si está vacío).

---

## 5. Cargar Oferta

Esta pestaña permite subir el archivo Excel con la **oferta del jueves** de granjas de engorde.

### 5.1 Formato del archivo Excel

El archivo debe ser `.xlsx` o `.xls` con las siguientes columnas:

| Columna | Campo | Ejemplo |
|---|---|---|
| **A** | Fecha de Peso | 12/2/2026 |
| **B** | Granja | LOS REMANSOS |
| **C** | Galpón | 5 |
| **D** | Núcleo | 1 |
| **E** | Cantidad | 4.370 |
| **F** | Sexo (M/H) | H |
| **G** | Edad Proyectada | 42 |
| **H** | Peso Muestreo Proyectado | 2,78 |
| **I** | Ganancia Diaria | 0,090 |
| **J** | Días Proyectados | 0 |
| **K** | Edad Real | 42 |
| **L** | Peso Muestreo Real | 2,78 |
| **N** | Fecha de Ingreso | 31/12/2025 |

> **Importante:** Respete el orden de columnas. El sistema parsea automáticamente los datos basándose en esta estructura.

### 5.2 Pasos para cargar la oferta

1. Haga clic en la **zona de carga** (cuadro punteado) o **arrastre el archivo** directamente sobre ella.
2. Verifique que aparezca el nombre del archivo seleccionado.
3. Haga clic en **"Cargar y Procesar"**.
4. Espere a que el sistema procese el archivo. Al finalizar, será redirigido automáticamente a la pestaña **Oferta**.

> **Tip:** Si seleccionó un archivo incorrecto, use el botón **"Limpiar"** para descartarlo y seleccionar otro.

### 5.3 Advertencia de sobreescritura

Si ya existen datos cargados en el sistema (oferta o proyección previas), aparecerá un cuadro de advertencia naranja indicando que la carga **reemplazará completamente** los datos actuales.

Para confirmar:
1. Marque la casilla **"Entiendo que los datos actuales serán reemplazados y deseo continuar"**.
2. Luego se habilitará el botón "Cargar y Procesar".

> **Alternativa:** Si solo desea actualizar los datos de peso/edad sin perder la planificación existente, use la opción **"Ajuste Martes"** desde la pestaña Proyección (ver sección 7.2).

---

## 6. Ver Oferta

Una vez cargado el archivo, esta pestaña muestra toda la información de los lotes importados.

### 6.1 Resumen estadístico

En la parte superior se muestran tres tarjetas con:

- **Total Lotes:** Cantidad de lotes (galpones) cargados.
- **Total Pollos:** Suma total de pollos en todos los lotes.
- **Granjas:** Cantidad de granjas distintas en la oferta.

### 6.2 Generar Proyección

Este es el paso clave. Complete los campos:

| Campo | Descripción | Ejemplo |
|---|---|---|
| **Fecha Inicio Semana (Lunes)** | El lunes de la semana a planificar | 2026-03-02 |
| **Pollos por Día (objetivo)** | Cuántos pollos desea faenar por día | 30000 |
| **Días de Faena** | Cuántos días trabajar (5 o 6) | 6 (Lunes a Sábado) |

Luego haga clic en **"Generar Proyección Automática"**. El sistema:

1. Calcula edad y peso proyectado de cada lote para cada día de la semana.
2. Filtra los lotes que están fuera de rango de edad/peso permitido.
3. Prioriza lotes según edad ideal y los distribuye equilibradamente entre los días.
4. Respeta el tope de pollos por día configurado.

Al completar, será redirigido a la pestaña **Proyección**.

### 6.3 Resumen por Granja

Tabla que muestra cada granja con la cantidad de lotes y pollos totales. Incluye un botón **"Descargar PDF"** para exportar este resumen.

### 6.4 Tabla de Oferta Completa

Tabla con todos los lotes cargados mostrando todos sus datos: fecha de peso, granja, galpón, núcleo, cantidad, sexo, edad, peso, ganancia diaria, etc. Es de solo lectura y permite verificar que los datos se importaron correctamente.

---

## 7. Proyección de Faena

Esta es la pestaña central de la aplicación. Aquí se visualiza y ajusta la distribución de lotes por día.

### 7.1 Indicadores semanales

En la parte superior se muestran 4 tarjetas:

| Indicador | Qué muestra |
|---|---|
| **Total Pollos Semana** | Suma de todos los pollos asignados en la semana |
| **Promedio Edad Semana** | Edad promedio de retiro de todos los lotes |
| **Cajas Semanales** | Total de cajas de 20 kg producidas en la semana |
| **Sofía (Total - 10.000)** | Pollos semanales menos el descuento de Sofía (configurable) |

### 7.2 Ajuste con Oferta del Martes

Esta sección (colapsable) permite actualizar la proyección existente con datos más frescos de la oferta del martes **sin perder la distribución de días ya planificada**.

**¿Cuándo usarlo?** El martes llega una nueva oferta con datos de peso y edad actualizados. Este ajuste:

- **Actualiza** los datos (peso, edad, ganancia) de lotes ya existentes.
- **Agrega** nuevos lotes si hay capacidad disponible en algún día.
- **Mantiene** la distribución de días que ya fue planificada.
- **Alerta** si algún lote existente queda fuera de rango tras la actualización.

**Pasos:**
1. Haga clic en **"Ajustar con Oferta del Martes"** para expandir la sección.
2. Seleccione el archivo Excel de la oferta del martes.
3. Haga clic en **"Aplicar Ajuste"**.
4. Revise el **resumen del ajuste** que aparece, indicando:
   - ✅ Lotes actualizados (datos cambiados)
   - ✅ Lotes nuevos asignados
   - ℹ️ Lotes nuevos sin capacidad
   - ⚠️ Lotes existentes que ahora quedaron fuera de rango
   - ⚠️ Lotes no encontrados en la nueva oferta

### 7.3 Lotes no asignados

Si el sistema no pudo asignar algunos lotes por exceso de capacidad diaria, aparece una sección amarilla listando esos lotes con:

- Granja, Galpón, Núcleo
- Cantidad de pollos
- Días elegibles (en qué días podría haber ido)
- Motivo (ej: "Tope diario alcanzado")

> **Acción:** Considere ajustar los parámetros de pollos por día o mover lotes manualmente para hacer espacio.

### 7.4 Lotes fuera de rango

Los lotes que no cumplen los requisitos de edad o peso mínimo/máximo para ningún día de la semana aparecen en una sección roja. Puede expandir cada lote para ver el detalle día por día (edad y peso proyectado, y la razón por la que no califica).

### 7.5 Vista por Día (Cards)

La vista predeterminada muestra una **grilla tipo Kanban** con una columna por cada día de faena (Lunes a Sábado). Cada columna contiene:

- **Encabezado:** Nombre del día y total de pollos.
- **Tarjetas de lotes:** Cada lote muestra:
  - Granja y Galpón
  - Sexo (M = Macho, H = Hembra, - = Sin sexar)
  - Cantidad de pollos
  - Edad al momento del retiro
  - Peso vivo (kg)
  - Diferencia de edad ideal (con código de color — ver semáforo)
  - Peso faenado
  - Cajas producidas
  - Botones **"Mover"** y **"Eliminar"**
- **Resumen inferior:** Peso promedio, diferencia de edad promedio y cajas del día.

### 7.6 Vista Tabla

Alterne a esta vista haciendo clic en **"Vista Tabla"**. Muestra todos los lotes en una tabla única con filas agrupadas por día. Incluye subtotales por cada día con los promedios ponderados.

### 7.7 Mover un lote a otro día

1. En la tarjeta o fila del lote, haga clic en **"Mover"**.
2. Se abrirá un diálogo mostrando los demás días disponibles con su fecha y total de pollos actual.
3. Haga clic en el día destino deseado.
4. El lote se recalcula automáticamente para la nueva fecha y se actualiza toda la proyección.

### 7.8 Eliminar un lote

1. Haga clic en **"Eliminar"** (o el ícono ✕ en la vista tabla).
2. Confirme en el diálogo de confirmación.
3. El lote se retira de la proyección y los totales se recalculan.

> **Precaución:** Eliminar un lote no lo devuelve a la oferta. Si necesita recuperarlo, regenere la proyección desde la pestaña Oferta.

---

## 8. Resumen Semanal

Esta pestaña ofrece una visión consolidada de la semana planificada.

### 8.1 Resumen Diario

Tabla con una fila por día que muestra:

| Columna | Descripción |
|---|---|
| **Día** | Lunes a Sábado |
| **Fecha** | Fecha calendario del día |
| **Pollos** | Total de pollos del día |
| **Lotes** | Cantidad de lotes asignados |
| **Peso Prom.** | Peso vivo promedio ponderado (kg) |
| **Dif. Edad Prom.** | Diferencia de edad promedio vs. ideal |
| **Calibre Prom.** | Calibre promedio (pollos/caja) ponderado |
| **Cajas** | Cajas producidas en el día |

La fila **TOTAL SEMANA** suma los pollos y cajas de toda la semana.

### 8.2 Distribución por Granja

Tabla cruzada que muestra cuántos pollos de cada granja se procesan en cada día. Permite visualizar rápidamente la distribución y detectar si alguna granja se concentra en un solo día.

### 8.3 Cobertura de la Oferta

Si existen lotes fuera de rango o no asignados, aparece una sección adicional que muestra:

- **Total Ofertados:** Todos los pollos de la oferta original.
- **Asignados (%):** Cuántos se incorporaron a la proyección.
- **Fuera de Rango:** Pollos que no cumplen edad/peso.
- **Exceso de Capacidad:** Pollos elegibles pero sin espacio por tope diario.

Incluye un botón **"Descargar PDF"** para exportar este resumen.

---

## 9. Parámetros de Cálculo

En esta pestaña puede configurar todos los valores que afectan los cálculos de la proyección.

### 9.1 Secciones de parámetros

#### Ganancia de Peso
| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| Ganancia diaria machos | 0.090 kg | Incremento de peso diario de pollos machos |
| Ganancia diaria hembras | 0.079 kg | Incremento de peso diario de pollos hembras |
| Factor medio día | 0.5 | Factor aplicado a la ganancia del último día (medio día) |

#### Rendimiento
| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| Rendimiento canal | 0.87 (87%) | Proporción del peso vivo que queda tras la faena |
| Kg por caja | 20.0 kg | Peso estándar por caja |
| Descuento sin sexar | 0.04 (4%) | Penalización aplicada a pollos sin sexar |

#### Edades Ideales
| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| Edad ideal machos | 40 días | Edad óptima de retiro para machos |
| Edad ideal hembras | 44 días | Edad óptima de retiro para hembras |
| Edad ideal sin sexar | 42 días | Edad óptima de retiro para lotes sin sexar |
| Edad mínima faena | — | Edad mínima para que un lote sea elegible |
| Edad máxima faena | — | Edad máxima para que un lote sea elegible |

#### Rango de Peso Faena
| Parámetro | Descripción |
|---|---|
| Peso mínimo faena | Peso vivo mínimo para que un lote sea elegible |
| Peso máximo faena | Peso vivo máximo para que un lote sea elegible |

#### Producción
| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| Pollos diarios mín. | 30.000 | Objetivo mínimo de pollos por día |
| Pollos diarios máx. | 35.000 | Objetivo máximo de pollos por día |
| Descuento Sofía | 10.000 | Constante que se resta del total semanal para calcular "Sofía" |

### 9.2 Guardar cambios

Después de modificar cualquier valor:

1. Haga clic en **"Guardar"** (esquina superior derecha de la sección).
2. Aparecerá un mensaje verde de confirmación.

> **Importante:** Los cambios en parámetros **no** se aplican retroactivamente a la proyección existente. Debe regenerar la proyección desde la pestaña Oferta para que los nuevos valores tomen efecto.

También puede descargar los parámetros actuales en PDF con el botón **"Descargar PDF"**.

---

## 10. Exportación a PDF

La aplicación permite exportar varios reportes en formato PDF:

| Reporte | Desde dónde | Contenido |
|---|---|---|
| **Oferta** | Pestaña Oferta → "Descargar PDF" | Resumen por granja + tabla completa de lotes |
| **Proyección** | Pestaña Proyección → "Descargar PDF" | Distribución detallada por día con indicadores |
| **Resumen** | Pestaña Resumen → "Descargar PDF" | Resumen diario, por granja y cobertura |
| **Parámetros** | Pestaña Parámetros → "Descargar PDF" | Configuración actual de todos los parámetros |

Los PDFs se generan al instante y se descargan directamente al navegador con un nombre que incluye la fecha (ej: `oferta-2026-02-27.pdf`).

---

## 11. Semáforo de edades

En las vistas de proyección, la **diferencia de edad ideal** se muestra con un código de colores para identificar rápidamente si un lote está en su punto óptimo:

| Color | Rango | Significado |
|---|---|---|
| 🟢 **Verde** | -1 a +1 días | Edad óptima — el lote está dentro del rango ideal |
| 🟠 **Naranja** | -3 a -2 o +2 a +3 días | Atención — el lote se aleja del ideal |
| 🔴 **Rojo** | Menor a -3 o mayor a +3 días | Alerta — el lote está significativamente fuera de la edad ideal |

La **diferencia de edad** se calcula como:

$$\text{Diferencia} = \text{Edad al retiro} - \text{Edad ideal según sexo}$$

Donde:
- Machos: edad ideal = 40 días
- Hembras: edad ideal = 44 días
- Sin sexar: edad ideal = 42 días

---

## 12. Flujo de trabajo recomendado

A continuación se describe el flujo semanal típico de uso de la aplicación:

### Jueves — Carga inicial

```
1. Recibir el Excel de oferta de granjas (OFERTA JUEV)
2. Iniciar sesión en ProyecFaena
3. Ir a "Cargar Oferta" → subir el archivo Excel
4. Ir a "Oferta" → verificar los datos importados
5. Configurar la fecha del próximo lunes, pollos/día y días de faena
6. Clic en "Generar Proyección Automática"
7. Ir a "Proyección" → revisar la distribución
8. Mover lotes entre días si es necesario
9. Ir a "Resumen" → validar los totales
10. Exportar a PDF para compartir con el equipo
```

### Martes — Ajuste con datos actualizados

```
1. Recibir el Excel de oferta actualizada (OFERTA MART)
2. Ir a "Proyección" → abrir "Ajustar con Oferta del Martes"
3. Subir el archivo y aplicar ajuste
4. Revisar el resumen de cambios
5. Verificar si hay lotes que ahora quedan fuera de rango
6. Ajustar manualmente si es necesario
7. Exportar el PDF actualizado
```

### Si necesita rehacer todo desde cero

```
1. Ir a "Cargar Oferta"
2. Confirmar la sobreescritura
3. Subir nuevo archivo
4. Regenerar la proyección
```

---

## 13. Glosario de términos

| Término | Definición |
|---|---|
| **Lote** | Un grupo de pollos de un mismo galpón, granja y núcleo |
| **Oferta** | Conjunto de lotes disponibles para faena, informado por las granjas |
| **Proyección** | Planificación de qué lotes se retiran cada día de la semana |
| **Faena** | Proceso industrial de sacrificio y procesamiento de los pollos |
| **Peso vivo** | Peso estimado del pollo al momento del retiro en la granja |
| **Peso faenado** | Peso del pollo después del proceso de faena (= peso vivo × rendimiento canal) |
| **Rendimiento canal** | Porcentaje del peso vivo que se conserva tras la faena (por defecto 87%) |
| **Calibre** | Cantidad de pollos que caben en una caja de 20 kg (= kg por caja / peso faenado) |
| **Cajas** | Unidad de producción; cada caja contiene 20 kg de pollo faenado |
| **Ganancia diaria** | Cuántos kg de peso gana un pollo por día |
| **Edad ideal** | Edad óptima de retiro según el sexo del pollo |
| **Diferencia de edad** | Días de más o de menos respecto a la edad ideal |
| **Descuento Sofía** | Constante (10.000 pollos por defecto) que se resta del total semanal |
| **Descuento sin sexar** | Penalización del 4% en peso aplicada a pollos cuyo sexo no se determinó |
| **Galpón** | Estructura individual dentro de una granja donde se crían los pollos |
| **Núcleo** | Subdivisión dentro de una granja (agrupación de galpones) |

---

## 14. Preguntas frecuentes

### ¿Puedo cargar la oferta más de una vez?
Sí. Cada vez que carga una nueva oferta desde "Cargar Oferta", **reemplaza completamente** la oferta anterior y la proyección. Si solo desea actualizar datos de peso/edad sin perder la planificación, use "Ajustar con Oferta del Martes" en la pestaña Proyección.

### ¿Qué pasa si el archivo Excel tiene un formato diferente?
El sistema esperará las columnas en el orden indicado en la sección 5.1. Si el formato difiere, se producirá un error con un mensaje descriptivo. Asegúrese de que el archivo siga la estructura "OFERTA JUEV".

### ¿Los cambios en Parámetros afectan la proyección existente?
No de forma automática. Los parámetros se aplican al **generar una nueva proyección** o al **aplicar un ajuste martes**. Si desea que los nuevos parámetros se reflejen, debe regenerar la proyección.

### ¿Puedo trabajar con 5 días de faena en vez de 6?
Sí. Al generar la proyección, seleccione "5 días" en el menú desplegable. La distribución se hará de lunes a viernes.

### ¿Qué significa "Sofía"?
Es un indicador que resta una cantidad fija (por defecto 10.000) al total de pollos semanales. Representa un ajuste contractual o de destino específico. El valor es configurable desde Parámetros.

### ¿Puedo agregar un lote manualmente?
Actualmente, los lotes se agregan cargando el archivo Excel. La interfaz principal no tiene un formulario de ingreso manual individual, pero la API del backend sí soporta esta operación.

### ¿Mis datos se pierden al cerrar el navegador?
No. Los datos (oferta, proyección, parámetros) se almacenan en el servidor y persisten entre sesiones. Al volver a iniciar sesión, se cargarán automáticamente.

### ¿Puedo usar la app desde el celular?
La interfaz es responsive y funciona en dispositivos móviles, aunque la experiencia óptima es en pantallas de escritorio o tablet dado el volumen de datos tabulares.

---

## 15. Solución de problemas

| Problema | Causa posible | Solución |
|---|---|---|
| "Usuario o contraseña incorrectos" | Credenciales erróneas | Verifique con el administrador sus datos de acceso |
| "Error al procesar el archivo" | Formato de Excel incorrecto | Revise que el archivo tenga las columnas en el orden esperado (sección 5.1) |
| "No hay oferta cargada" | Intentó generar proyección sin cargar archivo | Vaya a "Cargar Oferta" y suba el Excel primero |
| "No hay proyección generada" | No se ha ejecutado la generación | Vaya a "Oferta" y haga clic en "Generar Proyección Automática" |
| Muchos lotes fuera de rango | Parámetros de edad/peso muy restrictivos | Revise y ajuste los rangos en la pestaña "Parámetros" |
| Lotes no asignados por tope diario | Más pollos ofertados que capacidad configurada | Aumente el objetivo de "Pollos diarios máx." o agregue más días de faena |
| La página se queda cargando | Problema de red o servidor | Recargue la página (F5). Si persiste, verifique que el servidor esté activo |
| Sesión expirada (redirige al login) | Token JWT caducado | Inicie sesión nuevamente |
| PDF sale en blanco o incompleto | Navegador bloquea descargas | Permita descargas desde el navegador para este sitio |

---

> **¿Necesita ayuda adicional?** Contacte al administrador del sistema o al equipo de desarrollo.
