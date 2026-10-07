# Guía de la charla · Python que piensa

Recorrido completo, bloque por bloque, para armar las diapositivas y saber en
qué entorno estás en cada momento. Todas las cifras salen de ejecuciones reales
del 2026-10-07.

## Los entornos y cuándo se salta entre ellos

| Entorno | Qué se muestra | Cuándo |
|---|---|---|
| **Diapositivas** | La teoría: qué es, para qué sirve | Al abrir cada bloque |
| **Consola de Azure AI Foundry** | Deployment, endpoint, key | Bloque 1 |
| **Jupyter** (`01`, `02`, `03`) | El código y su resultado | Bloques 1 a 3 |
| **Terminal** | Levantar la API | Bloque 4 |
| **Navegador · `localhost:8000/docs`** | La API documentada, probarla en vivo | Bloque 4 |
| **Navegador · `localhost:8501`** | El chat en Streamlit | Bloque 4, cierre |

## Antes de la charla (checklist)

```bash
# 1. La base (una vez; tarda ~1 min)
cd datos && python preparar.py && python sabana.py && cd ..

# 2. Terminal A: la API
uvicorn app:app --app-dir 05_api --port 8000

# 3. Terminal B: el front
streamlit run 06_front/app_streamlit.py
```

- Probar `http://localhost:8000/salud` → `{"estado":"ok","modelo":"gpt-4.1","base":true}`.
- **Correr el 02 con la caché fría** (más de 10 minutos sin usarlo) para que la
  tabla de caché muestre la diferencia.
- Recurso de Azure ya desplegado: deployment `gpt-4.1`.
- **Windows:** si Python no importa `openai`, es el Control de aplicaciones;
  `requirements.txt` ya fija `jiter==0.16.0` y `tiktoken==0.13.0`.

---

## Bloque 0 · El problema (00_setup)

**Idea:** el riesgo no es el modelo, es el dato.

- Base CMS DE-SynPUF (sintética, Medicare). Se armó una **sábana**: una fila
  por reclamo, hospitalario y ambulatorio juntos, **656 147 reclamos, 25
  columnas, 2008 y 2009**.
- Se retiró: 2007 (solo nov-dic), 2010 (incompleto), 2 016 reclamos negativos y
  278 sin fecha.
- Advertencia en voz alta: datos sintéticos, no sirven para inferir sobre la
  población real.

## Bloque 1 · Qué es un LLM (notebook 01)

**Idea:** un LLM predice texto. LangChain hace que la llamada sea la misma para
cualquier proveedor.

- **Ejemplo 1, cuatro formas** (SDK `openai` y LangChain con Foundry, OpenAI y
  Claude): misma pregunta, y con LangChain **la misma línea** `modelo.invoke()`.
- **Costo:** la misma pregunta costó ~8 veces más con Claude Sonnet 5.5 (USD
  0,000856 contra 0,000106 de gpt-4.1): razona antes de responder y eso se
  cobra como salida (80 tokens contra 9; varía entre corridas).
- Ejemplos 2 a 4: el rol `system`, la temperatura (0 repite, 1 varía) y los
  tokens (`max_tokens` corta la respuesta).
- **Lo que no puede:** no sabe la fecha (dijo "10 de junio de 2024") y no conoce
  nuestros datos.
- **Decisión de arquitectura:** Foundry (el dato no sale de tu nube) vs. API
  directa vs. suscripción.

**Diapositiva clave:** *"Un LLM es un servicio web que completa texto."*

## Bloque 2 · LangChain (notebook 02)

**Idea:** el LLM escribe el SQL, nuestro código lo ejecuta. El agente no falla
por el modelo: falla por no saber qué significa cada columna.

| Paso | Resultado real |
|---|---|
| Sin diccionario | Escribió `ambito = 'hospitalización'` → `None` |
| Con diccionario | `ambito = 'Hospitalario'` → **245 512 790** ✓ |
| Dos tipos de pregunta | Total ambulatorio 2009: 94 184 290 ✓ · por sexo: 54 452 370 / 39 731 920 ✓ |

