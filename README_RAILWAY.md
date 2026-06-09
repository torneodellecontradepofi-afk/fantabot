# FantaBot — Deploy su Railway

## Variabili d'ambiente da impostare su Railway

Vai su Railway → il tuo progetto → **Variables** e aggiungi:

| Variabile | Valore |
|---|---|
| `TELEGRAM_TOKEN` | Il token del bot da BotFather |
| `ADMIN_CHAT_ID` | Il tuo Chat ID numerico |
| `SPREADSHEET_ID` | L'ID del Google Sheet |
| `GOOGLE_CREDENTIALS` | Il contenuto intero del file credentials.json |

### Come copiare GOOGLE_CREDENTIALS
1. Apri `credentials.json` con TextEdit
2. Seleziona tutto (Cmd+A) e copia (Cmd+C)
3. Incolla come valore della variabile su Railway

## Deploy
1. Crea account su https://railway.app
2. New Project → Deploy from GitHub repo
3. Collega questo repository
4. Aggiungi le variabili d'ambiente
5. Railway fa partire il bot automaticamente
