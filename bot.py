from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import gspread
from telegram.ext import CallbackQueryHandler
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === Google Sheets подключение через переменную среды ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if not credentials_json:
    raise Exception("Переменная GOOGLE_CREDENTIALS_JSON не найдена!")

creds_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("SharSalut_Bot").worksheet("Users")
orders_sheet = client.open("SharSalut_Bot").worksheet("Orders")
history_sheet = client.open("SharSalut_Bot").worksheet("History")

MANAGER_ID = 265458870
ADMINS = [265458870]  # 👈 Обязательно!


# Этапы анкеты и заказа
NAME, PHONE, GENDER = range(3)
ORDER_DATE, OCCASION, WHAT_TO_ORDER, COMMENT, ADDRESS = range(3, 8)

# Этапы для админки
ADMIN_MENU, CHOOSE_PHONE, ENTER_AMOUNT, ENTER_REASON, BROADCAST_CHOOSE, BROADCAST_TEXT = range(100, 106)
CASHBACK_PHONE, CASHBACK_AMOUNT = range(106, 108)

main_menu = ReplyKeyboardMarkup([
    ["🎈 Мои баллы", "📩 Оформить заявку"],
    ["👯 Пригласи друга", "⭐️ Оставить отзыв"],
    ["🎁 Акции и бонусы", "🧩 Профиль"]
], resize_keyboard=True)

cancel_order_kb = ReplyKeyboardMarkup([["🔙 Отменить заявку"]], resize_keyboard=True)

# === START / REGISTRATION ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # Сохраняем ID пригласившего, если передан через ссылку
    if context.args:
        context.user_data["ref_id"] = context.args[0]


    await update.message.reply_text("Привет! Давай начнём регистрацию. Как тебя зовут?")
    return NAME


async def bonuses_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎁 *Акции и бонусы:*\n\n"
        "1️⃣ *Кэшбэк с заказа* — до 10%:\n"
        "• От 3000₽ — 5%\n"
        "• От 5000₽ — 7%\n"
        "• От 10000₽ — 10%\n\n"
        "2️⃣ *За отзыв на Яндекс Картах* — 500 баллов\n"
        "3️⃣ *Приведи друга* —\n"
        "• Ты получишь 500 баллов\n"
        "• Друг получит 5 шариков 🎁\n"
        "• Отправь ему ссылку из раздела *«Пригласи друга»*\n\n"
        "Баллы можно тратить до 15% от суммы заказа.Не суммируются с акциями.\n"
        "Срок действия — 1 год.",
        parse_mode="Markdown"
    )


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Отлично! Теперь напиши свой номер телефона (через 8...):")
    return PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    gender_kb = ReplyKeyboardMarkup([["Женский", "Мужской"]], resize_keyboard=True)
    await update.message.reply_text("Укажи свой пол:", reply_markup=gender_kb)
    return GENDER

async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gender"] = update.message.text
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    user_id = str(update.effective_user.id)
    all_records = sheet.get_all_records()
    for row in all_records:
        if str(row["ID"]) == user_id:
            await update.message.reply_text("👋 Ты уже зарегистрирован!", reply_markup=main_menu)
            return ConversationHandler.END

    try:
        sheet.append_row([
    user_id,
    context.user_data["name"],
    context.user_data["phone"],
    context.user_data["gender"],
    context.user_data.get("ref_id", ""),  # 👈 сохраняем ID пригласившего
    300,
    now,
    ""
])


        history_sheet.append_row([
            user_id,
            now,
            "+",
            300,
            "Бонус за регистрацию"
        ])

        await context.bot.send_message(MANAGER_ID, f"👤 Новая регистрация:\nИмя: {context.user_data['name']}\nТелефон: {context.user_data['phone']}\nПол: {context.user_data['gender']}\nID: {update.effective_user.id}")

        await update.message.reply_text(
            "🎉 Ты получил 300 бонусных баллов за регистрацию!\nТеперь ты с нами — а значит, впереди много шаров, улыбок и приятных сюрпризов! 🎈",
            reply_markup=main_menu
        )

        await update.message.reply_text(
            "📌 Как получить баллы:\n"
            "• От 3000₽ — 5%\n"
            "• От 5000₽ — 7%\n"
            "• От 10000₽ — 10%\n"
            "• За отзыв: 500 баллов\n"
            "• За друга: 500 баллов\n\n"
            "📌 Как потратить:\n"
            "• До 15% от суммы заказа\n"
            "• Баллы действуют 1 год\n"
            "• Не суммируются с акциями"
        )

        return ConversationHandler.END
    except Exception as e:
        print(f"Ошибка при регистрации: {e}")
        await update.message.reply_text("⚠️ Что-то пошло не так при регистрации. Попробуй позже или напиши нам.")
        return ConversationHandler.END


