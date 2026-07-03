"""
Dashboard de Análisis de SLA - Reporte Diario
"""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils import (
    cargar_excel,
    parsear_fecha,
    calcular_sla,
    obtener_todas_categorias,
)

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de SLA",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Dashboard de Análisis de SLA")
st.markdown("Carga un archivo Excel con los datos de casos para analizar el SLA.")

# --- Carga de archivo ---
archivo = st.file_uploader(
    "Selecciona el archivo Excel",
    type=["xlsx", "xls"],
    help="El archivo debe contener las columnas: Número del caso, Estado, Fecha/Hora de apertura, Asunto, Account vertical, Nombre de Cuenta, Pais, Tipo de registro del caso, Motivo de contacto - Nivel 3, Propietario del caso",
)

if archivo is not None:
    try:
        # Cargar y procesar datos
        df = cargar_excel(archivo)
        df = parsear_fecha(df)
        df = calcular_sla(df)

        # --- Métricas generales ---
        st.markdown("---")
        st.subheader("📋 Vista previa de los datos cargados")
        st.dataframe(df.head(10), width="stretch")

        total_casos = len(df)
        sla_promedio = df["SLA"].mean()
        sla_maximo = df["SLA"].max()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de casos", total_casos)
        col2.metric("SLA Promedio (días)", f"{sla_promedio:.1f}")
        col3.metric("SLA Máximo (días)", f"{sla_maximo:.1f}")

        # --- Categorías ---
        st.markdown("---")
        st.subheader("📑 Resultados por Categoría")

        categorias = obtener_todas_categorias(df)

        for nombre, resultado in categorias.items():
            cantidad = len(resultado)
            with st.expander(f"{nombre} — {cantidad} caso(s)", expanded=(cantidad > 0)):
                if cantidad > 0:
                    st.dataframe(
                        resultado.reset_index(drop=True),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No hay casos en esta categoría.")

        # --- Exportar resultados ---
        st.markdown("---")
        st.subheader("📥 Exportar Resultados")

        if st.button("Generar archivo Excel con todas las categorías"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # Hoja de resumen con todos los datos
                df.to_excel(writer, sheet_name="Datos Completos", index=False)

                # Una hoja por categoría que tenga datos
                for nombre, resultado in categorias.items():
                    if len(resultado) > 0:
                        # Limpiar nombre para hoja de Excel (máx 31 chars)
                        nombre_hoja = nombre[:31]
                        resultado.to_excel(writer, sheet_name=nombre_hoja, index=False)

            output.seek(0)
            st.download_button(
                label="⬇️ Descargar Excel",
                data=output,
                file_name="reporte_sla.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        st.info(
            "Verifica que el archivo tenga las columnas esperadas y que la columna "
            "'Fecha/Hora de apertura' esté en formato 'dd/mm/yyyy hh:mm AM/PM' "
            "(ej: 20/03/2026 03:57 PM)."
        )
else:
    st.info("👆 Carga un archivo Excel para comenzar el análisis.")