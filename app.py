import base64
import sqlite3
import streamlit as st

st.set_page_config(
    page_title="Catálogo de Productos - Librería y Bazar",
    page_icon="🛍️",
    layout="wide",
)

# Estilos CSS con cuadrícula adaptable automática para PC y Celulares
st.markdown(
    """
    <style>
    .grid-catalogo {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
        gap: 10px;
        margin-bottom: 20px;
    }
    .card-producto {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        text-align: left;
    }
    .card-img-container {
        width: 100%;
        height: 110px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f9f9f9;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 6px;
    }
    .card-img-container img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
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
        font-size: 10px;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .card-stock {
        color: #555;
        font-size: 10px;
        margin-bottom: 4px;
    }
    .card-precio {
        font-weight: bold;
        color: #550055;
        font-size: 12px;
        text-align: right;
    }
    </style>
""",
    unsafe_allow_html=True,
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

  # Generamos la cuadrícula adaptativa para PC y celulares
  html_code = "<div class='grid-catalogo'>"

  for p in productos:
    codigo, nombre, marca, categoria, precio, stock, detalles, imagen_blob = p

    img_tag = "<div style='color: #888; font-size: 20px;'>📷</div>"
    if imagen_blob:
      try:
        encoded = base64.b64encode(imagen_blob).decode("utf-8")
        img_tag = f"<img src='data:image/jpeg;base64,{encoded}' alt='producto'>"
      except Exception:
        pass

    marca_texto = marca if marca else "S/M"
    nombre_escaped = (
        nombre.replace('"', "&quot;") if nombre else "Sin nombre"
    )

    html_code += f"""
        <div class='card-producto'>
            <div class='card-img-container'>
                {img_tag}
            </div>
            <div>
                <div class='card-nombre' title='{nombre_escaped}'>{nombre_escaped}</div>
                <div class='card-marca'>Marca: {marca_texto}</div>
                <div class='card-stock'>Stock: {stock} unids.</div>
            </div>
            <div class='card-precio'>S/ {precio:.2f}</div>
        </div>
        """

  html_code += "</div>"
  st.markdown(html_code, unsafe_allow_html=True)