# === ОФОРМЛЕНИЕ ЗАЯВКИ ===

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("На какую дату нужен заказ?", reply_markup=cancel_order_kb)
    return ORDER_DATE

async def order_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_date"] = update.message.text
    await update.message.reply_text("Что за чудо-повод? Расскажи! ✨", reply_markup=cancel_order_kb)
    return OCCASION

async def occasion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["occasion"] = update.message.text
    await update.message.reply_text("Что нужно — шары, композиции, что-то особенное?", reply_markup=cancel_order_kb)
    return WHAT_TO_ORDER

async def what_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["what"] = update.message.text
    await update.message.reply_text("Есть ли пожелания или комментарии?", reply_markup=cancel_order_kb)
    return COMMENT

async def comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text
    address_kb = ReplyKeyboardMarkup([
        ["Самовывоз", "Доставка"],
        ["🔙 Отменить заявку"]
    ], resize_keyboard=True)
    await update.message.reply_text("Укажи адрес или выбери 'Самовывоз':", reply_markup=address_kb)
    return ADDRESS

async def address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    orders_sheet.append_row([
        str(update.effective_user.id),
        context.user_data["order_date"],
        context.user_data["occasion"],
        context.user_data["what"],
        context.user_data["comment"],
        context.user_data["address"],
        now
    ])

    await context.bot.send_message(MANAGER_ID,
        f"📝 Новая заявка на заказ:\n"
        f"Дата: {context.user_data['order_date']}\n"
        f"Повод: {context.user_data['occasion']}\n"
        f"Что заказать: {context.user_data['what']}\n"
        f"Комментарий: {context.user_data['comment']}\n"
        f"Адрес: {context.user_data['address']}"
    )

    await update.message.reply_text("✅ Заявка принята! Мы свяжемся с тобой для уточнения деталей.", reply_markup=main_menu)
    return ConversationHandler.END

    await update.message.reply_text("Укажи адрес или выбери 'Самовывоз':", reply_markup=address_kb)
    return ADDRESS

    orders_sheet.append_row([
        str(update.effective_user.id),
        context.user_data.get("name", ""),
        context.user_data.get("phone", ""),
        context.user_data["order_date"],
        context.user_data["occasion"],
        context.user_data["what"],
        context.user_data["comment"],
        context.user_data["address"],
        now
    ])

    await context.bot.send_message(MANAGER_ID,
        f"📝 Новая заявка на заказ:\nДата: {context.user_data['order_date']}\nПовод: {context.user_data['occasion']}\n"
        f"Что заказать: {context.user_data['what']}\nКомментарий: {context.user_data['comment']}\nАдрес: {context.user_data['address']}"
    )

    await update.message.reply_text("✅ Заявка принята! Мы свяжемся с тобой для уточнения деталей.", reply_markup=main_menu)
    return ConversationHandler.END

