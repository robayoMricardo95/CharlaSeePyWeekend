"""
app.py — el agente del notebook 03, como servicio web.

Es exactamente el mismo agente: gpt-4.1 en Azure AI Foundry, la tool
ejecutar_sql sobre la tabla sabana, las mismas instrucciones y el diccionario
de datos. Lo único nuevo es que ahora vive en un servidor y cualquiera le puede
preguntar por HTTP: un notebook, curl, o el front en Streamlit (06_front).

La memoria funciona igual que en el 03: cada conversación es un HILO
(thread_id). Si mandas la misma "hilo", el agente recuerda lo anterior.

Endpoints:
    GET  /salud              ¿está vivo el servicio?
    POST /chat               pregunta -> respuesta completa (JSON)
    POST /chat/stream        pregunta -> los pasos a medida que ocurren (NDJSON)
    GET  /hilos/{hilo}       qué se ha preguntado en un hilo

Para levantarlo, desde la raíz del repositorio:
    uvicorn app:app --app-dir 05_api --port 8000

Documentación interactiva, ya levantado:  http://localhost:8000/docs
"""

import json
import os
import sqlite3
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

# ------------------------------------------------------------- configuración

RAIZ = Path(__file__).resolve().parent.parent          # la carpeta del repositorio
BASE = RAIZ / "datos" / "reclamos.db"
DICCIONARIO = RAIZ / "datos" / "diccionario_sabana.yaml"
load_dotenv(RAIZ / ".env")                             # las credenciales (ver notebook 01)

# USD por millón de tokens de gpt-4.1 (consultado el 2026-10-07).
PRECIO = {"entrada": 2.00, "cache_lectura": 0.50, "salida": 8.00}

# ------------------------------------------------------------- el agente (igual que en 03)

foundry = ChatOpenAI(
    base_url=os.environ["AZURE_OPENAI_BASE_URL"],      # a dónde llamar
    api_key=os.environ["AZURE_OPENAI_API_KEY"],        # quién llama
    model=os.environ["AZURE_OPENAI_MODELO"],           # qué modelo
    temperature=0,
)

diccionario = yaml.safe_load(DICCIONARIO.read_text(encoding="utf-8"))
diccionario["consultas_ejemplo"] = [e for e in diccionario["consultas_ejemplo"]
                                    if e["activa_desde"] <= "03"]
contexto = yaml.dump(diccionario, allow_unicode=True, sort_keys=False)


@tool
def ejecutar_sql(sql: str) -> str:
    """Ejecuta una consulta SQL de solo lectura sobre la tabla sabana (SQLite) y devuelve columnas y filas."""
    conexion = sqlite3.connect(BASE.as_uri() + "?mode=ro", uri=True)    # ro = solo lectura
    cursor = conexion.execute(sql)
    columnas = [c[0] for c in cursor.description]
    filas = cursor.fetchall()
    conexion.close()
    return json.dumps({"columnas": columnas, "filas": filas}, ensure_ascii=False)


instrucciones = """Eres un analista de siniestralidad. Respondes con datos de la tabla sabana usando la tool ejecutar_sql.
Reglas:
- Antes de responder, decide qué consultas necesitas y ejecútalas todas (puedes hacer varias).
- Toda cifra y toda variación se calcula en SQL (usa CASE WHEN para poner 2008 y 2009 lado a lado). No hagas cuentas de memoria.
- No cites ninguna cifra que no haya salido de una consulta.
- Responde solo con las aperturas que se piden. No agregues cruces que nadie pidió.
- "Mayor variación": primero, la apertura con mayor rango (variación más alta menos la más baja);
  dentro de ella, el grupo cuya variación más se aleja de la variación general.
- Para contar reclamos de un año usa sum(anio = 2008) y sum(anio = 2009), nunca count(*) sin filtrar.
- Si un grupo tiene menos de 100 reclamos en un año, advierte que su variación es poco confiable.
- Declara qué definición de costo usaste.

"""

agente = create_agent(
    foundry,
    tools=[ejecutar_sql],
    system_prompt=instrucciones + contexto,
    checkpointer=InMemorySaver(),     # la memoria por hilo. Vive mientras viva el servidor.
)


def costo_usd(mensaje):
    """Lo que costó una respuesta del modelo: tokens x precio por millón."""
    uso = mensaje.usage_metadata
    de_cache = uso["input_token_details"].get("cache_read", 0)
    return ((uso["input_tokens"] - de_cache) * PRECIO["entrada"]
            + de_cache * PRECIO["cache_lectura"]
            + uso["output_tokens"] * PRECIO["salida"]) / 1_000_000


# ------------------------------------------------------------- el servicio

app = FastAPI(title="Python que piensa · agente de siniestralidad")


class Pregunta(BaseModel):
    pregunta: str                     # lo que pregunta la persona
    hilo: str = "ambulatorio"         # la conversación a la que pertenece (thread_id)


def pasos_del_agente(pregunta: Pregunta):
    """Ejecuta el agente y va entregando cada paso apenas ocurre.

    stream_mode="updates" devuelve un evento por cada nodo del grafo que termina:
    "model" (el modelo decidió algo) o "tools" (se ejecutó una consulta)."""
    config = {"configurable": {"thread_id": pregunta.hilo}}
    total = 0.0
    for evento in agente.stream({"messages": [("user", pregunta.pregunta)]}, config,
                                stream_mode="updates"):
        for nodo, cambio in evento.items():
            for mensaje in cambio["messages"]:
                if nodo == "model":
                    total += costo_usd(mensaje)
                    for pedido in mensaje.tool_calls:          # el modelo pidió una consulta
                        yield {"tipo": "sql", "sql": pedido["args"]["sql"]}
                    if not mensaje.tool_calls:                 # ya no pide nada: es la respuesta
                        yield {"tipo": "respuesta", "texto": mensaje.text}
                elif nodo == "tools":                          # la consulta se ejecutó
                    filas = json.loads(mensaje.content)["filas"]
                    yield {"tipo": "resultado", "filas": len(filas)}
    yield {"tipo": "costo", "usd": round(total, 6), "hilo": pregunta.hilo}


@app.get("/salud")
def salud():
    return {"estado": "ok", "modelo": foundry.model_name, "base": BASE.exists()}


@app.post("/chat")
def chat(pregunta: Pregunta):
    """La respuesta completa de una vez: cómodo para un notebook o para curl."""
    pasos = list(pasos_del_agente(pregunta))
    return {
        "hilo": pregunta.hilo,
        "respuesta": next(p["texto"] for p in pasos if p["tipo"] == "respuesta"),
        "consultas": [p["sql"] for p in pasos if p["tipo"] == "sql"],
        "costo_usd": pasos[-1]["usd"],
    }


@app.post("/chat/stream")
def chat_stream(pregunta: Pregunta):
    """Los pasos a medida que ocurren: una línea JSON por evento (NDJSON).
    El front los muestra en vivo: cada SQL apenas el modelo lo pide."""
    lineas = (json.dumps(paso, ensure_ascii=False) + "\n" for paso in pasos_del_agente(pregunta))
    return StreamingResponse(lineas, media_type="application/x-ndjson")


@app.get("/hilos/{hilo}")
def ver_hilo(hilo: str):
    """Lo que guarda la memoria de un hilo: sus preguntas y cuántos mensajes tiene."""
    estado = agente.get_state({"configurable": {"thread_id": hilo}})
    mensajes = estado.values.get("messages", [])
    return {"hilo": hilo,
            "mensajes": len(mensajes),
            "preguntas": [m.text for m in mensajes if m.type == "human"]}
