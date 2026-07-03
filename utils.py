"""
Funciones auxiliares para el dashboard de SLA.
"""
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict


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


def calcular_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el SLA como la diferencia en días entre la fecha actual
    y la Fecha/Hora de apertura. Días corridos (calendario).
    """
    ahora = datetime.now()
    df["SLA"] = (ahora - df["Fecha/Hora de apertura"]).dt.total_seconds() / (24 * 3600)
    df["SLA"] = df["SLA"].round(2)
    return df


def filtrar_categoria(
    df: pd.DataFrame, asuntos: List[str], sla_min: float = None
) -> pd.DataFrame:
    """
    Filtra el DataFrame por asunto y opcionalmente por SLA mínimo.
    Retorna columnas: Número del caso, Propietario del caso (Agente), SLA
    """
    mascara = df["Asunto"].isin(asuntos)
    if sla_min is not None:
        mascara &= df["SLA"] >= sla_min

    resultado = df.loc[mascara, ["Número del caso", "Propietario del caso", "SLA"]].copy()
    resultado = resultado.rename(columns={"Propietario del caso": "Agente"})
    resultado = resultado.sort_values("SLA", ascending=False)
    return resultado


def obtener_todas_categorias(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Aplica todos los filtros y retorna un diccionario con los resultados
    de cada categoría.
    """
    categorias = {
        "Fuera de SLA General (SLA ≥ 10 días)": filtrar_categoria(
            df,
            asuntos=[
                "CDRS3A", "CDD3A", "CDRS3B", "CDD3B",
                "CDRS3C", "CDD3C", "CDRS3D", "CDD3D",
                "CDRS3E", "CDD3E", "CDRS3F", "CDD3F",
                "CDRS3G", "CDD3G",
            ],
            sla_min=10,
        ),
        "Documentación - Fuera de SLA (CDRS3A, CDD3A - SLA ≥ 5 días)": filtrar_categoria(
            df,
            asuntos=["CDRS3A", "CDD3A"],
            sla_min=5,
        ),
        "Fuera de SLA Firma (CDRS3C, CDD3C - SLA ≥ 6 días)": filtrar_categoria(
            df,
            asuntos=["CDRS3C", "CDD3C"],
            sla_min=6,
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