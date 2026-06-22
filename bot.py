import asyncio
import logging
import json
import os
import random
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= НАСТРОЙКИ БОТА =================
BOT_TOKEN = "8873268549:AAGMpcDD5XSelX29i1mvWEDjtvfdI2r2qME"  
ADMIN_ID = 8246599178         
SUPPORT USERNAME = "UZcardAdminshop"  
# ===================================================

# 🔥 Находим точный абсолютный путь к папке, где лежит этот файл bot.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "db_shop.json")
TICKETS_FILE = os.path.join(BASE_DIR, "db_tickets.json")

# Глобальные переменные
USERS = set()
TICKETS = {}
PRODUCTS = {}
PAYMENT_CARD = "Не указана (настройте в админке)"
WELCOME_TEXT = "Добро пожаловать в наш магазин! Используйте кнопки ниже для навигации."
MAIN_PHOTO_ID = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- НАДЕЖНЫЕ ФУНКЦИИ СОХРАНЕНИЯ И ЗАГРУЗКИ ---

def save_data():
    """Сохраняет настройки, пользователей и товары в файл"""
    global USERS, PRODUCTS, PAYMENT_CARD, WELCOME_TEXT, MAIN_PHOTO_ID
    data = {
        "users": list(USERS),
        "products": PRODUCTS,
        "card": PAYMENT_CARD,
        "welcome_text": WELCOME_TEXT,
        "photo_id": MAIN_PHOTO_ID
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"💾 ДАННЫЕ УСПЕШНО ЗАПИСАНЫ! Файл: {DATA_FILE}")
    except Exception as e:
        logging.critical(f"❌ ОШИБКА ЗАПИСИ ФАЙЛА db_shop.json: {e}")

def load_data():
    """Загружает настройки, пользователей и товары с диска"""
    global USERS, PRODUCTS, PAYMENT_CARD, WELCOME_TEXT, MAIN_PHOTO_ID
    
    # Дефолтные товары для самого первого запуска
    PRODUCTS = {
        "10001": {"name": "🎁 Товар 1", "price": "490 руб.", "desc": "Описание первого товара."},
        "10002": {"name": "⚡ Товар 2", "price": "990 руб.", "desc": "Описание премиального товара."}
    }
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                USERS = set(data.get("users", []))
                PRODUCTS = data.get("products", PRODUCTS)
                PAYMENT_CARD = data.get("card", "Не указана")
                WELCOME_TEXT = data.get("welcome_text", "Добро пожаловать в наш магазин!")
                MAIN_PHOTO_ID = data.get("photo_id", None)
            logging.info(f"📂 ДАННЫЕ СЧИТАНЫ С ДИСКА! Загружено товаров: {len(PRODUCTS)}")
        except Exception as e:
            logging.critical(f"❌ ОШИБКА ЧТЕНИЯ ФАЙЛА db_shop.json (Файл поврежден): {e}")
    else:
        logging.warning("⚠️ Файл базы данных не найден на диске. Создаем новый с дефолтными товарами...")
        save_data()

