"""Calculs derives sur une plongee et sur l'ensemble du carnet.

Tout ce qui est affiche dans l'interface est calcule ici, afin de pouvoir
etre teste sans Qt.
"""

from __future__ import annotations

import datetime as _dt
import math
from collections import Counter
from dataclasses import dataclass, field

from . import dates, deco
from .models import Dive, DiveMode, GasMix, Sample
from .storage import DiveSummary


@dataclass(frozen=True)
class Thresholds:
    """Seuils d'analyse, tous reglables depuis la boite « Paramètres ».

    Les valeurs d'usine sont celles que recommande Mares pour ses ordinateurs
    et celles retenues par la litterature nitrox; un plongeur qui suit
    d'autres regles les change une fois pour toutes.
    """

    ascent_limit: float = 10.0
    """Vitesse de remontee au-dela de laquelle on signale l'ecart (m/min)."""
    ppo2_warn: float = 1.4
    """Pression partielle d'oxygene a partir de laquelle on avertit (bar)."""
    ppo2_max: float = 1.6
    """Pression partielle d'oxygene consideree comme critique (bar)."""
    safety_stop_band: tuple[float, float] = (2.5, 6.5)
    """Bande de profondeur comptee comme palier de securite (m)."""
    safety_stop_target: int = 180
    """Duree de palier consideree comme tenue (s)."""
    rate_window: int = 30
    """Fenetre de lissage des vitesses verticales (s)."""


#: Seuils courants. `config.apply()` les remplace au demarrage.
LIMITS = Thresholds()

# Amplitude minimale d'un aller-retour vertical pour etre compte (m).
YOYO_THRESHOLD = 4.0

# Limites NOAA d'exposition unitaire au ppO2: (bar, minutes).
CNS_LIMITS: tuple[tuple[float, float], ...] = (
    (0.6, 720),
    (0.7, 570),
    (0.8, 450),
    (0.9, 360),
    (1.0, 300),
    (1.1, 240),
    (1.2, 210),
    (1.3, 180),
    (1.4, 150),
    (1.5, 120),
    (1.6, 45),
)

Series = list[tuple[int, float]]
"""Serie temporelle intra-plongee: `(temps_s, valeur)`."""

DatedSeries = list[tuple[_dt.datetime, float]]
"""Serie datee inter-plongees."""


@dataclass
class DiveStats:
    """Indicateurs calcules a partir du profil d'une plongee."""

    # -- duree et profondeur
    duration: int = 0
    max_depth: float = 0.0
    avg_depth: float = 0.0
    median_depth: float = 0.0
    bottom_time: int = 0
    """Temps passe a plus de 80 % de la profondeur maximale (s)."""
    time_to_max_depth: int = 0
    ascent_duration: int = 0
    """Temps entre le point le plus profond et le retour en surface (s)."""
    depth_profile_area: float = 0.0
    """Integrale profondeur-temps, en m.min."""
    total_descent: float = 0.0
    """Cumul des metres descendus (m)."""
    total_ascent: float = 0.0
    yoyo_count: int = 0
    """Nombre d'aller-retours verticaux de plus de 4 m."""

    # -- vitesses
    descent_rate_max: float = 0.0
    descent_rate_avg: float = 0.0
    ascent_rate_max: float = 0.0
    ascent_rate_avg: float = 0.0
    fast_ascent_seconds: int = 0
    safety_stop_seconds: int = 0

    # -- temperature
    temp_min: float | None = None
    temp_max: float | None = None
    temp_avg: float | None = None
    temp_at_max_depth: float | None = None
    thermocline_depth: float | None = None
    """Profondeur du plus fort gradient thermique (m)."""

    # -- gaz et oxygene
    max_ppo2: float = 0.0
    min_ppo2: float = 0.0
    mod_exceeded_seconds: int = 0
    """Temps au-dela de 1,4 bar de ppO2."""
    mod_critical_seconds: int = 0
    """Temps au-dela de 1,6 bar de ppO2."""
    cns: float = 0.0
    """Charge CNS en pourcentage (limites NOAA)."""
    otu: float = 0.0
    ead_max: float | None = None
    """Profondeur equivalente air a la profondeur maximale (m)."""
    gas_switches: int = 0

    # -- consommation
    sac: float | None = None
    """Consommation ramenee a la surface (L/min), si la bouteille est saisie."""
    rmv: float | None = None
    """Volume respiratoire minute en surface (L/min), synonyme de SAC."""
    gas_used: float | None = None
    """Volume de gaz consomme (L)."""
    gas_remaining_bar: float | None = None

    # -- decompression (modele indicatif)
    deco: deco.DecoProfile = field(default_factory=deco.DecoProfile)

    # -- series pour les graphiques
    time_at_depth: list[tuple[float, int]] = field(default_factory=list)
    ascent_series: Series = field(default_factory=list)
    ppo2_series: Series = field(default_factory=list)
    cns_series: Series = field(default_factory=list)
    otu_series: Series = field(default_factory=list)
    ead_series: Series = field(default_factory=list)
    pressure_series: Series = field(default_factory=list)
    speed_histogram: list[tuple[float, int]] = field(default_factory=list)
    temp_vs_depth: list[tuple[float, float]] = field(default_factory=list)

    @property
    def has_pressure(self) -> bool:
        return bool(self.pressure_series)


