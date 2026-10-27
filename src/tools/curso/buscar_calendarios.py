import asyncio
from collections import defaultdict
from datetime import date
from typing import Any

from application.config import URL_SIG
from application.core.current_period import (
    academic_period_key,
    local_now,
    next_academic_period,
    select_current_calendar,
)
from ..utils.run_tool import run_tool

from ...helpers.request_utils import make_request
from langchain_core.runnables import RunnableConfig


def _calendar_date(item: dict[str, Any], field: str) -> date:
    return date.fromisoformat(str(item[field]))


def _calendar_id(item: dict[str, Any]) -> tuple[int, str]:
    value = item.get("id")
    try:
        return 0, f"{int(value):020d}"
    except (TypeError, ValueError):
        return 1, str(value or "")


def _as_calendar_list(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _has_started(item: dict[str, Any], today: date) -> bool:
    try:
        return _calendar_date(item, "inicio_das_aulas") <= today
    except (KeyError, TypeError, ValueError):
        return False


def _select_reference_calendar(
    candidates: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not candidates or not references:
        return None

    candidate_ids = {str(item.get("id")): item for item in candidates}
    for reference in references:
        match = candidate_ids.get(str(reference.get("id")))
        if match is not None:
            return match

    # Protege contra uma eventual mudança de ID mantendo as datas canônicas
    # retornadas pelo endpoint de período corrente.
    date_fields = (
        "inicio_das_matriculas",
        "inicio_das_aulas",
        "ultimo_dia_para_registro_de_notas",
    )
    for reference in references:
        for candidate in candidates:
            if all(candidate.get(field) == reference.get(field) for field in date_fields):
                return candidate
    return None


def _select_closest_to_previous_end(
    candidates: list[dict[str, Any]],
    previous_end: date,
) -> dict[str, Any]:
    """Escolhe a matrícula mais próxima do encerramento anterior."""
    return min(
        candidates,
        key=lambda item: (
            abs((_calendar_date(item, "inicio_das_matriculas") - previous_end).days),
            _calendar_date(item, "inicio_das_matriculas"),
            _calendar_date(item, "inicio_das_aulas"),
            _calendar_id(item),
        ),
    )


def deduplicar(
    data: list[dict[str, Any]],
    referencias: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Mantém um calendário canônico por período acadêmico."""
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    reference_groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)

    for item in data:
        try:
            period_key = academic_period_key(str(item["periodo"]))
            _calendar_date(item, "inicio_das_matriculas")
            _calendar_date(item, "inicio_das_aulas")
            _calendar_date(item, "ultimo_dia_para_registro_de_notas")
        except (KeyError, TypeError, ValueError):
            continue
        groups[period_key].append(item)

    for item in referencias or []:
        try:
            reference_groups[academic_period_key(str(item["periodo"]))].append(item)
        except (KeyError, TypeError, ValueError):
            continue

    selected: list[dict[str, Any]] = []
    previous_end: date | None = None

    for period_key in sorted(groups):
        candidates = groups[period_key]
        calendar = _select_reference_calendar(
            candidates,
            reference_groups.get(period_key, []),
        )

        if calendar is None and previous_end is not None:
            calendar = _select_closest_to_previous_end(candidates, previous_end)
        elif calendar is None:
            calendar = min(
                candidates,
                key=lambda item: (
                    _calendar_date(item, "inicio_das_aulas"),
                    _calendar_id(item),
                ),
            )

        selected.append(calendar)
        previous_end = _calendar_date(
            calendar,
            "ultimo_dia_para_registro_de_notas",
        )

    return selected


async def buscar_calendarios(
    config: RunnableConfig,
    periodo: str,
    todos_calendarios: bool,
    proximo_periodo: bool,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """
    Busca informações dos calendários acadêmicos da UFCG.
    Informaçãoes como: início e fim das aulas, período, período atual, número de semanas de aula e último dia para registro de notas.
    
    Args:
        periodo (str): Período letivo desejado. Use a string vazia para buscar o período mais recente.
        todos_calendarios (bool): Se `True`, mostra todos os calendários até o período atual (se passar True não informe o periodo). Defaults to `False`.
        proximo_periodo (bool): Se `True`, mostra o próximo período letivo, se houver. Defaults to `False`.
    
    Returns:
        list: Lista com informações relevantes dos calendários acadêmicos do campus (como 'periodo', 'inicio_das_matriculas', 'inicio_das_aulas' e 'numero_de_semanas')
    """


    periodo = str(periodo or "").strip()

    try:
        callbacks = config["configurable"].get("callbacks_sio") or []
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por calendários da UFCG"})
            break
    except (AttributeError, KeyError, TypeError):
        pass

    hoje = local_now().date()
    calendars_url = f"{URL_SIG.rstrip('/')}/calendarios"
    current_url = f"{calendars_url}/periodo-corrente"

    if proximo_periodo:
        current_calendars = _as_calendar_list(await make_request(url=current_url))
        current = select_current_calendar(current_calendars, hoje)
        if current is None:
            return None

        next_period = next_academic_period(str(current["periodo"]))
        candidates = _as_calendar_list(
            await make_request(
                url=calendars_url,
                params={
                    "campus": "1",
                    "periodo-de": next_period,
                    "periodo-ate": next_period,
                },
            )
        )
        candidates = [
            item for item in candidates if str(item.get("periodo")) == next_period
        ]
        if not candidates:
            return None

        try:
            current_end = _calendar_date(
                current,
                "ultimo_dia_para_registro_de_notas",
            )
            return _select_closest_to_previous_end(candidates, current_end)
        except (KeyError, TypeError, ValueError):
            selected = deduplicar(candidates)
            return selected[0] if selected else None

    if periodo == "":
        current_calendars = _as_calendar_list(await make_request(url=current_url))
        if todos_calendarios:
            all_calendars = _as_calendar_list(
                await make_request(url=calendars_url, params={"campus": "1"})
            )
            data = [
                item
                for item in all_calendars
                if _has_started(item, hoje)
            ]
            return deduplicar(data, current_calendars)

        current = select_current_calendar(current_calendars, hoje)
        if current is None:
            raise ValueError(
                "Não foi possível encontrar o calendário acadêmico atual."
            )
        return [current]

    data = _as_calendar_list(
        await make_request(
            url=calendars_url,
            params={
                "campus": "1",
                "periodo-de": periodo,
                "periodo-ate": periodo,
            },
        )
    )
    data = [
        item
        for item in data
        if str(item.get("periodo")) == periodo
        and _has_started(item, hoje)
    ]

    if not data:
        raise ValueError(
            "Não foi possível encontrar o calendário acadêmico no respectivo período."
        )

    if len(data) == 1:
        return data

    current_calendars = _as_calendar_list(await make_request(url=current_url))
    return deduplicar(data, current_calendars)


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_calendarios.buscar_calendarios",
            config=RunnableConfig,
            periodo="",
            todos_calendarios=False,
            proximo_periodo=False,
        )
    )
