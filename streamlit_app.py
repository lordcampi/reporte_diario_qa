"""
Dashboard de Análisis de SLA - Reporte Diario
"""
import json
from datetime import timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from utils import (
    DEFAULT_SLA_CONFIG,
    ahora_local,
    cargar_excel,
    parsear_fecha,
    calcular_sla,
    obtener_todas_categorias,
    construir_info_casos,
    preparar_tabla_con_revision,
    sincronizar_revisiones,
    aplicar_estado_editor,
    obtener_alertas_revision,
    necesita_monitoreo,
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
    .notif-btn {
        width: 100%;
        padding: 0.6rem 1rem;
        background: #4F46E5;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        font-size: 0.9rem;
    }
    .notif-btn:hover { background: #4338CA; }
    .notif-status {
        display: block;
        margin-top: 0.5rem;
        font-size: 0.85rem;
        color: #94A3B8;
    }
    .notif-ok { color: #4ADE80 !important; }
    .notif-warn { color: #FBBF24 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Estado de sesión ---
if "sla_config" not in st.session_state:
    st.session_state.sla_config = DEFAULT_SLA_CONFIG.copy()

if "revisiones" not in st.session_state:
    st.session_state.revisiones = {}

if "alertas_vistas" not in st.session_state:
    st.session_state.alertas_vistas = set()


def sincronizar_todos_editores(
    categorias: dict,
    revisiones: dict,
) -> None:
    """Lee el estado de cada data editor y actualiza revisiones."""
    for nombre, resultado in categorias.items():
        if len(resultado) == 0:
            continue
        display = preparar_tabla_con_revision(resultado, revisiones)
        editor_key = f"editor_{nombre}"
        if editor_key in st.session_state:
            aplicar_estado_editor(
                display,
                st.session_state[editor_key],
                revisiones,
            )


def render_banner_alertas(alertas: list) -> None:
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


def render_activador_notificaciones() -> None:
    """Botón HTML para solicitar permiso de notificaciones (requiere clic del usuario)."""
    components.html(
        """
        <div>
            <button class="notif-btn" id="btn-notif">
                Activar notificaciones de escritorio
            </button>
            <span class="notif-status" id="notif-status"></span>
        </div>
        <script>
        const status = document.getElementById("notif-status");

        function actualizarEstado() {
            if (!("Notification" in window)) {
                status.textContent = "Tu navegador no soporta notificaciones.";
                status.className = "notif-status notif-warn";
                return;
            }
            if (Notification.permission === "granted") {
                status.textContent = "✓ Notificaciones activadas";
                status.className = "notif-status notif-ok";
                document.getElementById("btn-notif").textContent = "Notificaciones activadas";
            } else if (Notification.permission === "denied") {
                status.textContent = "Bloqueadas. Habilítalas en la configuración del navegador.";
                status.className = "notif-status notif-warn";
            } else {
                status.textContent = "Pendiente — haz clic para activar";
                status.className = "notif-status";
            }
        }

        document.getElementById("btn-notif").addEventListener("click", function () {
            if (!("Notification" in window)) return;
            Notification.requestPermission().then(function () {
                actualizarEstado();
            });
        });

        actualizarEstado();
        </script>
        """,
        height=90,
    )


def enviar_notificaciones_escritorio(alertas: list) -> None:
    """Envía una notificación de escritorio por cada caso nuevo."""
    payload = json.dumps([
        {
            "id": str(a["Número del caso"]),
            "agente": str(a["Agente"]),
            "asunto": str(a["Asunto"]),
            "sla": (
                f"{a['SLA']:.1f}"
                if isinstance(a["SLA"], (int, float))
                else str(a["SLA"])
            ),
            "hora": str(a["Hora"]),
        }
        for a in alertas
    ])

    components.html(
        f"""
        <script>
        (function () {{
            const alertas = {payload};
            if (!("Notification" in window) || Notification.permission !== "granted") {{
                return;
            }}

            alertas.forEach(function (a) {{
                const notif = new Notification("Revisar caso " + a.id, {{
                    body: a.agente + " · " + a.asunto + " · SLA " + a.sla + " días · desde las " + a.hora,
                    icon: "https://static.streamlit.io/favicon.ico",
                    requireInteraction: true,
                    tag: "sla-revision-" + a.id,
                    silent: false,
                }});
                notif.onclick = function () {{
                    window.focus();
                    notif.close();
                }};
            }});

            try {{
                const ctx = new AudioContext();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = 880;
                gain.gain.value = 0.15;
                osc.start();
                osc.stop(ctx.currentTime + 0.25);
            }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
    )


def notificar_alertas_nuevas(alertas: list) -> None:
    """Muestra toast y notificación del navegador para alertas nuevas."""
    ids_actuales = {a["Número del caso"] for a in alertas}
    nuevas = [a for a in alertas if a["Número del caso"] not in st.session_state.alertas_vistas]

    for alerta in nuevas:
        st.toast(
            f"Revisar caso {alerta['Número del caso']} — {alerta['Agente']}",
            icon="⚠️",
        )

    if nuevas:
        enviar_notificaciones_escritorio(nuevas)

    st.session_state.alertas_vistas = ids_actuales


@st.fragment(run_every=timedelta(seconds=15))
def monitoreo_alertas() -> None:
    """Verifica alertas automáticamente cada 15 segundos."""
    categorias = st.session_state.get("categorias_cache")
    casos_info = st.session_state.get("casos_info_cache")
    if not categorias or not casos_info:
        return

    revisiones = st.session_state.revisiones
    sincronizar_todos_editores(categorias, revisiones)
    alertas = obtener_alertas_revision(revisiones, casos_info)

    if alertas:
        render_banner_alertas(alertas)
        notificar_alertas_nuevas(alertas)
    elif necesita_monitoreo(revisiones):
        hora_actual = ahora_local().strftime("%I:%M %p")
        st.caption(
            f"Monitoreo activo — hora actual: {hora_actual} (Colombia). "
            "Verificando cada 15 s. Puedes minimizar la ventana."
        )


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

    if st.button("Restaurar valores por defecto", width="stretch"):
        st.session_state.sla_config = DEFAULT_SLA_CONFIG.copy()
        st.rerun()

    st.divider()
    st.subheader("Notificaciones")
    render_activador_notificaciones()
    st.caption(
        "Activa las notificaciones y deja esta pestaña abierta (puede estar minimizada). "
        "Cuando llegue la hora programada, recibirás un aviso en el escritorio."
    )

    st.divider()
    st.markdown(f"Hora actual (Colombia): **{ahora_local().strftime('%I:%M %p')}**")

# --- Contenido principal ---
if archivo is not None:
    try:
        df = cargar_excel(archivo)
        df = parsear_fecha(df)
        df = calcular_sla(df)

        casos_info = construir_info_casos(df)
        categorias = obtener_todas_categorias(df, st.session_state.sla_config)

        st.session_state.categorias_cache = categorias
        st.session_state.casos_info_cache = casos_info

        sincronizar_todos_editores(categorias, st.session_state.revisiones)

        monitoreo_alertas()

        if necesita_monitoreo(st.session_state.revisiones):
            alertas_pendientes = obtener_alertas_revision(
                st.session_state.revisiones, casos_info
            )
            if not alertas_pendientes:
                hora_actual = ahora_local().strftime("%I:%M %p")
                st.info(
                    f"Monitoreo activo. Hora actual: {hora_actual} (Colombia). "
                    "Activa las notificaciones en el panel lateral y minimiza la ventana. "
                    "La alerta llegará al escritorio cuando sea la hora programada."
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