# === ОСТАЛЬНЫЕ КНОПКИ ===
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    all_users = sheet.get_all_records()
    all_history = history_sheet.get_all_records()
    for row in all_users:
        if str(row["ID"]) == user_id:
            info = f"👤 Профиль:\nИмя: {row['Имя']}\nТелефон: {row['Телефон']}\nПол: {row['Пол']}\nБонусы: {row['Баллы']}"
            history_lines = [
                f"{h['Дата']}: {h['Тип (+/-)']} {h['Сумма']} — {h['Причина']}"
                for h in all_history if str(h["ID"]) == user_id
            ]
            history_text = "\n\n🕘 История операций:\n" + "\n".join(history_lines) if history_lines else "\n\nИстория пока пуста."
            await update.message.reply_text(info + history_text)
            return
    await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start")

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    all_records = sheet.get_all_records()
    for row in all_records:
        if str(row["ID"]) == user_id:
            await update.message.reply_text(
                f"🎈 У тебя {row['Баллы']} бонусных баллов!\n\n"
                "📌 Как получить:\n• От 3000₽ — 5%\n• От 5000₽ — 7%\n• От 10000₽ — 10%\n"
                "• За отзыв — 500 баллов\n• За друга — 500 баллов\n\n"
                "📌 Как потратить:\n• До 15% от заказа\n• Действуют 1 год\n• Не суммируются с акциями"
            )
            return
    await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start")

async def review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⭐️ Оставь отзыв на Яндекс.Картах:\n"
        "https://yandex.ru/maps/org/sharsalyut/71692700211\n\n"
        "Когда оставишь — пришли сюда скриншот отзыва!\n\n"
        "📌 За отзыв — 500 бонусных баллов."
    )

async def invite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"👯 Отправь другу эту ссылку: https://t.me/sharsalut_bot?start={user_id}\n\n"
        f"Если он закажет — ты получишь 500 баллов, а он — 5 шариков 🎁"
    )
     
# === АДМИНКА: Начисление, списание, рассылки ===
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

ADMIN_MENU, CHOOSE_PHONE, ENTER_AMOUNT, ENTER_REASON, BROADCAST_CHOOSE, BROADCAST_TEXT = range(100, 106)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    keyboard = ReplyKeyboardMarkup([
    ["➕ Начислить баллы", "➖ Списать баллы"],
    ["📢 Сделать рассылку", "💸 Начислить кэшбэк"]
], resize_keyboard=True)

    await update.message.reply_text("🔐 Админ-панель", reply_markup=keyboard)
    return ADMIN_MENU

async def choose_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["action"] = update.message.text
    await update.message.reply_text("📱 Введи номер телефона пользователя:")
    return CHOOSE_PHONE

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("💰 Введи количество баллов:")
    return ENTER_AMOUNT

async def enter_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["amount"] = int(update.message.text)
    await update.message.reply_text("✍️ Введи причину начисления/списания:")
    return ENTER_REASON
async def apply_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    phone = context.user_data["phone"]
    amount = context.user_data["amount"]
    sign = "+" if context.user_data["action"] == "➕ Начислить баллы" else "-"
    actual_amount = amount if sign == "+" else -amount
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    def normalize(phone):
        phone = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if phone.startswith("+7"):
            phone = "8" + phone[2:]
        elif phone.startswith("7"):
            phone = "8" + phone[1:]
        return phone

    normalized_input = normalize(phone)
    all_rows = sheet.get_all_records()

    for idx, row in enumerate(all_rows, start=2):  # строка 1 — заголовки
        row_phone = normalize(row.get("Телефон", ""))
        if row_phone == normalized_input:
            new_balance = int(row["Баллы"]) + actual_amount
            sheet.update_cell(idx, 6, new_balance)  # колонка F — Баллы
            history_sheet.append_row([row["ID"], now, sign, amount, reason])

            try:
                user_id = int(row["ID"])
                if 9 <= datetime.now().hour < 21:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"{'➕' if sign == '+' else '➖'} {amount} баллов\nПричина: {reason}"
                    )
            except:
                pass

            await update.message.reply_text(
                f"✅ Готово!\nИмя клиента: *{row['Имя']}*\n"
                f"Новый баланс: *{new_balance} баллов*",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

async def cashback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 Введи номер телефона клиента:")
    return CASHBACK_PHONE

async def cashback_phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cashback_phone"] = update.message.text.strip()
    await update.message.reply_text("💰 Введи сумму заказа (в рублях):")
    return CASHBACK_AMOUNT

async def apply_cashback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        phone = context.user_data.get("cashback_phone")
        percent = context.user_data.get("cashback_percent")
        amount_spent = int(update.message.text)
        cashback_amount = int(amount_spent * percent / 100)
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        all_rows = sheet.get_all_records()
        for idx, row in enumerate(all_rows, start=2):
            if normalize(row["Телефон"]) == normalize(phone):
                new_balance = int(row["Баллы"]) + cashback_amount
                sheet.update_cell(idx, 6, new_balance)
                history_sheet.append_row([row["ID"], now, "+", cashback_amount, f"Кэшбэк {percent}% с {amount_spent}₽"])

                try:
                    user_id = int(row["ID"])
                    if 9 <= datetime.now().hour < 21:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"💸 Начислен кэшбэк: +{cashback_amount} баллов\n{percent}% от суммы {amount_spent}₽"
                        )
                except:
                    pass

                await update.message.reply_text(
                    f"✅ Начислено {cashback_amount} баллов клиенту {row['Имя']} (кэшбэк {percent}% от {amount_spent}₽)"
                )
                return ConversationHandler.END

        await update.message.reply_text("❌ Пользователь с таким номером не найден.")
        return ConversationHandler.END
    except Exception as e:
        print(f"Ошибка при начислении кэшбэка: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуй ещё раз.")
        return ConversationHandler.END

