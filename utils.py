"""
Funciones auxiliares para el dashboard de SLA.
"""
import pandas as pd
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Union

TZ_COLOMBIA = ZoneInfo("America/Bogota")

DEFAULT_SLA_CONFIG = {
    "general": 10,
    "documentacion": 5,
    "firma": 6,
}

ASUNTOS_GENERAL = [
    "CDRS3A", "CDD3A", "CDRS3B", "CDD3B",
    "CDRS3C", "CDD3C", "CDRS3D", "CDD3D",
    "CDRS3E", "CDD3E", "CDRS3F", "CDD3F",
    "CDRS3G", "CDD3G",
]


def cargar_excel(file) -> pd.DataFrame:
    """Carga el archivo Excel y retorna un DataFrame."""
    df = pd.read_excel(file, dtype=str)
    return df


def parsear_fecha(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte la columna 'Fecha/Hora de apertura' a datetime.
    Formato esperado: '20/03/2026 03:57 PM'
    """
    df["Fecha/Hora de apertura"] = pd.to_datetime(
        df["Fecha/Hora de apertura"],
        format="%d/%m/%Y %I:%M %p",
        errors="coerce",
    )
    return df


def ahora_local() -> datetime:
    """Retorna la fecha/hora actual en Colombia (sin tzinfo para comparaciones)."""
    return datetime.now(TZ_COLOMBIA).replace(tzinfo=None)


def calcular_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el SLA como la diferencia en días entre la fecha actual
    y la Fecha/Hora de apertura. Días corridos (calendario).
    """
    ahora = ahora_local()
    df["SLA"] = (ahora - df["Fecha/Hora de apertura"]).dt.total_seconds() / (24 * 3600)
    df["SLA"] = df["SLA"].round(2)
    return df


def filtrar_categoria(
    df: pd.DataFrame,
    asuntos: List[str],
    sla_min: Optional[float] = None,
    incluir_asunto: bool = False,
) -> pd.DataFrame:
    """
    Filtra el DataFrame por asunto y opcionalmente por SLA mínimo.
    Retorna columnas: Número del caso, Agente, SLA y opcionalmente Asunto.
    """
    mascara = df["Asunto"].isin(asuntos)
    if sla_min is not None:
        mascara &= df["SLA"] >= sla_min

    columnas = ["Número del caso", "Propietario del caso", "SLA"]
    if incluir_asunto:
        columnas.insert(1, "Asunto")

    resultado = df.loc[mascara, columnas].copy()
    resultado = resultado.rename(columns={"Propietario del caso": "Agente"})
    resultado = resultado.sort_values("SLA", ascending=False)
    return resultado


def obtener_todas_categorias(
    df: pd.DataFrame,
    sla_config: Optional[Dict[str, int]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Aplica todos los filtros y retorna un diccionario con los resultados
    de cada categoría.
    """
    if sla_config is None:
        sla_config = DEFAULT_SLA_CONFIG.copy()

    sla_general = sla_config.get("general", DEFAULT_SLA_CONFIG["general"])
    sla_doc = sla_config.get("documentacion", DEFAULT_SLA_CONFIG["documentacion"])
    sla_firma = sla_config.get("firma", DEFAULT_SLA_CONFIG["firma"])

    categorias = {
        f"Fuera de SLA General (SLA ≥ {sla_general} días)": filtrar_categoria(
            df,
            asuntos=ASUNTOS_GENERAL,
            sla_min=sla_general,
            incluir_asunto=True,
        ),
        f"Documentación - Fuera de SLA (CDRS3A, CDD3A - SLA ≥ {sla_doc} días)": filtrar_categoria(
            df,
            asuntos=["CDRS3A", "CDD3A"],
            sla_min=sla_doc,
        ),
        f"Fuera de SLA Firma (CDRS3C, CDD3C - SLA ≥ {sla_firma} días)": filtrar_categoria(
            df,
            asuntos=["CDRS3C", "CDD3C"],
            sla_min=sla_firma,
        ),
        "Screening (CDRS3B, CDD3B)": filtrar_categoria(
            df,
            asuntos=["CDRS3B", "CDD3B"],
        ),
        "AM (CDRS3D, CDD3D)": filtrar_categoria(
            df,
            asuntos=["CDRS3D", "CDD3D"],
        ),
        "Legales (CDRS3G, CDD3G)": filtrar_categoria(
            df,
            asuntos=["CDRS3G", "CDD3G"],
        ),
        "Onb Local (CDRS3E, CDD3E)": filtrar_categoria(
            df,
            asuntos=["CDRS3E", "CDD3E"],
        ),
        "QC (CDRS3F, CDD3F)": filtrar_categoria(
            df,
            asuntos=["CDRS3F", "CDD3F"],
        ),
    }
    return categorias


def construir_info_casos(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Construye un diccionario de información por número de caso."""
    info = {}
    for _, row in df.iterrows():
        caso_id = str(row["Número del caso"])
        info[caso_id] = {
            "Agente": row.get("Propietario del caso", ""),
            "Asunto": row.get("Asunto", ""),
            "SLA": row.get("SLA", ""),
        }
    return info


def combinar_hora_hoy(hora: Any) -> Optional[datetime]:
    """Combina una hora con la fecha de hoy para programar la revisión."""
    if hora is None or pd.isna(hora):
        return None
    if isinstance(hora, str) and not hora.strip():
        return None

    hoy = ahora_local().date()

    if isinstance(hora, datetime):
        return datetime.combine(hoy, hora.time())
    if isinstance(hora, time):
        return datetime.combine(hoy, hora)

    parsed = pd.to_datetime(hora, errors="coerce")
    if pd.isna(parsed):
        return None
    return datetime.combine(hoy, parsed.time())


def extraer_hora_revision(proxima: Any) -> Optional[time]:
    """Extrae solo la hora de una revisión programada."""
    if proxima is None or pd.isna(proxima):
        return None
    if isinstance(proxima, time):
        return proxima
    if isinstance(proxima, datetime):
        return proxima.time()

    parsed = pd.to_datetime(proxima, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.time()


def preparar_tabla_con_revision(
    resultado: pd.DataFrame,
    revisiones: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    """Agrega columnas de revisión a la tabla de una categoría."""
    display = resultado.copy()
    display["Revisado"] = display["Número del caso"].apply(
        lambda x: revisiones.get(str(x), {}).get("revisado", False)
    )
    display["Revisar a las"] = display["Número del caso"].apply(
        lambda x: extraer_hora_revision(
            revisiones.get(str(x), {}).get("proxima_revision")
        )
    )
    return display


def sincronizar_revisiones(
    edited_df: pd.DataFrame,
    revisiones: Dict[str, Dict[str, Any]],
) -> None:
    """Sincroniza los cambios del data editor al estado de revisiones."""
    for _, row in edited_df.iterrows():
        caso_id = str(row["Número del caso"])
        hora = row.get("Revisar a las")

        revisiones[caso_id] = {
            "revisado": bool(row.get("Revisado", False)),
            "proxima_revision": combinar_hora_hoy(hora),
        }


def aplicar_estado_editor(
    display_df: pd.DataFrame,
    editor_state: Union[pd.DataFrame, Dict[str, Any], None],
    revisiones: Dict[str, Dict[str, Any]],
) -> None:
    """
    Aplica el estado del data editor al diccionario de revisiones.
    Compatible con DataFrame (retorno del widget) y dict (session_state).
    """
    if editor_state is None:
        return

    if isinstance(editor_state, pd.DataFrame):
        sincronizar_revisiones(editor_state, revisiones)
        return

    if not isinstance(editor_state, dict):
        return

    edited_rows = editor_state.get("edited_rows", {})
    if not edited_rows:
        return

    temp = display_df.reset_index(drop=True).copy()
    for row_idx, changes in edited_rows.items():
        idx = int(row_idx)
        if idx >= len(temp):
            continue
        for col, val in changes.items():
            if col in temp.columns:
                temp.at[idx, col] = val

    sincronizar_revisiones(temp, revisiones)


def obtener_alertas_revision(
    revisiones: Dict[str, Dict[str, Any]],
    casos_info: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Retorna casos pendientes de revisión cuya hora programada ya venció.
    """
    ahora = ahora_local()
    alertas = []

    for caso_id, rev in revisiones.items():
        if rev.get("revisado"):
            continue

        proxima = rev.get("proxima_revision")
        if proxima is None or pd.isna(proxima):
            continue

        if not isinstance(proxima, datetime):
            proxima = pd.to_datetime(proxima).to_pydatetime()

        if proxima <= ahora:
            info = casos_info.get(caso_id, {})
            alertas.append({
                "Número del caso": caso_id,
                "Agente": info.get("Agente", "—"),
                "Asunto": info.get("Asunto", "—"),
                "SLA": info.get("SLA", "—"),
                "Revisar a las": proxima,
                "Hora": proxima.strftime("%I:%M %p"),
            })

    alertas.sort(key=lambda x: x["Revisar a las"])
    return alertas


def necesita_monitoreo(revisiones: Dict[str, Dict[str, Any]]) -> bool:
    """Indica si hay casos con hora de revisión programada y no revisados."""
    for rev in revisiones.values():
        if rev.get("revisado"):
            continue
        proxima = rev.get("proxima_revision")
        if proxima is not None and not pd.isna(proxima):
            return True
    return False
