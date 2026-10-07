# Python que piensa

**Agentes de analítica con LangChain y LangGraph.**
Material de la charla para la Sociedad Ecuatoriana de Estadística, semana de Python.

**Objetivo:** conocer los frameworks LangChain y LangGraph para construir agentes
de inteligencia artificial, aplicados a la analítica: un agente que responde
preguntas de negocio sobre reclamos médicos consultando la base por sí mismo.

### 🖥️ La presentación

**https://robayomricardo95.github.io/CharlaSeePyWeekend/presentacion/**

También se abre en local: doble clic en `presentacion/index.html`. Tecla **S**
para las notas del orador, **F** para pantalla completa.

> Para que el enlace funcione, GitHub Pages debe estar activo en el repositorio:
> *Settings → Pages → Build and deployment → Deploy from a branch → `main` /
> `(root)` → Save*. Tarda un par de minutos en publicarse.

---

## La ruta: cuatro etapas

| Etapa | Qué se aprende | Dónde |
|---|---|---|
| **1 · El LLM básico** | Qué es un LLM, de dónde se trae (Azure AI Foundry, OpenAI, Claude) y cuánto cuesta cada pregunta | [`01_llm_basico/01_llm_y_agente.ipynb`](01_llm_basico/01_llm_y_agente.ipynb) |
| **2 · LangChain** | El LLM escribe el SQL y nuestro código lo ejecuta: el diccionario de datos, la caché, la tool SQL y la cadena | [`02_langchain/02_langchain.ipynb`](02_langchain/02_langchain.ipynb) |
| **3 · LangGraph** | El agente es un ciclo (`create_agent`) que decide cuántas consultas hacer, con memoria por hilo | [`03_langgraph/03_langgraph.ipynb`](03_langgraph/03_langgraph.ipynb) |
| **4 · API y front** | El mismo agente como servicio (FastAPI) y un chat para usarlo (Streamlit) | [`05_api/app.py`](05_api/app.py) · [`06_front/app_streamlit.py`](06_front/app_streamlit.py) |

Antes de todo, [`00_setup.ipynb`](00_setup.ipynb) construye la base y verifica el
entorno. Los notebooks se guardan **con sus resultados**: se pueden leer en GitHub
sin ejecutar nada. Cada llamada al modelo imprime el modelo que respondió, sus
tokens y su costo en dólares.

---

## Cómo correrlo

### 1. Instalar y configurar

```bash
git clone https://github.com/robayoMricardo95/CharlaSeePyWeekend.git
cd CharlaSeePyWeekend
pip install -r requirements.txt
cp .env.example .env          # y completa tus credenciales
```

Variables del `.env`:

