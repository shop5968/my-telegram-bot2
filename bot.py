import asyncio
import logging
import json
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= НАСТРОЙКИ БОТА =================
BOT_TOKEN = "8826949370:AAFPfMDKcxyOL0rkXnlMCUOox22btQWP3ZE"  
ADMIN_ID = 5632144886          
SUPPORT_USERNAME = "Wwww_068"  

# 🔴 ВСТАВЬ СЮДА ID СВОЕЙ ПРИВАТНОЙ ГРУППЫ С БОТОМ (ОБЯЗАТЕЛЬНО С МИНУСОМ!)
DB_CHAT_ID = -1004438623910
# ===================================================

# Глобальные переменные баз данных
USERS = set()
TICKETS = {}
PRODUCTS = {}
PAYMENT_CARD = "Не указана (настройте в админке)"
WELCOME_TEXT = "Добро пожаловать в наш магазин! Используйте кнопки ниже для навигации."
MAIN_PHOTO_ID = None

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- УМНАЯ ОБЛАЧНАЯ БАЗА ДАННЫХ ЧЕРЕЗ TELEGRAM ---
async def save_to_cloud():
    """Складывает все настройки магазина в один JSON и отправляет файл бэкапа в скрытый чат"""
    data = {
        "users": list(USERS),
        "tickets": TICKETS,
        "products": PRODUCTS,
        "card": PAYMENT_CARD,
        "welcome_text": WELCOME_TEXT,
        "photo_id": MAIN_PHOTO_ID
    }
    try:
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        file_input = types.BufferedInputFile(json_bytes, filename="cloud_db.json")
        await bot.send_document(chat_id=DB_CHAT_ID, document=file_input, caption="🔄 Автосохранение настроек базы данных")
        logging.info("Все настройки успешно сохранены в облако Telegram!")
    except Exception as e:
        logging.error(f"Ошибка сохранения настроек в облако: {e}")

async def load_from_cloud():
    """Ищет последний файл бэкапа cloud_db.json в чате и загружает из него данные при старте"""
    global USERS, TICKETS, PRODUCTS, PAYMENT_CARD, WELCOME_TEXT, MAIN_PHOTO_ID
    logging.info("Загрузка настроек из облака Telegram...")
    try:
        # Базовые товары для самого первого запуска, если чат еще пустой
        PRODUCTS = {
            "10001": {"name": "🎁 Товар 1", "price": "490 руб.", "desc": "Описание первого товара."},
            "10002": {"name": "⚡ Товар 2", "price": "990 руб.", "desc": "Описание премиального товара."}
        }
        
        async for message in bot.get_chat_history(chat_id=DB_CHAT_ID, limit=50):
            if message.document and message.document.file_name == "cloud_db.json":
                file_info = await bot.get_file(message.document.file_id)
                file_bytes = await bot.download_file(file_info.file_path)
                
                cloud_data = json.loads(file_bytes.read().decode('utf-8'))
                USERS = set(cloud_data.get("users", []))
                TICKETS = cloud_data.get("tickets", {})
                PRODUCTS = cloud_data.get("products", PRODUCTS)
                PAYMENT_CARD = cloud_data.get("card", "Не указана")
                WELCOME_TEXT = cloud_data.get("welcome_text", "Добро пожаловать в наш магазин!")
                MAIN_PHOTO_ID = cloud_data.get("photo_id", None)
                logging.info("Все настройки успешно восстановлены из облака!")
                return
        logging.warning("Файл настроек в чате не найден. Используем чистый запуск.")
    except Exception as e:
        logging.error(f"Ошибка загрузки из облака: {e}")

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

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if message.from_user.id not in USERS:
        USERS.add(message.from_user.id)
        await save_to_cloud()
    await send_main_menu(message.chat.id, message.from_user.id)

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(call.message.chat.id, call.from_user.id, message_to_edit=call.message)

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

