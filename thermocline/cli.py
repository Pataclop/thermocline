"""Ligne de commande: import, inspection et lancement de l'interface."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config
from .analytics import compute, compute_overview, pretty_duration
from .device import MODELS, Family
from .i18n import T
from .importer import import_from_port, open_source
from .simulator import DEMO_MODELS
from .storage import DEFAULT_DB_PATH, Database
from .transport import list_serial_ports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thermocline",
        description=(
            T("Thermocline — carnet de plongée pour les ordinateurs Mares "
            "(familles IconHD, Smart et Genius/Sirius).")
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=T("chemin de la base SQLite (défaut : {path})").format(path=DEFAULT_DB_PATH),
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help=T("journal détaillé"))

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("ui", help=T("ouvre l'interface graphique (défaut)"))
    subparsers.add_parser("ports", help=T("liste les ports série disponibles"))
    subparsers.add_parser("models", help=T("liste les modèles Mares gérés"))
    subparsers.add_parser(
        "diagnostic", help=T("versions, chemins et ports, à joindre à une demande d'aide")
    )

    importer = subparsers.add_parser("import", help=T("importe les plongées en base"))
    importer.add_argument("--port", help=T("port série (défaut : détection automatique)"))
    importer.add_argument("--demo", action="store_true", help=T("utilise l'ordinateur simulé"))
    importer.add_argument(
        "--demo-model",
        default="",
        choices=("", *DEMO_MODELS),
        help=T("modèle imité en mode démonstration"),
    )
    importer.add_argument("--limit", type=int, help=T("nombre maximum de plongées à lire"))
    importer.add_argument(
        "--full",
        action="store_true",
        help=T("relit tout l'historique sans s'arrêter à la dernière plongée connue"),
    )

    listing = subparsers.add_parser("list", help=T("affiche les plongées en base"))
    listing.add_argument("--asc", action="store_true", help=T("de la plus ancienne à la plus récente"))

    stats = subparsers.add_parser("stats", help=T("statistiques d'une plongée ou du carnet"))
    stats.add_argument("number", nargs="?", type=int, help=T("numéro de plongée"))

    hidden = subparsers.add_parser(
        "hidden", help=T("liste les plongées masquées, ou en restaure une")
    )
    hidden.add_argument(
        "--restore",
        metavar=T("EMPREINTE"),
        help=T("rend une plongée masquée à nouveau importable"),
    )
    hidden.add_argument(
        "--hide",
        metavar=T("NUMERO"),
        type=int,
        help=T("masque la plongée portant ce numéro : elle quitte le carnet et "
        "ne sera plus importée"),
    )

    dump = subparsers.add_parser("dump", help=T("copie la mémoire flash dans un fichier"))
    dump.add_argument("output", type=Path, help=T("fichier de destination"))
    dump.add_argument("--port", help=T("port série (défaut : détection automatique)"))

    return parser


def main(argv: list[str] | None = None) -> int:
    # La langue doit etre choisie avant de construire l'analyseur d'arguments,
    # sinon son aide s'affiche dans la langue du code source.
    config.apply()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING - min(args.verbose, 2) * 10,
        format="%(levelname)-7s %(name)s: %(message)s",
    )

    command = args.command or "ui"
    handlers = {
        "ui": _cmd_ui,
        "ports": _cmd_ports,
        "models": _cmd_models,
        "diagnostic": _cmd_diagnostic,
        "import": _cmd_import,
        "list": _cmd_list,
        "stats": _cmd_stats,
        "hidden": _cmd_hidden,
        "dump": _cmd_dump,
    }
    return handlers[command](args)


def _cmd_ui(args: argparse.Namespace) -> int:
    from .app import run_gui

    return run_gui(db_path=args.db)


def _cmd_models(_args: argparse.Namespace) -> int:
    """Recapitule ce que l'application sait lire, et comment."""
    families = {
        Family.ICONHD: T("lecture directe de la memoire flash"),
        Family.SMART: T("memoire flash, entete organisee autrement"),
        Family.GENIUS: T("protocole par objets"),
    }
    for family, description in families.items():
        names = sorted(
            {spec.name for spec in MODELS.values() if spec.family is family}
        )
        print(f"{family.value} - {description}")
        for name in names:
            spec = MODELS[name]
            air = T(", integration d'air") if spec.air_integration else ""
            print(T("    Mares {name}{air}").format(name=name, air=air))
        print()
    return 0


