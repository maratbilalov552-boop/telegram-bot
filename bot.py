import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import sqlite3
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text

# Конфигурация бота
API_TOKEN = '8781889382:AAFsK-9-7QbJihpcQCrOvlf_Ra53ikHqbQQ'  # Замените на ваш токен

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, db_name='bot_database.db'):
        self.db_name = db_name
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица задач
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date DATE,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица записей питания
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    meal_type TEXT,
                    food_name TEXT,
                    calories INTEGER,
                    proteins REAL,
                    fats REAL,
                    carbs REAL,
                    date DATE DEFAULT CURRENT_DATE,
                    time TIME DEFAULT CURRENT_TIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица привычек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS habits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    habit_name TEXT NOT NULL,
                    description TEXT,
                    frequency TEXT DEFAULT 'daily',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица выполнения привычек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS habit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    habit_id INTEGER,
                    user_id INTEGER,
                    completed_date DATE DEFAULT CURRENT_DATE,
                    FOREIGN KEY (habit_id) REFERENCES habits (id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица заметок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()

# Создаем экземпляр базы данных
db = Database()

# ==================== СОСТОЯНИЯ FSM ====================
class TaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_due_date = State()
    waiting_for_priority = State()
    waiting_for_task_id = State()
    waiting_for_edit_choice = State()
    waiting_for_new_title = State()

class FoodStates(StatesGroup):
    waiting_for_meal_type = State()
    waiting_for_food_name = State()
    waiting_for_calories = State()
    waiting_for_proteins = State()
    waiting_for_fats = State()
    waiting_for_carbs = State()
    waiting_for_date = State()

class HabitStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_frequency = State()

class NoteStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("📋 Задачи"),
        KeyboardButton("🍽 Дневник питания"),
        KeyboardButton("💪 Привычки"),
        KeyboardButton("📝 Заметки"),
        KeyboardButton("📊 Статистика"),
        KeyboardButton("❓ Помощь")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_tasks_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("➕ Добавить задачу"),
        KeyboardButton("📋 Мои задачи"),
        KeyboardButton("✅ Завершить задачу"),
        KeyboardButton("❌ Удалить задачу"),
        KeyboardButton("✏️ Редактировать задачу"),
        KeyboardButton("🔙 Главное меню")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_food_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("➕ Записать прием пищи"),
        KeyboardButton("📊 Сегодняшнее питание"),
        KeyboardButton("📅 Питание за дату"),
        KeyboardButton("🥗 Завтрак"),
        KeyboardButton("🍝 Обед"),
        KeyboardButton("🍽 Ужин"),
        KeyboardButton("🍎 Перекус"),
        KeyboardButton("🔙 Главное меню")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_habits_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("➕ Добавить привычку"),
        KeyboardButton("📋 Мои привычки"),
        KeyboardButton("✅ Отметить выполнение"),
        KeyboardButton("📊 Прогресс привычек"),
        KeyboardButton("🔙 Главное меню")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_notes_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("➕ Создать заметку"),
        KeyboardButton("📋 Мои заметки"),
        KeyboardButton("🔍 Просмотреть заметку"),
        KeyboardButton("✏️ Редактировать заметку"),
        KeyboardButton("❌ Удалить заметку"),
        KeyboardButton("🔙 Главное меню")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_priority_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = [
        KeyboardButton("🔴 Высокий"),
        KeyboardButton("🟡 Средний"),
        KeyboardButton("🟢 Низкий")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_frequency_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = [
        KeyboardButton("Ежедневно"),
        KeyboardButton("Еженедельно"),
        KeyboardButton("Ежемесячно")
    ]
    keyboard.add(*buttons)
    return keyboard

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def register_user(user: types.User):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user.id, user.username, user.first_name)
        )
        conn.commit()

