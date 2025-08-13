import os
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import json
import datetime
import base64
import pandas as pd
import logging

load_dotenv()

db = None  # Variable global

# ---------------------------
# Inicializar Firebase
# ---------------------------
def inicializar_firebase():
    global db

    if firebase_admin._apps:
        return

    if "FIREBASE_PRIVATE_KEY_B64" in st.secrets:
        b64_str = st.secrets["FIREBASE_PRIVATE_KEY_B64"].replace('\n', '').replace('\r', '').strip()
        json_str = base64.b64decode(b64_str).decode("utf-8")
        cred_dict = json.loads(json_str)
        cred = credentials.Certificate(cred_dict)

    elif isinstance(st.secrets["SERVICE_ACCOUNT"], dict):
        cred = credentials.Certificate(st.secrets["SERVICE_ACCOUNT"])

    else:
        cred_dict = json.loads(st.secrets["SERVICE_ACCOUNT"])
        cred = credentials.Certificate(cred_dict)

    firebase_admin.initialize_app(cred)
    db = firestore.client()

# ---------------------------
# Función auxiliar para ruta segura
# ---------------------------
def _coleccion_usuario(nombre_coleccion):
    uid = st.session_state.get("uid")
    if not uid or db is None:
        return None  # <- No rompe la ejecución
    return db.collection("usuarios").document(uid).collection(nombre_coleccion)

# ---------------------------
# Ventas
# ---------------------------
def guardar_venta(venta_dict):
    ref = _coleccion_usuario("ventas")
    if not ref:
        return
    ref.add(venta_dict)
    logging.info("Venta guardada.")

# ---------------------------
# Clientes
# ---------------------------
def guardar_cliente(id_cliente, cliente_dict):
    ref = _coleccion_usuario("clientes")
    if not ref:
        return
    ref.document(id_cliente).set(cliente_dict)
    logging.info(f"Cliente '{id_cliente}' guardado.")

def actualizar_cliente(id_cliente, datos_nuevos):
    ref = _coleccion_usuario("clientes")
    if not ref:
        return
    ref.document(id_cliente).update(datos_nuevos)
    logging.info(f"Cliente '{id_cliente}' actualizado.")

# ---------------------------
# Transacciones
# ---------------------------
def guardar_transaccion(transaccion_dict):
    ref = _coleccion_usuario("transacciones")
    if not ref:
        return
    ref.add(transaccion_dict)
    logging.info("Transacción guardada.")

def registrar_pago_cobranza(cliente, monto, metodo_pago, fecha, descripcion=""):
    ref = _coleccion_usuario("transacciones")
    if not ref:
        return
    pago_dict = {
        "Fecha": fecha,
        "Descripción": descripcion or f"Abono de crédito por parte de {cliente}",
        "Categoría": "Cobranza",
        "Tipo": "Ingreso",
        "Monto": monto,
        "Cliente": cliente,
        "Método de pago": metodo_pago
    }
    ref.add(pago_dict)
    logging.info("Pago de cobranza registrado.")

# ---------------------------
# Productos
# ---------------------------
def guardar_producto(producto_dict):
    ref = _coleccion_usuario("productos")
    if not ref:
        return
    for campo in ["Marca_Tipo", "Modelo", "Color", "Talla"]:
        if campo not in producto_dict:
            producto_dict[campo] = ""
    ref.add(producto_dict)
    logging.info("Producto guardado.")

