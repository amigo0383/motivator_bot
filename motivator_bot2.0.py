import os
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Конфигурация
API_TOKEN = '8014920100:AAGBt7DlitAa6EnWUE_6evp3DNUOoFXwzN8'  # Замените на токен от @BotFather
ADMIN_ID = 6250264162     # Ваш ID (узнать у @userinfobot)
BASE_DIR = Path(r"C:\Users\kluso\OneDrive\Рабочий стол\TG Bot 2_7867\Bot")
DB_PATH = BASE_DIR / "bot_data.db"
QUOTES_FILE = BASE_DIR / "цитаты.txt"
JOKES_FILE = BASE_DIR / "шутки.txt"

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def load_texts(file_path):
    """Загрузка цитат или шуток из файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Файл {file_path} не найден!")
        return []

def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect(DB_PATH) as conn:
        # Таблица цитат и шуток
        conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            rating INTEGER DEFAULT 0,
            votes INTEGER DEFAULT 0,
            type TEXT DEFAULT 'quote'
        )""")
        
        # Таблица пользователей
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            quotes_read INTEGER DEFAULT 0,
            jokes_read INTEGER DEFAULT 0,
            votes_made INTEGER DEFAULT 0,
            last_active DATETIME
        )""")
        
        # Таблица голосований
        conn.execute("""
        CREATE TABLE IF NOT EXISTS voted_items (
            user_id INTEGER,
            item_id INTEGER,
            item_type TEXT,
            vote_type TEXT,
            PRIMARY KEY (user_id, item_id, item_type)
        )""")
        
        # Добавляем данные только если таблица пуста
        if conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0] == 0:
            # Загружаем цитаты и шутки из файлов
            quotes = [(text, 'quote') for text in load_texts(QUOTES_FILE)[:100]]  # Берем первые 100
            jokes = [(text, 'joke') for text in load_texts(JOKES_FILE)[:100]]     # Берем первые 100
            
            # Вставляем с нулевыми рейтингами
            conn.executemany("INSERT INTO quotes (text, rating, votes, type) VALUES (?, 0, 0, ?)", quotes + jokes)
            print(f"Добавлено {len(quotes)} цитат и {len(jokes)} шуток")

def get_main_keyboard():
    """Клавиатура основного меню"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎲 Случайная цитата")
    kb.button(text="😂 Случайная шутка")
    kb.button(text="🏆 Топ цитат")
    kb.button(text="🏆 Топ шуток")
    kb.button(text="👤 Мой профиль")
    if ADMIN_ID:
        kb.button(text="👑 Админ-панель")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name, last_active)
        VALUES (?, ?, ?, ?)
        """, (message.from_user.id, message.from_user.username, message.from_user.full_name, datetime.now().isoformat()))
    
    await message.answer(
        "🌟 <b>Бот мотивации и юмора</b> 🌟\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )

async def get_random_item(item_type: str):
    """Получение случайной цитаты или шутки"""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT id, text, rating, votes FROM quotes 
        WHERE type = ? 
        ORDER BY RANDOM() LIMIT 1
        """, (item_type,)).fetchone()

async def show_item(message: types.Message, item_type: str):
    """Показ цитаты или шутки с кнопками оценки"""
    item = await get_random_item(item_type)
    if not item:
        await message.answer(f"В базе пока нет {'шуток' if item_type == 'joke' else 'цитат'}")
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        # Обновляем статистику пользователя
        if item_type == 'joke':
            conn.execute("""
            UPDATE users SET 
                jokes_read = jokes_read + 1,
                last_active = ?
            WHERE user_id = ?
            """, (datetime.now().isoformat(), message.from_user.id))
        else:
            conn.execute("""
            UPDATE users SET 
                quotes_read = quotes_read + 1,
                last_active = ?
            WHERE user_id = ?
            """, (datetime.now().isoformat(), message.from_user.id))
    
    # Создаем кнопки оценки
    kb = InlineKeyboardBuilder()
    kb.button(text="👍", callback_data=f"vote_up_{item_type}_{item[0]}")
    kb.button(text="👎", callback_data=f"vote_down_{item_type}_{item[0]}")
    
    await message.answer(
        f"{'😂 Шутка' if item_type == 'joke' else '🌟 Цитата'}:\n\n"
        f"{item[1]}\n\n"
        f"⭐ Рейтинг: {item[2]}\n"
        f"👍 Голосов: {item[3]}",
        reply_markup=kb.as_markup()
    )

@dp.message(lambda message: message.text == "🎲 Случайная цитата")
async def random_quote(message: types.Message):
    """Показ случайной цитаты"""
    await show_item(message, 'quote')

