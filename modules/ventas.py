# modules/ventas.py

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import guardar_venta, leer_ventas, leer_transacciones, guardar_transaccion, leer_clientes, leer_productos



def render():
    st.title("💸 Ventas")

    # --- Definir columnas numéricas al principio para asegurar su disponibilidad ---
    numeric_cols_ventas = ["Cantidad", "Precio Unitario", "Total", "Monto Crédito", "Monto Contado",
                           "Anticipo Aplicado"]

    # Validar clientes y productos cargados en sesión
    if "clientes" not in st.session_state or st.session_state.clientes.empty:
        st.session_state.clientes = leer_clientes()
        if st.session_state.clientes.empty:
            st.warning("⚠️ No hay clientes registrados. Agrega alguno en 'Clientes'.")
            st.stop()

    if "productos" not in st.session_state or st.session_state.productos.empty:
        st.session_state.productos = leer_productos()
        if st.session_state.productos.empty:
            st.warning("⚠️ No hay productos registrados. Agrega uno en 'Productos'.")
            st.stop()

    # Cargar ventas y transacciones si no están o recargarlas para asegurar tipos de datos
    if "ventas" not in st.session_state:
        st.session_state.ventas = leer_ventas()
        for col in numeric_cols_ventas:
            if col in st.session_state.ventas.columns:
                st.session_state.ventas[col] = pd.to_numeric(st.session_state.ventas[col], errors='coerce').fillna(0.0)
    else:
        # Refrescar ventas cada vez que se renderiza para tener los últimos datos
        st.session_state.ventas = leer_ventas()
        for col in numeric_cols_ventas:
            if col in st.session_state.ventas.columns:
                st.session_state.ventas[col] = pd.to_numeric(st.session_state.ventas[col], errors='coerce').fillna(0.0)

    # Cargar transacciones_data al inicio para el cálculo de anticipos y crédito
    if "transacciones_data" not in st.session_state:
        st.session_state.transacciones_data = leer_transacciones()
        if "Monto" in st.session_state.transacciones_data.columns:
            st.session_state.transacciones_data["Monto"] = pd.to_numeric(st.session_state.transacciones_data["Monto"],
                                                                         errors='coerce').fillna(0.0)
    else:
        # Refrescar transacciones_data cada vez que se renderiza para tener los últimos anticipos/movimientos
        st.session_state.transacciones_data = leer_transacciones()
        if "Monto" in st.session_state.transacciones_data.columns:
            st.session_state.transacciones_data["Monto"] = pd.to_numeric(st.session_state.transacciones_data["Monto"],
                                                                         errors='coerce').fillna(0.0)

    st.subheader("Registrar nueva venta")

    # --- CAMPOS QUE DEBEN ACTUALIZARSE AL CAMBIAR SU VALOR (FUERA DEL FORM) ---
    fecha = st.date_input("Fecha", key="venta_fecha")
    cliente = st.selectbox("Cliente", st.session_state.clientes["Nombre"].tolist(), key="venta_cliente")

    # --- CAMBIOS AQUÍ para mostrar la existencia ---
    producto = st.selectbox("Producto/Servicio", st.session_state.productos["Nombre"].tolist(), key="venta_producto")

    existencia_actual = 0
    if producto and not st.session_state.productos.empty:
        producto_info = st.session_state.productos[st.session_state.productos["Nombre"] == producto]
        if not producto_info.empty and "Cantidad" in producto_info.columns:
            existencia_actual = int(producto_info["Cantidad"].values[0])
        st.info(f"📦 Existencia actual: **{existencia_actual}** unidades.")
    # --- FIN CAMBIOS para mostrar la existencia ---

    cantidad = st.number_input("Cantidad", min_value=1, key="venta_cantidad")

    # Validar que la cantidad no exceda la existencia
    if cantidad > existencia_actual and existencia_actual >= 0:  # Solo si hay existencia definida
        st.warning(f"⚠️ La cantidad solicitada ({cantidad}) excede la existencia actual ({existencia_actual}).")
        # Opcional: Deshabilitar el botón de submit o ajustar la cantidad automáticamente
        # st.session_state.venta_cantidad = existencia_actual # Esto podría forzar la cantidad

    # Calcular precio y total EN TIEMPO REAL
    precio = 0.0
    if producto and not st.session_state.productos.empty and producto in st.session_state.productos["Nombre"].tolist():
        precio_from_df = st.session_state.productos.loc[
            st.session_state.productos["Nombre"] == producto, "Precio Unitario"
        ].values[0]
        precio = float(precio_from_df) if pd.notna(precio_from_df) else 0.0
    total = cantidad * precio

    st.markdown(f"**Precio unitario:** ${precio:.2f}")
    st.markdown(f"**Total de la venta:** ${total:.2f}")

    # --- Lógica y UI para Anticipos Disponibles (VISIBLES) ---
    anticipos_cliente_total = st.session_state.transacciones_data[
        (st.session_state.transacciones_data["Categoría"] == "Anticipo Cliente") &
        (st.session_state.transacciones_data["Cliente"] == cliente) &
        (st.session_state.transacciones_data["Tipo"] == "Ingreso")
        ]["Monto"].sum()

    anticipos_aplicados_total = st.session_state.transacciones_data[
        (st.session_state.transacciones_data["Categoría"] == "Anticipo Aplicado") &
        (st.session_state.transacciones_data["Cliente"] == cliente) &
        (st.session_state.transacciones_data["Tipo"] == "Gasto")  # Asegúrate que esto sea consistente con tu db.py
        ]["Monto"].sum()

    saldo_anticipos = float(anticipos_cliente_total) - float(anticipos_aplicados_total)

    aplicar_anticipo = 0.0  # Inicializar a 0.0
    if saldo_anticipos > 0:
        st.subheader("Gestión de Anticipos")
        st.info(f"✨ **Anticipo disponible para {cliente}:** ${saldo_anticipos:.2f}")

        # Permitir al usuario decidir cuánto anticipo aplicar
        # El valor máximo es el mínimo entre el saldo disponible y el total de la venta
        aplicar_anticipo = st.number_input(
            f"¿Cuánto anticipo desea aplicar a esta venta?",
            min_value=0.0,
            max_value=min(saldo_anticipos, total),
            value=0.0,  # Valor inicial en 0, para que el usuario decida
            step=0.01,
            key="input_anticipo_visible"
        )
        st.session_state["anticipo_seleccionado_para_venta"] = aplicar_anticipo  # Guardar en session_state

    # --- FIN Lógica y UI para Anticipos Disponibles ---

    # Calcular el total ajustado después de aplicar el anticipo
    total_ajustado = total - aplicar_anticipo
    st.markdown(f"**Total de la venta (ajustado por anticipo):** ${total_ajustado:.2f}")

    # --- INICIO DEL FORMULARIO PRINCIPAL DE VENTA ---
    with st.form("form_ventas"):
        cliente_info = st.session_state.clientes[st.session_state.clientes["Nombre"] == cliente].iloc[0]
        limite_credito_raw = cliente_info.get("Límite de crédito", 0.0)
        try:
            limite_credito = float(limite_credito_raw) if pd.notna(limite_credito_raw) else 0.0
        except Exception:
            st.warning("⚠️ El límite de crédito del cliente no es válido. Se asignará 0.")
            limite_credito = 0.0

        # Recargar ventas y transacciones dentro del form_submit_button
        # para asegurar la consistencia en el momento de la validación final
        # y antes de guardar. Esto ya lo tenías.
        # st.session_state.ventas = leer_ventas() # Esto se hace justo antes de la validación
        # st.session_state.transacciones_data = leer_transacciones() # Esto se hace justo antes de la validación

        # Filtrar pagos de cobranza para el cliente (para crédito)
        pagos = st.session_state.transacciones_data[  # Usar session_state.transacciones_data
            (st.session_state.transacciones_data["Categoría"] == "Cobranza") & (
                    st.session_state.transacciones_data["Cliente"] == cliente)
            ]
        pagos_realizados = pagos["Monto"].sum() if not pagos.empty else 0.0
        pagos_realizados = float(pagos_realizados)

        ventas_cliente = st.session_state.ventas[st.session_state.ventas["Cliente"] == cliente]

        total_credito_otorgado = 0.0
        if "Tipo de venta" in ventas_cliente.columns and "Monto Crédito" in ventas_cliente.columns:
            credito_otorgado_series = ventas_cliente[
                ventas_cliente["Tipo de venta"].isin(["Crédito", "Mixta"])
            ]["Monto Crédito"]
            total_credito_otorgado = float(credito_otorgado_series.sum()) if not credito_otorgado_series.empty else 0.0

        credito_usado = float(total_credito_otorgado) - float(pagos_realizados)
        credito_disponible = float(limite_credito) - float(credito_usado)

        st.markdown(f"💳 **Crédito autorizado:** ${limite_credito:.2f}")
        st.markdown(f"🔸 **Crédito usado:** ${credito_usado:.2f}")
        st.markdown(f"🟢 **Disponible para crédito:** ${credito_disponible:.2f}")

        # Monto contado y método de pago
        # El max_value debe ser el total ajustado, no el total original
        monto_contado = st.number_input("💵 Monto pagado al contado", min_value=0.0, max_value=float(total_ajustado),
                                        step=0.01, key="venta_monto_contado_final")
        metodo_pago = st.selectbox("Método de pago (contado)", ["Efectivo", "Transferencia", "Tarjeta"],
                                   key="venta_metodo_pago_final")

        monto_credito = total_ajustado - monto_contado
        st.markdown(f"**🧾 Crédito solicitado:** ${monto_credito:.2f}")

        submitted = st.form_submit_button("Registrar venta")

        if submitted:
            # Recargar productos y transacciones para la validación final y guardar
            st.session_state.productos = leer_productos()  # ¡Importante para la existencia actual!
            st.session_state.transacciones_data = leer_transacciones()  # ¡Importante para anticipos y crédito!

            # Obtener la existencia actual actualizada
            current_producto_info = st.session_state.productos[st.session_state.productos["Nombre"] == producto]
            current_existencia = int(current_producto_info["Cantidad"].values[
                                         0]) if not current_producto_info.empty and "Cantidad" in current_producto_info.columns else 0

            # Asegurarse de usar el anticipo que el usuario seleccionó en el number_input visible
            anticipo_final_aplicado = st.session_state.get("anticipo_seleccionado_para_venta", 0.0)

            # Recalcular el total ajustado con el anticipo final decidido por el usuario
            total_ajustado_f = float(total - anticipo_final_aplicado)

            monto_contado_f = float(monto_contado)  # Usar el monto de contado del formulario
            monto_credito_f = float(monto_credito)  # Usar el monto de crédito calculado en el formulario

            # Recalcular crédito disponible con los datos más frescos
            # Es vital recalcular esto AQUI antes de la validación
            current_cliente_info = st.session_state.clientes[st.session_state.clientes["Nombre"] == cliente].iloc[0]
            current_limite_credito = float(current_cliente_info.get("Límite de crédito", 0.0))

            current_pagos = st.session_state.transacciones_data[
                (st.session_state.transacciones_data["Categoría"] == "Cobranza") & (
                        st.session_state.transacciones_data["Cliente"] == cliente)
                ]
            current_pagos_realizados = current_pagos["Monto"].sum() if not current_pagos.empty else 0.0

            current_ventas_cliente = st.session_state.ventas[st.session_state.ventas["Cliente"] == cliente]
            current_total_credito_otorgado = 0.0
            if "Tipo de venta" in current_ventas_cliente.columns and "Monto Crédito" in current_ventas_cliente.columns:
                current_credito_otorgado_series = current_ventas_cliente[
                    current_ventas_cliente["Tipo de venta"].isin(["Crédito", "Mixta"])
                ]["Monto Crédito"]
                current_total_credito_otorgado = float(
                    current_credito_otorgado_series.sum()) if not current_credito_otorgado_series.empty else 0.0

            current_credito_usado = float(current_total_credito_otorgado) - float(current_pagos_realizados)
            current_credito_disponible = float(current_limite_credito) - float(current_credito_usado)

            suma_componentes = monto_contado_f + monto_credito_f + anticipo_final_aplicado

            # Definir una pequeña tolerancia para la comparación de punto flotante
            epsilon = 0.01  # Tolerancia de un centavo

            # Validaciones finales
            if cantidad > current_existencia:  # Validar existencia nuevamente al momento de guardar
                st.error(f"❌ No hay suficiente existencia de {producto}. Solo quedan {current_existencia} unidades.")
            elif abs(round(suma_componentes, 2) - round(total, 2)) > epsilon:
                st.error(
                    "❌ El total ingresado (contado + crédito + anticipo) no coincide con el total de la venta original. "
                    f"Desfase: {abs(round(suma_componentes, 2) - round(total, 2)):.4f}"
                )
            elif monto_credito_f > current_credito_disponible + epsilon:  # Añadir epsilon aquí también para seguridad
                st.error(
                    f"❌ El crédito solicitado (${monto_credito_f:.2f}) excede el disponible (${current_credito_disponible:.2f}).")
            else:
                # Determinar Tipo de Venta correctamente
                tipo_venta = ""
                if monto_credito_f > 0 and (monto_contado_f > 0 or anticipo_final_aplicado > 0):
                    tipo_venta = "Mixta"
                elif monto_credito_f > 0 and monto_contado_f == 0 and anticipo_final_aplicado == 0:
                    tipo_venta = "Crédito"
                elif monto_credito_f == 0 and (monto_contado_f > 0 or anticipo_final_aplicado > 0):
                    tipo_venta = "Contado"  # Puede ser 'Contado' si solo es anticipo, o solo efectivo
                elif monto_credito_f == 0 and monto_contado_f == 0 and anticipo_final_aplicado == 0 and total == 0:
                    tipo_venta = "Gratuita"
                else:
                    tipo_venta = "Indefinido"  # Fallback si no encaja

                venta_dict = {
                    "Fecha": fecha.isoformat(),
                    "Cliente": cliente,
                    "Producto": producto,
                    "Cantidad": float(cantidad),
                    "Precio Unitario": float(precio),
                    "Total": total,  # Guardar el total original de la venta
                    "Monto Crédito": monto_credito_f,
                    "Monto Contado": monto_contado_f,
                    "Anticipo Aplicado": anticipo_final_aplicado,  # Usar el valor decidido por el usuario
                    "Método de pago": metodo_pago if monto_contado_f > 0 else (
                        "Crédito" if monto_credito_f > 0 else (
                            "Anticipo" if anticipo_final_aplicado > 0 else "N/A"
                        )
                    ),
                    "Tipo de venta": tipo_venta
                }
                guardar_venta(venta_dict)

                if monto_contado_f > 0:
                    guardar_transaccion({
                        "Fecha": fecha.isoformat(),
                        "Descripción": f"Pago de contado por venta a {cliente}",
                        "Categoría": "Ventas",
                        "Tipo": "Ingreso",
                        "Monto": monto_contado_f,
                        "Cliente": cliente,
                        "Método de pago": metodo_pago
                    })

                if anticipo_final_aplicado > 0:
                    guardar_transaccion({
                        "Fecha": fecha.isoformat(),
                        "Descripción": f"Anticipo aplicado a venta de {cliente}",
                        "Categoría": "Anticipo Aplicado",
                        "Tipo": "Gasto",  # Desde la perspectiva del anticipo, es una reducción
                        "Monto": float(anticipo_final_aplicado),
                        "Cliente": cliente,
                        "Método de pago": "Anticipo"  # Método de pago específico
                    })

                # --- DESCONTAR CANTIDAD DEL INVENTARIO ---
                from utils.db import actualizar_producto_por_clave  # Importar aquí si no está global
                producto_clave = \
                st.session_state.productos.loc[st.session_state.productos["Nombre"] == producto, "Clave"].iloc[0]
                nueva_cantidad_inventario = current_existencia - cantidad
                actualizar_producto_por_clave(producto_clave, {"Cantidad": nueva_cantidad_inventario})
                # --- FIN DESCUENTO INVENTARIO ---

                nueva = pd.DataFrame([venta_dict])
                st.session_state.ventas = pd.concat([st.session_state.ventas, nueva], ignore_index=True)

                for col in numeric_cols_ventas:
                    if col in st.session_state.ventas.columns:
                        st.session_state.ventas[col] = pd.to_numeric(st.session_state.ventas[col],
                                                                     errors='coerce').fillna(0.0)

                st.success("✅ Venta registrada correctamente")
                # Recargar transacciones_data y productos para que el saldo de anticipos y existencia se actualicen en UI
                st.session_state.transacciones_data = leer_transacciones()
                st.session_state.productos = leer_productos()  # ¡Actualizar productos también!
                st.rerun()  # Volver a renderizar para limpiar el formulario y mostrar la venta reciente

    st.divider()
    st.subheader("📋 Histórico de ventas")
    st.dataframe(st.session_state.ventas, use_container_width=True)

    if not st.session_state.ventas.empty:
        st.subheader("📊 Ingresos diarios")
        df_daily = st.session_state.ventas.copy()
        df_daily["Total"] = pd.to_numeric(df_daily["Total"], errors='coerce').fillna(0.0)
        df_daily = df_daily.groupby("Fecha")["Total"].sum().reset_index()
        fig = px.bar(df_daily, x="Fecha", y="Total", title="Ventas por día", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)