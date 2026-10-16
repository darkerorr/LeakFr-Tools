from datetime import datetime, timezone
from core.common import DISCORD_EPOCH, console, demander, titre, bad, kv, C_DISCORD

def snowflake_parser():
    titre("DÉCODEUR UNIVERSEL DE SNOWFLAKE DISCORD", C_DISCORD)
    console.print("[dim]Fonctionne pour n'importe quel ID Discord : Utilisateur, Serveur, Rôle, Salon, Message, Emoji...[/]\n")
    s_id = demander("Snowflake ID Discord")
    if not s_id.isdigit():
        bad("L'ID doit être composé uniquement de chiffres.")
        return

    val = int(s_id)
    timestamp_ms = (val >> 22) + DISCORD_EPOCH
    internal_worker = (val & 0x3E0000) >> 17
    internal_process = (val & 0x1F000) >> 12
    increment = val & 0xFFF
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)

    # Binaire découpé
    bin_str = bin(val)[2:].zfill(64)
    part_ts = bin_str[:42]
    part_w = bin_str[42:47]
    part_p = bin_str[47:52]
    part_inc = bin_str[52:]

    lignes = [
        ("Snowflake brut", s_id),
        ("Date exacte de création (UTC)", dt.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] + " UTC"),
        ("Date exacte (ISO)", dt.isoformat()),
        ("Timestamp Epoch (ms)", str(timestamp_ms)),
        ("Timestamp Epoch (s)", str(int(timestamp_ms / 1000))),
        ("Worker ID", str(internal_worker)),
        ("Process ID", str(internal_process)),
        ("Incrément", str(increment)),
        ("Structure Binaire 64-bit", f"{part_ts} | {part_w} | {part_p} | {part_inc}"),
    ]
    kv("Détails d'Architecture Snowflake", lignes, C_DISCORD)