def effective_samples(dive: Dive) -> list[Sample]:
    """Ecarte la queue de surface enregistree apres la remontee."""
    if not dive.samples:
        return []
    if dive.mode is DiveMode.FREEDIVE or dive.duration <= 0:
        return dive.samples
    trimmed = [s for s in dive.samples if s.time <= dive.duration]
    return trimmed or dive.samples


def compute(
    dive: Dive,
    tank_volume: float = 0.0,
    pressure_start: float = 0.0,
    pressure_end: float = 0.0,
    gradient_factor: float = 1.0,
) -> DiveStats:
    """Calcule tous les indicateurs d'une plongee."""
    samples = effective_samples(dive)
    stats = DiveStats(duration=dive.duration, max_depth=dive.max_depth)
    if not samples:
        return stats

    depths = [s.depth for s in samples]
    interval = dive.sample_interval or _median_interval(samples)

    _fill_depth_stats(stats, dive, samples, depths, interval)
    _fill_rate_stats(stats, samples, interval)
    _fill_temperature_stats(stats, dive, samples)
    _fill_oxygen_stats(stats, dive, samples, depths, interval)
    _fill_consumption_stats(stats, dive, samples, tank_volume, pressure_start, pressure_end)

    stats.time_at_depth = time_at_depth(samples, interval)
    stats.temp_vs_depth = [
        (s.depth, s.temperature) for s in samples if s.temperature is not None
    ]
    stats.deco = deco.simulate(dive, samples, gf=gradient_factor)
    return stats


# -- blocs de calcul -------------------------------------------------------


