import streamlit as st
import time
import datetime
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

def subir_archivo_openai(uploaded_file, nombre_usuario):
    """
    Sube el archivo original asegurando que OpenAI sepa qué tipo de imagen es.
    """
    try:
        # 1. RESETEAR EL PUNTERO (Esto es vital, si no, se lee vacío)
        uploaded_file.seek(0)
        
        # 2. LEER DATOS
        datos_archivo = uploaded_file.read()
        
        # Validación: ¿Está vacío?
        if len(datos_archivo) == 0:
            st.error("❌ Error: El archivo pesa 0 bytes. Intenta tomar la captura de nuevo.")
            return None, None

        # 3. DETECTAR EXTENSIÓN Y TIPO MIME
        # Streamlit nos da el nombre original (ej: screenshot.png)
        nombre_orig = uploaded_file.name.lower()
        
        # Asignamos el MIME type correcto
        mime_type = "image/jpeg" # Default
        ext = "jpg"
        
        if nombre_orig.endswith(".png"):
            mime_type = "image/png"
            ext = "png"
        elif nombre_orig.endswith(".webp"):
            mime_type = "image/webp"
            ext = "webp"
        elif nombre_orig.endswith(".gif"):
            mime_type = "image/gif"
            ext = "gif"
            
        # 4. PREPARAR NOMBRE FINAL
        nombre_limpio = nombre_usuario.strip().replace(" ", "_")
        if not nombre_limpio: nombre_limpio = "Evidencia"
        nombre_final = f"{nombre_limpio}_{int(time.time())}.{ext}"
        
        # 5. SUBIDA CON 3 DATOS (Nombre, Bytes, TipoMime)
        # Esto es lo que faltaba: decirle explícitamente el 'mime_type'
        response = client.files.create(
            file=(nombre_final, datos_archivo, mime_type), 
            purpose="vision"
        )
        return response.id, nombre_final

    except Exception as e:
        st.error(f"Error crítico subiendo: {e}")
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

# --- SIDEBAR ---
with st.sidebar:
    st.header("🗂️ Biblioteca Manual")
    
    with st.expander("📤 Subir Evidencia", expanded=True):
        nombre_manual = st.text_input("Nombre (Ej: Roster OKC):", placeholder="Escribe aquí qué es...")
        archivo_nuevo = st.file_uploader("Pega tu captura:", type=["jpg", "png", "jpeg", "webp"])
        
        if st.button("Guardar en Biblioteca"):
            if not nombre_manual:
                st.error("¡Escribe un nombre primero!")
            elif not archivo_nuevo:
                st.error("¡Falta la imagen!")
            else:
                with st.spinner("Subiendo original..."):
                    rid, nombre_final = subir_archivo_openai(archivo_nuevo, nombre_manual)
                    if rid:
                        st.success(f"Guardado como: {nombre_final}")
                        time.sleep(1)
                        st.rerun()

    st.divider()

    st.write("### Selecciona qué usar hoy:")
    biblioteca = obtener_biblioteca()
    opciones_nombres = [f"{f['name']} ({f['date']})" for f in biblioteca]
    mapa_ids = {f"{f['name']} ({f['date']})": f['id'] for f in biblioteca}
    
    seleccionados_nombres = st.multiselect("Activar imágenes:", options=opciones_nombres, placeholder="Selecciona...")
    ids_activos = [mapa_ids[nombre] for nombre in seleccionados_nombres]

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
            
            elif run.status == 'failed':
                error_msg = run.last_error.message if run.last_error else "Error desconocido"
                st.error(f"❌ Error detallado: {error_msg}")
                if run.last_error:
                    st.code(f"Código: {run.last_error.code}")
            
            else:
                placeholder.markdown(f"❌ Estado inesperado: {run.status}")

    except Exception as e:
        st.error(f"Error: {e}")
