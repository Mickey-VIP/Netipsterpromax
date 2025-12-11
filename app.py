import streamlit as st
import io
import time
import datetime
from PIL import Image
from openai import OpenAI

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Yarbis Bets Control", page_icon="🎯")
st.title("🎯 Yarbis: Panel de Control (High-Res)")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    secret_thread_id = st.secrets["THREAD_ID"]
except:
    st.error("⚠️ Faltan secretos.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- GESTIÓN DE HILO ---
if "current_thread_id" not in st.session_state:
    st.session_state.current_thread_id = secret_thread_id

def crear_nuevo_hilo():
    try:
        thread = client.beta.threads.create()
        st.session_state.current_thread_id = thread.id
        st.session_state.messages = []
        st.toast("✅ Hilo Nuevo. Cerebro limpio.", icon="🧠")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

# --- FUNCIONES DE IMAGEN ---

def sanear_imagen(uploaded_file):
    """
    CAMBIO CLAVE: Usamos PNG en lugar de JPEG.
    El PNG es 'lossless' (sin pérdida), ideal para leer números pequeños en tablas.
    """
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            
            # OpenAI Vision maneja mejor RGB
            if image.mode in ("RGBA", "P", "LA"): 
                image = image.convert("RGB")
            
            # Aumentamos límite a 4000px para máxima nitidez
            if image.width > 4000 or image.height > 4000:
                image.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
            
            byte_stream = io.BytesIO()
            # GUARDAMOS COMO PNG (Texto nítido)
            image.save(byte_stream, format="PNG")
            byte_stream.seek(0)
            return byte_stream
        except Exception as e:
            st.error(f"Error imagen: {e}")
    return None

def subir_archivo_openai(byte_stream, nombre_usuario):
    try:
        if byte_stream.getbuffer().nbytes == 0: return None, None

        nombre_limpio = nombre_usuario.strip().replace(" ", "_")
        if not nombre_limpio: nombre_limpio = "Evidencia"
        # Extensión PNG
        nombre_final = f"{nombre_limpio}_{int(time.time())}.png"
        
        response = client.files.create(
            file=(nombre_final, byte_stream, "image/png"), 
            purpose="vision"
        )
        return response.id, nombre_final
    except Exception as e:
        st.error(f"Error subiendo: {e}")
        return None, None

def obtener_biblioteca():
    archivos = []
    try:
        response = client.files.list(purpose="vision")
        sorted_files = sorted(response.data, key=lambda x: x.created_at, reverse=True)
        for f in sorted_files:
            date = datetime.datetime.fromtimestamp(f.created_at).strftime('%d/%m %H:%M')
            archivos.append({"id": f.id, "name": f.filename, "date": date})
    except: pass
    return archivos

def borrar_archivo(file_id):
    try:
        client.files.delete(file_id)
        return True
    except: return False

def cancelar_runs_activos():
    try:
        tid = st.session_state.current_thread_id
        runs = client.beta.threads.runs.list(thread_id=tid)
        for run in runs.data:
            if run.status in ["queued", "in_progress", "requires_action"]:
                client.beta.threads.runs.cancel(thread_id=tid, run_id=run.id)
                time.sleep(1)
        return True
    except: return False

def cargar_historial():
    msgs = []
    try:
        tid = st.session_state.current_thread_id
        response = client.beta.threads.messages.list(thread_id=tid, limit=50, order="asc")
        for m in response.data:
            txt = ""
            for p in m.content:
                if p.type == 'text': txt += p.text.value
                elif p.type == 'image_file': txt += "\n*[📎 Imagen]*\n"
            msgs.append({"role": m.role, "content": txt})
    except: pass
    return msgs

# --- ESTADO ---
if "messages" not in st.session_state: st.session_state.messages = cargar_historial()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🗂️ Panel de Control")
    
    if st.button("🔥 Nuevo Hilo (Reset)", type="primary"):
        crear_nuevo_hilo()

    st.divider()

    with st.expander("📤 Subir Evidencia (PNG Mode)", expanded=True):
        nombre_manual = st.text_input("Nombre:", placeholder="Ej: Roster OKC")
        archivo_nuevo = st.file_uploader("Captura:", type=["jpg", "png", "jpeg", "webp"])
        
        if st.button("Guardar"):
            if not nombre_manual or not archivo_nuevo:
                st.error("Falta datos.")
            else:
                with st.spinner("Optimizando para lectura OCR..."):
                    png_img = sanear_imagen(archivo_nuevo)
                    if png_img:
                        rid, nfin = subir_archivo_openai(png_img, nombre_manual)
                        if rid:
                            st.success(f"Guardado: {nfin}")
                            time.sleep(1)
                            st.rerun()
    
    st.divider()
    
    st.write("### Imágenes Activas:")
    biblioteca = obtener_biblioteca()
    opciones = [f"{f['name']} ({f['date']})" for f in biblioteca]
    mapa = {f"{f['name']} ({f['date']})": f['id'] for f in biblioteca}
    seleccionados = st.multiselect("Selecciona:", options=opciones)
    ids_activos = [mapa[n] for n in seleccionados]

    if biblioteca:
        with st.expander("🗑️ Papelera"):
            a_borrar = st.selectbox("Eliminar:", options=opciones)
            if st.button("Borrar archivo"):
                if borrar_archivo(mapa[a_borrar]):
                    st.success("Borrado.")
                    time.sleep(0.5)
                    st.rerun()

    if st.button("🔄 Recargar Chat"):
        st.session_state.messages = cargar_historial()
        st.rerun()

# --- CHAT ---
for msg in st.session_state.messages:
    if msg["content"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

prompt = st.chat_input("Escribe aquí...")

if prompt:
    cancelar_runs_activos()
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if ids_activos: st.caption(f"📎 Analizando {len(ids_activos)} imágenes.")

    try:
        tid = st.session_state.current_thread_id
        
        # INYECCIÓN DE PROMPT DE VISIÓN
        # Esto le "grita" al modelo que lea literalmente
        texto_reforzado = f"{prompt}\n\n[INSTRUCCIÓN SISTEMA: Si hay una imagen adjunta, extrae los datos VISUALMENTE dígito por dígito. IGNORA tu conocimiento previo sobre jugadores. Lo que ves en la imagen es la única verdad.]"
        
        content_pkg = [{"type": "text", "text": texto_reforzado}]
        
        for fid in ids_activos:
            content_pkg.append({"type": "image_file", "image_file": {"file_id": fid}})

        client.beta.threads.messages.create(thread_id=tid, role="user", content=content_pkg)

        with st.chat_message("assistant"):
            box = st.empty()
            box.markdown("⏳ *Leyendo imagen pixel por pixel...*")
            
            run = client.beta.threads.runs.create_and_poll(thread_id=tid, assistant_id=assistant_id)
            
            if run.status == 'completed':
                msgs = client.beta.threads.messages.list(thread_id=tid, limit=1)
                txt = msgs.data[0].content[0].text.value
                import re
                clean = re.sub(r'【.*?】', '', txt)
                box.markdown(clean)
                st.session_state.messages.append({"role": "assistant", "content": clean})
            
            elif run.status == 'failed':
                err = run.last_error.message if run.last_error else "Error"
                st.error(f"❌ Error: {err}")
            else:
                box.markdown(f"Estado: {run.status}")

    except Exception as e:
        st.error(f"Error: {e}")