**La caché** (gpt-4.1, Foundry, automática):

| Escenario | Tokens de entrada | Con caché | Sin caché | Ahorro |
|---|---:|---:|---:|---:|
| Sin diccionario | 161 | USD 0,000658 | 0,000658 | 0 % |
| Con diccionario | 3 609 | USD 0,002090 | 0,007466 | **72 %** |

- **La tool:** `@tool` + docstring = la ficha que lee el modelo. Pasos 4-6:
  el modelo pide, nuestro código ejecuta, el modelo redacta.
- **La forma rápida:** todo encadenado con `|` en una sola llamada. La
  redacción cuesta casi nada (114 tokens, USD 0,0005): el peso está en el
  diccionario.
- **La pregunta de seguimiento, con memoria** (reenviar la conversación): el
  agente filtró hospitalización, sus cifras cuadraron y advirtió que el costo
  **bajó** 4,9 %… pero en una corrida citó un total 2008 de 258 170 340 que no
  consultó (el real: **258 063 920**).

**Diapositiva clave:** *"Responde con seguridad. Nadie revisa cuándo se
equivoca."*

## Bloque 3 · LangGraph (notebook 03)

**Idea:** `create_agent` es el bucle del agente, hecho con LangGraph. El modelo
decide cuántas consultas hacer. El checkpointer es la memoria por hilo.

- El grafo dibujado: dos nodos, `model ⇄ tools`. *Ese ciclo es el agente.*
- **Un hilo, cuatro pasos** (costo ambulatorio):

| Paso | Pregunta | Consultas |
|---|---|---|
| 1 | General, por sexo y por raza | 3 |
| 2 | "Donde está la mayor variación, ábrelo por grupo etario" | 1 |
| 3 | "En el grupo etario que más creció, ¿en qué enfermedades?" | 1 |
| 4 | Hallazgo para un gerente | 0 (usa la memoria) |

- **Los valores reales:** ambulatorio **+20,1 %**; sexo rango 3,0 puntos
  (Femenino +18,8 %, Masculino +21,8 %); raza rango **4,2** (Hispana +16,2 %).
- **La regla** (en sus instrucciones) manda abrir *raza = Hispana*. El agente
  escribió que el mayor rango era sexo y abrió **Masculino**. La verificación
  lo detecta: *"¿abrió el grupo que dice la regla? No"*.
- Costo de todo el notebook: ~USD 0,06.

**Diapositiva clave:** *"Recuerda bien, razona mal. Sin verificación, nadie lo
nota."* → por eso existe la observabilidad (LangSmith, bloque siguiente).

## Bloque 4 · Del notebook al servicio (05_api + 06_front)

**Idea:** el mismo agente del 03, ahora como servicio web y con una interfaz.

- **`05_api/app.py`** (FastAPI): el agente, sin cambios, detrás de HTTP.
  - `POST /chat` → respuesta completa (JSON)
  - `POST /chat/stream` → los pasos en vivo, una línea JSON por evento
  - `GET /hilos/{hilo}` → la memoria del hilo
  - `GET /docs` → documentación interactiva para mostrar en vivo
- **`06_front/app_streamlit.py`**: un chat. Botones *Paso 1-4* con las
  preguntas del 03, cada SQL aparece apenas el agente lo decide, y el costo de
  cada respuesta. El campo *Hilo* cambia de conversación (memoria separada).
- Medido: una pregunta por la API, USD ~0,008.

**Diapositiva de cierre:** *"Lo que vieron es el motor. En la semana de
productos de IA le ponemos la carrocería: multiusuario, nube y control de
costos."*

## Pendiente

- `04_evaluacion/` (LangSmith, 20 preguntas de regresión): no construido.
- La memoria de la API vive en el proceso (`InMemorySaver`): si se reinicia la
  API, se pierden los hilos. Para producción, un checkpointer en base de datos.