def normalize_phone(phone):
    phone = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+7"):
        phone = "8" + phone[2:]
    elif phone.startswith("7"):
        phone = "8" + phone[1:]
    return phone

async def cashback_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        phone = normalize_phone(context.user_data["cashback_phone"])
        order_sum = int(update.message.text.strip())
        cashback = 0

        if order_sum >= 10000:
            cashback = int(order_sum * 0.10)
            percent = 10
        elif order_sum >= 5000:
            cashback = int(order_sum * 0.07)
            percent = 7
        elif order_sum >= 3000:
            cashback = int(order_sum * 0.05)
            percent = 5
        else:
            await update.message.reply_text("⚠️ Сумма заказа меньше 3000 руб. Кэшбэк не начисляется.")
            return ConversationHandler.END

        users = sheet.get_all_records()
        for i, row in enumerate(users):
            if normalize_phone(row["Телефон"]) == phone:
                sheet.update_cell(i + 2, 6, row["Баллы"] + cashback)  # Колонка F — Баллы
                history_sheet.append_row([
                row["ID"],
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                "+",
                cashback,
                f"Кэшбэк {percent}% с {order_sum}₽"
                ])
                await context.bot.send_message(
                    chat_id=row["ID"],
                    text=f"🎉 Начислен кэшбэк {cashback} баллов ({percent}% от суммы заказа {order_sum} руб.)"
                )
                await update.message.reply_text("✅ Кэшбэк успешно начислен.")
                return ConversationHandler.END

        await update.message.reply_text("⚠️ Пользователь не найден. Проверь номер телефона.")
        return ConversationHandler.END

    except Exception as e:
        print(f"Ошибка при начислении кэшбэка: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуй ещё раз.")
        return ConversationHandler.END