def save_tickets():
    try:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(TICKETS, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения тикетов: {e}")

def load_tickets():
    global TICKETS
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                TICKETS = json.load(f)
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки тикетов: {e}")


# Состояния FSM
class ShopStates(StatesGroup):
    waiting_for_ticket = State()
    waiting_for_reply = State()
    waiting_for_broadcast = State()
    waiting_for_card = State()
    waiting_for_welcome_text = State()
    waiting_for_photo = State()
    add_prod_name = State()
    add_prod_desc = State()
    add_prod_price = State()

# --- СБОРЩИКИ КЛАВИАТУР ---
def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍️ Витрина товаров", callback_data="catalog")
    builder.button(text="👨‍💻 Поддержка", callback_data="support_menu")
    if user_id == ADMIN_ID:
        builder.button(text="👑 Админ-Панель", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

def catalog_kb():
    builder = InlineKeyboardBuilder()
    for p_id, p_info in PRODUCTS.items():
        builder.button(text=p_info["name"], callback_data=f"buy_{p_id}")
    builder.button(text="⬅️ Назад в меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def support_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎫 Создать обращение (Тикет)", callback_data="create_ticket")
    builder.button(text="🆘 Написать в ЛС (SOS)", url=f"https://t.me/{SUPPORT_USERNAME}")
    builder.button(text="⬅️ Назад в меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="➕ Добавить товар", callback_data="admin_add_product")
    builder.button(text="❌ Удалить товар", callback_data="admin_del_product")
    builder.button(text="💳 Изменить карту", callback_data="admin_change_card")
    builder.button(text="📝 Изменить приветствие", callback_data="admin_change_welcome")
    builder.button(text="🖼️ Изменить фото", callback_data="admin_change_photo")
    builder.button(text="⬅️ Выйти в меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()

# --- ФУНКЦИЯ ОТПРАВКИ ГЛАВНОГО МЕНЮ ---
async def send_main_menu(chat_id, user_id, message_to_edit=None):
    text = f"👋 Привет! {WELCOME_TEXT}"
    kb = main_menu_kb(user_id)
    
    if message_to_edit:
        try: await message_to_edit.delete()
        except Exception: pass

    if MAIN_PHOTO_ID:
        try: await bot.send_photo(chat_id=chat_id, photo=MAIN_PHOTO_ID, caption=text, reply_markup=kb)
        except Exception: await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)

# --- ХЕНДЛЕРЫ СТАРТА ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if message.from_user.id not in USERS:
        USERS.add(message.from_user.id)
        save_data() 
    await send_main_menu(message.chat.id, message.from_user.id)

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(call.message.chat.id, call.from_user.id, message_to_edit=call.message)

# --- РАЗДЕЛ МАГАЗИНА (ВИТРИНА) ---
@dp.callback_query(F.data == "catalog")
async def show_catalog(call: types.CallbackQuery):
    if not PRODUCTS:
        return await call.answer("📭 На витрине пока нет товаров.", show_alert=True)
    
    text = "🛍️ Выберите интересующий вас товар из каталога:"
    if call.message.photo:
        try: await call.message.delete()
        except Exception: pass
        await call.message.answer(text, reply_markup=catalog_kb())
    else:
        await call.message.edit_text(text, reply_markup=catalog_kb())

# --- КАРТОЧКА ТОВАРА ---
@dp.callback_query(F.data.startswith("buy_"))
async def product_card(call: types.CallbackQuery):
    p_id = call.data.split("_")[1]
    product = PRODUCTS.get(p_id)
    if product:
        text = f"📦 **{product['name']}**\n\n📝 **Описание:** {product['desc']}\n\n💰 **Цена:** {product['price']}"
        builder = InlineKeyboardBuilder()
        builder.button(text="💳 Оплатить", callback_data=f"pay_{p_id}")
        builder.button(text="⬅️ В каталог", callback_data="catalog")
        builder.adjust(1)
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await call.answer("❌ Товар не найден.", show_alert=True)

# --- ОКНО ОПЛАТЫ ---
@dp.callback_query(F.data.startswith("pay_"))
async def pay_invoice(call: types.CallbackQuery):
    p_id = call.data.split("_")[1]
    product = PRODUCTS.get(p_id)
    if not product: return
    
    invoice_text = (
        f"🧾 <b>Счёт на оплату товара:</b> {product['name']}\n"
        f"💰 <b>К оплате:</b> {product['price']}\n\n"
        f"💳 Переведите указанную сумму на карту:\n<code>{PAYMENT_CARD}</code>\n\n"
        f"🛑 <b>После оплаты:</b> Нажмите на кнопку ниже «🧾 Отправить чек», чтобы загрузить скриншот оплаты для администрации."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Отправить чек", callback_data="create_ticket")
    builder.button(text="⬅️ В каталог", callback_data="catalog")
    builder.adjust(1)
    await call.message.edit_text(invoice_text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- РАЗДЕЛ ПОДДЕРЖКИ (ТИКЕТЫ) ---
@dp.callback_query(F.data == "support_menu")
async def show_support(call: types.CallbackQuery):
    text = "🛠️ Как вы хотите связаться с поддержкой?"
    if call.message.photo:
        try: await call.message.delete()
        except Exception: pass
        await call.message.answer(text, reply_markup=support_kb())
    else:
        await call.message.edit_text(text, reply_markup=support_kb())

@dp.callback_query(F.data == "create_ticket")
async def start_ticket(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 Отправьте скриншот чека оплаты или опишите вашу проблему:")
    await state.set_state(ShopStates.waiting_for_ticket)

@dp.message(ShopStates.waiting_for_ticket)
async def process_ticket(message: types.Message, state: FSMContext):
    ticket_id = str(random.randint(10000, 99999))
    TICKETS[ticket_id] = int(message.from_user.id)
    save_tickets() 
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Ответить пользователю", callback_data=f"re_tk_{ticket_id}")
    
    username_str = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    admin_msg = f"🎫 <b>Новое обращение #{ticket_id}</b>\n👤 От: {message.from_user.full_name} ({username_str})\nID: <code>{message.from_user.id}</code>\n"
    
    if message.photo:
        await bot.send_photo(
            chat_id=ADMIN_ID, 
            photo=message.photo[-1].file_id, 
            caption=admin_msg + f"💬 Текст к фото: {message.caption or 'Отсутствует'}", 
            parse_mode="HTML", 
            reply_markup=builder.as_markup()
        )
    else:
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=admin_msg + f"\n💬 Сообщение:\n{message.text or 'Пустое сообщение'}", 
            parse_mode="HTML", 
            reply_markup=builder.as_markup()
        )
        
    await message.answer(f"✅ Ваше обращение #{ticket_id} принято! Ожидайте ответа администрации.")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data.startswith("re_tk_"))
async def setup_reply_ticket(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    t_id = call.data.split("_")[2]
    
    await call.message.answer(f"✍️ Напишите ответ на обращение #{t_id}:")
    await state.update_data(reply_to_ticket=str(t_id))
    await state.set_state(ShopStates.waiting_for_reply)
    await call.answer()

@dp.message(ShopStates.waiting_for_reply)
async def send_reply_to_user(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    data = await state.get_data()
    t_id = data.get("reply_to_ticket")
    user_id = TICKETS.get(str(t_id))
    
    if user_id:
        try:
            if message.text:
                await bot.send_message(
                    chat_id=int(user_id), 
                    text=f"✉️ <b>Ответ администрации на ваше обращение #{t_id}:</b>\n\n{message.text}", 
                    parse_mode="HTML"
                )
                await message.answer(f"✅ Ответ на тикет #{t_id} успешно отправлен пользователю!")
            else:
                await message.answer("❌ Ошибка: Поддерживаются только текстовые сообщения ответов.")
                return
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")
    else:
        await message.answer(f"❌ Ошибка: Лог тикета #{t_id} не найден.")
        
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

# --- УПРАВЛЕНИЕ В АДМИН-ПАНЕЛИ ---
@dp.callback_query(F.data == "admin_panel")
async def open_admin(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("❌ Доступ запрещен!", show_alert=True)
    status = f"👑 <b>Панель управления</b>\n\n💳 Карта:\n<code>{PAYMENT_CARD}</code>\n\n📦 Всего товаров: {len(PRODUCTS)}\n📝 Приветствие:\n<i>{WELCOME_TEXT}</i>"
    if call.message.photo:
        try: await call.message.delete()
        except Exception: pass
        await call.message.answer(status, parse_mode="HTML", reply_markup=admin_kb())
    else:
        await call.message.edit_text(status, parse_mode="HTML", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    await call.answer(f"📊 Всего активных клиентов в базе: {len(USERS)}", show_alert=True)

# --- ДОБАВЛЕНИЕ ТОВАРОВ ---
@dp.callback_query(F.data == "admin_add_product")
async def add_product_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("✍️ Введите <b>название</b> нового товара (например: 🎁 VIP-Доступ):", parse_mode="HTML")
    await state.set_state(ShopStates.add_prod_name)

@dp.message(ShopStates.add_prod_name)
async def add_product_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(p_name=message.text)
    await message.answer("📝 Введите **описание** для этого товара:")
    await state.set_state(ShopStates.add_prod_desc)

@dp.message(ShopStates.add_prod_desc)
async def add_product_desc(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(p_desc=message.text)
    await message.answer("💰 Введите **цену** товара (например: `500 руб.`):")
    await state.set_state(ShopStates.add_prod_price)

@dp.message(ShopStates.add_prod_price)
async def add_product_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    
    new_id = str(random.randint(10000, 99999))
    PRODUCTS[new_id] = {
        "name": data['p_name'],
        "desc": data['p_desc'],
        "price": message.text
    }
    
    save_data() # Настройки сохраняются на диск
    await message.answer(f"✅ Товар **{data['p_name']}** добавлен на витрину!", parse_mode="Markdown")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

# --- УДАЛЕНИЕ ТОВАРОВ ---
@dp.callback_query(F.data == "admin_del_product")
async def delete_product_list(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    if not PRODUCTS:
        return await call.answer("❌ На витрине нет товаров для удаления.", show_alert=True)
        
    builder = InlineKeyboardBuilder()
    for p_id, p_info in PRODUCTS.items():
        builder.button(text=f"🗑️ {p_info['name']}", callback_data=f"d_el_{p_id}")
    builder.button(text="⬅️ Назад в админку", callback_data="admin_panel")
    builder.adjust(1)
    await call.message.edit_text("🗑️ Выберите товар для удаления с витрины:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("d_el_"))
async def delete_product_confirm(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = call.data.split("_")[2]
    
    if p_id in PRODUCTS:
        removed_name = PRODUCTS[p_id]['name']
        del PRODUCTS[p_id]
        save_data() 
        await call.answer(f"🗑️ Товар '{removed_name}' удален!", show_alert=True)
    else:
        await call.answer("❌ Товар не найден.", show_alert=True)
    await delete_product_list(call)

# Изменение карты
@dp.callback_query(F.data == "admin_change_card")
async def change_card_req(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💳 Отправьте новый номер карты / реквизиты для оплаты:")
    await state.set_state(ShopStates.waiting_for_card)

@dp.message(ShopStates.waiting_for_card)
async def process_new_card(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    global PAYMENT_CARD
    PAYMENT_CARD = message.text
    save_data() 
    await message.answer("✅ Реквизиты успешно обновлены!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

# Изменение приветственного текста
@dp.callback_query(F.data == "admin_change_welcome")
async def change_welcome_req(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📝 Введите новый приветственный текст для главного экрана магазина:")
    await state.set_state(ShopStates.waiting_for_welcome_text)

@dp.message(ShopStates.waiting_for_welcome_text)
async def process_new_welcome(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    global WELCOME_TEXT
    WELCOME_TEXT = message.text
    save_data() 
    await message.answer("✅ Текст приветствия изменен!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

# Изменение главной картинки
@dp.callback_query(F.data == "admin_change_photo")
async def change_photo_req(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🖼️ Отправьте картинку (как фото), которая станет обложкой магазина:")
    await state.set_state(ShopStates.waiting_for_photo)

@dp.message(ShopStates.waiting_for_photo, F.photo)
async def process_new_photo(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    global MAIN_PHOTO_ID
    MAIN_PHOTO_ID = message.photo[-1].file_id
    save_data() 
    await message.answer("✅ Главное фото успешно установлено!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

# Рассылка
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📢 Напишите текст рекламной рассылки:")
    await state.set_state(ShopStates.waiting_for_broadcast)

@dp.message(ShopStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    count = 0
    for u_id in USERS:
        try:
            await bot.send_message(chat_id=u_id, text=f"📢 **Внимание, объявление от магазина!**\n\n{message.text}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await message.answer(f"✅ Рассылка завершена!\nУспешно доставлено: {count} пользователям.")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

async def main():
    load_data() 
    load_tickets()
    print(f"Запуск! Проверьте путь файлов: {DATA_FILE}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