@dp.callback_query(F.data.startswith("pay_"))
async def pay_invoice(call: types.CallbackQuery):
    p_id = call.data.split("_")[1]
    product = PRODUCTS.get(p_id)
    if not product: return
    invoice_text = (
        f"🧾 <b>Счёт на оплату товара:</b> {product['name']}\n💰 <b>К оплате:</b> {product['price']}\n\n"
        f"💳 Переведите указанную сумму на карту:\n<code>{PAYMENT_CARD}</code>\n\n"
        f"🛑 После оплаты нажмите «🧾 Отправить чек» для загрузки скриншота."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Отправить чек", callback_data="create_ticket")
    builder.button(text="⬅️ В каталог", callback_data="catalog")
    builder.adjust(1)
    await call.message.edit_text(invoice_text, parse_mode="HTML", reply_markup=builder.as_markup())

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
    await call.message.edit_text("📝 Отправьте скриншот чека или опишите проблему:")
    await state.set_state(ShopStates.waiting_for_ticket)

@dp.message(ShopStates.waiting_for_ticket)
async def process_ticket(message: types.Message, state: FSMContext):
    ticket_id = str(random.randint(10000, 99999))
    TICKETS[ticket_id] = int(message.from_user.id)
    await save_to_cloud()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Ответить", callback_data=f"re_tk_{ticket_id}")
    admin_msg = f"🎫 <b>Новое обращение #{ticket_id}</b>\n👤 От: {message.from_user.full_name}\n"
    
    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_msg + f"💬 {message.caption or ''}", parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg + f"\n💬 {message.text or ''}", parse_mode="HTML", reply_markup=builder.as_markup())
        
    await message.answer(f"✅ Обращение #{ticket_id} принято!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data.startswith("re_tk_"))
async def setup_reply_ticket(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    t_id = call.data.split("_")[2]
    await call.message.answer(f"✍️ Ответ на тикет #{t_id}:")
    await state.update_data(reply_to_ticket=str(t_id))
    await state.set_state(ShopStates.waiting_for_reply)

@dp.message(ShopStates.waiting_for_reply)
async def send_reply_to_user(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    t_id = data.get("reply_to_ticket")
    user_id = TICKETS.get(str(t_id))
    if user_id:
        try:
            await bot.send_message(chat_id=int(user_id), text=f"✉️ <b>Ответ админа на тикет #{t_id}:</b>\n\n{message.text}", parse_mode="HTML")
            await message.answer("✅ Отправлено!")
        except Exception: pass
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data == "admin_panel")
async def open_admin(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status = f"👑 <b>Панель управления</b>\n\n💳 Карта: <code>{PAYMENT_CARD}</code>\n📦 Товаров: {len(PRODUCTS)}"
    if call.message.photo:
        try: await call.message.delete()
        except Exception: pass
        await call.message.answer(status, parse_mode="HTML", reply_markup=admin_kb())
    else:
        await call.message.edit_text(status, parse_mode="HTML", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    await call.answer(f"📊 Клиентов в базе: {len(USERS)}", show_alert=True)

@dp.callback_query(F.data == "admin_add_product")
async def add_product_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("✍️ Введите название товара:")
    await state.set_state(ShopStates.add_prod_name)

@dp.message(ShopStates.add_prod_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(p_name=message.text)
    await message.answer("📝 Введите описание:")
    await state.set_state(ShopStates.add_prod_desc)

@dp.message(ShopStates.add_prod_desc)
async def add_product_desc(message: types.Message, state: FSMContext):
    await state.update_data(p_desc=message.text)
    await message.answer("💰 Введите цену:")
    await state.set_state(ShopStates.add_prod_price)

@dp.message(ShopStates.add_prod_price)
async def add_product_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_id = str(random.randint(10000, 99999))
    PRODUCTS[new_id] = {"name": data['p_name'], "desc": data['p_desc'], "price": message.text}
    await save_to_cloud() # Синхронизируем настройки
    await message.answer("✅ Товар добавлен!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data == "admin_del_product")
async def delete_product_list(call: types.CallbackQuery):
    if not PRODUCTS: return await call.answer("Магазин пуст", show_alert=True)
    builder = InlineKeyboardBuilder()
    for p_id, p_info in PRODUCTS.items():
        builder.button(text=f"🗑️ {p_info['name']}", callback_data=f"d_el_{p_id}")
    builder.button(text="⬅️ Назад", callback_data="admin_panel")
    builder.adjust(1)
    await call.message.edit_text("🗑️ Удалить товар:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("d_el_"))
async def delete_product_confirm(call: types.CallbackQuery):
    p_id = call.data.split("_")[2]
    if p_id in PRODUCTS:
        del PRODUCTS[p_id]
        await save_to_cloud()
        await call.answer("Удалено!")
    await delete_product_list(call)

@dp.callback_query(F.data == "admin_change_card")
async def change_card_req(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("💳 Введите новую карту:")
    await state.set_state(ShopStates.waiting_for_card)

@dp.message(ShopStates.waiting_for_card)
async def process_new_card(message: types.Message, state: FSMContext):
    global PAYMENT_CARD
    PAYMENT_CARD = message.text
    await save_to_cloud()
    await message.answer("✅ Карта обновлена!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data == "admin_change_welcome")
async def change_welcome_req(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 Новое приветствие:")
    await state.set_state(ShopStates.waiting_for_welcome_text)

@dp.message(ShopStates.waiting_for_welcome_text)
async def process_new_welcome(message: types.Message, state: FSMContext):
    global WELCOME_TEXT
    WELCOME_TEXT = message.text
    await save_to_cloud()
    await message.answer("✅ Изменено!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data == "admin_change_photo")
async def change_photo_req(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("🖼️ Отправьте новое фото:")
    await state.set_state(ShopStates.waiting_for_photo)

@dp.message(ShopStates.waiting_for_photo, F.photo)
async def process_new_photo(message: types.Message, state: FSMContext):
    global MAIN_PHOTO_ID
    MAIN_PHOTO_ID = message.photo[-1].file_id
    await save_to_cloud()
    await message.answer("✅ Фото установлено!")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📢 Текст рассылки:")
    await state.set_state(ShopStates.waiting_for_broadcast)

@dp.message(ShopStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    count = 0
    for u_id in USERS:
        try:
            await bot.send_message(chat_id=u_id, text=f"📢 <b>Объявление:</b>\n\n{message.text}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await message.answer(f"✅ Успешно доставлено: {count}")
    await send_main_menu(message.chat.id, message.from_user.id)
    await state.clear()

async def main():
    await load_from_cloud() # Восстанавливаем настройки при старте
    print("Бот запущен на GitHub Actions!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
