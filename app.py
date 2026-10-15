import io
import sqlite3
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Catálogo de Productos - Librería y Bazar",
    page_icon="🛍️",
    layout="wide",
)

# Reducir los márgenes superiores de Streamlit para ganar espacio
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

def conectar_db():
    return sqlite3.connect("inventario_web.db")

@st.cache_data(ttl=5)
def cargar_catalogo(categoria_filtro="Todas", busqueda=""):
    try:
        conn = conectar_db()
        cur = conn.cursor()
        query = "SELECT codigo, nombre, marca, categoria, precio, stock, detalles, imagen FROM productos WHERE activo = 1"
        params = []
        
        if categoria_filtro and categoria_filtro != "Todas":
            query += " AND categoria = ?"
            params.append(categoria_filtro)
        if busqueda:
            query += " AND (nombre LIKE ? OR marca LIKE ? OR codigo LIKE ?)"
            like = f"%{busqueda}%"
            params.extend([like, like, like])
            
        query += " ORDER BY categoria, nombre ASC"
        cur.execute(query, params)
        resultados = cur.fetchall()
        conn.close()
        return resultados
    except Exception:
        return []

def obtener_categorias():
    try:
        conn = conectar_db()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT categoria FROM productos WHERE activo=1 AND categoria !='' ORDER BY categoria")
        cats = [r[0] for r in cur.fetchall()]
        conn.close()
        return ["Todas"] + cats
    except Exception:
        return ["Todas"]

st.sidebar.header("🔍 Filtros de Búsqueda")
busqueda_texto = st.sidebar.text_input("Buscar por nombre o marca:")
categorias_disponibles = obtener_categorias()
categoria_seleccionada = st.sidebar.selectbox("Filtrar por Categoría:", categorias_disponibles)

productos = cargar_catalogo(categoria_filtro=categoria_seleccionada, busqueda=busqueda_texto)

# Cabecera compacta con mejor proporción para que el contador de productos respire y no se corte
col_tit, col_cont = st.columns([3, 2])
with col_tit:
    st.markdown("## 🛍️ Catálogo de Productos")
with col_cont:
    st.markdown(f"<div style='text-align: right; padding-top: 15px; color: #555; font-weight: bold;'>📦 {len(productos)} productos</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin: 0px 0px 15px 0px;'>", unsafe_allow_html=True)

if not productos:
    st.warning("No se encontraron productos que coincidan con tu búsqueda.")
else:
    # Mantenemos las 6 columnas por fila
    NUMERO_COLUMNAS = 6
    columnas = st.columns(NUMERO_COLUMNAS)
    
    for idx, p in enumerate(productos):
        codigo, nombre, marca, categoria, precio, stock, detalles, imagen_blob = p
        columna_actual = columnas[idx % NUMERO_COLUMNAS]
        
        with columna_actual:
            with st.container(border=True):
                if imagen_blob:
                    try:
                        img = Image.open(io.BytesIO(imagen_blob))
                        st.image(img, use_container_width=True)
                    except Exception:
                        st.info("📷")
                else:
                    st.info("📷")
                
                nombre_texto = nombre if nombre else "Sin nombre"
                st.markdown(f"<div style='font-size:11px; font-weight:bold; line-height:1.2; height:28px; overflow:hidden;' title='{nombre_texto}'>{nombre_texto}</div>", unsafe_allow_html=True)
                
                marca_texto = marca if marca else 'S/M'
                st.markdown(f"<div style='font-size:10px; color:#555;'>Marca: {marca_texto} | Stk: {stock}</div>", unsafe_allow_html=True)
                
                st.markdown(f"<div style='font-size:12px; font-weight:bold; color:#550055; text-align:right;'>S/ {precio:.2f}</div>", unsafe_allow_html=True)
