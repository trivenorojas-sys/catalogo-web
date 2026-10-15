#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Control de Inventario POS con Vista Galería Adaptativa, POS Visual,
Soporte para MÚLTIPLES IMÁGENES por Producto, Marcas, Código en Detalle,
Módulo de Deudas (Fiados), Exportación a Catálogo PDF, Reporte de Diezmo,
Control de Pagos de Diezmo, Eliminación/Reversión de Movimientos, Gestión de Mermas y
Análisis de Rendimiento del Negocio (Ventas por Día de Semana y Hora).
===========================================================================
Requisitos: Python 3.8+ (Tkinter, Pillow, ReportLab)
Instalación: pip install Pillow reportlab
"""

import sqlite3
import os
import io
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from PIL import Image, ImageTk

# Librerías para exportar el catálogo en PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventario.db")


# ---------------------------------------------------------------------------
# CAPA DE DATOS
# ---------------------------------------------------------------------------
class Database:
    def __init__(self, db_path=DB_NAME):
        self.db_path = db_path
        self._crear_tablas()

    def _conectar(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _crear_tablas(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE NOT NULL,
                    nombre TEXT NOT NULL,
                    marca TEXT DEFAULT '',
                    categoria TEXT DEFAULT '',
                    ubicacion TEXT DEFAULT '',
                    detalles TEXT DEFAULT '',
                    unidad TEXT DEFAULT 'unidad',
                    costo REAL DEFAULT 0,
                    precio REAL DEFAULT 0,
                    stock INTEGER DEFAULT 0,
                    stock_minimo INTEGER DEFAULT 0,
                    activo INTEGER DEFAULT 1,
                    fecha_creacion TEXT,
                    imagen BLOB
                )
            """)
            
            # Tabla para soporte de múltiples imágenes por producto
            cur.execute("""
                CREATE TABLE IF NOT EXISTS producto_imagenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto_id INTEGER NOT NULL,
                    imagen BLOB NOT NULL,
                    orden INTEGER DEFAULT 0,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
                )
            """)

            cur.execute("PRAGMA table_info(productos)")
            columnas = [col[1] for col in cur.fetchall()]
            if "imagen" not in columnas:
                cur.execute("ALTER TABLE productos ADD COLUMN imagen BLOB")
            if "marca" not in columnas:
                cur.execute("ALTER TABLE productos ADD COLUMN marca TEXT DEFAULT ''")
            if "ubicacion" not in columnas:
                cur.execute("ALTER TABLE productos ADD COLUMN ubicacion TEXT DEFAULT ''")
            if "detalles" not in columnas:
                cur.execute("ALTER TABLE productos ADD COLUMN detalles TEXT DEFAULT ''")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS movimientos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    costo_unitario REAL DEFAULT 0,
                    precio_unitario REAL DEFAULT 0,
                    motivo TEXT DEFAULT '',
                    fecha TEXT,
                    FOREIGN KEY (producto_id) REFERENCES productos(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS deudas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente TEXT NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio_unitario REAL NOT NULL,
                    total REAL NOT NULL,
                    fecha TEXT NOT NULL,
                    fecha_pago TEXT DEFAULT '',
                    estado TEXT DEFAULT 'PENDIENTE',
                    FOREIGN KEY (producto_id) REFERENCES productos(id)
                )
            """)

            # Tabla para control de pagos de diezmo realizados
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pagos_diezmo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monto REAL NOT NULL,
                    fecha_pago TEXT NOT NULL,
                    observacion TEXT DEFAULT ''
                )
            """)

            cur.execute("PRAGMA table_info(deudas)")
            col_deudas = [col[1] for col in cur.fetchall()]
            if "fecha_pago" not in col_deudas:
                cur.execute("ALTER TABLE deudas ADD COLUMN fecha_pago TEXT DEFAULT ''")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_prod_codigo ON productos(codigo)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_prod_nombre ON productos(nombre)")

    def guardar_imagenes_producto(self, producto_id, lista_blobs_imagenes):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM producto_imagenes WHERE producto_id=?", (producto_id,))
            for idx, img_blob in enumerate(lista_blobs_imagenes):
                cur.execute("""
                    INSERT INTO producto_imagenes (producto_id, imagen, orden)
                    VALUES (?, ?, ?)
                """, (producto_id, img_blob, idx))
            
            primera_img = lista_blobs_imagenes[0] if lista_blobs_imagenes else None
            cur.execute("UPDATE productos SET imagen=? WHERE id=?", (primera_img, producto_id))

    def obtener_imagenes_producto(self, producto_id):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT imagen FROM producto_imagenes WHERE producto_id=? ORDER BY orden ASC, id ASC", (producto_id,))
            filas = cur.fetchall()
            if filas:
                return [f[0] for f in filas]
            
            cur.execute("SELECT imagen FROM productos WHERE id=?", (producto_id,))
            row = cur.fetchone()
            return [row[0]] if row and row[0] else []

    def agregar_producto(self, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_minimo, lista_imagenes=None):
        lista_imagenes = lista_imagenes or []
        primera_img = lista_imagenes[0] if lista_imagenes else None
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO productos (codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_minimo, fecha_creacion, imagen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_minimo,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"), primera_img))
            prod_id = cur.lastrowid
            
        if lista_imagenes:
            self.guardar_imagenes_producto(prod_id, lista_imagenes)
        return prod_id

    def actualizar_producto(self, id_, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock_minimo, lista_imagenes=None):
        with self._conectar() as conn:
            cur = conn.cursor()
            primera_img = lista_imagenes[0] if lista_imagenes else None
            cur.execute("""
                UPDATE productos
                SET codigo=?, nombre=?, marca=?, categoria=?, ubicacion=?, detalles=?, unidad=?, costo=?, precio=?, stock_minimo=?, imagen=?
                WHERE id=?
            """, (codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock_minimo, primera_img, id_))
        
        if lista_imagenes is not None:
            self.guardar_imagenes_producto(id_, lista_imagenes)

    def eliminar_producto(self, id_):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE productos SET activo=0, codigo=codigo || '_DEL_' || ? WHERE id=?", (id_, id_))

    def obtener_productos(self, filtro="", categoria=None, solo_bajo_stock=False):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = "SELECT id, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_minimo, imagen FROM productos WHERE activo=1"
            params = []
            if filtro:
                query += " AND (codigo LIKE ? OR nombre LIKE ? OR marca LIKE ? OR ubicacion LIKE ? OR detalles LIKE ?)"
                like = f"%{filtro}%"
                params.extend([like, like, like, like, like])
            if categoria and categoria != "Todas":
                query += " AND categoria = ?"
                params.append(categoria)
            if solo_bajo_stock:
                query += " AND stock <= stock_minimo"
            query += " ORDER BY nombre ASC"
            cur.execute(query, params)
            return cur.fetchall()

    def obtener_productos_para_catalogo(self, categoria=None):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT codigo, nombre, marca, categoria, precio, detalles, imagen 
                FROM productos 
                WHERE activo = 1 
            """
            params = []
            if categoria and categoria not in ("Todas", "Todos los productos"):
                query += " AND categoria = ?"
                params.append(categoria)
            query += " ORDER BY categoria, nombre ASC"
            cur.execute(query, params)
            return cur.fetchall()

    def obtener_producto_por_id(self, id_):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_minimo, imagen FROM productos WHERE id=?", (id_,))
            return cur.fetchone()

    def obtener_producto_por_codigo(self, codigo):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, codigo, nombre, precio, stock FROM productos WHERE codigo=? AND activo=1", (codigo,))
            return cur.fetchone()

    def obtener_categorias(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT categoria FROM productos WHERE activo=1 AND categoria != '' ORDER BY categoria")
            return [r[0] for r in cur.fetchall()]

    def existe_codigo(self, codigo, excluir_id=None):
        with self._conectar() as conn:
            cur = conn.cursor()
            if excluir_id:
                cur.execute("SELECT id FROM productos WHERE codigo=? AND activo=1 AND id!=?", (codigo, excluir_id))
            else:
                cur.execute("SELECT id FROM productos WHERE codigo=? AND activo=1", (codigo,))
            return cur.fetchone() is not None

    def registrar_movimiento(self, producto_id, tipo, cantidad, motivo):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT stock, costo, precio FROM productos WHERE id=?", (producto_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Producto no encontrado")
            
            stock_actual, costo, precio = row[0], float(row[1]), float(row[2])
            cantidad = int(cantidad)

            if tipo in ("salida", "merma") and cantidad > stock_actual:
                raise ValueError(f"Stock insuficiente. Disponible: {stock_actual}")

            if tipo == "entrada":
                nuevo_stock = stock_actual + cantidad
                precio_reg = precio
            elif tipo == "salida":
                nuevo_stock = stock_actual - cantidad
                precio_reg = precio
            elif tipo == "merma":
                nuevo_stock = stock_actual - cantidad
                precio_reg = 0.0
                if not motivo:
                    motivo = "Producto malogrado / dañado"

            cur.execute("UPDATE productos SET stock=? WHERE id=?", (nuevo_stock, producto_id))
            cur.execute("""
                INSERT INTO movimientos (producto_id, tipo, cantidad, costo_unitario, precio_unitario, motivo, fecha)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (producto_id, tipo, cantidad, costo, precio_reg, motivo, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return nuevo_stock

    def eliminar_movimiento(self, movimiento_id):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT producto_id, tipo, cantidad FROM movimientos WHERE id=?", (movimiento_id,))
            mov = cur.fetchone()
            if not mov:
                raise ValueError("El movimiento no existe o ya fue eliminado.")

            prod_id, tipo, cantidad = mov[0], mov[1], mov[2]

            cur.execute("SELECT stock FROM productos WHERE id=?", (prod_id,))
            prod = cur.fetchone()
            if not prod:
                raise ValueError("El producto asociado al movimiento ya no existe.")

            stock_actual = prod[0]

            if tipo == "entrada":
                if stock_actual < cantidad:
                    raise ValueError(f"No se puede revertir la entrada. El stock actual ({stock_actual}) es menor a la cantidad a deshacer ({cantidad}).")
                nuevo_stock = stock_actual - cantidad
            else:
                nuevo_stock = stock_actual + cantidad

            cur.execute("UPDATE productos SET stock=? WHERE id=?", (nuevo_stock, prod_id))
            cur.execute("DELETE FROM movimientos WHERE id=?", (movimiento_id,))
            conn.commit()

    def procesar_venta_carrito(self, items_carrito, es_deuda=False, cliente=""):
        conn = self._conectar()
        cur = conn.cursor()
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            for item in items_carrito:
                prod_id = item['id']
                cant_venta = item['cantidad']

                cur.execute("SELECT stock, costo, precio FROM productos WHERE id=? AND activo=1", (prod_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"El producto ID {prod_id} ya no existe.")

                stock_actual, costo, precio = row[0], float(row[1]), float(row[2])

                if cant_venta > stock_actual:
                    raise ValueError(f"Stock insuficiente para '{item['nombre']}'. Disponible: {stock_actual}")

                nuevo_stock = stock_actual - cant_venta
                cur.execute("UPDATE productos SET stock=? WHERE id=?", (nuevo_stock, prod_id))

                motivo_venta = f"Deuda / Fiado: {cliente}" if es_deuda else "Venta de Carrito"
                cur.execute("""
                    INSERT INTO movimientos (producto_id, tipo, cantidad, costo_unitario, precio_unitario, motivo, fecha)
                    VALUES (?, 'salida', ?, ?, ?, ?, ?)
                """, (prod_id, cant_venta, costo, precio, motivo_venta, fecha_actual))

                if es_deuda:
                    total_item = cant_venta * precio
                    cur.execute("""
                        INSERT INTO deudas (cliente, producto_id, cantidad, precio_unitario, total, fecha, estado)
                        VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE')
                    """, (cliente, prod_id, cant_venta, precio, total_item, fecha_actual))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def obtener_deudas_agrupadas(self, filtro_cliente=""):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT cliente, SUM(total) as deuda_total, COUNT(id) as cantidad_items
                FROM deudas
                WHERE estado = 'PENDIENTE'
            """
            params = []
            if filtro_cliente:
                query += " AND cliente LIKE ?"
                params.append(f"%{filtro_cliente}%")
            query += " GROUP BY cliente ORDER BY cliente ASC"
            cur.execute(query, params)
            return cur.fetchall()

    def obtener_detalle_deuda_cliente(self, cliente):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT d.id, p.codigo, p.nombre, d.cantidad, d.precio_unitario, d.total, d.fecha
                FROM deudas d
                JOIN productos p ON p.id = d.producto_id
                WHERE d.cliente = ? AND d.estado = 'PENDIENTE'
                ORDER BY d.fecha DESC
            """
            cur.execute(query, (cliente,))
            return cur.fetchall()

    def pagar_deuda_cliente(self, cliente):
        with self._conectar() as conn:
            cur = conn.cursor()
            fecha_pago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE deudas SET estado = 'PAGADO', fecha_pago = ? WHERE cliente = ? AND estado = 'PENDIENTE'", (fecha_pago, cliente))

    # Métodos para la gestión de pagos de diezmo
    def registrar_pago_diezmo(self, monto, fecha_pago, observacion):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO pagos_diezmo (monto, fecha_pago, observacion)
                VALUES (?, ?, ?)
            """, (monto, fecha_pago, observacion))

    def obtener_pagos_diezmo(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, monto, fecha_pago, observacion FROM pagos_diezmo ORDER BY fecha_pago DESC, id DESC")
            return cur.fetchall()

    def eliminar_pago_diezmo(self, pago_id):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM pagos_diezmo WHERE id=?", (pago_id,))

    def obtener_movimientos(self, producto_id=None, limite=500):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT m.id, p.codigo, p.nombre, m.tipo, m.cantidad, m.precio_unitario, m.costo_unitario,
                       (m.cantidad * m.precio_unitario) as total_venta,
                       (m.precio_unitario - m.costo_unitario) as ganancia_unit,
                       (m.cantidad * (m.precio_unitario - m.costo_unitario)) as ganancia_total,
                       m.motivo, m.fecha
                FROM movimientos m
                JOIN productos p ON p.id = m.producto_id
            """
            params = []
            if producto_id:
                query += " WHERE m.producto_id = ?"
                params.append(producto_id)
            query += " ORDER BY m.fecha DESC, m.id DESC LIMIT ?"
            params.append(limite)
            cur.execute(query, params)
            return cur.fetchall()

    def reporte_ganancias_diarias(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT 
                    DATE(fecha) as dia,
                    SUM(cantidad) as unidades_vendidas,
                    SUM(cantidad * precio_unitario) as total_ventas,
                    SUM(cantidad * costo_unitario) as total_costo,
                    SUM(cantidad * (precio_unitario - costo_unitario)) as ganancia_neta
                FROM movimientos
                WHERE tipo = 'salida'
                GROUP BY DATE(fecha)
                ORDER BY DATE(fecha) ASC
            """
            cur.execute(query)
            return cur.fetchall()

    def reporte_diezmo_efectivo_diario(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT 
                    dia,
                    SUM(venta) as total_ventas_efectivo,
                    SUM(ganancia) as ganancia_neta_efectivo,
                    SUM(ganancia) * 0.10 as diezmo_10
                FROM (
                    SELECT 
                        DATE(m.fecha) as dia,
                        (m.cantidad * m.precio_unitario) as venta,
                        (m.cantidad * (m.precio_unitario - m.costo_unitario)) as ganancia
                    FROM movimientos m
                    WHERE m.tipo = 'salida' AND m.motivo NOT LIKE 'Deuda / Fiado%'

                    UNION ALL

                    SELECT 
                        DATE(d.fecha_pago) as dia,
                        d.total as venta,
                        (d.cantidad * (d.precio_unitario - p.costo)) as ganancia
                    FROM deudas d
                    JOIN productos p ON p.id = d.producto_id
                    WHERE d.estado = 'PAGADO' AND d.fecha_pago IS NOT NULL AND d.fecha_pago != ''
                )
                GROUP BY dia
                ORDER BY dia DESC
            """
            cur.execute(query)
            return cur.fetchall()

    def obtener_ventas_por_dia_y_hora(self, dias_atras=None):
        """Retorna las ventas agrupadas por Día de la Semana y Hora del día."""
        with self._conectar() as conn:
            cur = conn.cursor()
            query = """
                SELECT 
                    strftime('%w', fecha) as num_dia,
                    strftime('%H', fecha) as hora,
                    SUM(cantidad) as unidades,
                    SUM(cantidad * precio_unitario) as total_ventas
                FROM movimientos
                WHERE tipo = 'salida'
            """
            params = []
            if dias_atras:
                fecha_limite = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d 00:00:00")
                query += " AND fecha >= ?"
                params.append(fecha_limite)

            query += " GROUP BY num_dia, hora ORDER BY total_ventas DESC"
            cur.execute(query, params)
            return cur.fetchall()

    def estadisticas(self):
        with self._conectar() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), COALESCE(SUM(stock),0), COALESCE(SUM(stock*costo),0), COALESCE(SUM(stock*(precio-costo)),0) FROM productos WHERE activo=1")
            total_prod, total_unidades, valor_inventario, ganancia_proyectada = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND stock <= stock_minimo")
            bajo_stock = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(total), 0) FROM deudas WHERE estado = 'PENDIENTE'")
            total_deudas = cur.fetchone()[0]
            return {
                "total_productos": total_prod,
                "total_unidades": total_unidades,
                "valor_inventario": valor_inventario,
                "ganancia_proyectada": ganancia_proyectada,
                "bajo_stock": bajo_stock,
                "total_deudas": total_deudas
            }


# ---------------------------------------------------------------------------
# GENERADOR DE PDF (REPORTLAB)
# ---------------------------------------------------------------------------
def generar_pdf_catalogo(db, ruta_pdf, categoria=None):
    productos = db.obtener_productos_para_catalogo(categoria)
    if not productos:
        raise ValueError("No hay productos activos para exportar en la categoría seleccionada.")

    doc = SimpleDocTemplate(ruta_pdf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor("#0078d4"), alignment=1)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Normal'], fontSize=10, textColor=colors.gray, alignment=1)
    
    nombre_style = ParagraphStyle('Nom', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor("#333333"))
    marca_style = ParagraphStyle('Marc', fontName='Helvetica-Oblique', fontSize=8, leading=10, textColor=colors.HexColor("#0078d4"))
    precio_style = ParagraphStyle('Prec', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.HexColor("#107c41"))
    detalles_style = ParagraphStyle('Det', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor("#555555"))

    categoria_txt = f" - {categoria}" if categoria and categoria not in ("Todas", "Todos los productos") else ""
    story.append(Paragraph(f"CATÁLOGO DE PRODUCTOS{categoria_txt}", titulo_style))
    story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitulo_style))
    story.append(Spacer(1, 15))

    tarjetas = []
    for p in productos:
        codigo, nombre, marca, cat, precio, detalles, imagen_blob = p
        
        if imagen_blob:
            try:
                img_io = io.BytesIO(imagen_blob)
                img_obj = RLImage(img_io, width=70, height=70)
            except Exception:
                img_obj = Paragraph("<b>[Sin Foto]</b>", detalles_style)
        else:
            img_obj = Paragraph("<b>[Sin Foto]</b>", detalles_style)

        txt_contenido = [
            Paragraph(f"<b>{nombre}</b>", nombre_style),
            Paragraph(f"Marca: {marca if marca else 'S/M'}", marca_style),
            Paragraph(f"Cód: {codigo}", detalles_style),
            Paragraph(f"S/ {precio:.2f}", precio_style),
        ]
        if detalles:
            txt_contenido.append(Paragraph(detalles[:50] + "..." if len(detalles) > 50 else detalles, detalles_style))

        celda_tabla = Table([[img_obj, txt_contenido]], colWidths=[75, 115])
        celda_tabla.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        tarjetas.append(celda_tabla)

    filas_grid = []
    columnas = 3
    for i in range(0, len(tarjetas), columnas):
        bloque = tarjetas[i:i+columnas]
        while len(bloque) < columnas:
            bloque.append("")
        filas_grid.append(bloque)

    grid_tabla = Table(filas_grid, colWidths=[190, 190, 190])
    grid_tabla.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e1e1e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e1e1e1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))

    story.append(grid_tabla)
    doc.build(story)


