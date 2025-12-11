import streamlit as st
import io
import time
import datetime
from PIL import Image
from openai import OpenAI

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Yarbis Bets Library", page_icon="📚")
st.title("📚 Yarbis: Biblioteca de Análisis")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan secretos.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- FUNCIONES DE GESTIÓN DE ARCHIVOS ---

def redimensionar_imagen(uploaded_file):
    """Prepara la imagen para subirla ligera."""
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
            st.error(f"Error imagen: {e}")
    return None

def subir_archivo_openai(byte_stream, nombre_usuario):
    """Sube archivo a la nube de OpenAI."""
    try:
        # Usamos el nombre que tú le pongas + timestamp para que no se repita
        ext = int(time.time())
        nombre_final = f"{nombre_usuario}_{ext}.jpg"
        
        response = client.files.create(
            file=(nombre_final, byte_stream), 
            purpose="vision"
        )
        return response.id
    except Exception as e:
        st.error(f"Error subiendo: {e}")
        return None

def obtener_biblioteca():
    """Descarga la lista de archivos que tienes guardados en OpenAI."""
    archivos_disponibles = []
    try:
        # Listamos los archivos con propósito 'vision'
        response = client.files.list(purpose="vision")
        # OpenAI los da desordenados, vamos a ordenarlos por fecha (más nuevo primero)
        archivos_ordenados = sorted(response.data, key=lambda x: x.created_at, reverse=True)
        
        for file in archivos_ordenados:
            # Convertimos timestamp a fecha legible
            fecha = datetime.datetime.fromtimestamp(file.created_at).strftime('%d/%m %H:%M')
            archivos_disponibles.append({
                "id": file.id,
                "name": file.filename,
                "date": fecha
            })
    except Exception as e:
        st.error(f"No pude leer la biblioteca: {e}")
    return archivos_disponibles

def borrar_archivo(file_id):
    """Elimina un archivo de la nube para siempre."""
    try:
        client.files.delete(file_id)
        return True
    except:
        return False

def cancelar_runs_activos():
    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        for run in runs.data:
            if run.status in ["queued", "in_progress", "requires_action"]:
                client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                time.sleep(1)
        return True
    except: return False

def cargar_historial():
    messages = []
    try:
        response = client.beta.threads.messages.list(thread_id=thread_id, limit=50, order="asc")
        for msg in response.data:
            content = ""
            for part in msg.content:
                if part.type == 'text': content += part.text.value
                elif part.type == 'image_file': content += "\n*[📎 Referencia visual usada]*\n"
            messages.append({"role": msg.role, "content": content})
    except: pass
    return messages

# --- ESTADO DE SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = cargar_historial()

# --- BARRA LATERAL (TU BIBLIOTECA) ---
with st.sidebar:
    st.header("🗂️ Tu Biblioteca")
    
    # 1. CARGA DE ARCHIVOS
    with st.expander("📤 Subir Nueva Imagen"):
        nombre_archivo = st.text_input("Nombre (Ej: Roster OKC)", value="Imagen")
        archivo_nuevo = st.file_uploader("Elige foto", type=["jpg", "png", "jpeg"])
        
        if st.button("Guardar en Nube"):
            if archivo_nuevo:
                with st.spinner("Subiendo a la biblioteca..."):
                    bytes_img = redimensionar_imagen(archivo_nuevo)
                    if bytes_img:
                        rid = subir_archivo_openai(bytes_img, nombre_archivo)
                        if rid:
                            st.success("¡Guardada!")
                            time.sleep(1)
                            st.rerun() # Recargar para que aparezca en la lista

    st.divider()

    # 2. SELECTOR DE IMÁGENES (La magia)
    st.write("### Selecciona qué usar hoy:")
    
    # Traemos la lista real desde OpenAI
    biblioteca = obtener_biblioteca()
    
    # Creamos un diccionario para mapear nombres -> IDs
    opciones_nombres = [f"{f['name']} ({f['date']})" for f in biblioteca]
    mapa_ids = {f"{f['name']} ({f['date']})": f['id'] for f in biblioteca}
    
    # El Multiselect permite elegir varias
    seleccionados_nombres = st.multiselect(
        "Activar imágenes:",
        options=opciones_nombres,
        placeholder="Ninguna imagen seleccionada"
    )
    
    # Convertimos los nombres seleccionados a IDs reales
    ids_activos = [mapa_ids[nombre] for nombre in seleccionados_nombres]

    # 3. GESTIÓN (BORRAR)
    if biblioteca:
        with st.expander("🗑️ Borrar imágenes viejas"):
            borrar_nombre = st.selectbox("Elegir para borrar:", options=opciones_nombres)
            if st.button("Eliminar definitivamente"):
                id_a_borrar = mapa_ids[borrar_nombre]
                if borrar_archivo(id_a_borrar):
                    st.success("Borrado.")
                    time.sleep(1)
                    st.rerun()

    st.divider()
    if st.button("🔄 Recargar Chat"):
        st.cache_data.clear()
        st.session_state.messages = cargar_historial()
        st.rerun()
    
    if st.button("🔓 Destrabar"):
        cancelar_runs_activos()
        st.rerun()

# --- CHAT CENTRAL ---

# Mostrar mensajes
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Input usuario
prompt = st.chat_input("Escribe tu pregunta...")

if prompt:
    cancelar_runs_activos()

    # 1. Mostrar mensaje
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        # Mostrar visualmente qué imágenes se están usando
        if ids_activos:
            st.caption(f"📎 Analizando con {len(ids_activos)} imágenes activas de la biblioteca.")

    # 2. Preparar mensaje para OpenAI
    try:
        contenido_mensaje = [{"type": "text", "text": prompt}]
        
        # AGREGAR TODAS LAS IMÁGENES SELECCIONADAS AL MENSAJE
        if ids_activos:
            for fid in ids_activos:
                contenido_mensaje.append({
                    "type": "image_file", 
                    "image_file": {"file_id": fid}
                })

        # 3. Enviar y Ejecutar
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=contenido_mensaje)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Consultando biblioteca...*")
            
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
        st.error(f"Error: {e}")