def _fill_depth_stats(
    stats: DiveStats,
    dive: Dive,
    samples: list[Sample],
    depths: list[float],
    interval: int,
) -> None:
    stats.max_depth = max(dive.max_depth, max(depths))
    stats.avg_depth = round(sum(depths) / len(depths), 1)
    stats.median_depth = round(sorted(depths)[len(depths) // 2], 1)
    stats.depth_profile_area = round(sum(depths) * interval / 60.0, 1)

    threshold = stats.max_depth * 0.8
    stats.bottom_time = sum(interval for d in depths if d >= threshold)

    deepest_index = depths.index(max(depths))
    stats.time_to_max_depth = samples[deepest_index].time
    stats.temp_at_max_depth = samples[deepest_index].temperature
    stats.ascent_duration = max(samples[-1].time - samples[deepest_index].time, 0)
    stats.safety_stop_seconds = safety_stop_duration(samples, interval, deepest_index)

    descent = ascent = 0.0
    for previous, current in zip(samples, samples[1:]):
        delta = current.depth - previous.depth
        if delta > 0:
            descent += delta
        else:
            ascent -= delta
    stats.total_descent = round(descent, 1)
    stats.total_ascent = round(ascent, 1)
    stats.yoyo_count = count_yoyos(depths)


def _fill_rate_stats(stats: DiveStats, samples: list[Sample], interval: int) -> None:
    stats.ascent_series = vertical_rates(samples)
    ascents = [r for _, r in stats.ascent_series if r > 0]
    descents = [-r for _, r in stats.ascent_series if r < 0]
    stats.ascent_rate_max = round(max(ascents, default=0.0), 1)
    stats.ascent_rate_avg = round(sum(ascents) / len(ascents), 1) if ascents else 0.0
    stats.descent_rate_max = round(max(descents, default=0.0), 1)
    stats.descent_rate_avg = round(sum(descents) / len(descents), 1) if descents else 0.0
    stats.fast_ascent_seconds = sum(
        interval for _, r in stats.ascent_series if r > LIMITS.ascent_limit
    )
    stats.speed_histogram = speed_histogram(stats.ascent_series, interval)


def _fill_temperature_stats(
    stats: DiveStats, dive: Dive, samples: list[Sample]
) -> None:
    temps = [s.temperature for s in samples if s.temperature is not None]
    if temps:
        stats.temp_min = min(temps)
        stats.temp_max = max(temps)
        stats.temp_avg = round(sum(temps) / len(temps), 1)
        stats.thermocline_depth = thermocline(samples)
    else:
        stats.temp_min = dive.temperature_min
        stats.temp_max = dive.temperature_max


def _fill_oxygen_stats(
    stats: DiveStats,
    dive: Dive,
    samples: list[Sample],
    depths: list[float],
    interval: int,
) -> None:
    if not dive.gasmixes or dive.mode is DiveMode.GAUGE:
        return

    stats.ppo2_series = ppo2_series(dive, samples)
    values = [v for _, v in stats.ppo2_series]
    if values:
        stats.max_ppo2 = round(max(values), 2)
        stats.min_ppo2 = round(min(values), 2)
        stats.mod_exceeded_seconds = sum(
            interval for v in values if v > LIMITS.ppo2_warn
        )
        stats.mod_critical_seconds = sum(
            interval for v in values if v > LIMITS.ppo2_max
        )

    stats.cns_series, stats.otu_series = oxygen_series(stats.ppo2_series, interval)
    stats.cns = round(stats.cns_series[-1][1], 1) if stats.cns_series else 0.0
    stats.otu = round(stats.otu_series[-1][1], 1) if stats.otu_series else 0.0

    stats.ead_series = [
        (sample.time, equivalent_air_depth(sample.depth, _mix_at(dive, sample)))
        for sample in samples
    ]
    stats.ead_max = max((v for _, v in stats.ead_series), default=None)
    if stats.ead_max is not None:
        stats.ead_max = round(stats.ead_max, 1)
    stats.gas_switches = count_gas_switches(samples)


def _fill_consumption_stats(
    stats: DiveStats,
    dive: Dive,
    samples: list[Sample],
    tank_volume: float,
    pressure_start: float,
    pressure_end: float,
) -> None:
    measured = [(s.time, s.pressure) for s in samples if s.pressure is not None]
    if measured:
        stats.pressure_series = measured
        first, last = measured[0][1], measured[-1][1]
        if tank_volume > 0 and first > last:
            stats.gas_used = round((first - last) * tank_volume, 1)
        stats.gas_remaining_bar = last

    if tank_volume <= 0 or not (pressure_start > pressure_end >= 0):
        return

    stats.gas_used = round((pressure_start - pressure_end) * tank_volume, 1)
    stats.gas_remaining_bar = pressure_end
    minutes = max(stats.duration, 1) / 60.0
    avg_ata = 1.0 + stats.avg_depth / 10.0
    stats.sac = round(stats.gas_used / minutes / avg_ata, 1)
    stats.rmv = stats.sac

    if not stats.pressure_series:
        stats.pressure_series = estimated_pressure_series(
            samples, stats.sac, tank_volume, pressure_start
        )


# -- series intra-plongee --------------------------------------------------


def _median_interval(samples: list[Sample]) -> int:
    if len(samples) < 2:
        return 5
    deltas = sorted(b.time - a.time for a, b in zip(samples, samples[1:]))
    return max(deltas[len(deltas) // 2], 1)


def _mix_at(dive: Dive, sample: Sample) -> GasMix:
    if sample.gasmix is not None and sample.gasmix < len(dive.gasmixes):
        return dive.gasmixes[sample.gasmix]
    return dive.gasmixes[0] if dive.gasmixes else GasMix(oxygen=21)


def vertical_rates(samples: list[Sample], window: int = 0) -> Series:
    """Vitesse verticale lissee sur `window` secondes, en m/min.

    Une valeur positive correspond a une remontee.
    """
    if len(samples) < 2:
        return []
    window = window or LIMITS.rate_window
    series: Series = []
    left = 0
    for right in range(1, len(samples)):
        while samples[right].time - samples[left].time > window and left < right - 1:
            left += 1
        span = samples[right].time - samples[left].time
        if span <= 0:
            continue
        delta = samples[left].depth - samples[right].depth
        series.append((samples[right].time, delta / span * 60.0))
    return series


def ppo2_series(dive: Dive, samples: list[Sample]) -> Series:
    """Pression partielle d'oxygene au fil du temps, en bar."""
    atm = dive.atmospheric or 1.013
    return [
        (
            sample.time,
            round(_mix_at(dive, sample).oxygen / 100.0 * (atm + sample.depth / 10.0), 3),
        )
        for sample in samples
    ]


def oxygen_series(ppo2: Series, interval: int) -> tuple[Series, Series]:
    """Charge CNS (%) et OTU cumulees au fil du temps."""
    cns_total = 0.0
    otu_total = 0.0
    minutes = interval / 60.0
    cns: Series = []
    otu: Series = []
    for time, value in ppo2:
        if value > 0.5:
            otu_total += minutes * ((value - 0.5) / 0.5) ** 0.83
        limit = _cns_limit(value)
        if limit:
            cns_total += minutes / limit * 100.0
        cns.append((time, round(cns_total, 2)))
        otu.append((time, round(otu_total, 2)))
    return cns, otu


def oxygen_exposure(
    depths: list[float], interval: int, fo2: float, atm: float
) -> tuple[float, float]:
    """Charge CNS (%) et OTU totales, a partir d'un profil brut."""
    series = [(index * interval, fo2 * (atm + d / 10.0)) for index, d in enumerate(depths)]
    cns, otu = oxygen_series(series, interval)
    return (
        round(cns[-1][1], 1) if cns else 0.0,
        round(otu[-1][1], 1) if otu else 0.0,
    )


def _cns_limit(ppo2: float) -> float | None:
    """Duree d'exposition unitaire admissible (min) pour un ppO2 donne."""
    if ppo2 < CNS_LIMITS[0][0]:
        return None
    if ppo2 >= CNS_LIMITS[-1][0]:
        return CNS_LIMITS[-1][1]
    for (p_low, t_low), (p_high, t_high) in zip(CNS_LIMITS, CNS_LIMITS[1:]):
        if p_low <= ppo2 < p_high:
            ratio = (ppo2 - p_low) / (p_high - p_low)
            return t_low + (t_high - t_low) * ratio
    return None


def estimated_pressure_series(
    samples: list[Sample], sac: float, tank_volume: float, pressure_start: float
) -> Series:
    """Reconstitue la pression du bloc a partir d'une consommation constante.

    Utile pour les ordinateurs sans integration d'air: la courbe est une
    estimation, ponderee par la profondeur instantanee.
    """
    if tank_volume <= 0 or sac <= 0:
        return []
    series: Series = []
    pressure = pressure_start
    previous = 0
    for sample in samples:
        elapsed = (sample.time - previous) / 60.0
        previous = sample.time
        litres = sac * (1.0 + sample.depth / 10.0) * elapsed
        pressure = max(pressure - litres / tank_volume, 0.0)
        series.append((sample.time, round(pressure, 1)))
    return series


def safety_stop_duration(
    samples: list[Sample], interval: int, deepest_index: int
) -> int:
    """Plus longue plage continue passee dans la bande du palier, apres le fond."""
    low, high = LIMITS.safety_stop_band
    best = 0
    current = 0
    for sample in samples[deepest_index:]:
        if low <= sample.depth <= high:
            current += interval
            best = max(best, current)
        else:
            current = 0
    return best


def time_at_depth(
    samples: list[Sample], interval: int, bucket: float = 3.0
) -> list[tuple[float, int]]:
    """Temps cumule par tranche de profondeur: `(borne_basse, secondes)`."""
    counter: Counter[int] = Counter()
    for sample in samples:
        if sample.depth < 0.5:
            continue
        counter[int(sample.depth // bucket)] += interval
    if not counter:
        return []
    return [(slot * bucket, counter[slot]) for slot in range(max(counter) + 1)]


def speed_histogram(
    series: Series, interval: int, bucket: float = 2.0
) -> list[tuple[float, int]]:
    """Temps passe par tranche de vitesse verticale: `(borne_basse, secondes)`."""
    counter: Counter[int] = Counter()
    for _, rate in series:
        counter[int(math.floor(rate / bucket))] += interval
    if not counter:
        return []
    low, high = min(counter), max(counter)
    return [(slot * bucket, counter.get(slot, 0)) for slot in range(low, high + 1)]


def thermocline(samples: list[Sample], window: int = 6) -> float | None:
    """Profondeur ou le gradient thermique est le plus marque (m)."""
    points = [(s.depth, s.temperature) for s in samples if s.temperature is not None]
    if len(points) < window * 2:
        return None
    best_gradient = 0.0
    best_depth = None
    for index in range(window, len(points) - window):
        depth_span = points[index + window][0] - points[index - window][0]
        temp_span = points[index + window][1] - points[index - window][1]
        if abs(depth_span) < 1.0:
            continue
        gradient = abs(temp_span / depth_span)
        if gradient > best_gradient:
            best_gradient = gradient
            best_depth = points[index][0]
    return round(best_depth, 1) if best_depth is not None and best_gradient > 0.3 else None


def count_yoyos(depths: list[float], threshold: float = YOYO_THRESHOLD) -> int:
    """Compte les aller-retours verticaux d'au moins `threshold` metres."""
    if not depths:
        return 0
    count = 0
    direction = 0
    anchor = depths[0]
    for depth in depths[1:]:
        delta = depth - anchor
        if direction >= 0 and delta <= -threshold:
            if direction > 0:
                count += 1
            direction = -1
            anchor = depth
        elif direction <= 0 and delta >= threshold:
            if direction < 0:
                count += 1
            direction = 1
            anchor = depth
        elif direction > 0 and depth > anchor or direction < 0 and depth < anchor:
            anchor = depth
    return count


def count_gas_switches(samples: list[Sample]) -> int:
    switches = 0
    previous: int | None = None
    for sample in samples:
        if sample.gasmix is None:
            continue
        if previous is not None and sample.gasmix != previous:
            switches += 1
        previous = sample.gasmix
    return switches


def equivalent_air_depth(depth: float, mix: GasMix) -> float:
    """Profondeur equivalente air d'un nitrox, en metres."""
    fn2 = mix.nitrogen / 100.0
    ead = (depth + 10.0) * fn2 / 0.79 - 10.0
    return round(max(ead, 0.0), 1)


def nitrox_mod(mix: GasMix, ppo2_max: float = 0.0) -> float:
    """Profondeur maximale operationnelle d'un melange, en metres."""
    ppo2_max = ppo2_max or LIMITS.ppo2_warn
    if mix.oxygen <= 0:
        return math.inf
    return round((ppo2_max / (mix.oxygen / 100.0) - 1.0) * 10.0, 1)


# -- vue d'ensemble du carnet ----------------------------------------------


@dataclass
class Overview:
    """Agregats sur l'ensemble des plongees."""

    total_dives: int = 0
    total_seconds: int = 0
    max_depth: float = 0.0
    avg_depth: float = 0.0
    avg_max_depth: float = 0.0
    avg_duration: int = 0
    total_descent: float = 0.0
    """Cumul des profondeurs maximales, en metres."""
    longest_streak: int = 0
    """Plus longue serie de jours consecutifs avec au moins une plongee."""
    busiest_day: tuple[_dt.date, int] | None = None

    deepest: DiveSummary | None = None
    longest: DiveSummary | None = None
    coldest: DiveSummary | None = None
    warmest: DiveSummary | None = None
    first: DiveSummary | None = None
    last: DiveSummary | None = None

    per_month: list[tuple[str, int]] = field(default_factory=list)
    per_year: list[tuple[int, int]] = field(default_factory=list)
    per_weekday: list[tuple[str, int]] = field(default_factory=list)
    per_hour: list[tuple[int, int]] = field(default_factory=list)
    per_site: list[tuple[str, int]] = field(default_factory=list)
    modes: list[tuple[str, int]] = field(default_factory=list)
    gases: list[tuple[str, int]] = field(default_factory=list)
    depth_buckets: list[tuple[float, int]] = field(default_factory=list)
    duration_buckets: list[tuple[float, int]] = field(default_factory=list)

    depth_progression: DatedSeries = field(default_factory=list)
    avg_depth_progression: DatedSeries = field(default_factory=list)
    duration_progression: DatedSeries = field(default_factory=list)
    temp_progression: DatedSeries = field(default_factory=list)
    sac_progression: DatedSeries = field(default_factory=list)
    cumulative: DatedSeries = field(default_factory=list)
    """Temps immerge cumule en heures, au fil des plongees."""
    cumulative_dives: DatedSeries = field(default_factory=list)
    rolling_year: DatedSeries = field(default_factory=list)
    """Nombre de plongees sur les 365 jours precedents."""
    duration_vs_depth: list[tuple[float, float]] = field(default_factory=list)
    """`(duree_min, profondeur_max)` pour le nuage de points."""
    surface_intervals: DatedSeries = field(default_factory=list)
    """Intervalles de surface de moins de 24 h, en heures."""

    @property
    def total_hours(self) -> float:
        return round(self.total_seconds / 3600.0, 1)

    @property
    def total_duration_label(self) -> str:
        hours, remainder = divmod(self.total_seconds, 3600)
        return f"{hours} h {remainder // 60:02d}"


def compute_overview(summaries: list[DiveSummary]) -> Overview:
    """Agrege la liste des plongees pour le tableau de bord."""
    overview = Overview()
    if not summaries:
        return overview

    ordered = sorted(summaries, key=lambda s: s.started_at)
    overview.total_dives = len(ordered)
    overview.total_seconds = sum(s.duration for s in ordered)
    overview.max_depth = max(s.max_depth for s in ordered)
    overview.total_descent = round(sum(s.max_depth for s in ordered), 1)
    overview.avg_max_depth = round(
        sum(s.max_depth for s in ordered) / len(ordered), 1
    )
    depths = [s.avg_depth for s in ordered if s.avg_depth]
    overview.avg_depth = round(sum(depths) / len(depths), 1) if depths else 0.0
    overview.avg_duration = overview.total_seconds // overview.total_dives

    overview.deepest = max(ordered, key=lambda s: s.max_depth)
    overview.longest = max(ordered, key=lambda s: s.duration)
    cold = [s for s in ordered if s.temp_min is not None]
    overview.coldest = min(cold, key=lambda s: s.temp_min or 0) if cold else None
    warm = [s for s in ordered if s.temp_max is not None]
    overview.warmest = max(warm, key=lambda s: s.temp_max or 0) if warm else None
    overview.first = ordered[0]
    overview.last = ordered[-1]

    _fill_distributions(overview, ordered)
    _fill_progressions(overview, ordered)
    _fill_streaks(overview, ordered)
    return overview


def _fill_distributions(overview: Overview, ordered: list[DiveSummary]) -> None:
    months: Counter[str] = Counter()
    years: Counter[int] = Counter()
    weekdays: Counter[int] = Counter()
    hours: Counter[int] = Counter()
    sites: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    gases: Counter[str] = Counter()
    depth_slots: Counter[int] = Counter()
    duration_slots: Counter[int] = Counter()

    for summary in ordered:
        months[f"{summary.started_at:%Y-%m}"] += 1
        years[summary.started_at.year] += 1
        weekdays[summary.started_at.weekday()] += 1
        hours[summary.started_at.hour] += 1
        if summary.site:
            sites[summary.site] += 1
        modes[summary.mode.label] += 1
        gases[summary.gas_label] += 1
        depth_slots[int(summary.max_depth // 10)] += 1
        duration_slots[int(summary.duration // 600)] += 1

    overview.per_month = _fill_months(months)
    overview.per_year = sorted(years.items())
    overview.per_weekday = [
        (dates.day_name(day)[:3], weekdays.get(day, 0)) for day in range(7)
    ]
    overview.per_hour = [(hour, hours.get(hour, 0)) for hour in range(24)]
    overview.per_site = sites.most_common(12)
    overview.modes = modes.most_common()
    overview.gases = gases.most_common()
    overview.depth_buckets = [
        (slot * 10.0, depth_slots.get(slot, 0)) for slot in range(max(depth_slots) + 1)
    ]
    overview.duration_buckets = [
        (slot * 10.0, duration_slots.get(slot, 0))
        for slot in range(max(duration_slots) + 1)
    ]


def _fill_progressions(overview: Overview, ordered: list[DiveSummary]) -> None:
    cumulative_hours = 0.0
    for index, summary in enumerate(ordered, start=1):
        moment = summary.started_at
        overview.depth_progression.append((moment, summary.max_depth))
        overview.duration_progression.append((moment, summary.duration / 60.0))
        if summary.avg_depth:
            overview.avg_depth_progression.append((moment, summary.avg_depth))
        if summary.temp_min is not None:
            overview.temp_progression.append((moment, summary.temp_min))
        cumulative_hours += summary.duration / 3600.0
        overview.cumulative.append((moment, round(cumulative_hours, 2)))
        overview.cumulative_dives.append((moment, float(index)))
        overview.duration_vs_depth.append((summary.duration / 60.0, summary.max_depth))

        if summary.tank_volume and summary.pressure_start > summary.pressure_end > 0:
            minutes = max(summary.duration, 1) / 60.0
            litres = (summary.pressure_start - summary.pressure_end) * summary.tank_volume
            ata = 1.0 + (summary.avg_depth or summary.max_depth / 2) / 10.0
            overview.sac_progression.append(
                (moment, round(litres / minutes / ata, 1))
            )

    window = _dt.timedelta(days=365)
    for summary in ordered:
        count = sum(
            1
            for other in ordered
            if summary.started_at - window < other.started_at <= summary.started_at
        )
        overview.rolling_year.append((summary.started_at, float(count)))

    for previous, current in zip(ordered, ordered[1:]):
        gap = surface_interval(previous, current)
        if gap is not None and gap < 24 * 3600:
            overview.surface_intervals.append(
                (current.started_at, round(gap / 3600.0, 2))
            )


def _fill_streaks(overview: Overview, ordered: list[DiveSummary]) -> None:
    per_day: Counter[_dt.date] = Counter()
    for summary in ordered:
        per_day[summary.started_at.date()] += 1
    if per_day:
        day, count = per_day.most_common(1)[0]
        overview.busiest_day = (day, count)

    days = sorted(per_day)
    best = current = 1 if days else 0
    for previous, day in zip(days, days[1:]):
        if (day - previous).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    overview.longest_streak = best


def _fill_months(months: Counter[str]) -> list[tuple[str, int]]:
    """Complete les mois sans plongee pour obtenir un histogramme continu."""
    if not months:
        return []
    keys = sorted(months)
    start = _dt.date.fromisoformat(keys[0] + "-01")
    end = _dt.date.fromisoformat(keys[-1] + "-01")
    out: list[tuple[str, int]] = []
    cursor = start
    while cursor <= end:
        label = f"{cursor:%Y-%m}"
        out.append((label, months.get(label, 0)))
        year, month = divmod(cursor.month, 12)
        cursor = cursor.replace(year=cursor.year + year, month=month + 1)
    return out


def surface_interval(previous: DiveSummary, current: DiveSummary) -> int | None:
    """Intervalle de surface entre deux plongees consecutives, en secondes."""
    end = previous.started_at + _dt.timedelta(seconds=previous.duration)
    delta = (current.started_at - end).total_seconds()
    return int(delta) if delta >= 0 else None


def pretty_duration(seconds: int | float) -> str:
    """Formate une duree en `1 h 23` ou `12:34` selon son ordre de grandeur."""
    seconds = int(seconds)
    if seconds >= 3600:
        return f"{seconds // 3600} h {(seconds % 3600) // 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"
