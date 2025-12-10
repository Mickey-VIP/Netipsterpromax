import streamlit as st
import io
import time
from PIL import Image
from openai import OpenAI

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Yarbis Pro", page_icon="🤖")
st.title("🤖 Yarbis Pro (Visión Nativa)")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan secretos. Revisa tu configuración en Streamlit.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- FUNCIONES ---

def redimensionar_imagen(uploaded_file):
    """Procesa la imagen y la devuelve en memoria"""
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"): image = image.convert("RGB")
            
            image.thumbnail((1024, 1024))
            
            byte_stream = io.BytesIO()
            image.save(byte_stream, format="JPEG", quality=85)
            byte_stream.seek(0)
            return byte_stream
        except Exception as e:
            st.error(f"Error procesando imagen: {e}")
    return None

def subir_archivo_openai(byte_stream):
    """Sube el archivo a OpenAI con un nombre ÚNICO basado en la hora"""
    try:
        # Generamos un nombre único: imagen_ + hora actual
        nombre_unico = f"imagen_{int(time.time())}.jpg"
        
        response = client.files.create(
            # Aquí usamos el nombre dinámico
            file=(nombre_unico, byte_stream), 
            purpose="vision"
        )
        return response.id
    except Exception as e:
        st.error(f"Error subiendo a OpenAI: {e}")
        return None

def cancelar_runs_activos():
    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        for run in runs.data:
            if run.status in ["queued", "in_progress", "requires_action"]:
                client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                time.sleep(1)
        return True
    except:
        return False

def cargar_historial():
    messages = []
    try:
        response = client.beta.threads.messages.list(thread_id=thread_id, limit=50, order="asc")
        for msg in response.data:
            content = ""
            for part in msg.content:
                if part.type == 'text': 
                    content += part.text.value
                elif part.type == 'image_file':
                    content += "\n*[Imagen analizada]*\n"
            messages.append({"role": msg.role, "content": content})
    except: pass
    return messages

# --- ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = cargar_historial()

# --- INTERFAZ ---
with st.sidebar:
    st.header("📸 Evidencia")
    if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
    imagen_subida = st.file_uploader("Subir foto", type=["png", "jpg", "jpeg"], key=f"uploader_{st.session_state.uploader_key}")
    
    if st.button("🔄 Recargar Chat"):
        st.cache_data.clear()
        st.session_state.messages = cargar_historial()
        st.rerun()

    if st.button("🔓 Destrabar Yarbis"):
        with st.spinner("Destrabando..."):
            cancelar_runs_activos()
            st.success("Listo.")
            time.sleep(1)
            st.rerun()

# Mostrar historial visual
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- LÓGICA DE CHAT PRINCIPAL ---
prompt = st.chat_input("Escribe aquí...")

if prompt:
    cancelar_runs_activos()

    # 1. Mostrar visualmente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if imagen_subida:
            st.image(imagen_subida, width=200)
            st.caption("Analizando imagen...")

    # 2. Preparar contenido
    try:
        contenido_mensaje = [{"type": "text", "text": prompt}]
        
        if imagen_subida:
            archivo_memoria = redimensionar_imagen(imagen_subida)
            
            if archivo_memoria:
                # Subimos el archivo con el nombre correcto
                file_id = subir_archivo_openai(archivo_memoria)
                
                if file_id:
                    contenido_mensaje.append({
                        "type": "image_file", 
                        "image_file": {"file_id": file_id}
                    })
            
            st.session_state.uploader_key += 1

        # 3. Enviar mensaje
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=contenido_mensaje)

        # 4. Ejecutar Asistente
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Pensando...*")
            
            run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=assistant_id)

            if run.status == 'completed':
                msgs = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
                text = msgs.data[0].content[0].text.value
                import re
                clean_text = re.sub(r'【.*?】', '', text)
                
                placeholder.markdown(clean_text)
                st.session_state.messages.append({"role": "assistant", "content": clean_text})
            else:
                placeholder.markdown(f"❌ Error: {run.status}")

    except Exception as e:
        st.error(f"Error crítico: {e}")
        st.warning("Usa el botón de 'Destrabar Yarbis'.")
