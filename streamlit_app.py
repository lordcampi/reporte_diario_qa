"""
Dashboard de Análisis de SLA - Reporte Diario
"""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils import (
    DEFAULT_SLA_CONFIG,
    cargar_excel,
    parsear_fecha,
    calcular_sla,
    obtener_todas_categorias,
    construir_info_casos,
    preparar_tabla_con_revision,
    sincronizar_revisiones,
    aplicar_estado_editor,
    obtener_alertas_revision,
)

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de SLA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Estilos ---
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    .sub-header {
        color: #94A3B8;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-label {
        color: #94A3B8;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        color: #F8FAFC;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1;
    }
    .alert-banner {
        background: linear-gradient(135deg, #7C2D12 0%, #991B1B 100%);
        border: 1px solid #DC2626;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(220, 38, 38, 0.25);
    }
    .alert-title {
        color: #FEF2F2;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }
    .alert-item {
        color: #FECACA;
        font-size: 0.9rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(254, 202, 202, 0.15);
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #F1F5F9;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #4F46E5;
        display: inline-block;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: #F8FAFC;
    }
    .stExpander {
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        background: #1E293B !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Estado de sesión ---
if "sla_config" not in st.session_state:
    st.session_state.sla_config = DEFAULT_SLA_CONFIG.copy()

if "revisiones" not in st.session_state:
    st.session_state.revisiones = {}


def render_metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_column_config(columns: list) -> dict:
    config = {
        "Número del caso": st.column_config.TextColumn("Caso", disabled=True, width="medium"),
        "Agente": st.column_config.TextColumn("Agente", disabled=True, width="medium"),
        "SLA": st.column_config.NumberColumn("SLA (días)", format="%.1f", disabled=True, width="small"),
        "Revisado": st.column_config.CheckboxColumn("Revisado", default=False, width="small"),
        "Revisar a las": st.column_config.TimeColumn(
            "Revisar a las",
            format="h:mm a",
            step=60,
            width="medium",
        ),
    }
    if "Asunto" in columns:
        config["Asunto"] = st.column_config.TextColumn("Asunto", disabled=True, width="small")
    return config


# --- Header ---
st.markdown('<p class="main-header">Dashboard de Análisis de SLA</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Monitorea casos fuera de SLA, gestiona revisiones y exporta reportes.</p>',
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.header("Configuración")

    archivo = st.file_uploader(
        "Archivo Excel",
        type=["xlsx", "xls"],
        help=(
            "Columnas requeridas: Número del caso, Estado, Fecha/Hora de apertura, "
            "Asunto, Account vertical, Nombre de Cuenta, Pais, Tipo de registro del caso, "
            "Motivo de contacto - Nivel 3, Propietario del caso"
        ),
    )

    st.divider()
    st.subheader("Umbrales SLA")

    sla_general = st.number_input(
        "Fuera de SLA General (días)",
        min_value=0,
        step=1,
        value=st.session_state.sla_config["general"],
    )
    sla_documentacion = st.number_input(
        "Documentación (días)",
        min_value=0,
        step=1,
        value=st.session_state.sla_config["documentacion"],
    )
    sla_firma = st.number_input(
        "Fuera de SLA Firma (días)",
        min_value=0,
        step=1,
        value=st.session_state.sla_config["firma"],
    )

    st.session_state.sla_config = {
        "general": sla_general,
        "documentacion": sla_documentacion,
        "firma": sla_firma,
    }

    if st.button("Restaurar valores por defecto", use_container_width=True):
        st.session_state.sla_config = DEFAULT_SLA_CONFIG.copy()
        st.rerun()

# --- Contenido principal ---
if archivo is not None:
    try:
        df = cargar_excel(archivo)
        df = parsear_fecha(df)
        df = calcular_sla(df)

        casos_info = construir_info_casos(df)
        categorias = obtener_todas_categorias(df, st.session_state.sla_config)

        # Sincronizar revisiones previas antes de calcular alertas
        for nombre, resultado in categorias.items():
            if len(resultado) == 0:
                continue
            display = preparar_tabla_con_revision(resultado, st.session_state.revisiones)
            editor_key = f"editor_{nombre}"
            if editor_key in st.session_state:
                aplicar_estado_editor(
                    display,
                    st.session_state[editor_key],
                    st.session_state.revisiones,
                )

        alertas = obtener_alertas_revision(st.session_state.revisiones, casos_info)

        if alertas:
            items_html = ""
            for alerta in alertas:
                sla_val = alerta["SLA"]
                sla_str = f"{sla_val:.1f}" if isinstance(sla_val, (int, float)) else str(sla_val)
                items_html += (
                    f'<div class="alert-item">'
                    f'<strong>{alerta["Número del caso"]}</strong> · '
                    f'{alerta["Agente"]} · {alerta["Asunto"]} · '
                    f'SLA {sla_str} días · Revisar desde las {alerta["Hora"]}'
                    f'</div>'
                )
            st.markdown(
                f"""
                <div class="alert-banner">
                    <div class="alert-title">⚠ Casos pendientes de revisión ({len(alertas)})</div>
                    {items_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # --- Métricas generales ---
        total_casos = len(df)
        sla_promedio = df["SLA"].mean()
        sla_maximo = df["SLA"].max()

        col1, col2, col3 = st.columns(3)
        with col1:
            render_metric_card("Total de casos", str(total_casos))
        with col2:
            render_metric_card("SLA Promedio", f"{sla_promedio:.1f} días")
        with col3:
            render_metric_card("SLA Máximo", f"{sla_maximo:.1f} días")

        # --- Categorías ---
        st.markdown('<p class="section-title">Resultados por Categoría</p>', unsafe_allow_html=True)

        for nombre, resultado in categorias.items():
            cantidad = len(resultado)
            with st.expander(f"{nombre} — {cantidad} caso(s)", expanded=(cantidad > 0)):
                if cantidad > 0:
                    display = preparar_tabla_con_revision(resultado, st.session_state.revisiones)
                    edited = st.data_editor(
                        display.reset_index(drop=True),
                        column_config=build_column_config(display.columns.tolist()),
                        hide_index=True,
                        width="stretch",
                        height=min(400, 50 + cantidad * 38),
                        key=f"editor_{nombre}",
                    )
                    sincronizar_revisiones(edited, st.session_state.revisiones)
                else:
                    st.info("No hay casos en esta categoría.")

        # --- Exportar resultados ---
        st.markdown('<p class="section-title">Exportar Resultados</p>', unsafe_allow_html=True)

        if st.button("Generar archivo Excel con todas las categorías", type="primary"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Datos Completos", index=False)

                for nombre, resultado in categorias.items():
                    if len(resultado) > 0:
                        export_df = preparar_tabla_con_revision(
                            resultado, st.session_state.revisiones
                        )
                        nombre_hoja = nombre[:31]
                        export_df.to_excel(writer, sheet_name=nombre_hoja, index=False)

            output.seek(0)
            st.download_button(
                label="Descargar Excel",
                data=output,
                file_name="reporte_sla.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        st.info(
            "Verifica que el archivo tenga las columnas esperadas y que la columna "
            "'Fecha/Hora de apertura' esté en formato 'dd/mm/yyyy hh:mm AM/PM' "
            "(ej: 20/03/2026 03:57 PM)."
        )
else:
    st.info("Carga un archivo Excel desde el panel lateral para comenzar el análisis.")
