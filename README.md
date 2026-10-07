# Python que piensa

**Agentes de analítica con LangChain y LangGraph.**
Material de la charla para la Sociedad Ecuatoriana de Estadística, semana de Python.

Un agente que responde preguntas de siniestralidad en lenguaje natural sobre una
base de reclamos médicos: entiende la pregunta, planifica, consulta SQL, valida
si el resultado responde, reintenta si no, y redacta la respuesta.

---

## Cómo correr esto

### Requisito previo

```bash
git clone <este-repo>
cd PythonWeekend
pip install -r requirements.txt
cp .env.example .env     # y pon tus claves dentro
jupyter lab
```

### Paso 1 — Construir la base de datos

Todo el procesamiento de datos vive en `datos/` y son **scripts `.py`**, no
notebooks: se corren una vez y no hay nada que mostrar paso a paso.

```bash
cd datos
python descargar.py --descargar   # baja 40 MB desde el CMS y los descomprime
python preparar.py                # construye la base SQLite y la muestra
cd ..
```

| Script | Qué hace |
|---|---|
| `descargar.py` | Verifica los enlaces del CMS, baja los tres `.zip` a `crudos/` y los descomprime en `extraidos/` |
| `preparar.py` | Construye la base: traduce columnas y valores al español, parte las fechas, normaliza los indicadores crónicos, clasifica los diagnósticos por capítulo de la CIE-9, crea los índices y verifica las ocho trampas |
| `catalogos.py` | Las tablas de traducción (sexo, raza, estados, capítulos de la CIE-9). No se ejecuta solo; lo importa `preparar.py` |
| `enriquecer.py` | **Opcional.** Baja las descripciones oficiales de los códigos CIE-9 desde la NLM. Están en inglés; ver más abajo |

`preparar.py` imprime la verificación de las ocho trampas con cifras reales al
terminar. Si algún número no coincide con lo que dice este README, algo se rompió.

Los tres scripts también se usan desde un notebook:

```python
from descargar import descargar
from preparar import main as preparar
descargar()
preparar()
```

**Si tu red bloquea `cms.gov`** (pasa en redes corporativas y entornos con lista
blanca), `descargar.py` te lo dirá. Baja los tres `.zip` a mano desde la [página
de la muestra 1](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1),
descomprímelos en `extraidos/` y corre solo `preparar.py`.

### Paso 2 — Los notebooks, en orden

**`00_setup.ipynb` es el primero.** No construye nada por su cuenta: ejecuta los
scripts del paso 1 desde el notebook, verifica que el entorno tenga todo y deja
la base lista. Está pensado para que cualquiera que clone el repositorio arranque
de ahí.

| # | Notebook | De qué va |
|---|---|---|
| 00 | `00_setup.ipynb` | Corre el pipeline de datos, verifica paquetes, `.env` y que la base responda |
| 01 | `01_llm_basico/` | Qué es un LLM, primera llamada, conexión a Azure AI Foundry, capa para cambiar de proveedor |
| 02 | `02_langchain/` | Prompts, salida estructurada, la herramienta SQL, indexación del diccionario, memoria |
| 03 | `03_langgraph/` | Estado, nodos, aristas condicionales, ciclos, el grafo dibujado |
| 04 | `04_evaluacion/` | Trazas con LangSmith, costo, latencia, 20 preguntas como prueba de regresión |
| 05 | `05_api/` | `app.py` con FastAPI, lanzado y consumido desde el propio notebook |
| 06 | `06_front/` | `index.html`, servido y mostrado dentro del notebook |

Los únicos `.py` del proyecto son los de `datos/` y `05_api/app.py`. Todo lo
demás son notebooks, porque la charla se da ejecutando celdas.

### Consultar la base

Una vez construida, es un archivo SQLite: cualquier cliente lo abre.

```python
import sqlite3
con = sqlite3.connect("datos/reclamos.db")
con.execute("SELECT sum(monto_pagado) FROM hospitalario WHERE anio = 2009").fetchone()
```

**La base no está en el repositorio**, ni completa ni en muestra. Pesa 556 MB y
se reconstruye en menos de un minuto, así que viajarla no tendría sentido.

---

## Los datos

**CMS DE-SynPUF**, muestra 1 de 20. Reclamos médicos sintéticos publicados por
los Centers for Medicare & Medicaid Services de Estados Unidos, construidos a
partir de una muestra del 5 % de beneficiarios reales de Medicare.

