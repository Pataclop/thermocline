"""Verifie que le catalogue anglais suit le code.

Ajouter un texte a l'interface sans le traduire fait echouer ces tests: c'est
le seul moyen fiable de garder les deux langues au meme niveau.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from thermocline.translations import CATALOGS, EN

PACKAGE = Path(__file__).resolve().parent.parent / "thermocline"

#: Champs de remplacement d'une chaine a trous: `{nom}` ou `{nom:format}`.
FIELD = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)[^{}]*\}")

#: Chaines traduites ailleurs que par un appel `T()` litteral: les libelles de
#: mode viennent d'un dictionnaire, les en-tetes de colonnes d'un tuple.
INDIRECT = {
    "Air", "Profondimètre", "Nitrox", "Apnée", "Trimix", "Recycleur semi-fermé",
    "Date", "Max", "Temp.", "Gaz", "Site",
}

#: Chaines qui s'ecrivent pareil dans les deux langues: unites, symboles et
#: valeurs mises en forme. Les lister evite qu'un vrai oubli passe inapercu.
SAME_IN_BOTH = {
    " bar", "L/min", "ppO2", "ppO2 (bar)", "CNS", "CNS (%)", "CNS (%) · OTU",
    "OTU", "M-value", "Trimix", "Nitrox", "Air", "Python", "Version",
    "Thermocline", "Mode", "Actions", "Record", "Diagnostic", "Interface",
    "Temperature (°C)", "Température (°C)", "Port  ",
    "Date", "Max", "Temp.", "Site", "Export", "Temp", "Modes                ",
    "    Mares {name}{air}", "  Site                  {site}",
    "  CNS / OTU             {cns:.1f} % / {otu:.0f}",
    "{number:>4} {date:<17} {duration:>7} {max:>7} {avg:>7} {temp:>6}  "
    "{gas:<14} {site}",
    "{sac:.1f} L/min", "{max_ppo2:.2f} bar", "{min_ppo2:.2f} bar",
    "{atmospheric:.3f} bar", "{ascent_rate_max:.1f} m/min",
    "{ascent_rate_avg:.1f} m/min", "{descent_rate_max:.1f} m/min",
    "{descent_rate_avg:.1f} m/min", "{depth_profile_area:.0f} m.min",
    "{pressure_start:.0f} → {pressure_end:.0f} bar", "  ·  {pressure:.0f} bar",
    "max {temp_max:.1f} °C",
}


def module_constants(tree: ast.Module) -> dict[str, str]:
    """Constantes de module dont la valeur est une chaine."""
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value.value
    return found


def source_files() -> list[Path]:
    return [
        path
        for path in sorted(PACKAGE.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name != "translations.py"
    ]


def translatable_strings() -> dict[str, str]:
    """Toutes les chaines passees a `T()` ou `count_label()`, par fichier.

    Les constantes sont mises en commun: une infobulle definie dans `plots.py`
    est souvent traduite depuis `main_window.py`.
    """
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in source_files()}
    constants: dict[str, str] = {}
    for tree in trees.values():
        constants.update(module_constants(tree))

    found: dict[str, str] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "T" and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(
                    argument.value, str
                ):
                    found[argument.value] = path.name
                elif isinstance(argument, ast.Name) and argument.id in constants:
                    found[constants[argument.id]] = path.name
            elif node.func.id == "count_label" and len(node.args) >= 3:
                for argument in node.args[1:3]:
                    if isinstance(argument, ast.Constant) and isinstance(
                        argument.value, str
                    ):
                        found[argument.value] = path.name
    return found


class CatalogueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strings = translatable_strings()

    def test_the_project_actually_has_strings_to_translate(self) -> None:
        self.assertGreater(len(self.strings), 200)

    def test_every_string_is_translated(self) -> None:
        missing = sorted(
            f"{origin}: {text!r}"
            for text, origin in self.strings.items()
            if text not in EN
        )
        self.assertEqual(
            missing,
            [],
            f"{len(missing)} chaîne(s) absente(s) du catalogue anglais :\n"
            + "\n".join(missing[:20]),
        )

    def test_no_dead_entries(self) -> None:
        """Une entree qui ne correspond a plus rien est du poids mort."""
        dead = sorted(set(EN) - set(self.strings) - INDIRECT)
        self.assertEqual(dead, [], f"Entrées inutilisées : {dead[:20]}")

    def test_placeholders_match(self) -> None:
        """Un champ perdu a la traduction leve une erreur au moment d'afficher."""
        mismatched = []
        for source, translation in EN.items():
            if set(FIELD.findall(source)) != set(FIELD.findall(translation)):
                mismatched.append(source)
        self.assertEqual(mismatched, [], f"Champs différents : {mismatched[:10]}")

    def test_nothing_is_left_in_french(self) -> None:
        """Une traduction identique a la source est le plus souvent un oubli."""
        identical = {
            text
            for text, translation in EN.items()
            if text == translation and text not in SAME_IN_BOTH
        }
        self.assertEqual(identical, set(), f"Non traduites : {sorted(identical)[:10]}")

    def test_every_catalogue_is_a_string_mapping(self) -> None:
        for code, catalog in CATALOGS.items():
            self.assertIsInstance(code, str)
            for key, value in catalog.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, str)


if __name__ == "__main__":
    unittest.main()
