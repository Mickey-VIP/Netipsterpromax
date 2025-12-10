import streamlit as st
import base64
from openai import OpenAI

# Configuración de la página
st.set_page_config(page_title="Yarbis 2.0", page_icon="🤖")
st.title("🤖 Yarbis 2.0 (Historial Eterno)")

# --- 1. CONEXIÓN SEGURA ---
try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = "asst_..." # <--- ¡PON AQUI TU ID DE ASISTENTE (asst_...)!
    thread_id = st.secrets["THREAD_ID"] # <--- Ahora lee el ID fijo de los secretos
except:
    st.error("⚠️ Faltan configurar los Secretos (API Key o Thread ID).")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. FUNCIONES CLAVE ---

def procesar_imagen(uploaded_file):
    """Convierte imagen a base64 para enviarla a GPT"""
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.getvalue()
            base64_image = base64.b64encode(bytes_data).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            st.error(f"Error procesando imagen: {e}")
            return None
    return None

def cargar_historial():
    """Descarga los mensajes viejos de OpenAI para que no se vea vacío"""
    messages = []
    try:
        # Traemos los últimos 20 mensajes (para que cargue rápido)
        response = client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=20,
            order="asc" # Orden cronológico
        )
        for msg in response.data:
            role = msg.role
            content = ""
            # OpenAI devuelve el contenido en partes, hay que unirlo
            for part in msg.content:
                if part.type == 'text':
                    content += part.text.value
            
            messages.append({"role": role, "content": content})
    except Exception as e:
        st.error(f"No pude cargar el historial: {e}")
    return messages

# --- 3. INICIO DE SESIÓN ---

# Si es la primera vez que abres la pestaña, carga el historial de la nube
if "messages" not in st.session_state:
    st.session_state.messages = cargar_historial()

# --- 4. INTERFAZ ---

# Barra lateral para subir fotos y recargar
with st.sidebar:
    st.header("📸 Subir Evidencia")
    imagen_subida = st.file_uploader("Carga JPG o PNG", type=["png", "jpg", "jpeg"])
    
    if st.button("🔄 Recargar Chat"):
        # Borra la memoria local y vuelve a bajarla de la nube
        st.cache_data.clear()
        del st.session_state.messages
        st.rerun()

# Mostrar mensajes
for msg in st.session_state.messages:
    if msg["content"]: # Solo mostrar si hay texto
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- 5. LÓGICA DE CHAT ---
prompt = st.chat_input("Escribe aquí...")

if prompt:
    # A. Mostrar mensaje usuario (Visual inmediata)
    with st.chat_message("user"):
        st.markdown(prompt)
        if imagen_subida:
            st.image(imagen_subida, width=200)
    
    # Agregar a la lista local temporalmente
    st.session_state.messages.append({"role": "user", "content": prompt})

    # B. Preparar el paquete para OpenAI
    contenido_mensaje = [{"type": "text", "text": prompt}]
    
    if imagen_subida:
        url_imagen = procesar_imagen(imagen_subida)
        if url_imagen:
            contenido_mensaje.append({
                "type": "image_url",
                "image_url": {"url": url_imagen}
            })

    # C. Enviar a la nube (Al hilo eterno)
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=contenido_mensaje
    )

    # D. Ejecutar Yarbis
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Pensando...*")
        
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        if run.status == 'completed':
            # Obtener solo el último mensaje
            mensajes = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
            texto_respuesta = mensajes.data[0].content[0].text.value
            
            # Limpieza de texto
            import re
            texto_limpio = re.sub(r'【.*?】', '', texto_respuesta)
            
            message_placeholder.markdown(texto_limpio)
            st.session_state.messages.append({"role": "assistant", "content": texto_limpio})
        else:
            message_placeholder.markdown(f"❌ Error: {run.status}")
