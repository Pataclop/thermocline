"""Reconstitution de la charge en gaz inerte, modele Buhlmann ZH-L16C.

ATTENTION: ce module rejoue un modele theorique sur un profil deja realise,
a titre informatif. Il ne reproduit pas l'algorithme proprietaire de Mares et
ne doit en aucun cas servir a planifier une plongee.

La saturation de chaque compartiment suit l'equation de Haldane:

    P(t + dt) = P(t) + (P_inspire - P(t)) * (1 - 2^(-dt / demi_vie))

La pression ambiante tolerable d'un compartiment vient des coefficients a et
b du modele, moderee par un facteur de gradient (`gf`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Dive, GasMix, Sample

# Pression de vapeur d'eau alveolaire retenue par Buhlmann (bar).
WATER_VAPOUR = 0.0627

# Fraction d'azote de l'air.
AIR_N2 = 0.79

# Metres d'eau de mer par bar.
METRES_PER_BAR = 10.0

# Demi-vies (min) et coefficients a / b des 16 compartiments, ZH-L16C.
N2_HALFLIVES = (
    4.0, 8.0, 12.5, 18.5, 27.0, 38.3, 54.3, 77.0,
    109.0, 146.0, 187.0, 239.0, 305.0, 390.0, 498.0, 635.0,
)
N2_A = (
    1.2599, 1.0000, 0.8618, 0.7562, 0.6200, 0.5043, 0.4410, 0.4000,
    0.3750, 0.3500, 0.3295, 0.3065, 0.2835, 0.2610, 0.2480, 0.2327,
)
N2_B = (
    0.5050, 0.6514, 0.7222, 0.7825, 0.8126, 0.8434, 0.8693, 0.8910,
    0.9092, 0.9222, 0.9319, 0.9403, 0.9477, 0.9544, 0.9602, 0.9653,
)

HE_HALFLIVES = (
    1.51, 3.02, 4.72, 6.99, 10.21, 14.48, 20.53, 29.11,
    41.20, 55.19, 70.69, 90.34, 115.29, 147.42, 188.24, 240.03,
)
HE_A = (
    1.7424, 1.3830, 1.1919, 1.0458, 0.9220, 0.8205, 0.7305, 0.6502,
    0.5950, 0.5545, 0.5333, 0.5189, 0.5181, 0.5176, 0.5172, 0.5119,
)
HE_B = (
    0.4245, 0.5747, 0.6527, 0.7223, 0.7582, 0.7957, 0.8279, 0.8553,
    0.8757, 0.8903, 0.8997, 0.9073, 0.9122, 0.9171, 0.9217, 0.9267,
)

NCOMPARTMENTS = len(N2_HALFLIVES)


@dataclass
class TissueState:
    """Charge instantanee des 16 compartiments."""

    n2: list[float]
    he: list[float]

    def copy(self) -> TissueState:
        return TissueState(n2=list(self.n2), he=list(self.he))


class TissueModel:
    """Etat des compartiments au fil d'un profil."""

    def __init__(self, atmospheric: float = 1.013, gf: float = 1.0) -> None:
        self.atmospheric = atmospheric
        self.gf = gf
        surface_n2 = (atmospheric - WATER_VAPOUR) * AIR_N2
        self.state = TissueState(
            n2=[surface_n2] * NCOMPARTMENTS, he=[0.0] * NCOMPARTMENTS
        )

    # -- evolution ----------------------------------------------------------

    def step(self, depth: float, seconds: float, mix: GasMix) -> None:
        """Fait evoluer les compartiments pendant `seconds` a `depth` metres."""
        if seconds <= 0:
            return
        ambient = self.ambient_pressure(depth)
        inert = max(ambient - WATER_VAPOUR, 0.0)
        fhe = mix.helium / 100.0
        fn2 = max(1.0 - mix.oxygen / 100.0 - fhe, 0.0)
        p_n2 = inert * fn2
        p_he = inert * fhe
        minutes = seconds / 60.0

        for index in range(NCOMPARTMENTS):
            factor_n2 = 1.0 - 2.0 ** (-minutes / N2_HALFLIVES[index])
            factor_he = 1.0 - 2.0 ** (-minutes / HE_HALFLIVES[index])
            self.state.n2[index] += (p_n2 - self.state.n2[index]) * factor_n2
            self.state.he[index] += (p_he - self.state.he[index]) * factor_he

    def ambient_pressure(self, depth: float) -> float:
        return self.atmospheric + max(depth, 0.0) / METRES_PER_BAR

    # -- lecture de l'etat --------------------------------------------------

    def coefficients(self, index: int) -> tuple[float, float, float]:
        """Renvoie `(pression_totale, a, b)` ponderes azote / helium."""
        p_n2 = self.state.n2[index]
        p_he = self.state.he[index]
        total = p_n2 + p_he
        if total <= 0:
            return 0.0, N2_A[index], N2_B[index]
        a = (N2_A[index] * p_n2 + HE_A[index] * p_he) / total
        b = (N2_B[index] * p_n2 + HE_B[index] * p_he) / total
        return total, a, b

    def tolerated_pressure(self, index: int) -> float:
        """Pression ambiante minimale toleree par un compartiment (bar)."""
        total, a, b = self.coefficients(index)
        if self.gf >= 1.0:
            return (total - a) * b
        # Formulation classique des facteurs de gradient.
        return (total - a * self.gf) / (self.gf / b + 1.0 - self.gf)

    def ceiling(self) -> float:
        """Profondeur de plafond la plus contraignante, en metres (0 si aucune)."""
        worst = max(self.tolerated_pressure(i) for i in range(NCOMPARTMENTS))
        return max((worst - self.atmospheric) * METRES_PER_BAR, 0.0)

    def loading(self, depth: float) -> tuple[float, int]:
        """Sursaturation la plus forte en % de la M-value, et son compartiment."""
        ambient = self.ambient_pressure(depth)
        best = 0.0
        leading = 0
        for index in range(NCOMPARTMENTS):
            total, a, b = self.coefficients(index)
            m_value = ambient / b + a
            margin = m_value - ambient
            if margin <= 0:
                continue
            percent = (total - ambient) / margin * 100.0
            if percent > best:
                best = percent
                leading = index
        return max(best, 0.0), leading

    def loadings(self, depth: float) -> list[float]:
        """Sursaturation de chaque compartiment, en % de sa M-value."""
        ambient = self.ambient_pressure(depth)
        out: list[float] = []
        for index in range(NCOMPARTMENTS):
            total, a, b = self.coefficients(index)
            margin = (ambient / b + a) - ambient
            out.append(max((total - ambient) / margin * 100.0, 0.0) if margin > 0 else 0.0)
        return out

    def surface_loadings(self) -> list[float]:
        return self.loadings(0.0)


