"""
FantaBot Telegram - Gestione Fantacalcio Calcio a 5
Regole:
  - 7 giocatori: 1 POR + 6 CAM
  - Budget massimo 100 crediti
  - Max 2 giocatori della stessa squadra reale
  - Almeno 1 giocatore con status "O" (fuori lista)
  - Max 1 giocatore fuori lista
  - Nome squadra obbligatorio
"""

import logging
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from google_sheets import save_to_sheet
from players import PLAYERS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── CONFIGURAZIONE — lette da variabili d'ambiente Railway ───────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

SQUAD_SIZE      = 7
MAX_POR         = 1
MAX_CAM         = 6
BUDGET          = 100
MAX_PER_SQUADRA = 2

# ─── STATI ─────────────────────────────────────────────────────────────────────
INSERISCI_NOME, SELECTING = range(2)

# ─── ESCAPE MARKDOWN ───────────────────────────────────────────────────────────
def esc(text: str) -> str:
    return re.sub(r"([_*`\[\]])", r"\\\1", str(text))

# ─── UTILITIES ─────────────────────────────────────────────────────────────────
def get_selected(context):
    return context.user_data.get("selected", [])

def get_player(pid):
    return next((p for p in PLAYERS if p["id"] == pid), None)

def calc_total(selected_ids):
    return round(sum(
        p["quotazione"] for pid in selected_ids
        for p in PLAYERS if p["id"] == pid
    ), 1)

def count_ruolo(selected_ids, ruolo):
    return sum(1 for pid in selected_ids if (p := get_player(pid)) and p["ruolo"] == ruolo)

def count_per_squadra(selected_ids):
    counts = {}
    for pid in selected_ids:
        p = get_player(pid)
        if p:
            counts[p["squadra"]] = counts.get(p["squadra"], 0) + 1
    return counts

def ha_giocatore_O(selected_ids):
    return any(get_player(pid) and get_player(pid)["status"] == "O" for pid in selected_ids)

def toggle_player(context, player_id):
    sel = get_selected(context)
    p = get_player(player_id)
    if not p:
        return None

    if player_id in sel:
        sel.remove(player_id)
        context.user_data["selected"] = sel
        return None

    if len(sel) >= SQUAD_SIZE:
        return f"⛔ Hai già {SQUAD_SIZE} giocatori!"

    if p["ruolo"] == "POR" and count_ruolo(sel, "POR") >= MAX_POR:
        return f"⛔ Puoi avere solo {MAX_POR} portiere!"
    if p["ruolo"] == "CAM" and count_ruolo(sel, "CAM") >= MAX_CAM:
        return f"⛔ Puoi avere solo {MAX_CAM} giocatori di campo!"

    totale = calc_total(sel)
    if totale + p["quotazione"] > BUDGET:
        return f"⛔ Budget insufficiente! Rimangono {BUDGET - totale:.0f} crediti, questo ne costa {int(p['quotazione'])}."

    counts = count_per_squadra(sel)
    if counts.get(p["squadra"], 0) >= MAX_PER_SQUADRA:
        return f"⛔ Hai già {MAX_PER_SQUADRA} giocatori di {p['squadra']}!"

    if p["status"] == "O" and ha_giocatore_O(sel):
        return "⛔ Puoi selezionare solo 1 giocatore fuori lista ⭕!"

    sel.append(player_id)
    context.user_data["selected"] = sel
    return None

