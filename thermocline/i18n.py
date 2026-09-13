"""Traduction de l'interface.

La langue source est le francais: les chaines restent lisibles dans le code,
et `T()` les remplace par leur equivalent anglais quand c'est necessaire. Une
chaine absente du catalogue est renvoyee telle quelle, ce qui garantit qu'un
oubli degrade l'affichage sans jamais casser l'application.

    from .i18n import T
    label = T("Importer les plongées")

Les chaines a trous utilisent `str.format` plutot que les f-strings, sans quoi
le texte serait deja construit avant d'arriver ici:

    T("{count} plongées en base").format(count=12)
"""

from __future__ import annotations

import locale
import logging
import os

log = logging.getLogger(__name__)

#: Langues proposees, du code vers son nom dans sa propre langue.
LANGUAGES: dict[str, str] = {
    "fr": "Français",
    "en": "English",
}

#: Langue de redaction du code source: elle n'a pas de catalogue.
SOURCE_LANGUAGE = "fr"

_language = SOURCE_LANGUAGE
_catalog: dict[str, str] = {}


def detect_language() -> str:
    """Devine la langue du systeme, `fr` ou `en` a defaut."""
    candidates = [
        os.environ.get("THERMOCLINE_LANG", ""),
        os.environ.get("LANGUAGE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LANG", ""),
    ]
    try:
        current = locale.getlocale()[0] or ""
    except ValueError:  # pragma: no cover - locale exotique
        current = ""
    candidates.append(current)
    # Sous Windows les variables d'environnement sont souvent vides: on
    # interroge alors la langue de l'interface du systeme.
    if hasattr(locale, "getpreferredencoding"):
        try:
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is not None:  # pragma: no cover - Windows uniquement
                language_id = windll.kernel32.GetUserDefaultUILanguage()
                candidates.append(locale.windows_locale.get(language_id, ""))
        except (AttributeError, OSError, KeyError):  # pragma: no cover
            pass

    for value in candidates:
        code = value.strip().lower().replace("-", "_")[:2]
        if code in LANGUAGES:
            return code
    return "en"


def set_language(code: str) -> str:
    """Choisit la langue courante. `auto` suit le systeme.

    Renvoie le code effectivement retenu.
    """
    global _language, _catalog

    resolved = detect_language() if code in ("", "auto") else code
    if resolved not in LANGUAGES:
        log.warning("Langue inconnue (%s), on garde le français.", code)
        resolved = SOURCE_LANGUAGE

    _language = resolved
    if resolved == SOURCE_LANGUAGE:
        _catalog = {}
    else:
        from .translations import CATALOGS

        _catalog = CATALOGS.get(resolved, {})
    return resolved


def language() -> str:
    """Code de la langue courante."""
    return _language


def T(text: str) -> str:  # noqa: N802 - nom court, utilise partout
    """Traduit une chaine de l'interface."""
    return _catalog.get(text, text)


def count_label(count: int, singular: str, plural: str, **extra: object) -> str:
    """Compose une phrase accordee avec `count`.

    Les deux formes sont traduites separement, parce qu'aucune regle commune
    ne relie le singulier au pluriel d'une langue a l'autre.

        count_label(3, "{count} plongée", "{count} plongées")
    """
    template = T(singular if count <= 1 else plural)
    return template.format(count=count, **extra)