@dataclass
class DecoProfile:
    """Resultat de la simulation sur une plongee."""

    ceiling_series: list[tuple[int, float]] = field(default_factory=list)
    loading_series: list[tuple[int, float]] = field(default_factory=list)
    """Sursaturation maximale a la profondeur courante, en % de la M-value."""
    surface_loading_series: list[tuple[int, float]] = field(default_factory=list)
    """Sursaturation qu'on aurait en remontant immediatement en surface."""
    final_loadings: list[float] = field(default_factory=list)
    """Charge de chaque compartiment a la sortie de l'eau, en %."""
    final_pressures: list[float] = field(default_factory=list)
    """Pression d'azote de chaque compartiment a la sortie, en bar."""
    max_ceiling: float = 0.0
    max_loading: float = 0.0
    leading_compartment: int = 0
    deco_seconds: int = 0
    """Temps passe avec un plafond de decompression non nul."""
    desaturation_minutes: int = 0
    """Temps estime pour revenir a l'equilibre en surface."""

    @property
    def leading_halflife(self) -> float:
        return N2_HALFLIVES[self.leading_compartment]


def simulate(
    dive: Dive,
    samples: list[Sample],
    gf: float = 1.0,
    with_desaturation: bool = True,
) -> DecoProfile:
    """Rejoue le profil dans le modele et renvoie les series utiles."""
    profile = DecoProfile()
    if not samples:
        return profile

    atmospheric = dive.atmospheric or 1.013
    model = TissueModel(atmospheric=atmospheric, gf=gf)
    default_mix = dive.gasmixes[0] if dive.gasmixes else GasMix(oxygen=21)

    previous_time = 0
    for sample in samples:
        mix = default_mix
        if sample.gasmix is not None and sample.gasmix < len(dive.gasmixes):
            mix = dive.gasmixes[sample.gasmix]
        model.step(sample.depth, sample.time - previous_time, mix)
        previous_time = sample.time

        ceiling = model.ceiling()
        loading, leading = model.loading(sample.depth)
        surface_loading, _ = model.loading(0.0)
        profile.ceiling_series.append((sample.time, ceiling))
        profile.loading_series.append((sample.time, loading))
        profile.surface_loading_series.append((sample.time, surface_loading))
        if ceiling > 0.1:
            profile.deco_seconds += dive.sample_interval or 5
        if loading > profile.max_loading:
            profile.max_loading = loading
            profile.leading_compartment = leading
        profile.max_ceiling = max(profile.max_ceiling, ceiling)

    profile.final_loadings = [round(value, 1) for value in model.surface_loadings()]
    profile.final_pressures = [round(value, 3) for value in model.state.n2]
    profile.max_loading = round(profile.max_loading, 1)
    profile.max_ceiling = round(profile.max_ceiling, 1)

    if with_desaturation:
        profile.desaturation_minutes = _desaturation_time(model)
    return profile


def _desaturation_time(model: TissueModel, cap: int = 60 * 48) -> int:
    """Minutes en surface avant le retour a l'equilibre de tous les compartiments.

    Critere retenu: tous les compartiments a moins de 2 % au-dessus de leur
    pression d'equilibre en surface. Il porte sur la pression residuelle et non
    sur la sursaturation, qui retombe a zero des que la pression tissulaire
    passe sous la pression ambiante, bien avant que les compartiments lents
    soient reellement degazes.
    """
    target = (model.atmospheric - WATER_VAPOUR) * AIR_N2
    tolerance = target * 0.02
    clone = TissueModel(atmospheric=model.atmospheric, gf=model.gf)
    clone.state = model.state.copy()
    air = GasMix(oxygen=21)
    minutes = 0
    step = 5
    while minutes < cap:
        excess = max(
            max(clone.state.n2[i] - target, 0.0) + clone.state.he[i]
            for i in range(NCOMPARTMENTS)
        )
        if excess <= tolerance:
            break
        clone.step(0.0, step * 60, air)
        minutes += step
    return minutes
