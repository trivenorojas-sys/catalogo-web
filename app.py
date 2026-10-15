import io
import sqlite3
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Catálogo de Productos - Librería y Bazar",
    page_icon="🛍️",
    layout="wide",
)

# Estilos CSS para replicar exactamente la vista de tu sistema de escritorio
st.markdown("""
    <style>
    .card-producto {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 8px;
        margin-bottom: 10px;
        font-family: Arial, sans-serif;
        font-size: 11px;
        color: #333;
        height: 210px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .card-nombre {
        font-weight: bold;
        font-size: 11px;
        color: #111;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 2px;
    }
    .card-marca {
        color: #0066cc;
        margin-bottom: 2px;
    }
    .card-stock {
        color: #555;
        margin-bottom: 4px;
    }
    .card-precio {
        font-weight: bold;
        color: #550055;
        font-size: 13px;
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛍️ Catálogo de Productos Disponibles")
st.write("Explora nuestros productos, revisa los precios y utiliza el buscador para encontrar lo que necesitas al instante.")

def conectar_db():
    return sqlite3.connect("inventario_web.db")

@st.cache_data(ttl=5)
def cargar_catalogo(categoria_filtro="Todas", busqueda=""):
    try:
        conn = conectar_db()
        cur = conn.cursor()
        # Añadimos stock a la consulta
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
        conn.close()        return resultados
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

if not productos:
    st.warning("No se encontraron productos que coincidan con tu búsqueda.")
else:
    st.write(f"Mostrando **{len(productos)}** productos disponibles.")
    st.divider()

    # Mantenemos las 8 columnas por fila que pediste
    NUMERO_COLUMNAS = 8
    columnas = st.columns(NUMERO_COLUMNAS)
    
    for idx, p in enumerate(productos):
        codigo, nombre, marca, categoria, precio, stock, detalles, imagen_blob = p
        columna_actual = columnas[idx % NUMERO_COLUMNAS]
        
        with columna_actual:
            with st.container(border=True):
                # Imagen miniatura
                if imagen_blob:
                    try:
                        img = Image.open(io.BytesIO(imagen_blob))
                        st.image(img, use_container_width=True)
                    except Exception:
                        st.info("📷")
                else:
                    st.info("📷")
                
                # Datos idénticos a tu software de escritorio
                st.markdown(f"<div class='card-nombre' title='{nombre}'>{nombre}</div>", unsafe_allow_html=True)
                
                marca_texto = marca if marca else 'S/M'
                st.markdown(f"<div class='card-marca'>Marca: {marca_texto}</div>", unsafe_allow_html=True)
                
                st.markdown(f"<div class='card-stock'>Stock: {stock} unids.</div>", unsafe_allow_html=True)
                
                st.markdown(f"<div class='card-precio'>S/ {precio:.2f}</div>", unsafe_allow_html=True)
