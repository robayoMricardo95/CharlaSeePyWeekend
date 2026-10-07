"""
app_streamlit.py — un chat mínimo para hablar con el agente.

No tiene lógica de IA: todo lo hace la API (05_api/app.py). Este archivo solo
manda la pregunta por HTTP y va mostrando lo que llega: cada SQL que el agente
decide ejecutar, la respuesta y lo que costó.

Primero levanta la API, después este front. Desde la raíz del repositorio:
    uvicorn app:app --app-dir 05_api --port 8000
    streamlit run 06_front/app_streamlit.py

Se abre solo en el navegador: http://localhost:8501
"""

import json

import requests
import streamlit as st

st.set_page_config(page_title="Python que piensa", page_icon="🩺", layout="centered")
st.title("Agente de siniestralidad")
st.caption("Reclamos médicos sintéticos del CMS · gpt-4.1 en Azure AI Foundry · LangGraph")

# ------------------------------------------------------------- barra lateral

with st.sidebar:
    api = st.text_input("Dirección de la API", "http://localhost:8000")

    # El hilo es la memoria: misma conversación, mismo hilo (thread_id).
    hilo = st.text_input("Hilo de conversación", "ambulatorio")

    # Las preguntas del notebook 03, para la demo. Cada botón la manda al chat.
    st.subheader("Preguntas de la demo")
    ejemplos = [
        "¿Cómo cambió el costo ambulatorio de 2008 a 2009? Dame la variación general, "
        "la variación por sexo y la variación por raza, cada una por separado, "
        "y dime dónde está la mayor variación.",
        "Donde está la mayor variación, ábrelo por grupo etario.",
        "En el grupo etario que más creció, ¿en qué grupos de enfermedad se concentró el alza?",
        "De todo lo que vimos, ¿cuál es el hallazgo principal para un gerente, en dos frases?",
    ]
    for numero, ejemplo in enumerate(ejemplos, start=1):
        if st.button(f"Paso {numero}", help=ejemplo, use_container_width=True):
            st.session_state["pendiente"] = ejemplo

    # Lo que la API guarda de este hilo: se lee del checkpointer del agente.
    if st.button("Ver la memoria del hilo", use_container_width=True):
        memoria = requests.get(f"{api}/hilos/{hilo}", timeout=30).json()
        st.write(f"**{memoria['mensajes']} mensajes** en el hilo `{hilo}`")
        for numero, pregunta in enumerate(memoria["preguntas"], start=1):
            st.write(f"{numero}. {pregunta}")

# ------------------------------------------------------------- el historial

# st.session_state sobrevive entre recargas de la página. Guardamos un historial
# por hilo, para que al cambiar de hilo se vea su propia conversación.
historiales = st.session_state.setdefault("historiales", {})
historial = historiales.setdefault(hilo, [])

for turno in historial:
    with st.chat_message(turno["rol"]):
        if turno.get("consultas"):
            with st.expander(f"{len(turno['consultas'])} consultas SQL"):
                for sql in turno["consultas"]:
                    st.code(sql, language="sql")
        st.markdown(turno["texto"])
        if turno.get("costo") is not None:
            st.caption(f"Costo de esta respuesta: USD {turno['costo']:.6f}")

# ------------------------------------------------------------- una pregunta nueva

pregunta = st.chat_input("Pregunta sobre los reclamos…") or st.session_state.pop("pendiente", None)

if pregunta:
    historial.append({"rol": "user", "texto": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        consultas, respuesta, costo = [], "", None
        # st.status es una caja que se va llenando mientras el agente trabaja.
        with st.status("El agente está trabajando…", expanded=True) as estado:
            # stream=True: leemos la respuesta línea por línea, a medida que llega.
            with requests.post(f"{api}/chat/stream", json={"pregunta": pregunta, "hilo": hilo},
                               stream=True, timeout=600) as r:
                for linea in r.iter_lines(decode_unicode=True):
                    if not linea:
                        continue
                    paso = json.loads(linea)          # cada línea es un paso del agente
                    if paso["tipo"] == "sql":         # el modelo decidió ejecutar una consulta
                        consultas.append(paso["sql"])
                        st.code(paso["sql"], language="sql")
                    elif paso["tipo"] == "resultado":
                        st.write(f"↳ {paso['filas']} filas")
                    elif paso["tipo"] == "respuesta":
                        respuesta = paso["texto"]
                    elif paso["tipo"] == "costo":
                        costo = paso["usd"]
            estado.update(label=f"Listo · {len(consultas)} consultas SQL", state="complete",
                          expanded=False)
        st.markdown(respuesta)
        st.caption(f"Costo de esta respuesta: USD {costo:.6f}")

    historial.append({"rol": "assistant", "texto": respuesta, "consultas": consultas, "costo": costo})
