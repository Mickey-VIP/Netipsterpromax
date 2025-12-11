import streamlit as st
import io
import time
import datetime
from PIL import Image
from openai import OpenAI

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Yarbis Bets Control", page_icon="🎯")
st.title("🎯 Yarbis: Panel de Control")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan secretos.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- FUNCIONES ---

def redimensionar_imagen(uploaded_file):
    """
    Versión HD: Mantiene la calidad alta para que se lean los números pequeños.
    """
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            
            # Convertir a RGB si es necesario
            if image.mode in ("RGBA", "P"): 
                image = image.convert("RGB")
            
            # CAMBIO CLAVE: Aumentamos el límite de 1024 a 4096 píxeles.
            # Esto permite que las tablas grandes se vean nítidas.
            max_size = (4096, 4096) 
            image.thumbnail(max_size, Image.Resampling.LANCZOS) # Usamos un filtro de alta calidad
            
            byte_stream = io.BytesIO()
            # Guardamos con calidad al 95% (antes era 85%) y optimizado
            image.save(byte_stream, format="JPEG", quality=95, optimize=True)
            byte_stream.seek(0)
            
            return byte_stream
        except Exception as e:
            st.error(f"Error procesando imagen: {e}")
    return None

def subir_archivo_openai(byte_stream, nombre_usuario):
    """Sube archivo usando el nombre que TÚ escribiste."""
    try:
        # Limpiamos el nombre para que sea seguro (quitamos espacios raros)
        nombre_limpio = nombre_usuario.strip().replace(" ", "_")
        if not nombre_limpio: nombre_limpio = "Evidencia"
        
        # Agregamos timestamp corto para que sea único
        nombre_final = f"{nombre_limpio}_{int(time.time())}.jpg"
        
        response = client.files.create(
            file=(nombre_final, byte_stream), 
            purpose="vision"
        )
        return response.id, nombre_final
    except Exception as e:
        st.error(f"Error subiendo: {e}")
        return None, None

def obtener_biblioteca():
    archivos_disponibles = []
    try:
        response = client.files.list(purpose="vision")
        archivos_ordenados = sorted(response.data, key=lambda x: x.created_at, reverse=True)
        for file in archivos_ordenados:
            fecha = datetime.datetime.fromtimestamp(file.created_at).strftime('%d/%m %H:%M')
            archivos_disponibles.append({
                "id": file.id,
                "name": file.filename, 
                "date": fecha
            })
    except: pass
    return archivos_disponibles

def borrar_archivo(file_id):
    try:
        client.files.delete(file_id)
        return True
    except: return False

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
                elif part.type == 'image_file': content += "\n*[📎 Imagen]*\n"
            messages.append({"role": msg.role, "content": content})
    except: pass
    return messages

# --- ESTADO ---
if "messages" not in st.session_state: st.session_state.messages = cargar_historial()

# --- SIDEBAR (TU PANEL) ---
with st.sidebar:
    st.header("🗂️ Biblioteca Manual")
    
    # 1. ZONA DE CARGA (Ahora con campo de texto)
    with st.expander("📤 Subir Evidencia", expanded=True):
        # AQUI ESTÁ EL CAMBIO: Tú escribes el nombre primero
        nombre_manual = st.text_input("Nombre (Ej: Roster OKC):", placeholder="Escribe aquí qué es...")
        
        archivo_nuevo = st.file_uploader("Pega tu captura:", type=["jpg", "png", "jpeg"])
        
        if st.button("Guardar en Biblioteca"):
            if not nombre_manual:
                st.error("¡Escribe un nombre primero!")
            elif not archivo_nuevo:
                st.error("¡Falta la imagen!")
            else:
                with st.spinner("Subiendo..."):
                    bytes_img = redimensionar_imagen(archivo_nuevo)
                    if bytes_img:
                        rid, nombre_final = subir_archivo_openai(bytes_img, nombre_manual)
                        if rid:
                            st.success(f"Guardado como: {nombre_final}")
                            time.sleep(1)
                            st.rerun()

    st.divider()

    # 2. SELECTOR
    st.write("### Selecciona qué usar hoy:")
    biblioteca = obtener_biblioteca()
    
    # Creamos las opciones para el menú
    opciones_nombres = [f"{f['name']} ({f['date']})" for f in biblioteca]
    mapa_ids = {f"{f['name']} ({f['date']})": f['id'] for f in biblioteca}
    
    seleccionados_nombres = st.multiselect("Activar imágenes:", options=opciones_nombres, placeholder="Selecciona...")
    ids_activos = [mapa_ids[nombre] for nombre in seleccionados_nombres]

    # 3. BORRAR
    if biblioteca:
        with st.expander("🗑️ Borrar archivos"):
            borrar_nombre = st.selectbox("Eliminar:", options=opciones_nombres)
            if st.button("Borrar definitivamente"):
                if borrar_archivo(mapa_ids[borrar_nombre]):
                    st.success("Eliminado.")
                    time.sleep(1)
                    st.rerun()

    st.divider()
    if st.button("🔄 Reset Chat"):
        st.cache_data.clear()
        st.session_state.messages = cargar_historial()
        st.rerun()
    if st.button("🔓 Destrabar"):
        cancelar_runs_activos()
        st.rerun()

# --- CHAT ---
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

prompt = st.chat_input("Pregunta sobre las imágenes seleccionadas...")

if prompt:
    cancelar_runs_activos()
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if ids_activos: st.caption(f"📎 Analizando {len(ids_activos)} imágenes activas.")

    try:
        contenido_mensaje = [{"type": "text", "text": prompt}]
        if ids_activos:
            for fid in ids_activos:
                contenido_mensaje.append({"type": "image_file", "image_file": {"file_id": fid}})

        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=contenido_mensaje)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Analizando...*")
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

