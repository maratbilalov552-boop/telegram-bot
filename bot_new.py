import logging
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Токен
API_TOKEN = os.environ.get('BOT_TOKEN')

# Логи
logging.basicConfig(level=logging.INFO)

# Бот
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# База данных
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Клавиатура
def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📋 Задачи"))
    kb.add(KeyboardButton("❓ Помощь"))
    return kb

# Состояния
class TaskState(StatesGroup):
    waiting_for_title = State()

# Старт
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    # Сохраняем пользователя
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                  (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"Привет, {message.from_user.first_name}!\nЯ простой бот-помощник.",
        reply_markup=main_keyboard()
    )

# Помощь
@dp.message_handler(lambda msg: msg.text == "❓ Помощь")
async def help(message: types.Message):
    await message.answer("Просто нажимай кнопки!")

# Задачи
@dp.message_handler(lambda msg: msg.text == "📋 Задачи")
async def tasks(message: types.Message):
    # Показываем задачи
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM tasks WHERE user_id = ?", 
                  (message.from_user.id,))
    tasks = cursor.fetchall()
    conn.close()
    
    if tasks:
        text = "Твои задачи:\n"
        for task in tasks:
            text += f"• {task[1]} (id: {task[0]})\n"
    else:
        text = "У тебя нет задач. Напиши название новой задачи!"
        await TaskState.waiting_for_title.set()
    
    await message.answer(text)

# Добавление задачи
@dp.message_handler(state=TaskState.waiting_for_title)
async def add_task(message: types.Message, state: FSMContext):
    title = message.text
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (user_id, title) VALUES (?, ?)",
                  (message.from_user.id, title))
    conn.commit()
    conn.close()
    
    await message.answer(f"Задача '{title}' добавлена!")
    await state.finish()

# Эхо (на всякий случай)
@dp.message_handler()
async def echo(message: types.Message):
    await message.answer(f"Ты написал: {message.text}")

if __name__ == '__main__':
    print("Бот запущен!")
    executor.start_polling(dp, skip_updates=True)