def parse_date(date_str):
    try:
        if date_str.lower() in ['сегодня', 'today']:
            return datetime.now().date()
        elif date_str.lower() in ['завтра', 'tomorrow']:
            return datetime.now().date() + timedelta(days=1)
        else:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await register_user(message.from_user)
    
    welcome_text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я многофункциональный бот-помощник. Я помогу тебе:\n"
        "✅ Отслеживать задачи\n"
        "🥗 Вести дневник питания\n"
        "💪 Отслеживать привычки\n"
        "📝 Делать заметки\n\n"
        "Используй кнопки меню для навигации!"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message_handler(lambda message: message.text == "❓ Помощь")
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    help_text = (
        "📚 Доступные функции:\n\n"
        "📋 Задачи - управление списком дел\n"
        "🍽 Дневник питания - учет калорий и БЖУ\n"
        "💪 Привычки - отслеживание полезных привычек\n"
        "📝 Заметки - создание и хранение заметок\n"
        "📊 Статистика - просмотр статистики\n\n"
        "Для навигации используйте кнопки меню!"
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())

@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())

# ==================== ЗАДАЧИ ====================
@dp.message_handler(lambda message: message.text == "📋 Задачи")
async def tasks_menu(message: types.Message):
    await message.answer("Меню управления задачами:", reply_markup=get_tasks_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить задачу")
async def add_task_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название задачи:")
    await TaskStates.waiting_for_title.set()

@dp.message_handler(state=TaskStates.waiting_for_title)
async def add_task_title(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['title'] = message.text
    await message.answer("Введите описание задачи (или отправьте '-' если не нужно):")
    await TaskStates.next()

@dp.message_handler(state=TaskStates.waiting_for_description)
async def add_task_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = None if message.text == '-' else message.text
    await message.answer("Введите срок выполнения (ГГГГ-ММ-ДД, или 'сегодня'/'завтра'):")
    await TaskStates.next()

@dp.message_handler(state=TaskStates.waiting_for_due_date)
async def add_task_due_date(message: types.Message, state: FSMContext):
    due_date = parse_date(message.text)
    if not due_date:
        await message.answer("Неверный формат даты. Используйте ГГГГ-ММ-ДД или 'сегодня'/'завтра'")
        return
    
    async with state.proxy() as data:
        data['due_date'] = due_date
    
    await message.answer("Выберите приоритет:", reply_markup=get_priority_keyboard())
    await TaskStates.next()

@dp.message_handler(state=TaskStates.waiting_for_priority)
async def add_task_priority(message: types.Message, state: FSMContext):
    priority_map = {
        "🔴 Высокий": "high",
        "🟡 Средний": "medium",
        "🟢 Низкий": "low"
    }
    
    priority = priority_map.get(message.text, "medium")
    
    async with state.proxy() as data:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (user_id, title, description, due_date, priority) VALUES (?, ?, ?, ?, ?)",
                (message.from_user.id, data['title'], data['description'], data['due_date'], priority)
            )
            conn.commit()
    
    await message.answer("✅ Задача успешно создана!", reply_markup=get_tasks_keyboard())
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Мои задачи")
async def show_tasks(message: types.Message):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND status = 'active' ORDER BY due_date, priority",
            (message.from_user.id,)
        )
        tasks = cursor.fetchall()
    
    if not tasks:
        await message.answer("У вас нет активных задач.")
        return
    
    response = "📋 Ваши активные задачи:\n\n"
    for task in tasks:
        priority_emoji = "🔴" if task['priority'] == 'high' else "🟡" if task['priority'] == 'medium' else "🟢"
        due_date = datetime.strptime(task['due_date'], '%Y-%m-%d').date() if task['due_date'] else "Без срока"
        response += f"{priority_emoji} *{task['title']}*\n"
        response += f"📅 Срок: {due_date}\n"
        if task['description']:
            response += f"📝 {task['description']}\n"
        response += f"ID: {task['id']}\n\n"
    
    await message.answer(response, parse_mode='Markdown')

@dp.message_handler(lambda message: message.text == "✅ Завершить задачу")
async def complete_task_start(message: types.Message, state: FSMContext):
    await message.answer("Введите ID задачи для завершения:")
    await TaskStates.waiting_for_task_id.set()

@dp.message_handler(state=TaskStates.waiting_for_task_id)
async def complete_task(message: types.Message, state: FSMContext):
    try:
        task_id = int(message.text)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (task_id, message.from_user.id)
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                await message.answer(f"✅ Задача {task_id} завершена!")
            else:
                await message.answer("❌ Задача не найдена или уже завершена.")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректный ID задачи.")
    
    await state.finish()
    await message.answer("Меню задач:", reply_markup=get_tasks_keyboard())