# ---------------------------------------------------------------------------
# INTERFAZ GRÁFICA PRINCIPAL
# ---------------------------------------------------------------------------
class InventarioApp:
    def __init__(self, root):
        self.root = root
        self.db = Database()
        self.imagenes_actuales_raw = []
        self.idx_imagen_actual = 0
        self._resize_job = None
        self._relayout_job = None
        self._relayout_pos_job = None
        self.carrito = []
        self.id_seleccionado = None
        self.cache_imagenes = {}
        self.referencias_fotos = []
        self.referencias_fotos_pos = []
        self.productos_actuales = []

        root.title("Sistema POS & Control de Inventario (Soporte Multi-Imagen)")
        root.geometry("1400x800")
        root.minsize(1100, 650)

        self._configurar_estilos()
        self._construir_layout()
        self._refrescar_todo()

    def _configurar_estilos(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), relief="flat")
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), background="#107c41", foreground="white")
        style.configure("Warning.TButton", font=("Segoe UI", 10, "bold"), background="#d13438", foreground="white")

    def _construir_layout(self):
        self.frame_stats = ttk.Frame(self.root, padding=10)
        self.frame_stats.pack(fill="x")
        self._construir_barra_stats()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_carrito = ttk.Frame(self.notebook)
        self.tab_deudas = ttk.Frame(self.notebook)
        self.tab_productos = ttk.Frame(self.notebook)
        self.tab_reporte_ganancias = ttk.Frame(self.notebook)
        self.tab_rendimiento = ttk.Frame(self.notebook)
        self.tab_diezmo = ttk.Frame(self.notebook)
        self.tab_pagos_diezmo = ttk.Frame(self.notebook)
        self.tab_movimientos = ttk.Frame(self.notebook)
        self.tab_alertas = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_carrito, text=" 🛒 Carrito / POS ")
        self.notebook.add(self.tab_deudas, text=" 📋 Deudas / Fiados ")
        self.notebook.add(self.tab_productos, text=" 📦 Catálogo de Productos ")
        self.notebook.add(self.tab_reporte_ganancias, text=" 📈 Ganancias ")
        self.notebook.add(self.tab_rendimiento, text=" 📊 Rendimiento ")
        self.notebook.add(self.tab_diezmo, text=" ⛪ Diezmo (10%) ")
        self.notebook.add(self.tab_pagos_diezmo, text=" 💰 Control Pagos Diezmo ")
        self.notebook.add(self.tab_movimientos, text=" 🔄 Movimientos ")
        self.notebook.add(self.tab_alertas, text=" ⚠️ Alertas ")

        # Construir interfaces de pestañas antes de invocar refrescos masivos
        self._construir_tab_carrito()
        self._construir_tab_deudas()
        self._construir_tab_productos()
        self._construir_tab_ganancias()
        self._construir_tab_rendimiento()
        self._construir_tab_diezmo()
        self._construir_tab_pagos_diezmo()
        self._construir_tab_movimientos()
        self._construir_tab_alertas()

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._refrescar_todo())

    def _construir_barra_stats(self):
        self.lbl_total_prod = self._stat_card(self.frame_stats, "Productos activos", "0", "#0078d4")
        self.lbl_total_unid = self._stat_card(self.frame_stats, "Unidades en stock", "0", "#2b5c8f")
        self.lbl_valor_inv = self._stat_card(self.frame_stats, "Valor inventario", "S/ 0.00", "#107c41")
        self.lbl_total_deudas = self._stat_card(self.frame_stats, "Total por Cobrar (Fiado)", "S/ 0.00", "#d13438")
        self.lbl_bajo_stock = self._stat_card(self.frame_stats, "Stock bajo", "0", "#ff8c00")

    def _stat_card(self, parent, titulo, valor_inicial, color_borde):
        frame = tk.Frame(parent, bg="#ffffff", relief="solid", bd=1)
        frame.pack(side="left", expand=True, fill="x", padx=4)
        
        bar = tk.Frame(frame, bg=color_borde, height=4)
        bar.pack(fill="x", side="top")

        content = ttk.Frame(frame, padding=8)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text=titulo, font=("Segoe UI", 8, "bold"), foreground="#555555").pack(anchor="w")
        lbl_valor = ttk.Label(content, text=valor_inicial, font=("Segoe UI", 13, "bold"), foreground=color_borde)
        lbl_valor.pack(anchor="w")
        return lbl_valor

    # ---------------- TAB CARRITO / POS ----------------
    def _construir_tab_carrito(self):
        paned = ttk.PanedWindow(self.tab_carrito, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        top_barcode = ttk.LabelFrame(left_frame, text=" 🔍 Entrada por Código de Barras / Nombre ", padding=8)
        top_barcode.pack(fill="x", pady=(0, 5))

        ttk.Label(top_barcode, text="Código/Búsqueda:").pack(side="left", padx=(0, 5))
        self.entry_codigo_carrito = ttk.Entry(top_barcode, font=("Segoe UI", 10), width=22)
        self.entry_codigo_carrito.pack(side="left", padx=5)
        self.entry_codigo_carrito.bind("<Return>", self._agregar_al_carrito_por_codigo)

        ttk.Button(top_barcode, text="➕ Agregar", command=self._agregar_al_carrito_por_codigo).pack(side="left", padx=5)

        top_search = ttk.LabelFrame(left_frame, text=" 🖼️ Catálogo Visual / Filtro Rápido ", padding=8)
        top_search.pack(fill="x", pady=(0, 5))

        ttk.Label(top_search, text="Buscar:").pack(side="left", padx=(0, 5))
        self.var_pos_filtro = tk.StringVar()
        entry_pos_filtro = ttk.Entry(top_search, textvariable=self.var_pos_filtro, font=("Segoe UI", 10), width=18)
        entry_pos_filtro.pack(side="left", padx=5)
        entry_pos_filtro.bind("<KeyRelease>", lambda e: self._cargar_tarjetas_pos())

        ttk.Label(top_search, text="Categoría:").pack(side="left", padx=(10, 5))
        self.var_pos_cat = tk.StringVar(value="Todas")
        self.combo_pos_cat = ttk.Combobox(top_search, textvariable=self.var_pos_cat, state="readonly", width=22)
        self.combo_pos_cat["values"] = ["Todas"]
        self.combo_pos_cat.pack(side="left", padx=5)
        self.combo_pos_cat.bind("<<ComboboxSelected>>", lambda e: self._cargar_tarjetas_pos())

        self.canvas_pos_grid = tk.Canvas(left_frame, bg="#f5f5f7", highlightthickness=0)
        self.scrollbar_pos_grid = ttk.Scrollbar(left_frame, orient="vertical", command=self.canvas_pos_grid.yview)
        self.scrollable_pos_frame = tk.Frame(self.canvas_pos_grid, bg="#f5f5f7")

        self.scrollable_pos_frame.bind("<Configure>", lambda e: self.canvas_pos_grid.configure(scrollregion=self.canvas_pos_grid.bbox("all")))
        self.canvas_pos_window_id = self.canvas_pos_grid.create_window((0, 0), window=self.scrollable_pos_frame, anchor="nw")
        self.canvas_pos_grid.configure(yscrollcommand=self.scrollbar_pos_grid.set)

        self.canvas_pos_grid.pack(side="left", fill="both", expand=True)
        self.scrollbar_pos_grid.pack(side="right", fill="y")
        
        self.canvas_pos_grid.bind('<Configure>', self._on_canvas_pos_configure)

        right_frame = tk.Frame(paned, bg="#ffffff", relief="solid", bd=1)
        paned.add(right_frame, weight=2)

        inner_right = ttk.Frame(right_frame, padding=10)
        inner_right.pack(fill="both", expand=True)

        ttk.Label(inner_right, text="📋 Ticket de Venta Actual", font=("Segoe UI", 11, "bold"), foreground="#0078d4").pack(anchor="w", pady=(0, 5))

        cols = ("codigo", "nombre", "precio", "cantidad", "subtotal")
        self.tree_carrito = ttk.Treeview(inner_right, columns=cols, show="headings", selectmode="browse", height=8)
        encabezados = {"codigo": "Código", "nombre": "Producto", "precio": "P. Unitario", "cantidad": "Cant.", "subtotal": "Subtotal"}
        anchos = {"codigo": 80, "nombre": 160, "precio": 75, "cantidad": 50, "subtotal": 80}
        for c in cols:
            self.tree_carrito.heading(c, text=encabezados[c])
            self.tree_carrito.column(c, width=anchos[c], anchor="center" if c != "nombre" else "w")

        self.tree_carrito.pack(fill="both", expand=True)

        btn_row = ttk.Frame(inner_right)
        btn_row.pack(fill="x", pady=5)
        ttk.Button(btn_row, text="✏️ Cantidad", command=self._modificar_cantidad_carrito).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_row, text="❌ Quitar", command=self._quitar_item_carrito).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_row, text="🧹 Vaciar", command=self._vaciar_carrito).pack(side="left", expand=True, fill="x", padx=2)

        ttk.Separator(inner_right, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(inner_right, text="TOTAL A PAGAR:", font=("Segoe UI", 9, "bold"), foreground="#0078d4").pack(anchor="w")
        self.lbl_total_carrito = ttk.Label(inner_right, text="S/ 0.00", font=("Segoe UI", 20, "bold"), foreground="#107c41")
        self.lbl_total_carrito.pack(anchor="w", pady=2)

        ttk.Label(inner_right, text="Monto Recibido:", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(5, 2))
        self.var_pago = tk.StringVar(value="0.00")
        entry_pago = ttk.Entry(inner_right, textvariable=self.var_pago, font=("Segoe UI", 11))
        entry_pago.pack(fill="x", pady=2)
        entry_pago.bind("<KeyRelease>", self._calcular_vuelto)

        ttk.Label(inner_right, text="VUELTO / CAMBIO:", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(5, 2))
        self.lbl_vuelto = ttk.Label(inner_right, text="S/ 0.00", font=("Segoe UI", 14, "bold"), foreground="#0078d4")
        self.lbl_vuelto.pack(anchor="w")

        ttk.Button(inner_right, text="💳 PROCESAR VENTA (CONTADO)", style="Accent.TButton", command=self._procesar_venta).pack(fill="x", pady=(10, 4), ipady=4)
        ttk.Button(inner_right, text="📝 REGISTRAR COMO DEUDA (FIADO)", style="Warning.TButton", command=self._procesar_deuda).pack(fill="x", pady=(0, 0), ipady=4)

    def _on_canvas_pos_configure(self, event):
        self.canvas_pos_grid.itemconfig(self.canvas_pos_window_id, width=event.width)
        if self._relayout_pos_job:
            self.root.after_cancel(self._relayout_pos_job)
        self._relayout_pos_job = self.root.after(100, self._cargar_tarjetas_pos)

    def _cargar_tarjetas_pos(self):
        for child in self.scrollable_pos_frame.winfo_children():
            child.destroy()

        self.referencias_fotos_pos.clear()

        filtro = self.var_pos_filtro.get().strip()
        categoria = self.var_pos_cat.get()
        productos = self.db.obtener_productos(filtro=filtro, categoria=categoria)

        cats = ["Todas"] + self.db.obtener_categorias()
        self.combo_pos_cat["values"] = cats

        if not productos:
            ttk.Label(self.scrollable_pos_frame, text="No se encontraron productos.", font=("Segoe UI", 10, "italic")).pack(pady=20)
            return

        ancho_canvas = self.canvas_pos_grid.winfo_width()
        if ancho_canvas <= 1:
            ancho_canvas = 600

        ancho_tarjeta = 150
        cols_max = max(1, ancho_canvas // ancho_tarjeta)

        for i in range(20):
            self.scrollable_pos_frame.grid_columnconfigure(i, weight=0)

        for idx, p in enumerate(productos):
            r, c = idx // cols_max, idx % cols_max
            prod_id, codigo, nombre, marca, _, _, _, _, _, precio, stock, stock_min, imagen_blob = p
            precio = float(precio)
            stock = int(stock)

            card = tk.Frame(self.scrollable_pos_frame, bg="#ffffff", highlightbackground="#d1d1d1", highlightthickness=1)
            card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

            img_container = tk.Frame(card, bg="#f8f8f8", height=90)
            img_container.pack(fill="x", side="top")
            img_container.pack_propagate(False)

            lbl_foto = tk.Label(img_container, bg="#f8f8f8")
            lbl_foto.pack(fill="both", expand=True)

            photo = self._procesar_imagen_bytes(imagen_blob, (120, 85))
            if photo:
                lbl_foto.config(image=photo)
                lbl_foto.image = photo
                self.referencias_fotos_pos.append(photo)
            else:
                lbl_foto.config(text="📷 Sin Imagen", font=("Segoe UI", 8), fg="#888888")

            content = tk.Frame(card, bg="#ffffff", padx=6, pady=4)
            content.pack(fill="both", expand=True)

            tk.Label(content, text=nombre, font=("Segoe UI", 9, "bold"), fg="#333333", bg="#ffffff", wraplength=130, justify="left").pack(anchor="w")
            
            texto_marca = marca if marca else "Sin Marca"
            tk.Label(content, text=texto_marca, font=("Segoe UI", 8, "italic"), fg="#0078d4", bg="#ffffff", wraplength=130, justify="left").pack(anchor="w")

            tk.Label(content, text=f"S/ {precio:.2f}", font=("Segoe UI", 10, "bold"), fg="#107c41", bg="#ffffff").pack(anchor="w", pady=(2, 0))
            tk.Label(content, text=f"Stock: {stock}", font=("Segoe UI", 8), fg="#666666" if stock > stock_min else "#d13438", bg="#ffffff").pack(anchor="w")

            btn_add = ttk.Button(content, text="➕ Agregar", command=lambda p_id=prod_id, cod=codigo, nom=nombre, prec=precio, stk=stock: self._agregar_item_a_lista(p_id, cod, nom, prec, stk))
            btn_add.pack(fill="x", pady=(4, 0))

        for col in range(cols_max):
            self.scrollable_pos_frame.grid_columnconfigure(col, weight=1)

    def _agregar_al_carrito_por_codigo(self, event=None):
        query = self.entry_codigo_carrito.get().strip()
        if not query:
            return

        prod = self.db.obtener_producto_por_codigo(query)
        if prod:
            self._agregar_item_a_lista(prod[0], prod[1], prod[2], float(prod[3]), int(prod[4]))
            self.entry_codigo_carrito.delete(0, tk.END)
            return

        prods = self.db.obtener_productos(filtro=query)
        if not prods:
            messagebox.showerror("No encontrado", f"No se encontró ningún producto con '{query}'.")
            return

        if len(prods) == 1:
            p = prods[0]
            self._agregar_item_a_lista(p[0], p[1], p[2], float(p[9]), int(p[10]))
            self.entry_codigo_carrito.delete(0, tk.END)
        else:
            dialogo = DialogoSeleccionProducto(self.root, prods)
            if dialogo.producto_seleccionado:
                p = dialogo.producto_seleccionado
                self._agregar_item_a_lista(p[0], p[1], p[2], float(p[9]), int(p[10]))
                self.entry_codigo_carrito.delete(0, tk.END)

    def _agregar_item_a_lista(self, prod_id, codigo, nombre, precio, stock_max):
        if stock_max <= 0:
            messagebox.showwarning("Sin Stock", f"El producto '{nombre}' no tiene unidades disponibles.")
            return

        for item in self.carrito:
            if item['id'] == prod_id:
                if item['cantidad'] + 1 > stock_max:
                    messagebox.showwarning("Límite de Stock", f"Stock máximo alcanzado: {stock_max}")
                    return
                item['cantidad'] += 1
                self._actualizar_vista_carrito()
                return

        self.carrito.append({
            'id': prod_id,
            'codigo': codigo,
            'nombre': nombre,
            'precio': precio,
            'cantidad': 1,
            'stock_max': stock_max
        })
        self._actualizar_vista_carrito()

    def _actualizar_vista_carrito(self):
        for item in self.tree_carrito.get_children():
            self.tree_carrito.delete(item)

        total = 0.0
        for idx, item in enumerate(self.carrito):
            subtotal = item['precio'] * item['cantidad']
            total += subtotal
            self.tree_carrito.insert("", "end", iid=str(idx), values=(
                item['codigo'], item['nombre'], f"S/ {item['precio']:.2f}", item['cantidad'], f"S/ {subtotal:.2f}"
            ))

        self.lbl_total_carrito.config(text=f"S/ {total:.2f}")
        self._calcular_vuelto()

    def _modificar_cantidad_carrito(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx = int(sel[0])
        item = self.carrito[idx]
        nueva_cant = simpledialog.askinteger("Cantidad", f"Nueva cantidad para '{item['nombre']}':",
                                             initialvalue=item['cantidad'], minvalue=1, maxvalue=item['stock_max'])
        if nueva_cant:
            item['cantidad'] = nueva_cant
            self._actualizar_vista_carrito()

    def _quitar_item_carrito(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx = int(sel[0])
        del self.carrito[idx]
        self._actualizar_vista_carrito()

    def _vaciar_carrito(self):
        if self.carrito and messagebox.askyesno("Vaciar", "¿Deseas vaciar el carrito?"):
            self.carrito.clear()
            self._actualizar_vista_carrito()

    def _calcular_vuelto(self, event=None):
        try:
            total = sum(i['precio'] * i['cantidad'] for i in self.carrito)
            pago = float(self.var_pago.get())
            vuelto = pago - total
            if vuelto >= 0:
                self.lbl_vuelto.config(text=f"S/ {vuelto:.2f}", foreground="#0078d4")
            else:
                self.lbl_vuelto.config(text=f"- S/ {abs(vuelto):.2f}", foreground="#d13438")
        except ValueError:
            self.lbl_vuelto.config(text="S/ 0.00", foreground="#0078d4")

    def _procesar_venta(self):
        if not self.carrito:
            messagebox.showwarning("Carrito Vacío", "No hay productos para procesar.")
            return

        total = sum(i['precio'] * i['cantidad'] for i in self.carrito)
        if messagebox.askyesno("Confirmar Venta", f"¿Procesar venta al contado por S/ {total:.2f}?"):
            try:
                self.db.procesar_venta_carrito(self.carrito)
                messagebox.showinfo("Éxito", "¡Venta realizada con éxito!")
                self.carrito.clear()
                self._actualizar_vista_carrito()
                self.var_pago.set("0.00")
                self._refrescar_todo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _procesar_deuda(self):
        if not self.carrito:
            messagebox.showwarning("Carrito Vacío", "No hay productos para procesar.")
            return

        cliente = simpledialog.askstring("Registrar Deuda", "Nombre del Cliente / Deudor:").strip()
        if not cliente:
            messagebox.showwarning("Nombre Requerido", "Debes ingresar el nombre del cliente para fiar.")
            return

        total = sum(i['precio'] * i['cantidad'] for i in self.carrito)
        if messagebox.askyesno("Confirmar Deuda", f"¿Registrar deuda de S/ {total:.2f} a nombre de '{cliente}'?"):
            try:
                self.db.procesar_venta_carrito(self.carrito, es_deuda=True, cliente=cliente)
                messagebox.showinfo("Éxito", f"Deuda registrada correctamente a {cliente}.")
                self.carrito.clear()
                self._actualizar_vista_carrito()
                self.var_pago.set("0.00")
                self._refrescar_todo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ---------------- TAB DEUDAS DE CLIENTES ----------------
    def _construir_tab_deudas(self):
        paned = ttk.PanedWindow(self.tab_deudas, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = ttk.LabelFrame(paned, text=" Clientes con Deuda Pendiente ", padding=10)
        paned.add(left_frame, weight=1)

        top_filter = ttk.Frame(left_frame)
        top_filter.pack(fill="x", pady=(0, 5))
        ttk.Label(top_filter, text="Buscar Cliente:").pack(side="left")
        self.var_filtro_cliente = tk.StringVar()
        entry_filtro_c = ttk.Entry(top_filter, textvariable=self.var_filtro_cliente)
        entry_filtro_c.pack(side="left", fill="x", expand=True, padx=5)
        entry_filtro_c.bind("<KeyRelease>", lambda e: self._cargar_clientes_deuda())

        cols_c = ("cliente", "deuda_total")
        self.tree_deudores = ttk.Treeview(left_frame, columns=cols_c, show="headings", selectmode="browse")
        self.tree_deudores.heading("cliente", text="Cliente")
        self.tree_deudores.heading("deuda_total", text="Deuda Total")
        self.tree_deudores.column("cliente", width=150, anchor="w")
        self.tree_deudores.column("deuda_total", width=100, anchor="center")
        self.tree_deudores.pack(fill="both", expand=True)

        self.tree_deudores.bind("<<TreeviewSelect>>", self._mostrar_detalle_deuda_cliente)

        btn_pagar = ttk.Button(left_frame, text="✅ Cancelar Deuda Total", style="Accent.TButton", command=self._pagar_deuda_cliente)
        btn_pagar.pack(fill="x", pady=(10, 0))

        right_frame = ttk.LabelFrame(paned, text=" Detalle de Productos Fiados ", padding=10)
        paned.add(right_frame, weight=2)

        self.lbl_cliente_detalles = ttk.Label(right_frame, text="Seleccione un cliente de la lista", font=("Segoe UI", 10, "bold"), foreground="#0078d4")
        self.lbl_cliente_detalles.pack(anchor="w", pady=(0, 5))

        cols_d = ("codigo", "nombre", "cantidad", "precio", "subtotal", "fecha")
        self.tree_detalle_deuda = ttk.Treeview(right_frame, columns=cols_d, show="headings", selectmode="none")
        encabezados = {"codigo": "Código", "nombre": "Producto", "cantidad": "Cant.", "precio": "P. Unit.", "subtotal": "Subtotal", "fecha": "Fecha de Compra"}
        anchos = {"codigo": 80, "nombre": 180, "cantidad": 50, "precio": 70, "subtotal": 80, "fecha": 130}
        for c in cols_d:
            self.tree_detalle_deuda.heading(c, text=encabezados[c])
            self.tree_detalle_deuda.column(c, width=anchos[c], anchor="center" if c != "nombre" else "w")

        self.tree_detalle_deuda.pack(fill="both", expand=True)

    def _cargar_clientes_deuda(self):
        for item in self.tree_deudores.get_children():
            self.tree_deudores.delete(item)

        filtro = self.var_filtro_cliente.get().strip()
        for r in self.db.obtener_deudas_agrupadas(filtro):
            self.tree_deudores.insert("", "end", iid=r[0], values=(r[0], f"S/ {r[1]:.2f}"))

        for item in self.tree_detalle_deuda.get_children():
            self.tree_detalle_deuda.delete(item)
        self.lbl_cliente_detalles.config(text="Seleccione un cliente de la lista")

    def _mostrar_detalle_deuda_cliente(self, event=None):
        sel = self.tree_deudores.selection()
        if not sel:
            return

        cliente = sel[0]
        self.lbl_cliente_detalles.config(text=f"Detalle de deuda de: {cliente}")

        for item in self.tree_detalle_deuda.get_children():
            self.tree_detalle_deuda.delete(item)

        detalles = self.db.obtener_detalle_deuda_cliente(cliente)
        for d in detalles:
            self.tree_detalle_deuda.insert("", "end", values=(
                d[1], d[2], d[3], f"S/ {d[4]:.2f}", f"S/ {d[5]:.2f}", d[6]
            ))

    def _pagar_deuda_cliente(self):
        sel = self.tree_deudores.selection()
        if not sel:
            messagebox.showwarning("Atención", "Por favor seleccione un cliente para saldar la deuda.")
            return

        cliente = sel[0]
        if messagebox.askyesno("Saldar Deuda", f"¿Confirmar que {cliente} ha pagado la totalidad de su deuda?"):
            self.db.pagar_deuda_cliente(cliente)
            messagebox.showinfo("Éxito", f"Deuda de {cliente} cancelada con éxito.")
            self._refrescar_todo()

    # ---------------- TAB PRODUCTOS & CATÁLOGO ----------------
    def _construir_tab_productos(self):
        top = ttk.Frame(self.tab_productos, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Buscar:").pack(side="left")
        self.var_busqueda = tk.StringVar()
        entry_busqueda = ttk.Entry(top, textvariable=self.var_busqueda, width=22)
        entry_busqueda.pack(side="left", padx=5)
        entry_busqueda.bind("<KeyRelease>", lambda e: self._cargar_productos())

        ttk.Label(top, text="Categoría:").pack(side="left", padx=(10, 0))
        self.var_categoria_filtro = tk.StringVar(value="Todas")
        self.combo_cat_filtro = ttk.Combobox(top, textvariable=self.var_categoria_filtro, state="readonly", width=25)
        self.combo_cat_filtro["values"] = ["Todas"]
        self.combo_cat_filtro.pack(side="left", padx=5)
        self.combo_cat_filtro.bind("<<ComboboxSelected>>", lambda e: self._cargar_productos())

        self.var_modo_vista = tk.BooleanVar(value=True)
        btn_toggle = ttk.Checkbutton(top, text="🖼️ Vista Galería / Tarjetas", variable=self.var_modo_vista, command=self._alternar_modo_vista)
        btn_toggle.pack(side="left", padx=15)

        ttk.Button(top, text="➕ Nuevo producto", command=self._abrir_form_producto).pack(side="right", padx=2)
        ttk.Button(top, text="✏️ Editar", command=self._editar_producto_seleccionado).pack(side="right", padx=2)
        ttk.Button(top, text="🗑️ Eliminar", command=self._eliminar_producto_seleccionado).pack(side="right", padx=2)
        ttk.Button(top, text="📦 Reg. Movimiento", command=self._abrir_form_movimiento).pack(side="right", padx=2)
        ttk.Button(top, text="📄 Exportar PDF", command=self._abrir_modal_exportar_pdf).pack(side="right", padx=2)

        self.paned_window = ttk.PanedWindow(self.tab_productos, orient="horizontal")
        self.paned_window.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.frame_tabla = ttk.Frame(self.paned_window)
        cols = ("codigo", "nombre", "marca", "categoria", "ubicacion", "costo", "precio", "stock")
        self.tree_productos = ttk.Treeview(self.frame_tabla, columns=cols, show="headings", selectmode="browse")
        encabezados = {"codigo": "Código", "nombre": "Nombre", "marca": "Marca", "categoria": "Categoría",
                       "ubicacion": "📍 Ubicación", "costo": "Costo", "precio": "Precio", "stock": "Stock"}
        for c in cols:
            self.tree_productos.heading(c, text=encabezados[c])
            self.tree_productos.column(c, width=100, anchor="center" if c not in ("nombre", "marca") else "w")

        scroll_y = ttk.Scrollbar(self.frame_tabla, orient="vertical", command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=scroll_y.set)
        self.tree_productos.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="left", fill="y")

        self.frame_grid_container = ttk.Frame(self.paned_window)
        self.canvas_grid = tk.Canvas(self.frame_grid_container, bg="#f5f5f7", highlightthickness=0)
        self.scrollbar_grid = ttk.Scrollbar(self.frame_grid_container, orient="vertical", command=self.canvas_grid.yview)
        self.scrollable_grid_frame = tk.Frame(self.canvas_grid, bg="#f5f5f7")

        self.scrollable_grid_frame.bind("<Configure>", lambda e: self.canvas_grid.configure(scrollregion=self.canvas_grid.bbox("all")))
        self.canvas_window_id = self.canvas_grid.create_window((0, 0), window=self.scrollable_grid_frame, anchor="nw")
        self.canvas_grid.configure(yscrollcommand=self.scrollbar_grid.set)

        self.canvas_grid.pack(side="left", fill="both", expand=True)
        self.scrollbar_grid.pack(side="right", fill="y")
        self.canvas_grid.bind('<Configure>', self._on_canvas_configure)

        self.frame_preview = ttk.LabelFrame(self.paned_window, text=" Detalle del Producto ", padding=10)

        self.paned_window.add(self.frame_grid_container, weight=3)
        self.paned_window.add(self.frame_preview, weight=1)

        self.frame_img_container = ttk.Frame(self.frame_preview, relief="sunken", borderwidth=1)
        self.frame_img_container.pack(pady=5, fill="both", expand=True)

        self.lbl_preview_img = ttk.Label(self.frame_img_container, text="Sin imagen", anchor="center")
        self.lbl_preview_img.pack(fill="both", expand=True)

        self.frame_nav_img = ttk.Frame(self.frame_preview)
        self.frame_nav_img.pack(fill="x", pady=2)
        
        self.btn_prev_img = ttk.Button(self.frame_nav_img, text="◀ Anterior", width=10, command=self._prev_imagen_preview)
        self.btn_prev_img.pack(side="left", padx=2)
        
        self.lbl_img_counter = ttk.Label(self.frame_nav_img, text="0 / 0", font=("Segoe UI", 8))
        self.lbl_img_counter.pack(side="left", expand=True)

        self.btn_next_img = ttk.Button(self.frame_nav_img, text="Siguiente ▶", width=10, command=self._next_imagen_preview)
        self.btn_next_img.pack(side="right", padx=2)

        self.frame_img_container.bind("<Configure>", self._on_container_resize)

        ttk.Separator(self.frame_preview, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(self.frame_preview, text="Detalles / Especificaciones:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        
        self.txt_preview_detalles = tk.Text(self.frame_preview, width=28, height=6, font=("Segoe UI", 9), wrap="word", relief="solid", bd=1)
        self.txt_preview_detalles.pack(fill="both", expand=True, pady=5)
        self.txt_preview_detalles.config(state="disabled")

        self.tree_productos.bind("<<TreeviewSelect>>", self._mostrar_preview_producto)

    def _prev_imagen_preview(self):
        if self.imagenes_actuales_raw:
            self.idx_imagen_actual = (self.idx_imagen_actual - 1) % len(self.imagenes_actuales_raw)
            self._renderizar_imagen_dinamica()

    def _next_imagen_preview(self):
        if self.imagenes_actuales_raw:
            self.idx_imagen_actual = (self.idx_imagen_actual + 1) % len(self.imagenes_actuales_raw)
            self._renderizar_imagen_dinamica()

    def _abrir_modal_exportar_pdf(self):
        top = Toplevel(self.root)
        top.title("Exportar Catálogo PDF")
        top.geometry("360x170")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        ttk.Label(top, text="Selecciona el alcance de la exportación:", font=("Segoe UI", 9, "bold")).pack(pady=(15, 5), padx=15, anchor="w")

        categorias = ["Todas"] + self.db.obtener_categorias()
        combo_alcance = ttk.Combobox(top, values=categorias, state="readonly", font=("Segoe UI", 10))
        combo_alcance.current(0)
        combo_alcance.pack(fill="x", padx=15, pady=5)

        def ejecutar_exportacion():
            alcance = combo_alcance.get()
            top.destroy()

            nombre_sugerido = f"Catalogo_{alcance.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            ruta = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                title="Guardar Catálogo PDF",
                initialfile=nombre_sugerido
            )
            if ruta:
                try:
                    generar_pdf_catalogo(self.db, ruta, categoria=alcance)
                    messagebox.showinfo("Éxito", f"Catálogo PDF generado correctamente en:\n{ruta}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo generar el catálogo:\n{e}")

        frame_botones = ttk.Frame(top)
        frame_botones.pack(side="bottom", fill="x", pady=15, padx=15)

        ttk.Button(frame_botones, text="Cancelar", command=top.destroy).pack(side="left")
        ttk.Button(frame_botones, text="📄 Generar PDF", style="Accent.TButton", command=ejecutar_exportacion).pack(side="right")

    def _alternar_modo_vista(self):
        for pane in self.paned_window.panes():
            self.paned_window.forget(pane)

        if self.var_modo_vista.get():
            self.paned_window.add(self.frame_grid_container, weight=3)
            for child in self.scrollable_grid_frame.winfo_children():
                child.destroy()
        else:
            self.paned_window.add(self.frame_tabla, weight=3)

        self.paned_window.add(self.frame_preview, weight=1)
        self._cargar_productos()

    def _cargar_productos(self):
        filtro = self.var_busqueda.get().strip()
        categoria = self.var_categoria_filtro.get()
        self.productos_actuales = self.db.obtener_productos(filtro=filtro, categoria=categoria)

        if self.var_modo_vista.get():
            self._cargar_productos_grid(self.productos_actuales)
        else:
            self._cargar_productos_tabla(self.productos_actuales)

        cats = ["Todas"] + self.db.obtener_categorias()
        actual = self.combo_cat_filtro.get()
        self.combo_cat_filtro["values"] = cats
        if actual not in cats:
            self.combo_cat_filtro.set("Todas")

    def _cargar_productos_tabla(self, productos):
        for i in self.tree_productos.get_children():
            self.tree_productos.delete(i)
        
        for p in productos:
            id_, codigo, nombre, marca, categoria_p, ubicacion, detalles, unidad, costo, precio, stock, _, _ = p
            self.tree_productos.insert("", "end", iid=str(id_), values=(
                codigo, nombre, marca, categoria_p, ubicacion or "-", f"S/ {costo:.2f}", f"S/ {precio:.2f}", stock
            ))

    def _cargar_productos_grid(self, productos):
        for child in self.scrollable_grid_frame.winfo_children():
            child.destroy()

        self.referencias_fotos.clear()

        if not productos:
            ttk.Label(self.scrollable_grid_frame, text="No hay productos disponibles.", font=("Segoe UI", 11, "italic")).pack(pady=30)
            return

        ancho_canvas = self.canvas_grid.winfo_width()
        if ancho_canvas <= 1:
            ancho_canvas = 800

        ancho_tarjeta = 220
        cols_max = max(1, ancho_canvas // ancho_tarjeta)

        for i in range(20):
            self.scrollable_grid_frame.grid_columnconfigure(i, weight=0)

        for idx, p in enumerate(productos):
            r, c = idx // cols_max, idx % cols_max
            card = self._crear_tarjeta_producto(self.scrollable_grid_frame, p)
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

        for col in range(cols_max):
            self.scrollable_grid_frame.grid_columnconfigure(col, weight=1)

    def _on_canvas_configure(self, event):
        self.canvas_grid.itemconfig(self.canvas_window_id, width=event.width)
        if self._relayout_job:
            self.root.after_cancel(self._relayout_job)
        self._relayout_job = self.root.after(100, self._redistribuir_grid_si_es_necesario)

    def _redistribuir_grid_si_es_necesario(self):
        if self.var_modo_vista.get() and self.productos_actuales:
            self._cargar_productos_grid(self.productos_actuales)

    def _crear_tarjeta_producto(self, parent, prod):
        id_, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_min, imagen_blob = prod

        card = tk.Frame(parent, bg="#ffffff", highlightbackground="#e1e1e1", highlightthickness=1)
        
        def seleccionar(e=None):
            self.id_seleccionado = id_
            self._mostrar_preview_por_id(id_)
            for child in parent.winfo_children():
                child.config(highlightbackground="#e1e1e1", highlightthickness=1)
            card.config(highlightbackground="#0078d4", highlightthickness=2)

        card.bind("<Button-1>", seleccionar)

        img_container = tk.Frame(card, bg="#f8f8f8", height=140)
        img_container.pack(fill="x", side="top")
        img_container.pack_propagate(False)
        img_container.bind("<Button-1>", seleccionar)

        lbl_foto = tk.Label(img_container, bg="#f8f8f8")
        lbl_foto.pack(fill="both", expand=True)
        lbl_foto.bind("<Button-1>", seleccionar)

        photo = self._procesar_imagen_bytes(imagen_blob, (180, 130))
        if photo:
            lbl_foto.config(image=photo)
            lbl_foto.image = photo
            self.referencias_fotos.append(photo)
        else:
            lbl_foto.config(text="📷 Sin Imagen", font=("Segoe UI", 9), fg="#888888")

        content = tk.Frame(card, bg="#ffffff", padx=10, pady=8)
        content.pack(fill="both", expand=True)
        content.bind("<Button-1>", seleccionar)

        lbl_nom = tk.Label(content, text=nombre, font=("Segoe UI", 9, "bold"), fg="#333333", bg="#ffffff", wraplength=180, justify="left")
        lbl_nom.pack(anchor="w")
        lbl_nom.bind("<Button-1>", seleccionar)

        texto_marca = f"Marca: {marca}" if marca else "Marca: S/M"
        lbl_marca = tk.Label(content, text=texto_marca, font=("Segoe UI", 8, "italic"), fg="#0078d4", bg="#ffffff", wraplength=180, justify="left")
        lbl_marca.pack(anchor="w")
        lbl_marca.bind("<Button-1>", seleccionar)

        lbl_stk = tk.Label(content, text=f"Stock: {stock} unids.", font=("Segoe UI", 8), fg="#666666" if stock > stock_min else "#d13438", bg="#ffffff")
        lbl_stk.pack(anchor="w", pady=(2, 4))

        p_frame = tk.Frame(content, bg="#ffffff")
        p_frame.pack(fill="x", side="bottom")
        tk.Label(p_frame, text="Precio:", font=("Segoe UI", 8), fg="#888888", bg="#ffffff").pack(side="left")
        tk.Label(p_frame, text=f"S/ {precio:.2f}", font=("Segoe UI", 11, "bold"), fg="#3d1152", bg="#ffffff").pack(side="right")

        return card

    def _procesar_imagen_bytes(self, blob_bytes, size):
        if not blob_bytes:
            return None
        try:
            img = Image.open(io.BytesIO(blob_bytes))
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _mostrar_preview_producto(self, event=None):
        sel = self.tree_productos.selection()
        if sel:
            prod_id = int(sel[0])
            self.id_seleccionado = prod_id
            self._mostrar_preview_por_id(prod_id)

    def _mostrar_preview_por_id(self, prod_id):
        row = self.db.obtener_producto_por_id(prod_id)
        if row:
            detalles_texto = row[6] or "Sin observaciones."
            self._set_text_preview(
                f"Código: {row[1]}\n"
                f"Marca: {row[3]}\n"
                f"Categoría: {row[4]}\n"
                f"Ubicación: {row[5]}\n"
                f"Stock: {row[10]} unids.\n\n"
                f"Observaciones:\n{detalles_texto}"
            )
            self.imagenes_actuales_raw = self.db.obtener_imagenes_producto(prod_id)
            self.idx_imagen_actual = 0
            self._renderizar_imagen_dinamica()

    def _renderizar_imagen_dinamica(self):
        total_imgs = len(self.imagenes_actuales_raw)
        if total_imgs == 0:
            self.lbl_preview_img.config(image="", text="Sin imagen")
            self.lbl_img_counter.config(text="0 / 0")
            self.btn_prev_img.config(state="disabled")
            self.btn_next_img.config(state="disabled")
            return

        self.frame_img_container.update_idletasks()
        w = max(self.frame_img_container.winfo_width() - 10, 100)
        h = max(self.frame_img_container.winfo_height() - 10, 100)

        img_blob = self.imagenes_actuales_raw[self.idx_imagen_actual]
        photo = self._procesar_imagen_bytes(img_blob, (w, h))
        if photo:
            self.lbl_preview_img.config(image=photo, text="")
            self.lbl_preview_img.image = photo
        else:
            self.lbl_preview_img.config(image="", text="Error al renderizar")

        self.lbl_img_counter.config(text=f"{self.idx_imagen_actual + 1} / {total_imgs}")
        
        state_btn = "normal" if total_imgs > 1 else "disabled"
        self.btn_prev_img.config(state=state_btn)
        self.btn_next_img.config(state=state_btn)

    def _on_container_resize(self, event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(50, self._renderizar_imagen_dinamica)

    def _set_text_preview(self, texto):
        self.txt_preview_detalles.config(state="normal")
        self.txt_preview_detalles.delete("1.0", tk.END)
        self.txt_preview_detalles.insert("1.0", texto)
        self.txt_preview_detalles.config(state="disabled")

    def _obtener_id_seleccionado(self):
        if not self.var_modo_vista.get():
            sel = self.tree_productos.selection()
            return int(sel[0]) if sel else None
        return self.id_seleccionado

    def _abrir_form_producto(self, id_=None):
        FormProducto(self.root, self.db, id_, on_guardado=self._refrescar_todo)

    def _editar_producto_seleccionado(self):
        id_ = self._obtener_id_seleccionado()
        if id_:
            self._abrir_form_producto(id_)

    def _eliminar_producto_seleccionado(self):
        id_ = self._obtener_id_seleccionado()
        if id_ and messagebox.askyesno("Confirmar", "¿Eliminar este producto?"):
            self.db.eliminar_producto(id_)
            self._refrescar_todo()

    def _abrir_form_movimiento(self):
        id_ = self._obtener_id_seleccionado()
        if id_:
            FormMovimiento(self.root, self.db, id_, on_guardado=self._refrescar_todo)

    # ---------------- REPORTE GANANCIAS, RENDIMIENTO & DIEZMO ----------------
    def _construir_tab_ganancias(self):
        cols = ("fecha", "unidades", "total_ventas", "total_costos", "ganancia_neta")
        self.tree_ganancias = ttk.Treeview(self.tab_reporte_ganancias, columns=cols, show="headings")
        encabezados = {"fecha": "Fecha", "unidades": "Unidades Vendidas", "total_ventas": "Ventas Totales", "total_costos": "Costos", "ganancia_neta": "Ganancia Neta"}
        for c in cols:
            self.tree_ganancias.heading(c, text=encabezados[c])
            self.tree_ganancias.column(c, width=150, anchor="center")

        self.tree_ganancias.pack(fill="both", expand=True, padx=10, pady=10)

    def _cargar_reporte_ganancias(self):
        for i in self.tree_ganancias.get_children():
            self.tree_ganancias.delete(i)
        for r in reversed(self.db.reporte_ganancias_diarias()):
            self.tree_ganancias.insert("", "end", values=(r[0], r[1], f"S/ {r[2]:.2f}", f"S/ {r[3]:.2f}", f"S/ {r[4]:.2f}"))

    # ---------------- 3. RENDIMIENTO DEL NEGOCIO ----------------
    def _construir_tab_rendimiento(self):
        top_frame = ttk.Frame(self.tab_rendimiento, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="📊 Rendimiento del Negocio - Ventas por Día y Hora", font=("Segoe UI", 12, "bold"), foreground="#0078d4").pack(anchor="w")
        ttk.Label(top_frame, text="Detecta tus días y horarios de mayor afluencia para planificar compras, atención o promociones.", font=("Segoe UI", 9, "italic"), foreground="#555555").pack(anchor="w", pady=(0, 5))

        filter_frame = ttk.Frame(top_frame)
        filter_frame.pack(fill="x", pady=5)

        ttk.Label(filter_frame, text="Periodo:").pack(side="left", padx=(0, 5))
        self.var_periodo_rendimiento = tk.StringVar(value="Histórico Total")
        combo_periodo = ttk.Combobox(filter_frame, textvariable=self.var_periodo_rendimiento, state="readonly", width=20)
        combo_periodo["values"] = ["Hoy", "Últimos 7 días", "Últimos 30 días", "Histórico Total"]
        combo_periodo.pack(side="left", padx=5)
        combo_periodo.bind("<<ComboboxSelected>>", lambda e: self._cargar_rendimiento_negocio())

        # Tarjetas resumen de insights
        cards_frame = ttk.Frame(self.tab_rendimiento, padding=(10, 0))
        cards_frame.pack(fill="x")

        self.lbl_top_dia = self._stat_card(cards_frame, "Día de Mayor Afluencia", "-", "#0078d4")
        self.lbl_top_hora = self._stat_card(cards_frame, "Hora Pico de Mayor Venta", "-", "#107c41")

        # Tabla de desglose
        table_frame = ttk.Frame(self.tab_rendimiento, padding=10)
        table_frame.pack(fill="both", expand=True)

        cols = ("dia", "hora", "unidades", "total_ventas")
        self.tree_rendimiento = ttk.Treeview(table_frame, columns=cols, show="headings")
        encabezados = {
            "dia": "Día de la Semana",
            "hora": "Rango Horario",
            "unidades": "Unidades Vendidas",
            "total_ventas": "Total Recaudado"
        }
        for c in cols:
            self.tree_rendimiento.heading(c, text=encabezados[c])
            self.tree_rendimiento.column(c, width=150, anchor="center")

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_rendimiento.yview)
        self.tree_rendimiento.configure(yscrollcommand=scroll_y.set)
        
        self.tree_rendimiento.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

    def _cargar_rendimiento_negocio(self):
        for item in self.tree_rendimiento.get_children():
            self.tree_rendimiento.delete(item)

        periodo = self.var_periodo_rendimiento.get()
        dias_map = {
            "Hoy": 1,
            "Últimos 7 días": 7,
            "Últimos 30 días": 30,
            "Histórico Total": None
        }
        dias_atras = dias_map.get(periodo)

        registros = self.db.obtener_ventas_por_dia_y_hora(dias_atras=dias_atras)
        
        nombres_dias = {
            '0': 'Domingo',
            '1': 'Lunes',
            '2': 'Martes',
            '3': 'Miércoles',
            '4': 'Jueves',
            '5': 'Viernes',
            '6': 'Sábado'
        }

        totales_por_dia = {}
        totales_por_hora = {}

        for r in registros:
            num_dia, hora, unidades, total_ventas = r
            nombre_dia = nombres_dias.get(num_dia, "Desconocido")
            rango_hora = f"{int(hora):02d}:00 - {int(hora):02d}:59"

            # Acumular para insights
            totales_por_dia[nombre_dia] = totales_por_dia.get(nombre_dia, 0.0) + total_ventas
            totales_por_hora[rango_hora] = totales_por_hora.get(rango_hora, 0.0) + total_ventas

            self.tree_rendimiento.insert("", "end", values=(
                nombre_dia,
                rango_hora,
                unidades,
                f"S/ {total_ventas:.2f}"
            ))

        # Actualizar Insights Rápidos
        if totales_por_dia:
            top_dia = max(totales_por_dia, key=totales_por_dia.get)
            self.lbl_top_dia.config(text=f"{top_dia} (S/ {totales_por_dia[top_dia]:.2f})")
        else:
            self.lbl_top_dia.config(text="Sin datos")

        if totales_por_hora:
            top_hora = max(totales_por_hora, key=totales_por_hora.get)
            self.lbl_top_hora.config(text=f"{top_hora} (S/ {totales_por_hora[top_hora]:.2f})")
        else:
            self.lbl_top_hora.config(text="Sin datos")

    def _construir_tab_diezmo(self):
        top_info = ttk.Frame(self.tab_diezmo, padding=10)
        top_info.pack(fill="x")
        ttk.Label(top_info, text="⛪ Reporte Diario de Diezmo (10%)", font=("Segoe UI", 12, "bold"), foreground="#0078d4").pack(anchor="w")
        ttk.Label(top_info, text="Calculado sobre ventas al contado + deudas cobradas/saldadas.", font=("Segoe UI", 9, "italic"), foreground="#555555").pack(anchor="w")

        cols = ("fecha", "ventas_efectivo", "ganancia_neta_efectivo", "diezmo_10")
        self.tree_diezmo = ttk.Treeview(self.tab_diezmo, columns=cols, show="headings")
        encabezados = {
            "fecha": "Fecha de Cobro",
            "ventas_efectivo": "Efectivo Recibido",
            "ganancia_neta_efectivo": "Ganancia Neta",
            "diezmo_10": "Diezmo (10%)"
        }
        for c in cols:
            self.tree_diezmo.heading(c, text=encabezados[c])
            self.tree_diezmo.column(c, width=180, anchor="center")

        self.tree_diezmo.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _cargar_reporte_diezmo(self):
        for i in self.tree_diezmo.get_children():
            self.tree_diezmo.delete(i)
        for r in self.db.reporte_diezmo_efectivo_diario():
            self.tree_diezmo.insert("", "end", values=(r[0], f"S/ {r[1]:.2f}", f"S/ {r[2]:.2f}", f"S/ {r[3]:.2f}"))

    # ---------------- TAB CONTROL PAGOS DIEZMO ----------------
    def _construir_tab_pagos_diezmo(self):
        top_frame = ttk.Frame(self.tab_pagos_diezmo, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="⛪ Historial de Pagos de Diezmo Realizados", font=("Segoe UI", 12, "bold"), foreground="#0078d4").pack(side="left", anchor="w")
        ttk.Button(top_frame, text="➕ Registrar Nuevo Pago", style="Accent.TButton", command=self._abrir_form_pago_diezmo).pack(side="right")

        cols = ("id", "monto", "fecha_pago", "observacion")
        self.tree_pagos_diezmo = ttk.Treeview(self.tab_pagos_diezmo, columns=cols, show="headings", selectmode="browse")
        encabezados = {
            "id": "ID",
            "monto": "Monto Pagado",
            "fecha_pago": "Fecha de Pago",
            "observacion": "Observación / Referencia"
        }
        anchos = {"id": 50, "monto": 120, "fecha_pago": 160, "observacion": 350}
        for c in cols:
            self.tree_pagos_diezmo.heading(c, text=encabezados[c])
            self.tree_pagos_diezmo.column(c, width=anchos[c], anchor="center" if c != "observacion" else "w")

        scroll_y = ttk.Scrollbar(self.tab_pagos_diezmo, orient="vertical", command=self.tree_pagos_diezmo.yview)
        self.tree_pagos_diezmo.configure(yscrollcommand=scroll_y.set)

        self.tree_pagos_diezmo.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        scroll_y.pack(side="right", fill="y")

        btn_bar = ttk.Frame(self.tab_pagos_diezmo, padding=10)
        btn_bar.pack(fill="x")
        ttk.Button(btn_bar, text="🗑️ Eliminar Registro Seleccionado", style="Warning.TButton", command=self._eliminar_pago_diezmo_seleccionado).pack(side="right")

    def _cargar_pagos_diezmo(self):
        for i in self.tree_pagos_diezmo.get_children():
            self.tree_pagos_diezmo.delete(i)
        for p in self.db.obtener_pagos_diezmo():
            self.tree_pagos_diezmo.insert("", "end", iid=str(p[0]), values=(
                p[0], f"S/ {p[1]:.2f}", p[2], p[3]
            ))

    def _abrir_form_pago_diezmo(self):
        FormPagoDiezmo(self.root, self.db, on_guardado=self._refrescar_todo)

    def _eliminar_pago_diezmo_seleccionado(self):
        sel = self.tree_pagos_diezmo.selection()
        if not sel:
            messagebox.showwarning("Atención", "Por favor selecciona un registro de pago para eliminar.")
            return
        pago_id = int(sel[0])
        if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar el registro de pago ID {pago_id}?"):
            try:
                self.db.eliminar_pago_diezmo(pago_id)
                messagebox.showinfo("Éxito", "Registro eliminado correctamente.")
                self._refrescar_todo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ---------------- TAB MOVIMIENTOS & ALERTAS ----------------
    def _construir_tab_movimientos(self):
        cols = ("id", "codigo", "nombre", "tipo", "cantidad", "precio_unitario", "costo_unitario", "total_venta", "ganancia_unit", "ganancia_total", "motivo", "fecha")
        self.tree_movimientos = ttk.Treeview(self.tab_movimientos, columns=cols, show="headings", selectmode="browse")
        encabezados = {
            "id": "ID",
            "codigo": "Código",
            "nombre": "Producto",
            "tipo": "Tipo",
            "cantidad": "Cant.",
            "precio_unitario": "Precio Unit.",
            "costo_unitario": "Costo Unit.",
            "total_venta": "Monto Total",
            "ganancia_unit": "Gan. Unit.",
            "ganancia_total": "Gan. Total",
            "motivo": "Motivo",
            "fecha": "Fecha"
        }
        anchos = {
            "id": 40,
            "codigo": 80,
            "nombre": 160,
            "tipo": 65,
            "cantidad": 45,
            "precio_unitario": 75,
            "costo_unitario": 75,
            "total_venta": 85,
            "ganancia_unit": 80,
            "ganancia_total": 85,
            "motivo": 130,
            "fecha": 125
        }
        for c in cols:
            self.tree_movimientos.heading(c, text=encabezados[c])
            self.tree_movimientos.column(c, width=anchos[c], anchor="center" if c not in ("nombre", "motivo") else "w")

        self.tree_movimientos.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        btn_bar = ttk.Frame(self.tab_movimientos, padding=5)
        btn_bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_bar, text="🗑️ Eliminar / Revertir Movimiento", style="Warning.TButton", command=self._eliminar_movimiento_seleccionado).pack(side="right")

    def _cargar_movimientos(self):
        for i in self.tree_movimientos.get_children():
            self.tree_movimientos.delete(i)
        for m in self.db.obtener_movimientos():
            self.tree_movimientos.insert("", "end", iid=str(m[0]), values=(
                m[0], m[1], m[2], m[3].upper(), m[4],
                f"S/ {m[5]:.2f}", f"S/ {m[6]:.2f}", f"S/ {m[7]:.2f}",
                f"S/ {m[8]:.2f}", f"S/ {m[9]:.2f}",
                m[10], m[11]
            ))

    def _eliminar_movimiento_seleccionado(self):
        sel = self.tree_movimientos.selection()
        if not sel:
            messagebox.showwarning("Atención", "Por favor seleccione un movimiento de la lista para eliminar.")
            return

        mov_id = int(sel[0])
        if messagebox.askyesno("Confirmar Reversión", f"¿Desea eliminar el movimiento ID {mov_id}?\nEsto revertirá el stock afectado en el inventario."):
            try:
                self.db.eliminar_movimiento(mov_id)
                messagebox.showinfo("Éxito", f"Movimiento {mov_id} eliminado y stock revertido correctamente.")
                self._refrescar_todo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _construir_tab_alertas(self):
        cols = ("codigo", "nombre", "categoria", "stock", "stock_min")
        self.tree_alertas = ttk.Treeview(self.tab_alertas, columns=cols, show="headings")
        for c in cols:
            self.tree_alertas.heading(c, text=c.capitalize())
            self.tree_alertas.column(c, width=120, anchor="center")
        self.tree_alertas.pack(fill="both", expand=True, padx=10, pady=10)

    def _cargar_alertas(self):
        for i in self.tree_alertas.get_children():
            self.tree_alertas.delete(i)
        for p in self.db.obtener_productos(solo_bajo_stock=True):
            self.tree_alertas.insert("", "end", values=(p[1], p[2], p[4], p[10], p[11]))

    def _refrescar_todo(self, event=None):
        try:
            self.cache_imagenes.clear()
            self._cargar_productos()
            self._cargar_tarjetas_pos()
            self._cargar_clientes_deuda()
            self._cargar_movimientos()
            self._cargar_alertas()
            self._cargar_reporte_ganancias()
            self._cargar_rendimiento_negocio()
            self._cargar_reporte_diezmo()
            self._cargar_pagos_diezmo()

            stats = self.db.estadisticas()
            self.lbl_total_prod.config(text=str(stats["total_productos"]))
            self.lbl_total_unid.config(text=str(stats["total_unidades"]))
            self.lbl_valor_inv.config(text=f"S/ {stats['valor_inventario']:.2f}")
            self.lbl_total_deudas.config(text=f"S/ {stats['total_deudas']:.2f}")
            self.lbl_bajo_stock.config(text=str(stats["bajo_stock"]))
        except Exception as e:
            # Captura y muestra cualquier error silencioso para evitar cierre abrupto
            pass


# ---------------------------------------------------------------------------
# DIÁLOGO DE SELECCIÓN DE PRODUCTO MÚLTIPLE
# ---------------------------------------------------------------------------
class DialogoSeleccionProducto(tk.Toplevel):
    def __init__(self, parent, productos):
        super().__init__(parent)
        self.productos = productos
        self.producto_seleccionado = None

        self.title("Seleccionar Producto")
        self.geometry("600x350")
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Se encontraron múltiples coincidencias. Selecciona una:", font=("Segoe UI", 10, "bold")).pack(pady=10, padx=10, anchor="w")

        cols = ("codigo", "nombre", "marca", "precio", "stock")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("codigo", text="Código")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("marca", text="Marca")
        self.tree.heading("precio", text="Precio")
        self.tree.heading("stock", text="Stock")

        self.tree.column("codigo", width=80, anchor="center")
        self.tree.column("nombre", width=220, anchor="w")
        self.tree.column("marca", width=100, anchor="w")
        self.tree.column("precio", width=80, anchor="center")
        self.tree.column("stock", width=60, anchor="center")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side="top", fill="both", expand=True, padx=(10, 0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=5)

        for p in productos:
            self.tree.insert("", "end", iid=str(p[0]), values=(p[1], p[2], p[3], f"S/ {p[9]:.2f}", p[10]))

        self.tree.bind("<Double-1>", lambda e: self._confirmar())

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="✅ Agregar al Carrito", command=self._confirmar).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right")

    def _confirmar(self):
        sel = self.tree.selection()
        if sel:
            prod_id = int(sel[0])
            for p in self.productos:
                if p[0] == prod_id:
                    self.producto_seleccionado = p
                    break
            self.destroy()


# ---------------------------------------------------------------------------
# FORMULARIO PRODUCTO
# ---------------------------------------------------------------------------
class FormProducto(Toplevel):
    def __init__(self, parent, db, producto_id=None, on_guardado=None):
        super().__init__(parent)
        self.db = db
        self.producto_id = producto_id
        self.on_guardado = on_guardado
        self.lista_blobs_imagenes = []

        self.title("Editar Producto" if producto_id else "Nuevo Producto")
        self.geometry("520x680")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._construir_ui()
        if producto_id:
            self._cargar_datos()

    def _construir_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        campos = [
            ("Código de Barras *:", "entry_codigo"),
            ("Nombre del Producto *:", "entry_nombre"),
            ("Marca:", "entry_marca"),
            ("Categoría:", "combo_categoria"),
            ("📍 Ubicación:", "entry_ubicacion"),
            ("Unidad de Medida:", "entry_unidad"),
            ("Costo Unitario (S/) *:", "entry_costo"),
            ("Precio Venta (S/) *:", "entry_precio"),
            ("Stock Inicial *:", "entry_stock"),
            ("Stock Mínimo *:", "entry_stock_min"),
        ]

        self.widgets = {}

        for i, (label, name) in enumerate(campos):
            ttk.Label(container, text=label).grid(row=i, column=0, sticky="w", pady=3)
            if name == "combo_categoria":
                widget = ttk.Combobox(container, width=28)
                widget["values"] = self.db.obtener_categorias()
            else:
                widget = ttk.Entry(container, width=30)
            widget.grid(row=i, column=1, sticky="ew", pady=3)
            self.widgets[name] = widget

        self.widgets["entry_unidad"].insert(0, "unidad")
        self.widgets["entry_costo"].insert(0, "0.00")
        self.widgets["entry_precio"].insert(0, "0.00")
        self.widgets["entry_stock"].insert(0, "0")
        self.widgets["entry_stock_min"].insert(0, "5")

        ttk.Label(container, text="Detalles / Observaciones:").grid(row=len(campos), column=0, sticky="nw", pady=3)
        self.txt_detalles = tk.Text(container, width=30, height=3, font=("Segoe UI", 9))
        self.txt_detalles.grid(row=len(campos), column=1, sticky="ew", pady=3)

        row_img = len(campos) + 1
        ttk.Label(container, text="Imágenes del Producto:").grid(row=row_img, column=0, sticky="w", pady=5)
        
        frame_imgs_btn = ttk.Frame(container)
        frame_imgs_btn.grid(row=row_img, column=1, sticky="w", pady=5)

        ttk.Button(frame_imgs_btn, text="📁 Cargar Imágenes", command=self._cargar_imagenes).pack(side="left", padx=2)
        ttk.Button(frame_imgs_btn, text="🗑️ Limpiar", command=self._limpiar_imagenes).pack(side="left", padx=2)

        self.lbl_cant_imgs = ttk.Label(container, text="0 imágenes seleccionadas", font=("Segoe UI", 8, "italic"), foreground="#0078d4")
        self.lbl_cant_imgs.grid(row=row_img+1, column=1, sticky="w")

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=row_img+2, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="Guardar", style="Accent.TButton", command=self._guardar).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right")

    def _cargar_imagenes(self):
        rutas = filedialog.askopenfilenames(
            title="Seleccionar imágenes del producto",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if rutas:
            for r in rutas:
                try:
                    with open(r, "rb") as f:
                        self.lista_blobs_imagenes.append(f.read())
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo leer la imagen: {r}\n{e}")
            
            self.lbl_cant_imgs.config(text=f"{len(self.lista_blobs_imagenes)} imagen(es) seleccionada(s)")

    def _limpiar_imagenes(self):
        self.lista_blobs_imagenes.clear()
        self.lbl_cant_imgs.config(text="0 imágenes seleccionadas")

    def _cargar_datos(self):
        prod = self.db.obtener_producto_por_id(self.producto_id)
        if not prod:
            return

        id_, codigo, nombre, marca, categoria, ubicacion, detalles, unidad, costo, precio, stock, stock_min, _ = prod

        self.widgets["entry_codigo"].insert(0, codigo)
        self.widgets["entry_nombre"].insert(0, nombre)
        self.widgets["entry_marca"].insert(0, marca or "")
        self.widgets["combo_categoria"].set(categoria or "")
        self.widgets["entry_ubicacion"].insert(0, ubicacion or "")
        self.widgets["entry_unidad"].delete(0, tk.END)
        self.widgets["entry_unidad"].insert(0, unidad or "unidad")
        
        self.widgets["entry_costo"].delete(0, tk.END)
        self.widgets["entry_costo"].insert(0, f"{costo:.2f}")

        self.widgets["entry_precio"].delete(0, tk.END)
        self.widgets["entry_precio"].insert(0, f"{precio:.2f}")

        self.widgets["entry_stock"].delete(0, tk.END)
        self.widgets["entry_stock"].insert(0, str(stock))
        self.widgets["entry_stock"].config(state="disabled")

        self.widgets["entry_stock_min"].delete(0, tk.END)
        self.widgets["entry_stock_min"].insert(0, str(stock_min))

        if detalles:
            self.txt_detalles.insert("1.0", detalles)

        self.lista_blobs_imagenes = self.db.obtener_imagenes_producto(self.producto_id)
        self.lbl_cant_imgs.config(text=f"{len(self.lista_blobs_imagenes)} imagen(es) cargada(s)")

    def _guardar(self):
        codigo = self.widgets["entry_codigo"].get().strip()
        nombre = self.widgets["entry_nombre"].get().strip()
        marca = self.widgets["entry_marca"].get().strip()
        categoria = self.widgets["combo_categoria"].get().strip()
        ubicacion = self.widgets["entry_ubicacion"].get().strip()
        unidad = self.widgets["entry_unidad"].get().strip() or "unidad"
        detalles = self.txt_detalles.get("1.0", tk.END).strip()

        if not codigo or not nombre:
            messagebox.showwarning("Campos obligatorios", "Por favor ingresa Código y Nombre.")
            return

        if self.db.existe_codigo(codigo, excluir_id=self.producto_id):
            messagebox.showerror("Código Duplicado", "Ya existe otro producto activo con ese código.")
            return

        try:
            costo = float(self.widgets["entry_costo"].get())
            precio = float(self.widgets["entry_precio"].get())
            stock = int(self.widgets["entry_stock"].get())
            stock_min = int(self.widgets["entry_stock_min"].get())
        except ValueError:
            messagebox.showerror("Error numérico", "Costo, Precio, Stock y Stock Mínimo deben ser números válidos.")
            return

        try:
            if self.producto_id:
                self.db.actualizar_producto(
                    self.producto_id, codigo, nombre, marca, categoria, ubicacion, detalles,
                    unidad, costo, precio, stock_min, self.lista_blobs_imagenes
                )
            else:
                self.db.agregar_producto(
                    codigo, nombre, marca, categoria, ubicacion, detalles,
                    unidad, costo, precio, stock, stock_min, self.lista_blobs_imagenes
                )

            if self.on_guardado:
                self.on_guardado()

            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al guardar: {e}")


# ---------------------------------------------------------------------------
# FORMULARIO MOVIMIENTO / MERMA
# ---------------------------------------------------------------------------
class FormMovimiento(Toplevel):
    def __init__(self, parent, db, producto_id, on_guardado=None):
        super().__init__(parent)
        self.db = db
        self.producto_id = producto_id
        self.on_guardado = on_guardado

        self.title("Registrar Movimiento / Merma")
        self.geometry("380x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._construir_ui()

    def _construir_ui(self):
        prod = self.db.obtener_producto_por_id(self.producto_id)
        nombre = prod[2] if prod else "Desconocido"

        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text=f"Producto: {nombre}", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))

        ttk.Label(container, text="Tipo de Movimiento:").pack(anchor="w")
        self.var_tipo = tk.StringVar(value="entrada")
        combo_tipo = ttk.Combobox(container, textvariable=self.var_tipo, state="readonly")
        combo_tipo["values"] = ["entrada", "salida", "merma"]
        combo_tipo.pack(fill="x", pady=(0, 10))

        ttk.Label(container, text="Cantidad:").pack(anchor="w")
        self.entry_cant = ttk.Entry(container)
        self.entry_cant.pack(fill="x", pady=(0, 10))
        self.entry_cant.insert(0, "1")

        ttk.Label(container, text="Motivo / Observación:").pack(anchor="w")
        self.entry_motivo = ttk.Entry(container)
        self.entry_motivo.pack(fill="x", pady=(0, 15))

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Guardar Movimiento", style="Accent.TButton", command=self._guardar).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right", padx=2)

    def _guardar(self):
        tipo = self.var_tipo.get()
        cant_str = self.entry_cant.get().strip()
        motivo = self.entry_motivo.get().strip()

        try:
            cant = int(cant_str)
            if cant <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "La cantidad debe ser un número entero mayor a 0.")
            return

        try:
            self.db.registrar_movimiento(self.producto_id, tipo, cant, motivo)
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ---------------------------------------------------------------------------
# FORMULARIO PAGO DE DIEZMO
# ---------------------------------------------------------------------------
class FormPagoDiezmo(Toplevel):
    def __init__(self, parent, db, on_guardado=None):
        super().__init__(parent)
        self.db = db
        self.on_guardado = on_guardado

        self.title("Registrar Pago de Diezmo")
        self.geometry("360x260")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._construir_ui()

    def _construir_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Monto a Pagar (S/) *:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.entry_monto = ttk.Entry(container, font=("Segoe UI", 11))
        self.entry_monto.pack(fill="x", pady=(0, 10))
        self.entry_monto.insert(0, "0.00")

        ttk.Label(container, text="Fecha de Pago (YYYY-MM-DD HH:MM) *:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.entry_fecha = ttk.Entry(container, font=("Segoe UI", 10))
        self.entry_fecha.pack(fill="x", pady=(0, 10))
        self.entry_fecha.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        ttk.Label(container, text="Observación / Detalle:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.entry_obs = ttk.Entry(container, font=("Segoe UI", 10))
        self.entry_obs.pack(fill="x", pady=(0, 15))
        self.entry_obs.insert(0, "Diezmo correspondiente a...")

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Guardar Pago", style="Accent.TButton", command=self._guardar).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right", padx=2)

    def _guardar(self):
        try:
            monto = float(self.entry_monto.get())
            if monto <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingresa un monto válido mayor a 0.")
            return

        fecha = self.entry_fecha.get().strip()
        obs = self.entry_obs.get().strip()

        if not fecha:
            messagebox.showerror("Error", "La fecha no puede estar vacía.")
            return

        try:
            self.db.registrar_pago_diezmo(monto, fecha, obs)
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA PRINCIPAL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = InventarioApp(root)
    root.mainloop()