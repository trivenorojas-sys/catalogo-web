import sqlite3
import streamlit as st

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
  conn = sqlite3.connect("inventario.db")
  return conn


# Inicializar la base de datos web con productos de ejemplo listos para mostrar
def inicializar_db_web():
  conn = conectar_db()
  cur = conn.cursor()
  cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            marca TEXT DEFAULT '',
            categoria TEXT DEFAULT '',
            detalles TEXT DEFAULT '',
            precio REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            imagen BLOB
        )
    """)
  # Ver si está vacía para insertar productos de prueba
  cur.execute("SELECT COUNT(*) FROM productos")
  if cur.fetchone()[0] == 0:
    productos_ejemplo = [
        ("001", "Cuaderno cuadriculado 100 hojas", "Standford", "Cuadernos", "Tapa dura, excelente calidad", 7.50, 1),
        ("002", "Lapicero tinta seca azul", "Faber-Castell", "Escritura", "Punta fina 0.7mm", 1.50, 1),
        ("003", "Juego de Geometría completo", "Lego", "Útiles Escolares", "Regla, escuadras, transportador y compás", 5.00, 1),
        ("004", "Mochila escolar reforzada", "RP", "Mochilas", "Impermeable con varios compartimentos", 65.00, 1),
        ("005", "Plumones de colores x 12", "Crayola", "Dibujo y Pintura", "No tóxicos, colores vivos", 12.00, 1),
    ]
    cur.executemany("""
            INSERT OR IGNORE INTO productos (codigo, nombre, marca, categoria, detalles, precio, activo, imagen)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """, productos_ejemplo)
    conn.commit()
  conn.close()


inicializar_db_web()


@st.cache_data(ttl=5)
def cargar_catalogo(categoria_filtro="Todas", busqueda=""):
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
  columnas = st.columns(3)
  for idx, p in enumerate(productos):
    codigo, nombre, marca, categoria, precio, detalles, imagen_blob = p
    columna_actual = columnas[idx % 3]
    with columna_actual:
      with st.container(border=True):
        st.info("📷 [Catálogo Bazar]")
        st.subheader(nombre)
        st.caption(f"**Marca:** {marca} | **Categoría:** {categoria}")
        if detalles:
          st.text(detalles)
        st.markdown(f"### 💰 S/ {precio:.2f}")
