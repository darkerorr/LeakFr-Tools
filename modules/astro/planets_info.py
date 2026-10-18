from rich.table import Table
from core.common import console, choisir_option, titre, pause, kv, BX, C_ASTRO, C_GOLD

PLANETES= [
    dict(nom="Mercure", rayon="2 439", g=3.70, temp="167", dist="57,9", masse="0,33",
         jour='58,6 j', annee='88 j', lunes='0',
         fait="Un jour solaire y dure 176 jours terrestres, plus long que son année."),
    dict(nom="Vénus", rayon="6 052", g=8.87, temp="464", dist="108,2", masse="4,87",
         jour='243 j (rétrograde)', annee='225 j', lunes='0',
         fait="La planète la plus chaude du système solaire, à cause de son atmosphère de CO2."),
    dict(nom="Terre", rayon="6 371", g=9.81, temp="15", dist="149,6", masse="5,97",
         jour='23 h 56', annee='365,25 j', lunes='1',
         fait="Seule planète connue à abriter la vie."),
    dict(nom="Mars", rayon="3 390", g=3.71, temp="-65", dist="227,9", masse="0,642",
         jour='24 h 37', annee='687 j', lunes='2',
         fait="Abrite Olympus Mons, le plus haut volcan connu du système solaire (~22 km)."),
    dict(nom="Jupiter", rayon="69 911", g=24.79, temp="-110", dist="778,5", masse="1 898",
         jour='9 h 56', annee='11,9 ans', lunes='95+',
         fait="La plus grosse planète : plus de 1 300 Terres tiendraient dedans."),
    dict(nom="Saturne", rayon="58 232", g=10.44, temp="-140", dist="1 433", masse="568",
         jour='~10 h 33', annee='29,5 ans', lunes='270+',
         fait="Moins dense que l'eau. Ses anneaux sont surtout faits de glace d'eau."),
    dict(nom="Uranus", rayon="25 362", g=8.87, temp="-195", dist="2 872", masse="86,8",
         jour='17 h 14 (rétrograde)', annee='84 ans', lunes='28+',
         fait="Son axe est incliné d'environ 98° : elle tourne presque couchée."),
    dict(nom="Neptune", rayon="24 622", g=11.15, temp="-200", dist="4 495", masse="102",
         jour='16 h 6', annee='164,8 ans', lunes='20+',
         fait="Des vents de plus de 2 000 km/h, les plus rapides du système solaire."),
]

def planetes():
    while True:
        titre('PLANÈTES DU SYSTÈME SOLAIRE', C_ASTRO)
        t = Table(box=BX, border_style=C_ASTRO, header_style=f"bold {C_ASTRO}")
        t.add_column("Planète", style="bold")
        t.add_column('Rayon (km)', justify='right')
        t.add_column("Gravité (m/s²)", justify="right")
        t.add_column("Temp. moy. (°C)", justify="right")
        t.add_column('Dist. Soleil (M km)', justify='right')
        t.add_column("Jour")
        t.add_column("Année")
        t.add_column('Lunes', justify='right')
        for p in PLANETES:
            t.add_row(p["nom"], p["rayon"], str(p["g"]).replace(".", ","),
                      p['temp'], p['dist'], p['jour'], p['annee'], p['lunes'])
        console.print(t)
        choix = choisir_option("FICHE D'UNE PLANETE", [p["nom"] for p in PLANETES] + ["Retour"])
        if choix in (None, 'Retour'):
            return
        p= next(planet for planet in PLANETES if planet["nom"] ==choix)
        console.print()
        kv(f"Fiche : {p['nom']}", [
            ("Masse", f"{p['masse']} x 10^24 kg"),
            ('Rayon moyen', f"{p["rayon"]} km"),
            ("Gravité", f"{p['g']} m/s²  ({p['g'] / 9.81:.2f} g)"),
            ("Température moyenne", f"{p['temp']} °C"),
            ('Distance au Soleil', f"{p["dist"]} millions de km"),
            ("Durée du jour", p["jour"]),
            ("Durée de l'année", p["annee"]),
            ('Lunes connues', p['lunes']),
            ("À savoir", p["fait"]),
        ], C_ASTRO)
        pause()