@dp.message(lambda message: message.text == "😂 Случайная шутка")
async def random_joke(message: types.Message):
    """Показ случайной шутки"""
    await show_item(message, 'joke')

async def show_top(message: types.Message, item_type: str):
    """Показ топ-5 цитат или шуток"""
    with sqlite3.connect(DB_PATH) as conn:
        items = conn.execute("""
        SELECT text, rating, votes FROM quotes 
        WHERE type = ?
        ORDER BY rating DESC, votes DESC 
        LIMIT 5
        """, (item_type,)).fetchall()
        
        if items:
            response = f"🏆 <b>Топ-5 {'шуток' if item_type == 'joke' else 'цитат'}:</b>\n\n"
            for i, (text, rating, votes) in enumerate(items, 1):
                response += f"{i}. {text}\n⭐ {rating} (Голосов: {votes})\n\n"
            await message.answer(response)
        else:
            await message.answer(f"В базе пока нет {'шуток' if item_type == 'joke' else 'цитат'}")

@dp.message(lambda message: message.text == "🏆 Топ цитат")
async def top_quotes(message: types.Message):
    """Показ топ-5 цитат"""
    await show_top(message, 'quote')

@dp.message(lambda message: message.text == "🏆 Топ шуток")
async def top_jokes(message: types.Message):
    """Показ топ-5 шуток"""
    await show_top(message, 'joke')

@dp.callback_query(lambda c: c.data.startswith('vote_'))
async def process_vote(callback: types.CallbackQuery):
    """Обработка голосования"""
    action, item_type, item_id = callback.data.split('_')[1], callback.data.split('_')[2], int(callback.data.split('_')[3])
    
    with sqlite3.connect(DB_PATH) as conn:
        # Проверяем, голосовал ли уже пользователь
        voted = conn.execute("""
        SELECT vote_type FROM voted_items 
        WHERE user_id = ? AND item_id = ? AND item_type = ?
        """, (callback.from_user.id, item_id, item_type)).fetchone()
        
        if voted:
            await callback.answer("Вы уже голосовали за этот элемент!")
            return
        
        # Обновляем рейтинг
        if action == 'up':
            conn.execute("""
            UPDATE quotes SET 
                rating = rating + 1,
                votes = votes + 1
            WHERE id = ?
            """, (item_id,))
        else:
            conn.execute("""
            UPDATE quotes SET 
                rating = rating - 1,
                votes = votes + 1
            WHERE id = ?
            """, (item_id,))
        
        # Записываем факт голосования
        conn.execute("""
        INSERT INTO voted_items (user_id, item_id, item_type, vote_type)
        VALUES (?, ?, ?, ?)
        """, (callback.from_user.id, item_id, item_type, action))
        
        # Обновляем статистику пользователя
        conn.execute("""
        UPDATE users SET 
            votes_made = votes_made + 1,
            last_active = ?
        WHERE user_id = ?
        """, (datetime.now().isoformat(), callback.from_user.id))
        
        # Получаем обновленные данные
        item = conn.execute("""
        SELECT text, rating, votes FROM quotes WHERE id = ?
        """, (item_id,)).fetchone()
        
        await callback.message.edit_text(
            f"{'😂 Шутка' if item_type == 'joke' else '🌟 Цитата'}:\n\n"
            f"{item[0]}\n\n"
            f"⭐ Рейтинг: {item[1]}\n"
            f"👍 Голосов: {item[2]}",
            reply_markup=callback.message.reply_markup
        )
        await callback.answer("Спасибо за ваш голос!")

@dp.message(lambda message: message.text == "👤 Мой профиль")
async def user_profile(message: types.Message):
    """Показ профиля пользователя"""
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute("""
        SELECT full_name, quotes_read, jokes_read, votes_made FROM users
        WHERE user_id = ?
        """, (message.from_user.id,)).fetchone()
        
        if user:
            await message.answer(
                f"👤 <b>Ваш профиль</b>\n\n"
                f"📛 Имя: {user[0]}\n"
                f"📖 Прочитано цитат: {user[1]}\n"
                f"😂 Прочитано шуток: {user[2]}\n"
                f"⭐ Оставлено оценок: {user[3]}"
            )

