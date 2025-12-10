import streamlit as st
import os
import base64
from openai import OpenAI

# --- CONFIGURACIÓN DE USUARIO ---
API_KEY = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID = "asst_R586kupUESTSmqPXjyGhNHOw"                  # <--- ¡PON EL ID DE TU ASISTENTE AQUÍ!
ARCHIVO_THREAD = "mi_hilo_guardado.txt"
# -------------------------------

# Configuración de la página web
st.set_page_config(page_title="Yarbis 2.0", page_icon="🤖")
st.title("🤖 Yarbis 2.0 (Con Ojos)")

# Conexión a OpenAI
client = OpenAI(api_key=API_KEY)

# --- FUNCIONES DE MEMORIA Y VISIÓN ---

def obtener_hilo():
    """Recupera el hilo guardado o crea uno nuevo."""
    if os.path.exists(ARCHIVO_THREAD):
        with open(ARCHIVO_THREAD, "r") as f:
            return f.read().strip()
    else:
        thread = client.beta.threads.create()
        with open(ARCHIVO_THREAD, "w") as f:
            f.write(thread.id)
        return thread.id

def procesar_imagen(uploaded_file):
    """Convierte la imagen subida a formato base64 para que GPT la vea."""
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_image}"
    return None

# --- LÓGICA DEL CHAT ---

# 1. Inicializar sesión y cargar hilo
if "thread_id" not in st.session_state:
    st.session_state.thread_id = obtener_hilo()

if "messages" not in st.session_state:
    st.session_state.messages = []

# 2. Barra lateral para subir imágenes
with st.sidebar:
    st.header("📸 Subir Evidencia")
    imagen_subida = st.file_uploader("Carga una imagen para análisis", type=["png", "jpg", "jpeg"])
    
    if st.button("🗑️ Borrar Memoria (Reiniciar Chat)"):
        if os.path.exists(ARCHIVO_THREAD):
            os.remove(ARCHIVO_THREAD)
        st.session_state.messages = []
        del st.session_state.thread_id
        st.rerun()

# 3. Mostrar historial visual en pantalla
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "image" in msg and msg["image"]:
            st.image(msg["image"], width=200)

# 4. CAPTURAR ENTRADA DEL USUARIO
prompt = st.chat_input("Escribe tu mensaje aquí...")

if prompt:
    # A. Mostrar mensaje del usuario de inmediato
    with st.chat_message("user"):
        st.markdown(prompt)
        # Si hay imagen, la mostramos también
        if imagen_subida:
            st.image(imagen_subida, width=200)
            st.caption("Imagen adjunta enviada.")
    
    # Guardar en historial visual local
    st.session_state.messages.append({"role": "user", "content": prompt, "image": imagen_subida})

    # B. Preparar el mensaje para OpenAI (Texto + Imagen si existe)
    contenido_mensaje = [{"type": "text", "text": prompt}]
    
    if imagen_subida:
        url_imagen = procesar_imagen(imagen_subida)
        contenido_mensaje.append({
            "type": "image_url",
            "image_url": {"url": url_imagen}
        })

    # C. Enviarlo al hilo en la nube
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=contenido_mensaje
    )

    # D. Ejecutar al Asistente
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Analizando...*")
        
        run = client.beta.threads.runs.create_and_poll(
            thread_id=st.session_state.thread_id,
            assistant_id=ASSISTANT_ID
        )

        if run.status == 'completed':
            mensajes = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
            # La respuesta 0 es la última
            texto_respuesta = mensajes.data[0].content[0].text.value
            
            # Limpiar anotaciones raras de citas [source]
            import re
            texto_limpio = re.sub(r'【.*?】', '', texto_respuesta)
            
            message_placeholder.markdown(texto_limpio)
            st.session_state.messages.append({"role": "assistant", "content": texto_limpio})
        else:
            message_placeholder.markdown(f"❌ Error: {run.status}")