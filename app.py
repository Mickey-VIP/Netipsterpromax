import streamlit as st
import base64
from PIL import Image
import io
from openai import OpenAI

# Configuración de la página
st.set_page_config(page_title="Yarbis Pro", page_icon="🤖")
st.title("🤖 Yarbis Pro (Self-Healing)")

# --- 1. CONEXIÓN ---
try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"] # Asegúrate de tener este nombre en Secrets
    thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan configurar los Secretos. Revisa tu archivo secrets.toml en Streamlit.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. FUNCIONES DE UTILIDAD ---

def procesar_imagen(uploaded_file):
    """Procesa imagen para evitar errores de formato"""
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"): image = image.convert("RGB")
            max_size = (1024, 1024)
            image.thumbnail(max_size)
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            st.error(f"Error imagen: {e}")
            return None
    return None

def verificar_estado_hilo():
    """Revisa si el hilo está trabado en una ejecución anterior"""
    try:
        # Buscamos si hay ejecuciones activas (queued, in_progress, etc)
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        for run in runs.data:
            if run.status in ["queued", "in_progress", "requires_action", "cancelling"]:
                return run.id
        return None
    except:
        return None

def cancelar_run(run_id):
    """Cancela una ejecución trabada"""
    try:
        client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
        return True
    except Exception as e:
        st.error(f"No se pudo cancelar: {e}")
        return False

def cargar_historial():
    """Descarga mensajes previos"""
    messages = []
    try:
        response = client.beta.threads.messages.list(
            thread_id=thread_id, limit=20, order="asc"
        )
        for msg in response.data:
            role = msg.role
            content = ""
            for part in msg.content:
                if part.type == 'text':
                    content += part.text.value
            messages.append({"role": role, "content": content})
    except:
        pass
    return messages

# --- 3. LÓGICA PRINCIPAL ---

# A. SISTEMA DE DESBLOQUEO (Lo primero que revisa)
run_trabado = verificar_estado_hilo()

if run_trabado:
    st.warning("⚠️ Yarbis se quedó pensando en una sesión anterior y el chat está bloqueado.")
    if st.button("🔓 DETENER Y DESBLOQUEAR"):
        with st.spinner("Cancelando proceso anterior..."):
            if cancelar_run(run_trabado):
                st.success("¡Listo! Hilo liberado.")
                st.rerun() # Recarga la página
    st.stop() # Detiene la app aquí hasta que se desbloquee

# B. CARGA DE CHAT (Solo si no está trabado)
if "messages" not in st.session_state:
    st.session_state.messages = cargar_historial()

# Barra lateral
with st.sidebar:
    st.header("📸 Evidencia")
    imagen_subida = st.file_uploader("Subir foto", type=["png", "jpg", "jpeg"])
    if st.button("🔄 Actualizar Chat"):
        st.cache_data.clear()
        del st.session_state.messages
        st.rerun()

# Mostrar mensajes
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# C. INPUT DE USUARIO
prompt = st.chat_input("Escribe aquí...")

if prompt:
    # Mostrar visualmente
    with st.chat_message("user"):
        st.markdown(prompt)
        if imagen_subida:
            st.image(imagen_subida, width=200)
