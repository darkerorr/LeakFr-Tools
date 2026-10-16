# Discord — outils publics et administration du bot

Les outils publics lisent des données publiquement accessibles. Le panneau d’administration utilise un **token de bot** fourni localement et les permissions réellement attribuées au bot. Les tokens sont des secrets : ne les copiez jamais dans un dépôt, une capture ou un rapport. Les tokens utilisateur/self-bots ne sont pas pris en charge par le panneau.

![Aperçu de la catégorie Discord](../../docs/screenshots/categories/discord.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Panel Bot Discord | Dashboard Gateway, cible, présence, salons, rôles, webhooks, permission, surnom, invitation et export JSON. | ![Panel](../../docs/screenshots/modules/discord/panel-bot-discord.svg) |
| Lookup ID Discord | Affiche les informations publiques associées à un identifiant. | ![Lookup](../../docs/screenshots/modules/discord/lookup-id-discord.svg) |
| Info Webhook | Consulte les métadonnées visibles d’un webhook donné. | ![Webhook](../../docs/screenshots/modules/discord/info-webhook.svg) |
| Envoi / Test Webhook | Envoie un message de test via un webhook que vous contrôlez. | ![Envoi webhook](../../docs/screenshots/modules/discord/envoi-test-webhook.svg) |
| Supprimer Webhook | Supprime le webhook fourni après confirmation. | ![Suppression](../../docs/screenshots/modules/discord/supprimer-webhook.svg) |
| Info Bot Token | Vérifie des informations disponibles sur votre bot. | ![Bot token](../../docs/screenshots/modules/discord/info-bot-token.svg) |
| Resolveur Invitation | Consulte les informations publiques d’une invitation. | ![Invitation](../../docs/screenshots/modules/discord/resolveur-invitation.svg) |
| Widget Serveur | Consulte le widget public d’un serveur lorsque celui-ci est activé. | ![Widget](../../docs/screenshots/modules/discord/widget-serveur.svg) |
| Décodeur Snowflake | Convertit un identifiant Discord en timestamp et composants techniques. | ![Snowflake](../../docs/screenshots/modules/discord/decodeur-snowflake.svg) |
| Générateur OAuth Bot | Prépare un lien d’installation et des permissions OAuth choisies. | ![OAuth](../../docs/screenshots/modules/discord/generateur-oauth-bot.svg) |

## Panel Bot — actions

- `1` connexion/déconnexion de la Gateway, `2` cible et chargement du serveur, `3` statut/activité.
- `4` liste des salons et création de salon, `5` rôles, `6` webhooks (jetons toujours masqués), `7` message confirmé.
- `8` actualisation, `9` permissions de rôles, `10` surnom du bot confirmé, `11` invitation limitée à une heure et une utilisation, `12` export JSON sans tokens ni messages.
- `0` déconnexion et retour.

L’audit de permissions additionne les permissions des rôles, mais ne calcule pas les surcharges spécifiques de salons. L’export et les changements de serveur sont à examiner avant utilisation. N’accordez que les permissions nécessaires.

Les visuels du guide sont des aperçus statiques du menu, sans connexion réelle à Discord.