@dp.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    """Админ-панель"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    kb = ReplyKeyboardBuilder()
    kb.button(text="📝 Добавить цитату")
    kb.button(text="📝 Добавить шутку")
    kb.button(text="🗑️ Удалить цитату")
    kb.button(text="🗑️ Удалить шутку")
    kb.button(text="📊 Статистика")
    kb.button(text="🔙 Главное меню")
    kb.adjust(2)
    
    await message.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(lambda message: message.text == "🗑️ Удалить цитату")
async def delete_quote_start(message: types.Message):
    """Начало процесса удаления цитаты"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    with sqlite3.connect(DB_PATH) as conn:
        quotes = conn.execute("SELECT id, text FROM quotes WHERE type = 'quote'").fetchall()
        
        if not quotes:
            return await message.answer("В базе нет цитат для удаления")
        
        kb = InlineKeyboardBuilder()
        for quote_id, text in quotes:
            kb.button(text=f"{quote_id}: {text[:20]}...", callback_data=f"delete_quote_{quote_id}")
        kb.adjust(1)
        
        await message.answer(
            "📚 <b>Выберите цитату для удаления:</b>",
            reply_markup=kb.as_markup()
        )

@dp.message(lambda message: message.text == "🗑️ Удалить шутку")
async def delete_joke_start(message: types.Message):
    """Начало процесса удаления шутки"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    with sqlite3.connect(DB_PATH) as conn:
        jokes = conn.execute("SELECT id, text FROM quotes WHERE type = 'joke'").fetchall()
        
        if not jokes:
            return await message.answer("В базе нет шуток для удаления")
        
        kb = InlineKeyboardBuilder()
        for joke_id, text in jokes:
            kb.button(text=f"{joke_id}: {text[:20]}...", callback_data=f"delete_joke_{joke_id}")
        kb.adjust(1)
        
        await message.answer(
            "😂 <b>Выберите шутку для удаления:</b>",
            reply_markup=kb.as_markup()
        )

@dp.callback_query(lambda c: c.data.startswith('delete_'))
async def process_delete(callback: types.CallbackQuery):
    """Обработка удаления цитат/шуток"""
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("❌ Доступ запрещен")
    
    action, item_type, item_id = callback.data.split('_')[1], callback.data.split('_')[2], int(callback.data.split('_')[3])
    
    with sqlite3.connect(DB_PATH) as conn:
        # Получаем текст перед удалением
        text = conn.execute("SELECT text FROM quotes WHERE id = ?", (item_id,)).fetchone()[0]
        
        # Удаляем запись
        conn.execute("DELETE FROM quotes WHERE id = ?", (item_id,))
        conn.execute("DELETE FROM voted_items WHERE item_id = ?", (item_id,))
        
        await callback.message.edit_text(
            f"✅ {'Шутка' if item_type == 'joke' else 'Цитата'} удалена:\n\n"
            f"{text}",
            reply_markup=None
        )
        await callback.answer()

@dp.message(Command("add_quote"))
async def add_quote(message: types.Message):
    """Добавление новой цитаты (админ)"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    text = message.text.replace("/add_quote", "").strip()
    if not text:
        return await message.answer("Использование: /add_quote [текст цитаты]")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO quotes (text, type) VALUES (?, 'quote')", (text,))
    
    await message.answer(f"✅ Цитата добавлена:\n\n{text}")

@dp.message(Command("add_joke"))
async def add_joke(message: types.Message):
    """Добавление новой шутки (админ)"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    text = message.text.replace("/add_joke", "").strip()
    if not text:
        return await message.answer("Использование: /add_joke [текст шутки]")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO quotes (text, type) VALUES (?, 'joke')", (text,))
    
    await message.answer(f"✅ Шутка добавлена:\n\n{text}")

@dp.message(lambda message: message.text == "📊 Статистика")
async def show_stats(message: types.Message):
    """Показ статистики бота"""
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещен")
    
    with sqlite3.connect(DB_PATH) as conn:
        stats = conn.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE type = 'quote') as quotes_count,
            COUNT(*) FILTER (WHERE type = 'joke') as jokes_count,
            (SELECT COUNT(*) FROM users) as users_count,
            SUM(quotes_read) as total_quotes_read,
            SUM(jokes_read) as total_jokes_read
        FROM quotes
        """).fetchone()
        
        await message.answer(
            "📊 <b>Статистика бота:</b>\n\n"
            f"📚 Цитат в базе: {stats[0]}\n"
            f"😂 Шуток в базе: {stats[1]}\n"
            f"👥 Пользователей: {stats[2]}\n"
            f"📖 Прочитано цитат: {stats[3]}\n"
            f"🎭 Прочитано шуток: {stats[4]}"
        )

@dp.message(lambda message: message.text == "🔙 Главное меню")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )

async def on_startup():
    """Действия при запуске бота"""
    init_db()
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, "🤖 Бот успешно запущен!")

async def main():
    await dp.start_polling(bot, on_startup=on_startup)

if __name__ == "__main__":
    print("Бот запускается...")
    asyncio.run(main())