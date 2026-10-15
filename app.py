import io
import sqlite3
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Catálogo de Productos - Librería y Bazar",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Catálogo de Productos Disponibles")
st.write(
    "Explora nuestros productos, revisa los precios y utiliza el buscador"
    " para encontrar lo que necesitas al instante."
)


def conectar_db():
  return sqlite3.connect("inventario_web.db")


@st.cache_data(ttl=5)
def cargar_catalogo(categoria_filtro="Todas", busqueda=""):
  try:
    conn = conectar_db()
    cur = conn.cursor()
    query = "SELECT codigo, nombre, marca, categoria, precio, detalles, imagen FROM productos WHERE activo = 1"
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
    cur.execute(
        "SELECT DISTINCT categoria FROM productos WHERE activo=1 AND categoria"
        " !='' ORDER BY categoria"
    )
    cats = [r[0] for r in cur.fetchall()]
    conn.close()
    return ["Todas"] + cats
  except Exception:
    return ["Todas"]


st.sidebar.header("🔍 Filtros de Búsqueda")
busqueda_texto = st.sidebar.text_input("Buscar por nombre o marca:")
categorias_disponibles = obtener_categorias()
categoria_seleccionada = st.sidebar.selectbox(
    "Filtrar por Categoría:", categorias_disponibles
)

productos = cargar_catalogo(
    categoria_filtro=categoria_seleccionada, busqueda=busqueda_texto
)

if not productos:
  st.warning("No se encontraron productos que coincidan con tu búsqueda.")
else:
  st.write(f"Mostrando **{len(productos)}** productos disponibles.")
  st.divider()

  # Configuramos exactamente 8 productos por fila
  NUMERO_COLUMNAS = 8
  columnas = st.columns(NUMERO_COLUMNAS)

  for idx, p in enumerate(productos):
    codigo, nombre, marca, categoria, precio, detalles, imagen_blob = p
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

        # Letras y textos más compactos para que encajen bien en 8 columnas
        st.markdown(f"**{nombre}**")
        st.caption(
            f"Marca: {marca if marca else 'S/M'}\nCat: {categoria if categoria else 'Gral'}"
        )
        if detalles:
          st.text(detalles)
        st.markdown(f"#### 💰 S/ {precio:.2f}")
