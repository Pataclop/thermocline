"""Dates ecrites en toutes lettres, sans dependre de la locale du systeme.

Les locales installees varient beaucoup d'une machine a l'autre, et sous
Windows elles portent des noms differents: fixer les noms de jours et de mois
ici garantit le meme affichage partout.
"""

from __future__ import annotations

import datetime as _dt

from .i18n import language

JOURS = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)

MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

MOIS_COURTS = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)

DAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

MONTHS_EN_SHORT = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _english() -> bool:
    return language() == "en"


def day_name(index: int) -> str:
    """Nom du jour de la semaine, `0` etant lundi."""
    return (DAYS_EN if _english() else JOURS)[index % 7]


def month_name(index: int) -> str:
    """Nom du mois, `1` etant janvier."""
    return (MONTHS_EN if _english() else MOIS)[(index - 1) % 12]


def short_month(index: int) -> str:
    return (MONTHS_EN_SHORT if _english() else MOIS_COURTS)[(index - 1) % 12]


def long_date(moment: _dt.datetime | _dt.date) -> str:
    """`vendredi 11 septembre 2026`, ou `Friday 11 September 2026`."""
    day = day_name(moment.weekday())
    return f"{day} {moment.day} {month_name(moment.month)} {moment.year}"


def long_datetime(moment: _dt.datetime) -> str:
    """`vendredi 11 septembre 2026 à 14h41`, ou `... at 14:41`."""
    if _english():
        return f"{long_date(moment)} at {moment:%H:%M}"
    return f"{long_date(moment)} à {moment:%Hh%M}"


def short_date(moment: _dt.datetime | _dt.date) -> str:
    """`11 sept. 2026`, ou `11 Sep 2026`."""
    return f"{moment.day} {short_month(moment.month)} {moment.year}"


def month_label(key: str) -> str:
    """Transforme une cle `2026-09` en `sept. 26`."""
    year, month = key.split("-")
    return f"{short_month(int(month))} {year[2:]}"