> Los datos son sintéticos y el CMS alteró deliberadamente las relaciones entre
> variables para proteger la privacidad. Sirven para construir y probar
> herramientas; **no admiten inferencia sobre la población real de Medicare.**

| Tabla | Grano | Filas | Reclamos distintos |
|---|---|---:|---:|
| `afiliados` | un asegurado | 116 352 | — |
| `hospitalario` | un segmento de reclamo | 66 773 | 66 705 |
| `ambulatorio` | un segmento de reclamo | 790 790 | 779 815 |
| `diagnosticos` | un diagnóstico de un reclamo | 2 611 067 | — |
| `capitulos_cie9` | un capítulo de la CIE-9, en español | 20 | — |

### El diccionario de negocio

`datos/diccionario.yaml` traduce las columnas crípticas del CMS a nombres de
negocio, define las métricas en SQL y documenta las ocho trampas del dato.

**Es el archivo más importante del repositorio.** Es lo que lee el agente antes
de escribir SQL, y la tesis de la charla es justamente esa: el agente no falla
por el modelo, falla por no saber qué significa cada columna.

### Todo en español

No solo los nombres de columna: también los valores.

| Columna | Valores |
|---|---|
| `sexo` | Masculino, Femenino |
| `raza` | Blanca, Negra, Otras, Hispana |
| `estado` | California, Florida, Texas, Nueva York… (52 valores) |
| `grupo_enfermedad` | Enfermedades del aparato circulatorio, Neoplasias… (19 capítulos) |

Las traducciones están en `datos/catalogos.py`, con su fuente anotada.

Las banderas binarias — los once `cronico_*` y `enfermedad_renal_terminal` — se
dejaron en **1/0 y no en "Sí"/"No" a propósito**: así `sum(cronico_diabetes)`
cuenta afiliados con diabetes y `avg()` da la prevalencia, sin escribir un `CASE`
en cada consulta.

### Lo que no se tradujo

| Qué | Valores distintos | Por qué |
|---|---:|---|
| `codigo` CIE-9 de diagnóstico | 11 897 | Sin catálogo oficial en español |
| `procedimiento_1..6` | 4 005 | Sin catálogo, y muy incompletos |
| `grupo_drg` | 739 | Catálogo oficial existe, en inglés |
| `codigo_condado` | 307 | Códigos SSA aleatorizados por el CMS |

Traducir 11 897 términos clínicos sin fuente oficial en español sería inventar
significados médicos, y eso en un repositorio público es peor que no tenerlos.

La solución es el **capítulo de la CIE-9**: 19 grupos de enfermedad, traducidos
completos, que vuelven interpretable cualquier análisis de diagnósticos. En vez
de "el alza está en 41401", el agente responde "el alza está en enfermedades del
aparato circulatorio".

Si además quieres las descripciones código por código, `datos/enriquecer.py` las
baja del catálogo de la NLM a una tabla `cie9_descripciones`. Están en inglés,
es opcional, y el proyecto funciona sin ellas.

### Convenciones de SQLite

SQLite no tiene tipo `DATE`. Las fechas se guardan como texto ISO
`'AAAA-MM-DD'`, que ordena y compara bien. Las tablas de reclamos tienen además
`anio`, `mes` y `dia` como enteros derivados de `fecha_inicio`, con `anio` y
`mes` indexados juntos. Úsalos para filtrar o agrupar en lugar de parsear texto.

---

## Las ocho trampas

Las cifras salieron de ejecutar `preparar.py` sobre la muestra 1 del CMS. El
script las vuelve a verificar cada vez que corre.

1. **Los indicadores crónicos venían invertidos.** 1 = sí, 2 = no en el origen.
   Sumar la columna sin convertirla cuenta a los sanos como enfermos. Resuelto en
   `preparar.py`; la prevalencia de diabetes queda en 37,9 %, que coincide con el
   37,96 % del codebook oficial. Si te sale 62 %, la conversión está mal.
2. **No existe una columna de costo total.** Lo pagado por el asegurador son
   639 260 180; el costo del episodio (sumando deducible, coaseguro y pago de
   tercero), 740 188 096. Un 15,8 % de diferencia, suficiente para cambiar una
   conclusión. El agente debe desambiguar o declarar qué definición usó.