# === Рассылка через кнопки ===
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📬 Всем", callback_data="broadcast_all"),
            InlineKeyboardButton("👨 Мужчинам", callback_data="broadcast_men"),
        ],
        [
            InlineKeyboardButton("👩 Женщинам", callback_data="broadcast_women"),
            InlineKeyboardButton("💎 >2000 баллов", callback_data="broadcast_gt2000"),
        ],
        [
            InlineKeyboardButton("🔻 <500 баллов", callback_data="broadcast_lt500"),
            InlineKeyboardButton("❌ Нет баллов", callback_data="broadcast_0"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📢 Кому отправить рассылку?", reply_markup=reply_markup)
    return BROADCAST_CHOOSE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Действие отменено. Ты вернулся в главное меню.", reply_markup=main_menu)
    return ConversationHandler.END

async def broadcast_choose_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["broadcast_filter"] = query.data
    await query.edit_message_text("✍️ Введи текст рассылки:")
    return BROADCAST_TEXT

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("===> Вошли в функцию broadcast_send")

    text = update.message.text
    filter_key = context.user_data["broadcast_filter"]
    print(f"===> Выбран фильтр: {filter_key}")
    print(f"===> Текст рассылки: {text}")

    users = sheet.get_all_records()
    print(f"===> Всего пользователей в таблице: {len(users)}")

    count = 0

    filters_map = {
        "broadcast_all": lambda row: True,
        "broadcast_men": lambda row: row["Пол"] == "Мужской",
        "broadcast_women": lambda row: row["Пол"] == "Женский",
        "broadcast_gt2000": lambda row: int(row["Баллы"]) > 2000,
        "broadcast_lt500": lambda row: int(row["Баллы"]) < 500,
        "broadcast_0": lambda row: int(row["Баллы"]) == 0,
    }

    target_filter = filters_map.get(filter_key, lambda row: False)

    for row in users:
        if target_filter(row):
            try:
                print(f"===> Пытаемся отправить сообщение пользователю ID {row['ID']}")
                await context.bot.send_message(chat_id=row["ID"], text=text)
                count += 1
            except Exception as e:
                print(f"===> Ошибка при отправке пользователю ID {row['ID']}: {e}")
                continue

    await update.message.reply_text(f"✅ Рассылка отправлена {count} пользователям.")
    print(f"===> Рассылка завершена. Отправлено: {count}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено. Ты вернулся в главное меню.", reply_markup=main_menu)
    return ConversationHandler.END

 

# === ХЕНДЛЕРЫ ===
app = ApplicationBuilder().token("7802089142:AAFA3DCk2aWx5C-8Hd_bSMzfeJYpGA_G2O8").build()

reg_conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)],
        GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
    },
    fallbacks=[]
)

order_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📩 Оформить заявку$"), order_start)],
    states={
        ORDER_DATE: [
            MessageHandler(filters.Regex("^🔙 Отменить заявку$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_date)
        ],
        OCCASION: [
            MessageHandler(filters.Regex("^🔙 Отменить заявку$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, occasion)
        ],
        WHAT_TO_ORDER: [
            MessageHandler(filters.Regex("^🔙 Отменить заявку$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, what_to_order)
        ],
        COMMENT: [
            MessageHandler(filters.Regex("^🔙 Отменить заявку$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, comment)
        ],
        ADDRESS: [
            MessageHandler(filters.Regex("^🔙 Отменить заявку$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, address)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(reg_conv)
app.add_handler(order_conv)
app.add_handler(MessageHandler(filters.Regex("^🎈 Мои баллы$"), balance_handler))
app.add_handler(MessageHandler(filters.Regex("^🧩 Профиль$"), profile_handler))
app.add_handler(MessageHandler(filters.Regex("^👯 Пригласи друга$"), invite_handler))
app.add_handler(MessageHandler(filters.Regex("^⭐️ Оставить отзыв$"), review_handler))

CASHBACK_PHONE, CASHBACK_AMOUNT = range(200, 202)  # Добавь в начало файла, если ещё не добавлено

admin_conv = ConversationHandler(
    entry_points=[
        CommandHandler("admin", admin_start),
        MessageHandler(filters.Regex("^➕ Начислить баллы$"), choose_phone),
        MessageHandler(filters.Regex("^➖ Списать баллы$"), choose_phone),
        MessageHandler(filters.Regex("^📢 Сделать рассылку$"), broadcast_start),
        MessageHandler(filters.Regex("^💸 Начислить кэшбэк$"), cashback_handler),
    ],
    states={
        CHOOSE_PHONE: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount),
        ],
        ENTER_AMOUNT: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_reason),
        ],
        ENTER_REASON: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, apply_bonus),
        ],
        CASHBACK_PHONE: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_phone_handler),
        ],
        CASHBACK_AMOUNT: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_amount_handler),
        ],
        BROADCAST_CHOOSE: [
            CallbackQueryHandler(broadcast_choose_target, pattern="^broadcast_")
        ],
        BROADCAST_TEXT: [
            MessageHandler(filters.Regex("^🔙 Назад в админку$"), admin_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)



from telegram.ext import CallbackQueryHandler  # Сначала импорт


app.add_handler(CommandHandler("start", start))

app.add_handler(admin_conv)

app.add_handler(MessageHandler(filters.Regex("^🎁 Акции и бонусы$"), bonuses_handler))

app.run_polling()