def build_keyboard(selected, page=0):
    PAGE_SIZE = 8
    start = page * PAGE_SIZE
    chunk = PLAYERS[start:start + PAGE_SIZE]
    total_pages = (len(PLAYERS) + PAGE_SIZE - 1) // PAGE_SIZE
    total = calc_total(selected)
    counts = count_per_squadra(selected)
    n_por = count_ruolo(selected, "POR")
    n_cam = count_ruolo(selected, "CAM")

    keyboard = []
    for p in chunk:
        badge = "⭕ " if p["status"] == "O" else ""
        if p["id"] in selected:
            label = f"✅ {badge}{p['nome']} [{p['ruolo']}] — {int(p['quotazione'])}⭐"
        elif p["ruolo"] == "POR" and n_por >= MAX_POR:
            label = f"🔒 {p['nome']} [POR] — {int(p['quotazione'])}⭐"
        elif p["ruolo"] == "CAM" and n_cam >= MAX_CAM:
            label = f"🔒 {p['nome']} [CAM] — {int(p['quotazione'])}⭐"
        elif total + p["quotazione"] > BUDGET:
            label = f"💸 {badge}{p['nome']} [{p['ruolo']}] — {int(p['quotazione'])}⭐"
        elif counts.get(p["squadra"], 0) >= MAX_PER_SQUADRA:
            label = f"🚫 {badge}{p['nome']} [{p['ruolo']}] — {int(p['quotazione'])}⭐"
        elif p["status"] == "O" and ha_giocatore_O(selected) and p["id"] not in selected:
            label = f"🔒 ⭕ {p['nome']} [{p['ruolo']}] — {int(p['quotazione'])}⭐"
        else:
            label = f"{badge}{p['nome']} [{p['ruolo']}] — {int(p['quotazione'])}⭐"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"sel_{p['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if start + PAGE_SIZE < len(PLAYERS):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    keyboard.append(nav)

    n_sel = len(selected)
    keyboard.append([InlineKeyboardButton(
        f"📋 Invia ({n_sel}/{SQUAD_SIZE} | 🧤{n_por}/{MAX_POR} ⚽{n_cam}/{MAX_CAM} | 💰{total}/{BUDGET})",
        callback_data="submit"
    )])
    keyboard.append([InlineKeyboardButton("🗑️ Reset selezione", callback_data="reset")])

    return InlineKeyboardMarkup(keyboard)

def status_text(selected, nome_squadra):
    total = calc_total(selected)
    rimanenti = BUDGET - total
    n_por = count_ruolo(selected, "POR")
    n_cam = count_ruolo(selected, "CAM")
    bar = "🟢" if rimanenti > 20 else ("🟡" if rimanenti > 0 else "🔴")
    ha_o = "✅" if ha_giocatore_O(selected) else "❌"
    return (
        f"🏟️ *{esc(nome_squadra)}*\n\n"
        f"🧤 Portiere: *{n_por}/{MAX_POR}*\n"
        f"⚽ Campo: *{n_cam}/{MAX_CAM}*\n"
        f"{bar} Crediti: *{total}/{BUDGET}* (rimangono *{rimanenti:.0f}*)\n"
        f"{ha_o} Giocatore ⭕ fuori lista: {'presente' if ha_giocatore_O(selected) else 'mancante!'}\n\n"
        f"_⭕=fuori lista  🔒=slot pieno  💸=costoso  🚫=max 2 per squadra_"
    )

def squad_summary(user, selected_ids, nome_squadra):
    lines = [
        f"🏆 *{esc(nome_squadra)}*",
        f"_Fantallenatore: {esc(user.first_name)} {esc(user.last_name or '')}_\n"
    ]

    por = [p for pid in selected_ids for p in PLAYERS if p["id"] == pid and p["ruolo"] == "POR"]
    cam = [p for pid in selected_ids for p in PLAYERS if p["id"] == pid and p["ruolo"] == "CAM"]

    if por:
        lines.append("🧤 *Portiere*")
        for p in por:
            badge = " ⭕" if p["status"] == "O" else ""
            lines.append(f"  • {esc(p['nome'])}{badge} ({esc(p['squadra'])}) — {int(p['quotazione'])}⭐")
    if cam:
        lines.append("⚽ *Giocatori di campo*")
        for p in cam:
            badge = " ⭕" if p["status"] == "O" else ""
            lines.append(f"  • {esc(p['nome'])}{badge} ({esc(p['squadra'])}) — {int(p['quotazione'])}⭐")

    total = calc_total(selected_ids)
    lines.append(f"\n💰 *Crediti spesi: {total}/{BUDGET}*")
    lines.append(f"👤 *Username:* @{esc(user.username or 'N/A')}")
    lines.append(f"🆔 *User ID:* `{user.id}`")
    return "\n".join(lines)

# ─── HANDLERS ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["selected"] = []
    context.user_data["page"] = 0
    context.user_data["nome_squadra"] = ""
    await update.message.reply_text(
        "⚽ *Benvenuto nel FantaBot Calcio a 5\\!*\n\n"
        "Prima di tutto, *come si chiama la tua fantasquadra?* 🏟️\n\n"
        "Scrivi il nome qui sotto:",
        parse_mode="Markdown"
    )
    return INSERISCI_NOME