3. **Hay montos negativos y en cero, y son válidos.** 55 reclamos hospitalarios
   negativos (mínimo −8 000) y 2 160 en cero. Un `WHERE monto > 0` reflejo los borra.
4. **Las fechas eran enteros, y el periodo real no es el del nombre del archivo.**
   Venían como `AAAAMMDD`. Los archivos dicen "2008 a 2010" pero traen 224
   reclamos hospitalarios de 2007 y 312 ambulatorios.
5. **Contar filas no es contar reclamos.** Un reclamo largo viene partido en dos
   segmentos: en ambulatorio, 790 790 filas son 779 815 reclamos. Usa
   `count(DISTINCT id_reclamo)`.
6. **Un cuarto de los afiliados no tiene ningún reclamo.** 29 614 de 116 352
   (25,5 %). Un `INNER JOIN` los desaparece e infla el gasto per cápita.
7. **Los montos anuales de `afiliados` son solo de 2008**, mientras las tablas de
   reclamos cubren 2008-2010. Cruzarlos compara un año contra tres.
8. **`'OTHER'` no es un código de diagnóstico.** El CMS dejó esa cadena literal
   en las columnas de diagnóstico, 5 675 veces. No es CIE-9, es un marcador de
   agrupación. Tiene capítulo 99, "Sin clasificar", para que no desaparezca
   silenciosamente en un `GROUP BY`.

## Preguntas de referencia

Con respuesta verificada. Sirven como prueba de regresión del agente; el SQL de
cada una está en `diccionario.yaml`.

| Dificultad | Pregunta | Respuesta |
|---|---|---|
| Fácil | ¿Cuánto se pagó en hospitalización en 2009? | 244 810 270,00 |
| Media | ¿Cómo cambió el costo promedio por reclamo entre 2008 y 2009? | 9 311,83 → 9 702,76 (+4,2 %), con 8,8 % menos reclamos |
| Alta | ¿Qué prestadores tienen estancias más largas que sus pares en el mismo grupo DRG? | — |
| Media | ¿En qué grupos de enfermedad se concentra el costo hospitalario? | Aparato circulatorio 165 127 000 (15 901 reclamos), respiratorio 75 982 000, lesiones 67 375 420 |

La media es la que rompe una cadena lineal: necesita dos consultas y una
comparación entre ellas. Ahí es donde entra LangGraph.

---

## Decisiones de diseño

**SQLite y no un servidor.** Es un archivo, lo lee la biblioteca estándar de
Python y viaja en el repositorio. Nadie tiene que levantar un contenedor para
seguir la charla. Lo que se construye encima funciona igual contra PostgreSQL,
Oracle o SQL Server: lo único que cambia es el conector.

**El paso de datos no usa pandas.** Solo `sqlite3` y `csv` de la biblioteca
estándar, así corre en cualquier Python 3.11+ sin instalar nada.

**Con índices.** SQLite sin índices hace barrido completo en cada join.

**Sin muestra reducida.** Se evaluó y se descartó. Nadie descarga la base: todos
la construyen con `00_setup.ipynb`. Optimizar su tamaño era resolver un problema
que no existe.

**Las 45 columnas HCPCS se descartaron.** En hospitalización vienen casi vacías
porque el pago se calcula por DRG. Solo inflaban la tabla con nulos.

**La tabla `diagnosticos` es derivada, no viene del CMS.** Evita escribir diez
condiciones `OR` para buscar un diagnóstico en cualquier posición. Las columnas
anchas `diagnostico_1..10` se conservan porque esa trampa es pedagógicamente útil.

**El capítulo de la CIE-9 se calcula una vez por código distinto**, no por fila.
Hay 2,6 millones de filas y menos de 12 000 códigos.

---

## Fuentes

- [CMS DE-SynPUF, muestra 1](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1)
- [Codebook (PDF)](https://www.cms.gov/files/document/de-10-codebook.pdf-0)
- [Data Users Document (PDF)](https://www.cms.gov/research-statistics-data-and-systems/downloadable-public-use-files/synpufs/downloads/synpuf_dug.pdf)

En esa página de descarga, el enlace del *Beneficiary Summary 2010* de la muestra 1
apunta por error al archivo de la muestra 20. Es un error del CMS. No afecta a
este proyecto porque solo se usa el de 2008.

## Licencia

MIT. Los datos del CMS son de dominio público.