def _cmd_diagnostic(_args: argparse.Namespace) -> int:
    print(config.diagnostic().as_text())
    return 0


def _cmd_ports(_args: argparse.Namespace) -> int:
    ports = list_serial_ports()
    if not ports:
        print(T("Aucun port série détecté."))
        return 1
    print(T("Ports série (* = convertisseur USB reconnu) :"))
    for port in ports:
        print(" ", port.label)
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        try:
            result = import_from_port(
                db,
                args.port,
                demo=args.demo,
                demo_model=args.demo_model or config.settings().demo_model,
                limit=args.limit,
                full=args.full,
                progress=lambda step, done, total: print(f"  {step}", file=sys.stderr),
            )
        except (OSError, RuntimeError) as exc:
            print(T("Échec : {exc}").format(exc=exc), file=sys.stderr)
            return 1
        print(result.message)
        for dive in result.added:
            print(
                f"  #{dive.number} {dive.started_at:%d/%m/%Y %H:%M} "
                f"{dive.max_depth:5.1f} m  {dive.duration_label:>6}  {dive.gas_label}"
            )
        for error in result.errors:
            print(f"  ! {error}", file=sys.stderr)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        rows = db.list_dives(order="asc" if args.asc else "desc")
        if not rows:
            print(T("Base vide. Lancez `thermocline import` (ou `--demo`)."))
            return 0
        print(
            T("{number:>4} {date:<17} {duration:>7} {max:>7} {avg:>7} "
              "{temp:>6}  {gas:<14} {site}").format(
                number=T("N°"),
                date=T("Date"),
                duration=T("Durée"),
                max=T("Max"),
                avg=T("Moy"),
                temp=T("Temp"),
                gas=T("Gaz"),
                site=T("Site"),
            )
        )
        for row in rows:
            temp = f"{row.temp_min:.0f}°" if row.temp_min is not None else "-"
            print(
                f"{row.number:>4} {row.started_at:%d/%m/%Y %H:%M} "
                f"{row.duration_label:>7} {row.max_depth:>6.1f}m "
                f"{(row.avg_depth or 0):>6.1f}m {temp:>6}  "
                f"{row.gas_label:<14} {row.site}"
            )
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        rows = db.list_dives(order="asc")
        if not rows:
            print(T("Base vide."))
            return 0
        if args.number is None:
            return _print_overview(rows)
        matches = [row for row in rows if row.number == args.number]
        if not matches:
            print(T("Aucune plongée n° {number}.").format(number=args.number), file=sys.stderr)
            return 1
        return _print_dive_stats(db, matches[0])


def _print_overview(rows) -> int:
    overview = compute_overview(rows)
    print(T("Plongées              {total_dives}").format(total_dives=overview.total_dives))
    print(T("Temps immergé         {total_duration_label}").format(total_duration_label=overview.total_duration_label))
    print(T("Profondeur max        {max_depth:.1f} m").format(max_depth=overview.max_depth))
    print(T("Profondeur moyenne    {avg_depth:.1f} m").format(avg_depth=overview.avg_depth))
    print(T("Durée moyenne         {pretty_duration}").format(pretty_duration=pretty_duration(overview.avg_duration)))
    if overview.deepest:
        print(
            T("Record de profondeur  {max_depth:.1f} m ({where})").format(
                max_depth=overview.deepest.max_depth,
                where=overview.deepest.site or overview.deepest.started_at.date(),
            )
        )
    if overview.longest:
        print(
            T("Plus longue           {duration_label} ({where})").format(
                duration_label=overview.longest.duration_label,
                where=overview.longest.site or overview.longest.started_at.date(),
            )
        )
    print(T("Par année            "), ", ".join(f"{y}: {n}" for y, n in overview.per_year))
    print(T("Modes                "), ", ".join(f"{m}: {n}" for m, n in overview.modes))
    return 0