| Variable | Para qué |
|---|---|
| `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_MODELO` | El modelo de trabajo: gpt-4.1 en Azure AI Foundry (endpoint terminado en `/openai/v1`) |
| `OPENAI_API_KEY`, `OPENAI_MODELO` | OpenAI directo (solo el ejemplo 1 del notebook 01) |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODELO` | Claude (solo el ejemplo 1 del notebook 01) |

> **Windows 11:** el *Control de aplicaciones inteligente* bloquea los binarios de
> `jiter` 0.17 y `tiktoken` 0.14, y sin ellos no carga `openai`. Por eso
> `requirements.txt` fija `jiter==0.16.0` y `tiktoken==0.13.0`.

### 2. Construir la base

Abre `00_setup.ipynb` y ejecútalo, o desde la terminal:

```bash
cd datos
python descargar.py --descargar   # baja 40 MB desde el CMS y los descomprime
python preparar.py                # construye la base SQLite (~45 s)
python sabana.py                  # arma la tabla que lee el agente (~30 s)
cd ..
```

### 3. Los notebooks, en orden

`01` → `02` → `03`. Cada uno es independiente: carga su propio modelo y su propio
diccionario.

### 4. El agente como servicio

Desde la raíz del repositorio, en dos terminales:

```bash
uvicorn app:app --app-dir 05_api --port 8000     # la API
streamlit run 06_front/app_streamlit.py          # el chat
```

- API documentada e interactiva: http://localhost:8000/docs
- Chat: http://localhost:8501

| Ruta | Qué hace |
|---|---|
| `POST /chat` | Pregunta → respuesta completa (JSON) |
| `POST /chat/stream` | Pregunta → cada paso en vivo, una línea JSON por evento |
| `GET /hilos/{hilo}` | Lo que guarda la memoria de un hilo |
| `GET /salud` | ¿Está vivo el servicio? |

---

## Lo que muestra cada etapa (resultados reales)

### 1 · El LLM básico

- La misma pregunta, con LangChain, es **la misma línea** (`modelo.invoke`) para
  Foundry, OpenAI y Claude. Claude razona antes de responder: en la corrida
  guardada gastó 80 tokens de salida contra 8-9 de gpt-4.1 (USD 0,000856 contra
  0,000106).
- No sabe qué día es ("10 de junio de 2024") ni conoce nuestros datos.
- El notebook completo cuesta USD 0,005.

### 2 · LangChain

| Escenario | Resultado |
|---|---|
| Solo los nombres de las columnas | Escribe `ambito = 'hospitalización'` → `None` |
| Con el diccionario en el prompt | `ambito = 'Hospitalario'` → **245 512 790** ✓ |

**La caché** (automática en Foundry):

| Escenario | Tokens de entrada | Con caché | Sin caché | Ahorro |
|---|---:|---:|---:|---:|
| Sin diccionario | 161 | USD 0,000658 | 0,000658 | 0 % |
| Con diccionario | 3 609 | USD 0,002090 | 0,007466 | 72,0 % |
| Con diccionario, en caché | 3 610 | USD 0,002124 | 0,007500 | 71,7 % |

La pregunta de seguimiento ("¿y comparado con el año anterior…?") necesita
memoria: con ella el agente mantiene el contexto, pero no siempre acierta. En
corridas de prueba citó un total hospitalario de 2008 que no había consultado.
El notebook completo cuesta USD 0,028.

### 3 · LangGraph

Un hilo de conversación sobre el costo ambulatorio, abierto en cuatro pasos:
panorama (general, sexo y raza) → mayor variación por grupo etario → grupos de
enfermedad → hallazgo para un gerente.

Los valores reales: variación general **+20,1 %**; rango por sexo 3,0 puntos; rango
por raza **4,2** puntos. La regla de "mayor variación" manda abrir raza =
Hispana (+16,2 %). En la corrida guardada el agente dijo que el mayor rango era
sexo y abrió Masculino: la verificación automática del notebook lo detecta. El
notebook completo cuesta USD 0,06.

---

## Los datos

**CMS DE-SynPUF**, muestra 1 de 20. Reclamos médicos sintéticos publicados por
los Centers for Medicare & Medicaid Services de Estados Unidos.

> Los datos son sintéticos y el CMS alteró deliberadamente las relaciones entre
> variables para proteger la privacidad. Sirven para construir y probar
> herramientas; **no admiten inferencia sobre la población real de Medicare.**

### Dos modelos en la misma base

**Desagregado** (lo arma `preparar.py`, documentado en `datos/diccionario.yaml`):

| Tabla | Grano | Filas |
|---|---|---:|
| `afiliados` | un asegurado | 116 352 |
| `hospitalario` | un segmento de reclamo | 66 773 |
| `ambulatorio` | un segmento de reclamo | 790 790 |
| `diagnosticos` | un diagnóstico de un reclamo | 2 611 067 |
| `capitulos_cie9` | un capítulo de la CIE-9, en español | 20 |

**Agregado** (lo arma `sabana.py`, documentado en `datos/diccionario_sabana.yaml`):
la tabla `sabana`, **una fila por reclamo**, hospitalario y ambulatorio juntos,
sin uniones que el agente pueda escribir mal. **Es la única tabla que lee el
agente.**

- 656 147 reclamos, 25 columnas, solo 2008 y 2009 (los dos años completos).
- Se retiraron 2007 (solo nov-dic), 2010 (incompleto), 2 016 reclamos con
  monto negativo y 278 sin fecha.
- `monto_total` = pagado + deducible + coaseguro + tercero. `monto_pagado` es
  la métrica por defecto.
- `edad` a la fecha del reclamo y `banda_edad` (0-5, 6-10 y de 10 en 10 hasta
  71+). Las bandas de 0 a 20 quedan vacías: Medicare cubre a mayores de 65 y a
  personas con discapacidad.
- No permite calcular gasto per cápita: solo tiene afiliados con reclamos.

### El diccionario de la sábana

`datos/diccionario_sabana.yaml` es **lo que lee el agente antes de escribir SQL**:
el significado y los valores de cada columna, las trampas del dato y consultas de
ejemplo con su resultado verificado. Los ejemplos se activan por módulo
(`activa_desde`): los básicos desde el 02, los comparativos y de varios pasos
desde el 03.

### Todo en español

| Columna | Valores |
|---|---|
| `ambito` | Hospitalario, Ambulatorio |
| `sexo` | Masculino, Femenino |
| `raza` | Blanca, Negra, Otras, Hispana |
| `estado` | California, Florida, Texas, Nueva York… (52 valores) |
| `grupo_enfermedad` | Enfermedades del aparato circulatorio, Neoplasias… (capítulos CIE-9) |

**Lo que no se tradujo:** los 11 897 códigos CIE-9 de diagnóstico, los
procedimientos y los 739 grupos DRG. Traducir terminología clínica sin fuente
oficial sería inventar. El agente usa `grupo_enfermedad` para hablar de
enfermedades, y si cita un código, dice que no tiene su descripción.
`datos/enriquecer.py` (opcional) baja las descripciones oficiales en inglés.

---

## Las trampas del dato

El agente no falla por el modelo: falla por no saber qué significa cada columna.

1. **Los indicadores crónicos venían invertidos** (1 = sí, 2 = no). Convertidos a
   1/0: la prevalencia de diabetes queda en 37,9 %, como en el codebook (37,96 %).
2. **No existe un único "costo".** En 2009, `monto_total` es 20,7 % mayor que
   `monto_pagado`. El agente debe declarar qué definición usó.
3. **Hay montos en cero, y son válidos.** Un `WHERE monto > 0` reflejo los borra.
4. **Los archivos dicen 2008-2010, pero traen reclamos de 2007** y 2010 está
   incompleto.
5. **Contar filas no es contar reclamos** en las tablas segmentadas. En la
   sábana, `count(*)` sí cuenta reclamos.
6. **El 25,5 % de los afiliados no tiene ningún reclamo.** Un `INNER JOIN` los
   desaparece e infla el gasto per cápita.
7. **Los montos anuales de `afiliados` son solo de 2008.**
8. **`'OTHER'` no es un código de diagnóstico**: es un marcador del CMS.
9. **El segundo segmento de un reclamo no tiene fecha ni diagnóstico.** Un
   `WHERE anio = 2009` sobre la tabla segmentada lo pierde: da 244 810 270 en
   hospitalización 2009, contra 245 512 790 en la sábana.

## Preguntas de referencia (sobre la sábana)

| Pregunta | Respuesta verificada |
|---|---|
| ¿Cuánto se pagó en hospitalización en 2009? | 245 512 790 |
| ¿Cuánto se pagó en ambulatorio en 2009? | 94 184 290 (Femenino 54 452 370, Masculino 39 731 920) |
| ¿Cómo cambió el costo promedio por reclamo hospitalario, 2008 → 2009? | 9 331,21 → 9 738,71 (+4,4 %), con 8,8 % menos reclamos |
| ¿Cómo cambió el costo hospitalario total, 2008 → 2009? | 258 063 920 → 245 512 790 (**−4,9 %**: bajó) |
| ¿Cómo cambió el costo ambulatorio, 2008 → 2009? | 78 449 490 → 94 184 290 (**+20,1 %**) |
| ¿En qué grupos de enfermedad se concentra el costo hospitalario? | Aparato circulatorio 130 733 060, respiratorio 60 921 100, lesiones y envenenamientos 52 526 820 |

---

## Estructura

```
├── 00_setup.ipynb              # construye la base y verifica el entorno
├── 01_llm_basico/              # etapa 1 · el LLM básico
├── 02_langchain/               # etapa 2 · LangChain
├── 03_langgraph/               # etapa 3 · LangGraph
├── 05_api/app.py               # etapa 4 · el agente como servicio (FastAPI)
├── 06_front/app_streamlit.py   # etapa 4 · el chat (Streamlit)
├── presentacion/               # la presentación (reveal.js) y sus imágenes
├── datos/                      # scripts del pipeline y los dos diccionarios
├── GUIA_CHARLA.md              # el recorrido de la charla, bloque por bloque
├── requirements.txt
└── .env.example
```

**La base no está en el repositorio** (pesa ~556 MB): se reconstruye en menos de
un minuto. Tampoco las credenciales: el `.env` está en `.gitignore`.

## Decisiones de diseño

- **SQLite y no un servidor.** Es un archivo y lo lee la biblioteca estándar. Lo
  que se construye encima funciona igual contra PostgreSQL, Oracle o SQL Server:
  cambia el conector.
- **El paso de datos no usa pandas**: solo `sqlite3` y `csv`, corre en cualquier
  Python 3.11+.
- **Una sábana para el agente.** Cada unión es una oportunidad de equivocarse.
- **El diccionario entero en el prompt, y en caché.** Mientras quepa, es más
  simple y más barato que una búsqueda vectorial, y no se equivoca al buscar.
- **Un solo modelo de trabajo** (gpt-4.1 en Foundry). Los otros proveedores
  aparecen solo para mostrar que con LangChain cambiar es cambiar una línea.
- **Costo visible en cada llamada.** Toda celda que llama al modelo imprime cuánto
  costó.

## Pendiente

- `04_evaluacion/`: trazas con LangSmith y preguntas de regresión.
- La memoria de la API vive en el proceso (`InMemorySaver`): si se reinicia, se
  pierden los hilos. Para producción, un checkpointer en base de datos.

## Fuentes

- [CMS DE-SynPUF, muestra 1](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1)
- [Codebook (PDF)](https://www.cms.gov/files/document/de-10-codebook.pdf-0)
- [Data Users Document (PDF)](https://www.cms.gov/research-statistics-data-and-systems/downloadable-public-use-files/synpufs/downloads/synpuf_dug.pdf)
- Precios de los modelos: [OpenAI · gpt-4.1](https://developers.openai.com/api/docs/models/gpt-4.1),
  [Azure OpenAI](https://azure.microsoft.com/es-es/pricing/details/azure-openai),
  [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing) (consultados el 2026-10-07).

## Licencia

MIT. Los datos del CMS son de dominio público. Los logos de la presentación
pertenecen a sus respectivos dueños y se usan solo para identificar cada
herramienta.
