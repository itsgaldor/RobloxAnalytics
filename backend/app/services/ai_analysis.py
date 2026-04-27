"""
Servicio de analisis con IA para reportes de Peru City Analytics.
Usa la Anthropic API si ANTHROPIC_API_KEY esta configurada.
En caso contrario genera un analisis simulado con estructura real.
"""
from app.config import settings


async def generate_analysis(data: dict, language: str) -> str:
    """
    Genera analisis narrativo de las metricas.
    Si ANTHROPIC_API_KEY esta configurada, usa Claude API.
    Si no, devuelve texto simulado para desarrollo.
    """
    prompt = build_analysis_prompt(data, language)

    if settings.anthropic_api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    return generate_mock_analysis(data, language)


def generate_mock_analysis(data: dict, language: str) -> str:
    """
    Analisis simulado con estructura real pero datos placeholder.
    Imita el formato que devolveria Claude para que el PDF se vea completo.
    """
    brand = data["brand_name"]
    period = data["period_label"]
    sessions = data["metrics"]["sessions"]
    dau = data["metrics"]["dau"]
    delta_sessions = data["deltas"]["sessions"]
    peak_day = data["peak_day"]

    if language == "es":
        tendencia = "tendencia positiva" if delta_sessions >= 0 else "tendencia a la baja"
        supera = "superan" if delta_sessions >= 0 else "se ubican por debajo de"
        crecio = "crecio" if delta_sessions >= 0 else "disminuyo"
        retencion = (
            "una mayor retencion y recurrencia de los jugadores"
            if delta_sessions >= 0
            else "una oportunidad de mejora en la retencion de jugadores"
        )
        return f"""**Resumen ejecutivo**

Durante {period}, {brand} registro {sessions:,} sesiones con un promedio diario de {round(dau):,} usuarios activos. El periodo muestra una {tendencia} en comparacion con el periodo anterior, con una variacion de {delta_sessions:+.1f}% en sesiones totales.

**Performance vs periodo anterior**

Las metricas del periodo analizado {supera} las del periodo previo en la mayoria de los indicadores seleccionados. El DAU promedio {crecio} un {abs(delta_sessions):.1f}%, lo que indica {retencion}.

**Tendencias identificadas**

El analisis de la serie temporal muestra que los fines de semana concentran la mayor actividad, con picos consistentes los sabados y domingos. El dia de mayor actividad fue {peak_day}, lo que sugiere que las iniciativas de comunicacion o eventos especiales en esa fecha tuvieron impacto positivo en el engagement.

La distribucion entre servidores publicos y privados refleja el patron tipico de experiencias de marca, donde los servidores privados se utilizan principalmente para eventos corporativos y activaciones controladas.

**Recomendaciones**

1. Concentrar las acciones de activacion los jueves y viernes para capitalizar el pico de trafico del fin de semana y maximizar el alcance organico.

2. Evaluar la implementacion de eventos especiales en los dias de menor actividad para nivelar la curva de sesiones y mantener el engagement durante los dias habiles.

3. Monitorear la proporcion publico/privado: un incremento en servidores privados puede indicar mayor interes de marcas aliadas en activaciones exclusivas."""
    else:
        trend = "positive trend" if delta_sessions >= 0 else "downward trend"
        exceed = "exceed" if delta_sessions >= 0 else "fall below"
        grew = "grew" if delta_sessions >= 0 else "decreased"
        retention = (
            "stronger player retention and recurrence"
            if delta_sessions >= 0
            else "an opportunity to improve player retention"
        )
        return f"""**Executive Summary**

During {period}, {brand} recorded {sessions:,} sessions with a daily average of {round(dau):,} active users. The period shows a {trend} compared to the previous period, with a {delta_sessions:+.1f}% variation in total sessions.

**Performance vs Previous Period**

The metrics for the analyzed period {exceed} those of the previous period across most selected indicators. Average DAU {grew} by {abs(delta_sessions):.1f}%, indicating {retention}.

**Identified Trends**

The time series analysis shows that weekends concentrate the highest activity, with consistent peaks on Saturdays and Sundays. The highest activity day was {peak_day}, suggesting that communication initiatives or special events on that date had a positive impact on engagement.

**Recommendations**

1. Focus activation actions on Thursdays and Fridays to capitalize on weekend traffic peaks and maximize organic reach.

2. Consider implementing special events on lower-activity days to level the session curve and maintain engagement during weekdays.

3. Monitor the public/private ratio: an increase in private servers may indicate growing interest from partner brands in exclusive activations."""


def build_analysis_prompt(data: dict, language: str) -> str:
    """Construye el prompt para Claude con todos los datos del periodo."""
    lang_instruction = "en espanol" if language == "es" else "in English"
    m = data["metrics"]
    d = data["deltas"]
    return f"""Eres un analista experto en metricas de experiencias en Roblox.
Analiza los siguientes datos y genera un reporte ejecutivo profesional {lang_instruction}.

MARCA: {data['brand_name']}
PERIODO: {data['period_label']}
PERIODO ANTERIOR: {data['prev_period_label']}

METRICAS DEL PERIODO:
- Sesiones totales: {m['sessions']:,} ({d['sessions']:+.1f}% vs anterior)
- DAU promedio: {m['dau']:,} ({d['dau']:+.1f}% vs anterior)
- MAU: {m['mau']:,}
- Tiempo promedio de sesion: {m['avg_session_minutes']:.0f} min ({d['avg_session_minutes']:+.1f}% vs anterior)
- Horas totales de juego: {m['total_hours']:.0f}h ({d['total_hours']:+.1f}% vs anterior)
- Distribucion: {data['pct_public']:.0f}% publico, {data['pct_private']:.0f}% privado

DIA PICO: {data['peak_day']} ({data['peak_sessions']:,} sesiones)
DIA MAS BAJO: {data['low_day']} ({data['low_sessions']:,} sesiones)

El reporte debe incluir:
1. Resumen ejecutivo (max 3 oraciones)
2. Performance vs periodo anterior (por cada KPI)
3. Tendencias del periodo
4. Analisis de distribucion publico/privado
5. 2-3 recomendaciones accionables

Tono: profesional, directo, orientado a negocio. Sin tecnicismos innecesarios."""