def _print_dive_stats(db: Database, summary) -> int:
    dive = db.load_dive(summary.uid)
    if dive is None:
        return 1
    stats = compute(
        dive,
        tank_volume=summary.tank_volume,
        pressure_start=summary.pressure_start,
        pressure_end=summary.pressure_end,
    )
    print(T("Plongée n° {number} — {datetime:%d/%m/%Y %H:%M} — {label}").format(number=summary.number, datetime=dive.datetime, label=dive.mode.label))
    print(T("  Site                  {site}").format(site=summary.site or "-"))
    print(T("  Durée                 {pretty_duration}").format(pretty_duration=pretty_duration(stats.duration)))
    print(T("  Profondeur max        {max_depth:.1f} m (atteinte à {pretty_duration})").format(max_depth=stats.max_depth, pretty_duration=pretty_duration(stats.time_to_max_depth)))
    print(T("  Profondeur moyenne    {avg_depth:.1f} m").format(avg_depth=stats.avg_depth))
    print(T("  Temps au fond (>80%)  {pretty_duration}").format(pretty_duration=pretty_duration(stats.bottom_time)))
    print(T("  Température           {temp_min:.1f} à {temp_max:.1f} °C").format(temp_min=stats.temp_min, temp_max=stats.temp_max))
    print(T("  Descente max          {descent_rate_max:.1f} m/min").format(descent_rate_max=stats.descent_rate_max))
    print(T("  Remontée max          {ascent_rate_max:.1f} m/min ({pretty_duration} au-delà de la limite)").format(ascent_rate_max=stats.ascent_rate_max, pretty_duration=pretty_duration(stats.fast_ascent_seconds)))
    print(T("  Palier 3-6 m          {pretty_duration}").format(pretty_duration=pretty_duration(stats.safety_stop_seconds)))
    print(T("  Mélanges              {gas_label}").format(gas_label=dive.gas_label))
    print(T("  ppO2 max              {max_ppo2:.2f} bar").format(max_ppo2=stats.max_ppo2))
    print(T("  CNS / OTU             {cns:.1f} % / {otu:.0f}").format(cns=stats.cns, otu=stats.otu))
    if stats.ead_max is not None:
        print(T("  Prof. équivalente air {ead_max:.1f} m").format(ead_max=stats.ead_max))
    if stats.sac:
        print(T("  Consommation          {sac:.1f} L/min ({gas_used:.0f} L)").format(sac=stats.sac, gas_used=stats.gas_used))
    print(T("  Échantillons          {len} toutes les {sample_interval} s").format(len=len(dive.samples), sample_interval=dive.sample_interval))
    return 0


def _cmd_hidden(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        if args.hide is not None:
            matches = [row for row in db.list_dives() if row.number == args.hide]
            if not matches:
                print(T("Aucune plongée n° {hide}.").format(hide=args.hide), file=sys.stderr)
                return 1
            target = matches[0]
            db.hide_dive(target.uid)
            print(T("Masquée : {label}").format(label=target.label))
            print(T("Elle ne sera plus importée, même avec --full."))
            return 0

        if args.restore:
            entries = [e for e in db.hidden_dives() if e.fingerprint == args.restore]
            if not entries:
                print(T("Aucune plongée masquée d'empreinte {restore}.").format(restore=args.restore), file=sys.stderr)
                return 1
            entry = entries[0]
            db.restore_hidden(entry.device_serial, entry.fingerprint)
            print(T("Restaurée : {label}").format(label=entry.label))
            print(T("Relancez `thermocline import --full` pour la récupérer."))
            return 0

        entries = db.hidden_dives()
        if not entries:
            print(T("Aucune plongée masquée."))
            return 0
        print(T("{len} plongée(s) masquée(s) :").format(len=len(entries)))
        for entry in entries:
            print(f"  {entry.fingerprint}  {entry.label}")
        print(T("\nPour en restaurer une : thermocline hidden --restore <empreinte>"))
    return 0


def _cmd_dump(args: argparse.Namespace) -> int:
    source = open_source(port=args.port)
    try:
        info = source.connect()
        print(T("Connecté : {label}").format(label=info.label))
        total = getattr(source, "layout").memsize
        print(T("Lecture de {total} octets, cela prend plusieurs minutes…").format(total=total))

        def report(done: int, size: int) -> None:
            print(f"\r  {done * 100 // size:3d} %", end="", file=sys.stderr)

        data = source.dump_memory(progress=report)  # type: ignore[attr-defined]
        print()
        args.output.write_bytes(data)
        print(T("{len} octets ecrits dans {output}").format(len=len(data), output=args.output))
    except (OSError, RuntimeError) as exc:
        print(T("Échec : {exc}").format(exc=exc), file=sys.stderr)
        return 1
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
