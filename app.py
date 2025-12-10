import streamlit as st
import base64
from PIL import Image
import io
import time
from openai import OpenAI

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Yarbis Pro", page_icon="🤖")
st.title("🤖 Yarbis Pro (Chat Continuo)")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan secretos. Revisa tu configuración en Streamlit.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- FUNCIONES ---
def procesar_imagen(uploaded_file):
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"): image = image.convert("RGB")
            image.thumbnail((1024, 1024))
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            st.error(f"Error imagen: {e}")
    return None

def cargar_historial():
    messages = []
    try:
        # Traemos más mensajes para tener mejor contexto
        response = client.beta.threads.messages.list(thread_id=thread_id, limit=50, order="asc")
        for msg in response.data:
            content = ""
            for part in msg.content:
                if part.type == 'text': content += part.text.value
            messages.append({"role": msg.role, "content": content})
    except: pass
    return messages

# --- ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = cargar_historial()

# --- INTERFAZ ---
with st.sidebar:
    st.header("📸 Evidencia")
    # Usamos una clave única para el uploader para resetearlo después de usarlo
    if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
    imagen_subida = st.file_uploader("Subir foto", type=["png", "jpg", "jpeg"], key=f"uploader_{st.session_state.uploader_key}")
    
    if st.button("🔄 Recargar Chat"):
        st.cache_data.clear()
        st.session_state.messages = cargar_historial()
        st.rerun()

# Mostrar historial visual
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- LÓGICA DE CHAT PRINCIPAL ---
prompt = st.chat_input("Escribe aquí...")

if prompt:
    # 1. AGREGAR MENSAJE DE USUARIO AL HISTORIAL VISUAL INMEDIATAMENTE
    # Esto asegura que se vea tu mensaje nuevo y no se sobrescriba el anterior.
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if imagen_subida:
            st.image(imagen_subida, width=200)

    # 2. Preparar y enviar a OpenAI
    contenido_mensaje = [{"type": "text", "text": prompt}]
    if imagen_subida:
        url = procesar_imagen(imagen_subida)
        if url: contenido_mensaje.append({"type": "image_url", "image_url": {"url": url}})
        # Importante: Resetear el uploader para la próxima vez
        st.session_state.uploader_key += 1

    client.beta.threads.messages.create(thread_id=thread_id, role="user", content=contenido_mensaje)

    # 3. EJECUTAR AL ASISTENTE Y ESPERAR RESPUESTA
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⏳ *Pensando...*")
        
        run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=assistant_id)

        if run.status == 'completed':
            msgs = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
            text = msgs.data[0].content[0].text.value
            import re
            clean_text = re.sub(r'【.*?】', '', text)
            
            # Mostrar respuesta
            placeholder.markdown(clean_text)
            
            # 4. AGREGAR RESPUESTA DEL ASISTENTE AL HISTORIAL VISUAL
            # Fundamental para que la respuesta se quede ahí y no desaparezca.
            st.session_state.messages.append({"role": "assistant", "content": clean_text})
        else:
            placeholder.markdown(f"❌ Error: {run.status}")