# ==================== ДНЕВНИК ПИТАНИЯ ====================
@dp.message_handler(lambda message: message.text == "🍽 Дневник питания")
async def food_menu(message: types.Message):
    await message.answer("Меню дневника питания:", reply_markup=get_food_keyboard())

@dp.message_handler(lambda message: message.text in ["➕ Записать прием пищи", "🥗 Завтрак", "🍝 Обед", "🍽 Ужин", "🍎 Перекус"])
async def add_food_start(message: types.Message, state: FSMContext):
    meal_map = {
        "🥗 Завтрак": "завтрак",
        "🍝 Обед": "обед",
        "🍽 Ужин": "ужин",
        "🍎 Перекус": "перекус",
        "➕ Записать прием пищи": None
    }
    
    meal_type = meal_map.get(message.text)
    
    async with state.proxy() as data:
        if meal_type:
            data['meal_type'] = meal_type
            await message.answer("Что вы съели?")
            await FoodStates.waiting_for_food_name.set()
        else:
            await message.answer("Выберите тип приема пищи:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
                KeyboardButton("🥗 Завтрак"),
                KeyboardButton("🍝 Обед"),
                KeyboardButton("🍽 Ужин"),
                KeyboardButton("🍎 Перекус")
            ))
            await FoodStates.waiting_for_meal_type.set()

@dp.message_handler(state=FoodStates.waiting_for_meal_type)
async def add_food_meal_type(message: types.Message, state: FSMContext):
    meal_map = {
        "🥗 Завтрак": "завтрак",
        "🍝 Обед": "обед",
        "🍽 Ужин": "ужин",
        "🍎 Перекус": "перекус"
    }
    
    meal_type = meal_map.get(message.text)
    if not meal_type:
        await message.answer("Пожалуйста, выберите тип приема пищи из меню.")
        return
    
    async with state.proxy() as data:
        data['meal_type'] = meal_type
    
    await message.answer("Что вы съели?")
    await FoodStates.next()

@dp.message_handler(state=FoodStates.waiting_for_food_name)
async def add_food_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['food_name'] = message.text
    
    await message.answer("Сколько калорий? (только число)")
    await FoodStates.next()

@dp.message_handler(state=FoodStates.waiting_for_calories)
async def add_food_calories(message: types.Message, state: FSMContext):
    try:
        calories = int(message.text)
        async with state.proxy() as data:
            data['calories'] = calories
        
        await message.answer("Белки (г): (только число, или 0)")
        await FoodStates.next()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message_handler(state=FoodStates.waiting_for_proteins)
async def add_food_proteins(message: types.Message, state: FSMContext):
    try:
        proteins = float(message.text)
        async with state.proxy() as data:
            data['proteins'] = proteins
        
        await message.answer("Жиры (г): (только число, или 0)")
        await FoodStates.next()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message_handler(state=FoodStates.waiting_for_fats)
async def add_food_fats(message: types.Message, state: FSMContext):
    try:
        fats = float(message.text)
        async with state.proxy() as data:
            data['fats'] = fats
        
        await message.answer("Углеводы (г): (только число, или 0)")
        await FoodStates.next()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message_handler(state=FoodStates.waiting_for_carbs)