def leer_productos():
    columnas = [
        "Clave", "Nombre", "Marca_Tipo", "Modelo", "Color", "Talla",
        "Categoría", "Precio Unitario", "Costo Unitario", "Cantidad", "Descripción"
    ]
    ref = _coleccion_usuario("productos")
    if not ref:
        return pd.DataFrame(columns=columnas)

    docs = ref.stream()
    productos = []
    for doc in docs:
        data = doc.to_dict()
        producto_normalizado = {col: data.get(col, None) for col in columnas}
        productos.append(producto_normalizado)

    if not productos:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(productos)
    for col in columnas:
        if col not in df.columns:
            df[col] = None
    numeric_cols = ["Precio Unitario", "Costo Unitario", "Cantidad"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    return df[columnas]

def actualizar_producto_por_clave(clave, campos_actualizados: dict):
    ref = _coleccion_usuario("productos")
    if not ref:
        return
    for campo in ["Marca_Tipo", "Modelo", "Color", "Talla"]:
        if campo not in campos_actualizados:
            campos_actualizados[campo] = ""
    query = ref.where("Clave", "==", clave).get()
    if query:
        doc_id = query[0].id
        ref.document(doc_id).update(campos_actualizados)

def eliminar_producto_por_clave(clave):
    ref = _coleccion_usuario("productos")
    if not ref:
        return
    query = ref.where("Clave", "==", clave).get()
    if query:
        doc_id = query[0].id
        ref.document(doc_id).delete()

def obtener_id_producto(clave):
    ref = _coleccion_usuario("productos")
    if not ref:
        return None
    query = ref.where("Clave", "==", clave).get()
    if query:
        return query[0].id
    return None

# ---------------------------
# Reportes y cálculos
# ---------------------------
def leer_ventas():
    columnas = [
        "Fecha", "Cliente", "Producto", "Cantidad", "Precio Unitario", "Total",
        "Descuento", "Importe Neto",
        "Monto Crédito", "Monto Contado", "Anticipo Aplicado",
        "Método de pago", "Tipo de venta"
    ]
    ref = _coleccion_usuario("ventas")
    if not ref:
        return pd.DataFrame(columns=columnas)

    docs = ref.stream()
    ventas = []
    for doc in docs:
        data = doc.to_dict()
        venta_normalizada = {col: data.get(col, None) for col in columnas}
        ventas.append(venta_normalizada)

    if not ventas:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(ventas)
    for col in columnas:
        if col not in df.columns:
            df[col] = None
    numeric_cols = ["Cantidad", "Precio Unitario", "Total", "Descuento", "Importe Neto",
                    "Monto Crédito", "Monto Contado", "Anticipo Aplicado"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    return df[columnas]

def leer_transacciones():
    columnas = ["Fecha", "Descripción", "Categoría", "Tipo", "Monto", "Cliente", "Método de pago"]
    ref = _coleccion_usuario("transacciones")
    if not ref:
        return pd.DataFrame(columns=columnas)

    docs = ref.stream()
    transacciones = []
    for doc in docs:
        data = doc.to_dict()
        transaccion_normalizada = {col: data.get(col, None) for col in columnas}
        transacciones.append(transaccion_normalizada)

    if not transacciones:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(transacciones)
    for col in columnas:
        if col not in df.columns:
            df[col] = None
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').fillna(0.0)

    return df[columnas]

def leer_cobranza():
    columnas = ["Fecha", "Cliente", "Descripción", "Monto", "Método de pago"]
    ref = _coleccion_usuario("transacciones")
    if not ref:
        return pd.DataFrame(columns=columnas)

    docs = ref.where("Categoría", "==", "Cobranza").stream()
    cobranza = []
    for doc in docs:
        data = doc.to_dict()
        registro = {col: data.get(col, None) for col in columnas}
        cobranza.append(registro)

    df = pd.DataFrame(cobranza)
    if "Monto" in df.columns:
        df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').fillna(0.0)

    return df

def calcular_balance_contable():
    transacciones = leer_transacciones()
    if transacciones.empty:
        return 0, 0, 0
    transacciones['Monto'] = pd.to_numeric(transacciones['Monto'], errors='coerce').fillna(0)
    ingresos = transacciones[transacciones['Tipo'] == 'Ingreso']['Monto'].sum()
    egresos = transacciones[transacciones['Tipo'] == 'Egreso']['Monto'].sum()
    balance = ingresos - egresos
    return ingresos, egresos, balance

def leer_clientes():
    columnas = ["ID", "Nombre", "Correo", "Teléfono", "Empresa", "RFC", "Límite de crédito"]
    ref = _coleccion_usuario("clientes")
    if not ref:
        return pd.DataFrame(columns=columnas)

    docs = ref.stream()
    clientes = []
    for doc in docs:
        data = doc.to_dict()
        data["ID"] = doc.id
        cliente_normalizado = {col: data.get(col, None) for col in columnas}
        clientes.append(cliente_normalizado)

    if not clientes:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(clientes)
    for col in columnas:
        if col not in df.columns:
            df[col] = None
    if "Límite de crédito" in df.columns:
        df["Límite de crédito"] = pd.to_numeric(df["Límite de crédito"], errors='coerce').fillna(0.0)

    return df[columnas]
