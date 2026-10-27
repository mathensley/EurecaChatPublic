import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from application.config import URL_SIG
from src.helpers.request_utils import make_request


logger = logging.getLogger("http")
ACADEMIC_TIMEZONE = ZoneInfo("America/Recife")
CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class PeriodCacheEntry:
    periodo: str | None
    valid_from: date | None
    valid_until: date | None
    refresh_after: datetime


def local_now() -> datetime:
    return datetime.now(ACADEMIC_TIMEZONE)


def academic_period_key(periodo: str) -> tuple[int, int]:
    """Converte um período regular, como 2026.2, em uma chave ordenável."""
    try:
        year_text, term_text = str(periodo).strip().split(".", maxsplit=1)
        year = int(year_text)
        term = int(term_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Período acadêmico inválido: {periodo!r}.") from exc

    if year < 1 or term not in (1, 2):
        raise ValueError(f"Período acadêmico inválido: {periodo!r}.")
    return year, term


def next_academic_period(periodo: str) -> str:
    """Retorna o período regular imediatamente posterior."""
    year, term = academic_period_key(periodo)
    return f"{year}.2" if term == 1 else f"{year + 1}.1"


def select_current_calendar(calendars: Any, today: date) -> dict[str, Any] | None:
    """Seleciona o maior período já iniciado e ainda ativo."""
    active: list[tuple[tuple[int, int], date, date, dict[str, Any]]] = []

    for item in calendars if isinstance(calendars, list) else []:
        if not isinstance(item, dict) or not item.get("periodo"):
            continue
        try:
            start = date.fromisoformat(str(item["inicio_das_aulas"]))
            end = date.fromisoformat(str(item["ultimo_dia_para_registro_de_notas"]))
            period_key = academic_period_key(str(item["periodo"]))
        except (KeyError, TypeError, ValueError):
            continue

        if start <= today <= end:
            active.append((period_key, start, end, item))

    if not active:
        return None

    latest_period = max(value[0] for value in active)
    same_period = [value for value in active if value[0] == latest_period]

    # Duplicatas espúrias costumam aparecer como uma segunda versão mais
    # tardia do mesmo período. Entre calendários ativos com o mesmo rótulo,
    # preserva o primeiro início publicado.
    _, _, _, selected = min(
        same_period,
        key=lambda value: (
            value[1],
            value[2],
            str(value[3].get("id", "")),
        ),
    )
    return selected


def select_current_period(
    calendars: Any,
    today: date,
    *,
    now: datetime | None = None,
) -> PeriodCacheEntry:
    """Seleciona o calendário atual e limita o cache a no máximo 24 horas."""
    reference_now = now or datetime.combine(today, time.min, ACADEMIC_TIMEZONE)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=ACADEMIC_TIMEZONE)
    else:
        reference_now = reference_now.astimezone(ACADEMIC_TIMEZONE)

    selected = select_current_calendar(calendars, today)
    ttl_deadline = reference_now + CACHE_TTL

    valid_calendars: list[tuple[tuple[int, int], date]] = []
    for item in calendars if isinstance(calendars, list) else []:
        if not isinstance(item, dict) or not item.get("periodo"):
            continue
        try:
            period_key = academic_period_key(str(item["periodo"]))
            start = date.fromisoformat(str(item["inicio_das_aulas"]))
        except (KeyError, TypeError, ValueError):
            continue
        valid_calendars.append((period_key, start))

    if selected:
        start = date.fromisoformat(str(selected["inicio_das_aulas"]))
        end = date.fromisoformat(str(selected["ultimo_dia_para_registro_de_notas"]))
        periodo = str(selected["periodo"])
        selected_key = academic_period_key(periodo)
        future_starts = [
            future_start
            for period_key, future_start in valid_calendars
            if period_key > selected_key and future_start > today
        ]

        deadlines = [
            ttl_deadline,
            datetime.combine(end + timedelta(days=1), time.min, ACADEMIC_TIMEZONE),
        ]
        if future_starts:
            deadlines.append(
                datetime.combine(min(future_starts), time.min, ACADEMIC_TIMEZONE)
            )

        return PeriodCacheEntry(periodo, start, end, min(deadlines))

    # Sem calendário ativo, consulta novamente no início do próximo calendário
    # conhecido ou, no máximo, em 24 horas.
    future_starts = [start for _, start in valid_calendars if start > today]
    refresh_after = ttl_deadline
    if future_starts:
        refresh_after = min(
            refresh_after,
            datetime.combine(min(future_starts), time.min, ACADEMIC_TIMEZONE),
        )
    return PeriodCacheEntry(None, None, None, refresh_after)


class CurrentPeriodCache:
    """Cache persistente do período atual, com uma camada em memória por processo."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._entry: PeriodCacheEntry | None = None
        self._lock = asyncio.Lock()

    async def get_current_period(self) -> str | None:
        now = local_now()
        if self._entry and now < self._entry.refresh_after:
            return self._entry.periodo

        async with self._lock:
            now = local_now()
            if self._entry and now < self._entry.refresh_after:
                return self._entry.periodo

            persisted = await self._load_persisted(now)
            if persisted:
                self._entry = persisted
                return persisted.periodo

            try:
                calendars = await make_request(
                    url=f"{URL_SIG.rstrip('/')}/calendarios/periodo-corrente"
                )
                entry = select_current_period(calendars, now.date(), now=now)
                await self._persist(entry)
                self._entry = entry
                return entry.periodo
            except Exception:
                logger.exception("current_academic_period_refresh_failed")
                # Evita uma rajada de chamadas quando o SIG estiver indisponível.
                self._entry = PeriodCacheEntry(
                    periodo=None,
                    valid_from=None,
                    valid_until=None,
                    refresh_after=now + timedelta(minutes=15),
                )
                return None

    async def _load_persisted(self, now: datetime) -> PeriodCacheEntry | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT periodo, valid_from, valid_until, refresh_after, updated_at
                FROM academic_period_cache
                WHERE cache_key = 'current' AND refresh_after > $1
                """,
                now,
            )
        if not row:
            return None

        # Entradas criadas pela política antiga podiam permanecer válidas por
        # meses. Rejeita tanto uma entrada velha quanto um prazo incompatível
        # com o TTL usado pela política atual.
        if (
            row["updated_at"] <= now - CACHE_TTL
            or row["refresh_after"] > now + CACHE_TTL
        ):
            return None
        return PeriodCacheEntry(
            periodo=row["periodo"],
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            refresh_after=row["refresh_after"],
        )

    async def _persist(self, entry: PeriodCacheEntry) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO academic_period_cache (
                    cache_key, periodo, valid_from, valid_until, refresh_after, updated_at
                )
                VALUES ('current', $1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (cache_key) DO UPDATE SET
                    periodo = EXCLUDED.periodo,
                    valid_from = EXCLUDED.valid_from,
                    valid_until = EXCLUDED.valid_until,
                    refresh_after = EXCLUDED.refresh_after,
                    updated_at = CURRENT_TIMESTAMP
                """,
                entry.periodo,
                entry.valid_from,
                entry.valid_until,
                entry.refresh_after,
            )