async def ricevi_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    if len(nome) < 2:
        await update.message.reply_text("⚠️ Nome troppo corto\\! Inserisci almeno 2 caratteri:", parse_mode="Markdown")
        return INSERISCI_NOME
    if len(nome) > 30:
        await update.message.reply_text("⚠️ Nome troppo lungo\\! Massimo 30 caratteri:", parse_mode="Markdown")
        return INSERISCI_NOME

    context.user_data["nome_squadra"] = nome
    await update.message.reply_text(
        f"🎉 Perfetto\\! La tua squadra si chiama *{esc(nome)}*\n\n"
        f"Ora componi la rosa rispettando queste regole:\n\n"
        f"🧤 *1 portiere* \\+ ⚽ *6 giocatori di campo*\n"
        f"💰 Budget massimo: *{BUDGET} crediti*\n"
        f"🚫 Max *{MAX_PER_SQUADRA} giocatori* della stessa squadra\n"
        f"⭕ Esattamente *1 giocatore fuori lista* \\(marcati ⭕\\)\n",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Avvia selezione", callback_data="page_0")
        ]])
    )
    return SELECTING

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    nome_squadra = context.user_data.get("nome_squadra", "La mia squadra")

    if data == "noop":
        return SELECTING

    if data.startswith("sel_"):
        pid = data[4:]
        errore = toggle_player(context, pid)
        if errore:
            await query.answer(errore, show_alert=True)
            return SELECTING
        page = context.user_data.get("page", 0)
        sel = get_selected(context)
        await query.edit_message_text(
            text=status_text(sel, nome_squadra),
            parse_mode="Markdown",
            reply_markup=build_keyboard(sel, page)
        )

    elif data.startswith("page_"):
        page = int(data[5:])
        context.user_data["page"] = page
        sel = get_selected(context)
        await query.edit_message_text(
            text=status_text(sel, nome_squadra),
            parse_mode="Markdown",
            reply_markup=build_keyboard(sel, page)
        )

    elif data == "reset":
        context.user_data["selected"] = []
        await query.edit_message_text(
            text=f"🗑️ Selezione azzerata\\.\n\n🏟️ *{esc(nome_squadra)}* — ricomincia\\!",
            parse_mode="Markdown",
            reply_markup=build_keyboard([], 0)
        )

    elif data == "submit":
        sel = get_selected(context)

        if len(sel) != SQUAD_SIZE:
            await query.answer(f"⚠️ Servono {SQUAD_SIZE} giocatori! (hai {len(sel)})", show_alert=True)
            return SELECTING
        if count_ruolo(sel, "POR") != MAX_POR:
            await query.answer(f"🧤 Devi selezionare esattamente {MAX_POR} portiere!", show_alert=True)
            return SELECTING
        if count_ruolo(sel, "CAM") != MAX_CAM:
            await query.answer(f"⚽ Devi selezionare esattamente {MAX_CAM} giocatori di campo!", show_alert=True)
            return SELECTING
        if not ha_giocatore_O(sel):
            await query.answer("⭕ Devi includere 1 giocatore fuori lista (marcati con ⭕)!", show_alert=True)
            return SELECTING

        user = query.from_user
        summary = squad_summary(user, sel, nome_squadra)

        await query.edit_message_text(
            text=f"✅ *Squadra inviata all'admin\\!*\n\n{summary}",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📨 *Nuova fantasquadra ricevuta\\!*\n\n{summary}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Errore invio admin: {e}")

        try:
            players_data = [p for pid in sel for p in PLAYERS if p["id"] == pid]
            save_to_sheet(user, players_data, calc_total(sel), nome_squadra)
            await context.bot.send_message(chat_id=user.id, text="✅ Squadra salvata su Google Sheets!")
        except Exception as e:
            logger.error(f"Errore Google Sheets: {e}")
            await context.bot.send_message(chat_id=user.id, text="⚠️ Errore Google Sheets. Contatta l'admin.")

        context.user_data["selected"] = []
        return ConversationHandler.END

    return SELECTING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata\\. Usa /start per ricominciare\\.", parse_mode="Markdown")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INSERISCI_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_nome)],
            SELECTING:      [CallbackQueryHandler(button_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("🤖 FantaBot avviato!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