async def add_food_carbs(message: types.Message, state: FSMContext):
    try:
        carbs = float(message.text)
        
        async with state.proxy() as data:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO food_entries 
                       (user_id, meal_type, food_name, calories, proteins, fats, carbs) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (message.from_user.id, data['meal_type'], data['food_name'], 
                     data['calories'], data['proteins'], data['fats'], carbs)
                )
                conn.commit()
        
        await message.answer("✅ Запись о питании добавлена!", reply_markup=get_food_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message_handler(lambda message: message.text == "📊 Сегодняшнее питание")
async def show_today_food(message: types.Message):
    today = datetime.now().date()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM food_entries 
               WHERE user_id = ? AND date = ? 
               ORDER BY time""",
            (message.from_user.id, today)
        )
        entries = cursor.fetchall()
    
    if not entries:
        await message.answer("За сегодня записей о питании нет.")
        return
    
    total_calories = sum(entry['calories'] for entry in entries)
    total_proteins = sum(entry['proteins'] for entry in entries)
    total_fats = sum(entry['fats'] for entry in entries)
    total_carbs = sum(entry['carbs'] for entry in entries)
    
    response = f"📊 Питание за {today}:\n\n"
    
    for entry in entries:
        response += f"🕐 {entry['time'][:5]} - {entry['meal_type'].capitalize()}\n"
        response += f"🍽 {entry['food_name']}\n"
        response += f"📊 {entry['calories']} ккал | Б:{entry['proteins']} Ж:{entry['fats']} У:{entry['carbs']}\n\n"
    
    response += f"Итого: {total_calories} ккал\n"
    response += f"Б:{total_proteins:.1f} Ж:{total_fats:.1f} У:{total_carbs:.1f}"
    
    await message.answer(response)

# ==================== ПРИВЫЧКИ ====================
@dp.message_handler(lambda message: message.text == "💪 Привычки")
async def habits_menu(message: types.Message):
    await message.answer("Меню привычек:", reply_markup=get_habits_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить привычку")
async def add_habit_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название привычки:")
    await HabitStates.waiting_for_name.set()

@dp.message_handler(state=HabitStates.waiting_for_name)
async def add_habit_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['habit_name'] = message.text
    await message.answer("Введите описание привычки (или '-' если не нужно):")
    await HabitStates.next()

@dp.message_handler(state=HabitStates.waiting_for_description)
async def add_habit_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = None if message.text == '-' else message.text
    await message.answer("Выберите частоту:", reply_markup=get_frequency_keyboard())
    await HabitStates.next()

@dp.message_handler(state=HabitStates.waiting_for_frequency)
async def add_habit_frequency(message: types.Message, state: FSMContext):
    frequency_map = {
        "Ежедневно": "daily",
        "Еженедельно": "weekly",
        "Ежемесячно": "monthly"
    }
    
    frequency = frequency_map.get(message.text, "daily")
    
    async with state.proxy() as data:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO habits (user_id, habit_name, description, frequency) VALUES (?, ?, ?, ?)",
                (message.from_user.id, data['habit_name'], data['description'], frequency)
            )
            conn.commit()
    
    await message.answer("✅ Привычка успешно создана!", reply_markup=get_habits_keyboard())
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Мои привычки")
async def show_habits(message: types.Message):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM habits WHERE user_id = ?",
            (message.from_user.id,)
        )
        habits = cursor.fetchall()
    
    if not habits:
        await message.answer("У вас нет созданных привычек.")
        return
    
    response = "💪 Ваши привычки:\n\n"
    for habit in habits:
        cursor.execute(
            "SELECT COUNT(*) as count FROM habit_logs WHERE habit_id = ? AND completed_date = CURRENT_DATE",
            (habit['id'],)
        )
        completed_today = cursor.fetchone()['count'] > 0
        
        status = "✅" if completed_today else "⭕"
        response += f"{status} *{habit['habit_name']}*\n"
        response += f"📝 {habit['description'] or 'Нет описания'}\n"
        response += f"📅 Частота: {habit['frequency']}\n"
        response += f"ID: {habit['id']}\n\n"
    
    await message.answer(response, parse_mode='Markdown')

@dp.message_handler(lambda message: message.text == "✅ Отметить выполнение")
async def complete_habit_start(message: types.Message):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, habit_name FROM habits WHERE user_id = ?",
            (message.from_user.id,)
        )
        habits = cursor.fetchall()
    
    if not habits:
        await message.answer("У вас нет привычек для отметки.")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for habit in habits:
        keyboard.add(InlineKeyboardButton(
            text=habit['habit_name'],
            callback_data=f"complete_habit_{habit['id']}"
        ))
    
    await message.answer("Выберите привычку для отметки:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('complete_habit_'))
async def complete_habit_callback(callback_query: types.CallbackQuery):
    habit_id = int(callback_query.data.replace('complete_habit_', ''))
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO habit_logs (habit_id, user_id) VALUES (?, ?)",
            (habit_id, callback_query.from_user.id)
        )
        conn.commit()
    
    await bot.answer_callback_query(callback_query.id, text="✅ Отмечено!")
    await bot.send_message(callback_query.from_user.id, "Привычка отмечена как выполненная!")

# ==================== ЗАМЕТКИ ====================
@dp.message_handler(lambda message: message.text == "📝 Заметки")
async def notes_menu(message: types.Message):
    await message.answer("Меню заметок:", reply_markup=get_notes_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать заметку")
async def create_note_start(message: types.Message, state: FSMContext):
    await message.answer("Введите заголовок заметки:")
    await NoteStates.waiting_for_title.set()

@dp.message_handler(state=NoteStates.waiting_for_title)
async def create_note_title(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['title'] = message.text
    await message.answer("Введите содержимое заметки:")
    await NoteStates.next()

@dp.message_handler(state=NoteStates.waiting_for_content)
async def create_note_content(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)",
                (message.from_user.id, data['title'], message.text)
            )
            conn.commit()
    
    await message.answer("✅ Заметка создана!", reply_markup=get_notes_keyboard())
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Мои заметки")
async def show_notes(message: types.Message):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC",
            (message.from_user.id,)
        )
        notes = cursor.fetchall()
    
    if not notes:
        await message.answer("У вас нет заметок.")
        return
    
    response = "📝 Ваши заметки:\n\n"
    for note in notes:
        created_at = datetime.strptime(note['created_at'], '%Y-%m-%d %H:%M:%S')
        response += f"📌 *{note['title']}*\n"
        response += f"🆔 ID: {note['id']}\n"
        response += f"📅 {created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await message.answer(response, parse_mode='Markdown')

@dp.message_handler(lambda message: message.text == "🔍 Просмотреть заметку")
async def view_note_start(message: types.Message, state: FSMContext):
    await message.answer("Введите ID заметки для просмотра:")
    await state.set_state("waiting_for_note_id")

@dp.message_handler(state="waiting_for_note_id")
async def view_note(message: types.Message, state: FSMContext):
    try:
        note_id = int(message.text)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                (note_id, message.from_user.id)
            )
            note = cursor.fetchone()
        
        if note:
            response = f"📝 *{note['title']}*\n\n"
            response += f"{note['content']}\n\n"
            response += f"📅 Создано: {note['created_at']}"
            await message.answer(response, parse_mode='Markdown')
        else:
            await message.answer("❌ Заметка не найдена.")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректный ID.")
    
    await state.finish()
    await message.answer("Меню заметок:", reply_markup=get_notes_keyboard())

# ==================== СТАТИСТИКА ====================
@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Статистика задач
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed FROM tasks WHERE user_id = ?",
            (message.from_user.id,)
        )
        task_stats = cursor.fetchone()
        
        # Статистика питания за сегодня
        cursor.execute(
            "SELECT SUM(calories) as total_calories FROM food_entries WHERE user_id = ? AND date = CURRENT_DATE",
            (message.from_user.id,)
        )
        food_stats = cursor.fetchone()
        
        # Статистика привычек
        cursor.execute(
            "SELECT COUNT(*) as total_habits FROM habits WHERE user_id = ?",
            (message.from_user.id,)
        )
        habit_stats = cursor.fetchone()
        
        cursor.execute(
            "SELECT COUNT(*) as completed_today FROM habit_logs WHERE user_id = ? AND completed_date = CURRENT_DATE",
            (message.from_user.id,)
        )
        habit_today = cursor.fetchone()
        
        # Статистика заметок
        cursor.execute(
            "SELECT COUNT(*) as total_notes FROM notes WHERE user_id = ?",
            (message.from_user.id,)
        )
        note_stats = cursor.fetchone()
    
    response = "📊 Ваша статистика:\n\n"
    response += f"📋 Задачи:\n"
    response += f"├ Всего: {task_stats['total']}\n"
    response += f"└ Выполнено: {task_stats['completed']}\n\n"
    
    response += f"🍽 Питание сегодня:\n"
    response += f"└ Калории: {food_stats['total_calories'] or 0} ккал\n\n"
    
    response += f"💪 Привычки:\n"
    response += f"├ Всего: {habit_stats['total_habits']}\n"
    response += f"└ Выполнено сегодня: {habit_today['completed_today']}\n\n"
    
    response += f"📝 Заметки:\n"
    response += f"└ Всего: {note_stats['total_notes']}"
    
    await message.answer(response)

# ==================== ЗАПУСК БОТА ====================
if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
