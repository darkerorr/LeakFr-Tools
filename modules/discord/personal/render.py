"""Rendu Rich du panel personnel Discord."""
from rich.panel import Panel
from rich.table import Table

from core.common import BX, C_DISCORD, C_GOLD, console
from modules.discord import permissions as perms
from modules.discord.personal.models import Profil


def render_profil(profil:Profil):
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {C_DISCORD}", width=22)
    table.add_column()
    table.add_row("Nom affiche", profil.libelle)
    table.add_row('Utilisateur', profil.username)
    table.add_row("ID", profil.id)
    table.add_row("Locale", profil.locale)
    table.add_row('MFA', 'active' if profil.mfa else 'non active')
    return Panel(table, box=BX, border_style=C_DISCORD,
                 title="[bold] Profil autorise (scope identify) [/]")


def render_serveurs(serveurs, titre="Serveurs accessibles"):
    table = Table(title=titre, box=BX, border_style=C_DISCORD)
    table.add_column("Serveur")
    table.add_column("ID", style="dim")
    table.add_column('Proprietaire')
    table.add_column("Administrateur")
    table.add_column("Fonctionnalites")
    for serveur in serveurs:
        table.add_row(
            serveur.nom,
            serveur.id,
            "oui" if serveur.proprietaire else "non",
            "oui" if perms.has_permission(serveur.permissions, perms.ADMINISTRATOR)
            else 'non',
            ", ".join(serveur.features[:3]) or "-",
        )
    return table


def render_historique(entrees):
    table = Table(title="Historique local (sans secret)", box=BX, border_style=C_GOLD)
    table.add_column("Date (UTC)")
    table.add_column('Action')
    table.add_column("Detail")
    for entree in entrees:
        table.add_row(str(entree.get('timestamp', '?')),
                      str(entree.get("action", "?")),
                      str(entree.get("detail") or "-"))
    return table


def afficher_serveurs(serveurs, titre='Serveurs accessibles'):
    if not serveurs:
        console.print("[yellow]Aucun serveur retourne par l'API OAuth2.[/]")
        return
    console.print(render_serveurs(serveurs, titre))
