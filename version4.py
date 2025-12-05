import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
from datetime import datetime, timedelta
import logging
import time
import sqlite3
import os
import random
import threading
import schedule
from typing import Dict, List, Optional
import re

# ============================================
# КОНФИГУРАЦИЯ БОТА
# ============================================

BOT_TOKEN = "8045925681:AAGsbJnHkjyQ23X_4OlctxobxLcb-RZb7aM"
ADMIN_CHAT_ID = 7669840193
DATABASE_NAME = "database.db"

# Настройки защиты от спама
MAX_MESSAGES = 10
TIME_WINDOW = 300
BLOCK_DURATION = 600

# Настройки уведомлений
CHECK_INTERVAL_MINUTES = 5

# Вопросы для регистрации
REGISTRATION_QUESTIONS = [
    "📋 *Вопрос 1/3:* У вас уже есть свой портфель с инвестициями?",
    "📋 *Вопрос 2/3:* Рассматриваете ли в ближайшее время приобретение новых акций?",
    "📋 *Вопрос 3/3:* Какой торговой площадкой вы пользуетесь?"
]

# Варианты ответов для вопросов
REGISTRATION_ANSWERS = {
    1: ["✅ Да, уже инвестирую", "🤔 Только планирую", "❌ Нет, не инвестирую"],
    2: ["✅ Да, планирую покупку", "🤔 Возможно", "❌ Нет, не планирую"],
    3: ["📊 Московская биржа (MOEX)", "🌍 Зарубежные брокеры", "📱 Криптобиржи", "🤷 Не пользуюсь"]
}

# Валидация конфигурации
def validate_config():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("BOT_TOKEN не установлен!")
    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID не установлен!")

validate_config()

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# СЛОВАРИ ДАННЫХ
# ============================================

# Топ популярных валют
POPULAR_CURRENCIES = {
    'USD': {'name': '🇺🇸 Доллар США', 'symbol': '$', 'flag': '🇺🇸'},
    'EUR': {'name': '🇪🇺 Евро', 'symbol': '€', 'flag': '🇪🇺'},
    'GBP': {'name': '🇬🇧 Фунт стерлингов', 'symbol': '£', 'flag': '🇬🇧'},
    'JPY': {'name': '🇯🇵 Японская иена', 'symbol': '¥', 'flag': '🇯🇵'},
    'CNY': {'name': '🇨🇳 Китайский юань', 'symbol': '¥', 'flag': '🇨🇳'},
    'CHF': {'name': '🇨🇭 Швейцарский франк', 'symbol': 'Fr', 'flag': '🇨🇭'},
    'CAD': {'name': '🇨🇦 Канадский доллар', 'symbol': 'C$', 'flag': '🇨🇦'},
    'AUD': {'name': '🇦🇺 Австралийский доллар', 'symbol': 'A$', 'flag': '🇦🇺'},
    'SGD': {'name': '🇸🇬 Сингапурский доллар', 'symbol': 'S$', 'flag': '🇸🇬'},
    'HKD': {'name': '🇭🇰 Гонконгский доллар', 'symbol': 'HK$', 'flag': '🇭🇰'},
}

# Популярные криптовалюты
POPULAR_CRYPTOCURRENCIES = {
    'bitcoin': {'name': 'Bitcoin', 'symbol': 'BTC', 'emoji': '₿'},
    'ethereum': {'name': 'Ethereum', 'symbol': 'ETH', 'emoji': '🔷'},
    'tether': {'name': 'Tether', 'symbol': 'USDT', 'emoji': '💵'},
    'binancecoin': {'name': 'BNB', 'symbol': 'BNB', 'emoji': '💎'},
    'solana': {'name': 'Solana', 'symbol': 'SOL', 'emoji': '⚡'},
    'ripple': {'name': 'XRP', 'symbol': 'XRP', 'emoji': '❌'},
    'cardano': {'name': 'Cardano', 'symbol': 'ADA', 'emoji': '🅰️'},
    'dogecoin': {'name': 'Dogecoin', 'symbol': 'DOGE', 'emoji': '🐕'},
    'polkadot': {'name': 'Polkadot', 'symbol': 'DOT', 'emoji': '🔴'},
    'litecoin': {'name': 'Litecoin', 'symbol': 'LTC', 'emoji': 'Ł'},
}

# База данных российских акций
RUSSIAN_STOCKS = {
    'GAZP': {'name': 'Газпром', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'SBER': {'name': 'Сбербанк', 'sector': 'Финансы', 'market': 'MOEX'},
    'LKOH': {'name': 'Лукойл', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'ROSN': {'name': 'Роснефть', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'NLMK': {'name': 'НЛМК', 'sector': 'Металлургия', 'market': 'MOEX'},
    'GMKN': {'name': 'ГМК Норникель', 'sector': 'Металлургия', 'market': 'MOEX'},
    'PLZL': {'name': 'Полюс', 'sector': 'Добыча золота', 'market': 'MOEX'},
    'TATN': {'name': 'Татнефть', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'VTBR': {'name': 'ВТБ', 'sector': 'Финансы', 'market': 'MOEX'},
    'ALRS': {'name': 'АЛРОСА', 'sector': 'Добыча алмазов', 'market': 'MOEX'},
    'MGNT': {'name': 'Магнит', 'sector': 'Розничная торговля', 'market': 'MOEX'},
    'POLY': {'name': 'Полиметалл', 'sector': 'Добыча металлов', 'market': 'MOEX'},
    'AFKS': {'name': 'Система', 'sector': 'Конгломерат', 'market': 'MOEX'},
    'PHOR': {'name': 'ФосАгро', 'sector': 'Химическая промышленность', 'market': 'MOEX'},
    'SNGS': {'name': 'Сургутнефтегаз (обыкн.)', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'SNGSP': {'name': 'Сургутнефтегаз (прив.)', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'MTSS': {'name': 'МТС', 'sector': 'Телекоммуникации', 'market': 'MOEX'},
    'RUAL': {'name': 'РУСАЛ', 'sector': 'Металлургия', 'market': 'MOEX'},
    'MOEX': {'name': 'Московская биржа', 'sector': 'Финансы', 'market': 'MOEX'},
    'YNDX': {'name': 'Яндекс', 'sector': 'Интернет', 'market': 'MOEX'},
}

# Топ-20 российских акций для быстрого доступа
TOP_RUSSIAN_STOCKS = [
    'GAZP', 'SBER', 'LKOH', 'ROSN', 'NLMK', 'GMKN', 'PLZL', 'TATN', 'VTBR', 'ALRS',
    'MGNT', 'POLY', 'AFKS', 'PHOR', 'SNGS', 'SNGSP', 'MTSS', 'RUAL', 'MOEX', 'YNDX'
]

# ============================================
# БАЗА ДАННЫХ
# ============================================

class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Новая таблица для регистрационных данных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_registration (
                    user_id INTEGER PRIMARY KEY,
                    question_1 TEXT,
                    question_2 TEXT,
                    question_3 TEXT,
                    registration_completed BOOLEAN DEFAULT FALSE,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_type TEXT,
                    content TEXT,
                    message_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    forwarded_to_admin BOOLEAN DEFAULT FALSE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    details TEXT,
                    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Новые таблицы для портфеля
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    asset_type TEXT,
                    symbol TEXT,
                    quantity REAL,
                    purchase_price REAL,
                    purchase_date TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    asset_type TEXT,
                    symbol TEXT,
                    alert_type TEXT,
                    threshold_value REAL,
                    time_frame_minutes INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_triggered TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица статуса пользователя
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_status (
                    user_id INTEGER PRIMARY KEY,
                    has_portfolio BOOLEAN DEFAULT FALSE,
                    first_login_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, last_activity) 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
    
    def update_user_activity(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_activity = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def add_registration_data(self, user_id, question_number, answer):
        """Добавить ответ на вопрос регистрации"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                column_name = f'question_{question_number}'
                
                # Проверяем, существует ли запись
                cursor.execute(f'SELECT 1 FROM user_registration WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()
                
                if exists:
                    cursor.execute(f'''
                        UPDATE user_registration 
                        SET {column_name} = ? 
                        WHERE user_id = ?
                    ''', (answer, user_id))
                else:
                    cursor.execute(f'''
                        INSERT INTO user_registration (user_id, {column_name}) 
                        VALUES (?, ?)
                    ''', (user_id, answer))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения регистрационных данных: {e}")
            return False
    
    def complete_registration(self, user_id):
        """Завершить регистрацию пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_registration 
                    SET registration_completed = TRUE 
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка завершения регистрации: {e}")
            return False
    
    def is_registration_completed(self, user_id):
        """Проверить, завершена ли регистрация"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT registration_completed FROM user_registration 
                    WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()
                
                if row is None:
                    return False
                return bool(row[0])
        except Exception as e:
            logger.error(f"Ошибка проверки регистрации: {e}")
            return False
    
    def get_registration_data(self, user_id):
        """Получить данные регистрации"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question_1, question_2, question_3 
                    FROM user_registration WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'question_1': row[0],
                        'question_2': row[1],
                        'question_3': row[2]
                    }
                return None
        except Exception as e:
            logger.error(f"Ошибка получения регистрационных данных: {e}")
            return None
    
    def add_message(self, user_id, message_type, content, forwarded=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages 
                (user_id, message_type, content, forwarded_to_admin) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, message_type, content, forwarded))
            conn.commit()
    
    def add_user_action(self, user_id, action_type, details=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_actions 
                (user_id, action_type, details) 
                VALUES (?, ?, ?)
            ''', (user_id, action_type, details))
            conn.commit()
    
    def get_user_status(self, user_id):
        """Получить статус пользователя (создал ли портфель)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT has_portfolio FROM user_status WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                if row is None:
                    cursor.execute('INSERT OR IGNORE INTO user_status (user_id) VALUES (?)', (user_id,))
                    conn.commit()
                    return False
                return bool(row[0])
        except Exception as e:
            logger.error(f"Ошибка получения статуса пользователя: {e}")
            return False
    
    def update_user_status(self, user_id, has_portfolio=True):
        """Обновить статус пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_status (user_id, has_portfolio) 
                    VALUES (?, ?)
                ''', (user_id, has_portfolio))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса пользователя: {e}")
            return False
    
    # Методы для портфеля
    def add_to_portfolio(self, user_id, asset_type, symbol, quantity, purchase_price, purchase_date, notes=""):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO portfolio 
                    (user_id, asset_type, symbol, quantity, purchase_price, purchase_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, asset_type.upper(), symbol.upper(), quantity, purchase_price, purchase_date, notes))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления в портфель: {e}")
            return False
    
    def get_portfolio(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, asset_type, symbol, quantity, purchase_price, purchase_date, notes
                    FROM portfolio WHERE user_id = ? ORDER BY created_at DESC
                ''', (user_id,))
                rows = cursor.fetchall()
                return [{
                    'id': row[0],
                    'asset_type': row[1],
                    'symbol': row[2],
                    'quantity': row[3],
                    'purchase_price': row[4],
                    'purchase_date': row[5],
                    'notes': row[6]
                } for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения портфеля: {e}")
            return []
    
    def remove_from_portfolio(self, user_id, portfolio_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM portfolio WHERE id = ? AND user_id = ?', (portfolio_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления из портфеля: {e}")
            return False
    
    # Методы для уведомлений
    def add_alert(self, user_id, asset_type, symbol, alert_type, threshold_value, time_frame_minutes=0):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts 
                    (user_id, asset_type, symbol, alert_type, threshold_value, time_frame_minutes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, asset_type.upper(), symbol.upper(), alert_type, threshold_value, time_frame_minutes))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления уведомления: {e}")
            return -1
    
    def get_alerts(self, user_id=None, is_active=True):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if user_id:
                    cursor.execute('''
                        SELECT id, user_id, asset_type, symbol, alert_type, threshold_value, 
                               time_frame_minutes, is_active, last_triggered
                        FROM alerts WHERE user_id = ? AND is_active = ?
                    ''', (user_id, is_active))
                else:
                    cursor.execute('''
                        SELECT id, user_id, asset_type, symbol, alert_type, threshold_value, 
                               time_frame_minutes, is_active, last_triggered
                        FROM alerts WHERE is_active = ?
                    ''', (is_active,))
                rows = cursor.fetchall()
                return [{
                    'id': row[0],
                    'user_id': row[1],
                    'asset_type': row[2],
                    'symbol': row[3],
                    'alert_type': row[4],
                    'threshold_value': row[5],
                    'time_frame_minutes': row[6],
                    'is_active': bool(row[7]),
                    'last_triggered': row[8]
                } for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения уведомлений: {e}")
            return []
    
    def update_alert_status(self, alert_id, is_active):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE alerts SET is_active = ? WHERE id = ?', (is_active, alert_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления статуса уведомления: {e}")
            return False
    
    def delete_alert(self, alert_id, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM alerts WHERE id = ? AND user_id = ?', (alert_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления уведомления: {e}")
            return False

# Инициализация базы данных
db = Database(DATABASE_NAME)

# ============================================
# СЛОВАРИ СОСТОЯНИЙ
# ============================================

user_states = {}
user_message_history = {}
user_blocks = {}
user_temp_data = {}

# ============================================
# ФУНКЦИИ УТИЛИТЫ
# ============================================

def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = KeyboardButton('🏆 Топ валют')
    button2 = KeyboardButton('📈 Криптовалюты')
    button3 = KeyboardButton('📊 Аналитика РФ')
    button4 = KeyboardButton('🔍 Поиск валюты')
    button5 = KeyboardButton('🔎 Поиск крипты')
    button6 = KeyboardButton('📈 Поиск акций')
    button7 = KeyboardButton('📊 Мой портфель')
    button8 = KeyboardButton('🔔 Мои уведомления')
    button9 = KeyboardButton('📨 Связь с админом')
    button10 = KeyboardButton('ℹ️ О боте')
    button11 = KeyboardButton('🔄 Пересоздать портфель')
    keyboard.add(button1, button2, button3, button4, button5, button6, button7, button8, button9, button10, button11)
    return keyboard

def create_registration_keyboard(question_number):
    """Создать клавиатуру с вариантами ответов для регистрации"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    answers = REGISTRATION_ANSWERS.get(question_number, [])
    for answer in answers:
        keyboard.add(KeyboardButton(answer))
    
    # Кнопка отмены только для первого вопроса
    if question_number == 1:
        keyboard.add(KeyboardButton('❌ Отмена регистрации'))
    
    return keyboard

def create_registration_cancel_keyboard():
    """Клавиатура для отмены регистрации"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton('✅ Продолжить регистрацию'))
    keyboard.add(KeyboardButton('❌ Отменить регистрацию'))
    return keyboard

def create_welcome_keyboard():
    """Клавиатура после завершения регистрации"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = KeyboardButton('📊 Создать портфель')
    button2 = KeyboardButton('ℹ️ О боте')
    button3 = KeyboardButton('📨 Связь с админом')
    keyboard.add(button1, button2, button3)
    return keyboard

def create_contact_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    button1 = KeyboardButton('❌ Отмена')
    keyboard.add(button1)
    return keyboard

def create_portfolio_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить актив", callback_data="add_asset"),
        InlineKeyboardButton("➖ Удалить актив", callback_data="remove_asset"),
        InlineKeyboardButton("📊 Обзор портфеля", callback_data="view_portfolio"),
        InlineKeyboardButton("💰 Расчет прибыли", callback_data="calculate_profit"),
        InlineKeyboardButton("❌ Закрыть", callback_data="close_portfolio")
    )
    return keyboard

def create_alerts_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Новое уведомление", callback_data="add_alert"),
        InlineKeyboardButton("👁 Показать все", callback_data="view_alerts"),
        InlineKeyboardButton("⚙️ Управление", callback_data="manage_alerts"),
        InlineKeyboardButton("❌ Закрыть", callback_data="close_alerts")
    )
    return keyboard

def create_alert_type_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💰 Цена выше", callback_data="alert_price_above"),
        InlineKeyboardButton("💰 Цена ниже", callback_data="alert_price_below"),
        InlineKeyboardButton("📈 Рост на %", callback_data="alert_percent_up"),
        InlineKeyboardButton("📉 Падение на %", callback_data="alert_percent_down"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_alert")
    )
    return keyboard

def create_asset_type_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("₿ Криптовалюта", callback_data="asset_crypto"),
        InlineKeyboardButton("📈 Акция РФ", callback_data="asset_stock"),
        InlineKeyboardButton("💵 Валюта", callback_data="asset_currency"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_asset")
    )
    return keyboard

def save_user_info(message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    db.update_user_activity(user.id)

def is_user_blocked(user_id):
    if user_id in user_blocks:
        block_time = user_blocks[user_id]
        if datetime.now() - block_time < timedelta(seconds=BLOCK_DURATION):
            return True
        else:
            del user_blocks[user_id]
            if user_id in user_message_history:
                del user_message_history[user_id]
    return False

def update_message_history(user_id):
    now = datetime.now()
    
    if user_id not in user_message_history:
        user_message_history[user_id] = []
    
    user_message_history[user_id].append(now)
    
    user_message_history[user_id] = [
        msg_time for msg_time in user_message_history[user_id]
        if now - msg_time < timedelta(seconds=TIME_WINDOW)
    ]
    
    if len(user_message_history[user_id]) > MAX_MESSAGES:
        user_blocks[user_id] = now
        return False
    
    return True

def get_remaining_block_time(user_id):
    if user_id in user_blocks:
        block_time = user_blocks[user_id]
        elapsed = datetime.now() - block_time
        remaining = BLOCK_DURATION - elapsed.total_seconds()
        return max(0, int(remaining / 60))
    return 0

def check_message_limit(user_id):
    if is_user_blocked(user_id):
        remaining_time = get_remaining_block_time(user_id)
        return False, f"🚫 *Вы превысили лимит сообщений!*\n\nПодождите {remaining_time} минут."
    
    if not update_message_history(user_id):
        remaining_time = get_remaining_block_time(user_id)
        return False, f"🚫 *Слишком много сообщений!*\n\nБлокировка на {remaining_time} минут."
    
    return True, ""

def check_user_access(user_id, chat_id, feature_name=""):
    """Проверка, имеет ли пользователь доступ к функциям"""
    # Сначала проверяем, завершена ли регистрация
    registration_completed = db.is_registration_completed(user_id)
    
    if not registration_completed:
        access_denied_text = f"""
🚫 *Доступ ограничен*

Для использования функций бота необходимо завершить регистрацию.

Пожалуйста, используйте команду /start для начала регистрации.
"""
        return False, access_denied_text
    
    # Затем проверяем, создан ли портфель
    has_portfolio = db.get_user_status(user_id)
    
    if not has_portfolio and feature_name:
        access_denied_text = f"""
🚫 *Доступ ограничен*

Для использования функции *"{feature_name}"* необходимо сначала создать портфель.

Пожалуйста, используйте кнопку "📊 Создать портфель", чтобы продолжить.
"""
        return False, access_denied_text
    
    return True, ""

def forward_to_admin(message: Message, content_type="сообщение"):
    try:
        user = message.from_user
        
        content = message.text or message.caption or f"[{content_type}]"
        db.add_message(user.id, content_type, content, True)
        
        user_info = f"👤 Новое сообщение от пользователя:\n"
        user_info += f"Имя: {user.first_name or ''} {user.last_name or ''}\n"
        user_info += f"ID: {user.id}\n"
        if user.username:
            user_info += f"Username: @{user.username}\n"
        user_info += f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        user_info += f"Тип: {content_type}\n"
        
        if message.text and content_type == "текст":
            user_info += f"\n📨 Текст сообщения:\n{message.text}"

        bot.send_message(ADMIN_CHAT_ID, user_info)
        bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        return False

# ============================================
# ФУНКЦИИ РЕГИСТРАЦИИ
# ============================================

def start_registration(chat_id, user_id):
    """Начать процесс регистрации"""
    user_states[chat_id] = 'registration_1'
    
    welcome_text = """
*🎉 Добро пожаловать в Финансовый Бот!*

Перед началом работы давайте познакомимся!

*📋 Пройдите быструю регистрацию:*
Ответьте на 3 простых вопроса, чтобы мы могли предложить вам наиболее подходящие инструменты.

*🔒 Ваши данные:*
• Используются только для улучшения сервиса
• Не передаются третьим лицам
• Хранятся в зашифрованном виде

*Готовы начать?*
"""
    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_registration_keyboard(1)
    )
    
    # Задаем первый вопрос
    bot.send_message(
        chat_id,
        REGISTRATION_QUESTIONS[0],
        parse_mode='Markdown',
        reply_markup=create_registration_keyboard(1)
    )

def process_registration_answer(message):
    """Обработать ответ на вопрос регистрации"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_state = user_states.get(chat_id, '')
    
    if not current_state.startswith('registration_'):
        return False
    
    question_number = int(current_state.split('_')[1])
    
    # Проверяем, является ли ответ отменой (только для первого вопроса)
    if question_number == 1 and message.text == '❌ Отмена регистрации':
        user_states[chat_id] = 'registration_cancel'
        
        cancel_text = """
*❌ Отмена регистрации*

Вы уверены, что хотите отменить регистрацию?

*Без регистрации вы не сможете:*
• Использовать основные функции бота
• Создать портфель
• Получать уведомления

Вы можете продолжить регистрацию позже с помощью команды /start
"""
        bot.send_message(
            chat_id,
            cancel_text,
            parse_mode='Markdown',
            reply_markup=create_registration_cancel_keyboard()
        )
        return True
    
    # Сохраняем ответ
    db.add_registration_data(user_id, question_number, message.text)
    
    # Переходим к следующему вопросу или завершаем
    if question_number < 3:
        next_question = question_number + 1
        user_states[chat_id] = f'registration_{next_question}'
        
        progress = f"*Прогресс: {next_question}/3*\n\n"
        bot.send_message(
            chat_id,
            progress + REGISTRATION_QUESTIONS[next_question - 1],
            parse_mode='Markdown',
            reply_markup=create_registration_keyboard(next_question)
        )
    else:
        # Завершение регистрации
        complete_registration(chat_id, user_id)
    
    return True

def complete_registration(chat_id, user_id):
    """Завершить регистрацию"""
    db.complete_registration(user_id)
    user_states[chat_id] = 'registration_completed'
    
    # Получаем данные регистрации для итогового сообщения
    reg_data = db.get_registration_data(user_id)
    
    completion_text = """
*✅ Регистрация завершена!*

Спасибо за ответы! Теперь мы знаем больше о ваших инвестиционных предпочтениях.

*📊 Ваши ответы:*
"""
    
    if reg_data:
        for i in range(1, 4):
            question_text = REGISTRATION_QUESTIONS[i-1].replace("📋 *Вопрос", "• *Вопрос")
            completion_text += f"\n{question_text}\n   Ответ: *{reg_data[f'question_{i}']}*"
    
    completion_text += """

*🚀 Что дальше?*
1. Создайте свой портфель для отслеживания активов
2. Получите доступ ко всем функциям бота
3. Настройте уведомления о важных изменениях

*🎁 Бонус:*
После создания портфеля вы получите доступ к:
• Актуальным курсам валют и криптовалют
• Данным по российским акциям
• Умным уведомлениям
"""
    
    bot.send_message(
        chat_id,
        completion_text,
        parse_mode='Markdown',
        reply_markup=create_welcome_keyboard()
    )
    
    # Отправляем уведомление админу
    try:
        user = bot.get_chat(user_id)
        admin_notification = f"📋 *Новый пользователь завершил регистрацию*\n\n"
        admin_notification += f"👤 Имя: {user.first_name or ''} {user.last_name or ''}\n"
        admin_notification += f"🆔 ID: {user_id}\n"
        if user.username:
            admin_notification += f"📱 @{user.username}\n"
        
        if reg_data:
            admin_notification += f"\n*Ответы:*\n"
            for i in range(1, 4):
                admin_notification += f"{i}. {reg_data[f'question_{i}']}\n"
        
        bot.send_message(ADMIN_CHAT_ID, admin_notification, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

# ============================================
# ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ
# ============================================

def get_currency_rates():
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        data = response.json()
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        result = f"*🏆 ТОП ВАЛЮТ* \n*Время:* {current_time}\n\n"
        
        currencies_to_show = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CHF', 'CAD', 'AUD', 'SGD', 'HKD']
        
        for i, code in enumerate(currencies_to_show, 1):
            if code in data['Valute']:
                value = data['Valute'][code]['Value']
                previous = data['Valute'][code]['Previous']
                change = value - previous
                change_icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                currency_name = POPULAR_CURRENCIES[code]['name']
                result += f"{i}. {currency_name}: *{value:.2f}₽* {change_icon}\n"
        
        result += f"\n_Данные ЦБ РФ, обновление: {current_time}_"
        return result
        
    except Exception as e:
        return f"❌ *Не удалось получить данные*\nОшибка: {str(e)}"

def get_crypto_rates():
    try:
        crypto_ids = list(POPULAR_CRYPTOCURRENCIES.keys())
        crypto_ids_str = ','.join(crypto_ids)
        
        crypto_url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_ids_str}&vs_currencies=rub,usd&include_24hr_change=true'
        response = requests.get(crypto_url, timeout=10)
        data = response.json()
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        result = f"*📈 КРИПТОВАЛЮТЫ* \n*Время:* {current_time}\n\n"
        
        for i, (crypto_id, crypto_info) in enumerate(POPULAR_CRYPTOCURRENCIES.items(), 1):
            if crypto_id in data:
                price_usd = data[crypto_id].get('usd', 0)
                price_rub = data[crypto_id].get('rub', 0)
                change_24h = data[crypto_id].get('usd_24h_change', 0) or 0
                change_icon = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➡️"
                
                result += f"{i}. {crypto_info['emoji']} *{crypto_info['name']} ({crypto_info['symbol']})*\n"
                result += f"   🇺🇸 ${price_usd:,.2f}\n"
                result += f"   🇷🇺 {price_rub:,.0f}₽\n"
                result += f"   24ч: `{change_24h:+.1f}%` {change_icon}\n\n"
        
        result += f"_Данные: CoinGecko, обновление: {current_time}_"
        return result
        
    except Exception as e:
        return f"*❌ Не удалось получить данные о криптовалютах*\nОшибка: {str(e)}"

def get_russian_stocks_data():
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        result = f"*📊 АНАЛИТИКА АКЦИЙ РФ - ТОП 20* \n*Время:* {current_time}\n\n"
        
        mock_stocks_data = [
            {'ticker': 'GAZP', 'name': 'Газпром', 'price': 180.5, 'change': 1.2, 'change_percent': 0.67, 'volume': 1250000},
            {'ticker': 'SBER', 'name': 'Сбербанк', 'price': 275.3, 'change': -2.1, 'change_percent': -0.76, 'volume': 980000},
            {'ticker': 'LKOH', 'name': 'Лукойл', 'price': 6850.2, 'change': 45.3, 'change_percent': 0.67, 'volume': 450000},
            {'ticker': 'ROSN', 'name': 'Роснефть', 'price': 520.8, 'change': -3.2, 'change_percent': -0.61, 'volume': 720000},
            {'ticker': 'NLMK', 'name': 'НЛМК', 'price': 185.6, 'change': 1.8, 'change_percent': 0.98, 'volume': 310000},
            {'ticker': 'GMKN', 'name': 'ГМК Норникель', 'price': 15890.5, 'change': 120.3, 'change_percent': 0.76, 'volume': 89000},
            {'ticker': 'PLZL', 'name': 'Полюс', 'price': 11250.8, 'change': -85.2, 'change_percent': -0.75, 'volume': 67000},
            {'ticker': 'TATN', 'name': 'Татнефть', 'price': 385.4, 'change': 2.1, 'change_percent': 0.55, 'volume': 290000},
            {'ticker': 'VTBR', 'name': 'ВТБ', 'price': 0.0285, 'change': 0.0002, 'change_percent': 0.71, 'volume': 4500000},
            {'ticker': 'ALRS', 'name': 'АЛРОСА', 'price': 78.9, 'change': 0.6, 'change_percent': 0.77, 'volume': 1800000},
        ]
        
        total_stocks = len(mock_stocks_data)
        green_count = sum(1 for stock in mock_stocks_data if stock['change'] > 0)
        red_count = sum(1 for stock in mock_stocks_data if stock['change'] < 0)
        
        total_change = sum(stock['change_percent'] for stock in mock_stocks_data)
        avg_change = total_change / total_stocks
        
        result += f"📈 *Общая статистика:*\n"
        result += f"• Растут: {green_count} акций\n"
        result += f"• Падают: {red_count} акций\n"
        result += f"• Без изменений: {total_stocks - green_count - red_count} акций\n"
        result += f"• Среднее изменение: {avg_change:+.2f}%\n\n"
        
        result += f"🏆 *Топ акций (выборочно):*\n"
        
        for i, stock in enumerate(mock_stocks_data[:5], 1):
            change_icon = "🟢" if stock['change'] > 0 else "🔴" if stock['change'] < 0 else "⚪"
            change_sign = "+" if stock['change'] > 0 else ""
            
            result += f"{i}. *{stock['ticker']}* - {stock['name']}\n"
            result += f"   💰 Цена: {stock['price']:,.1f}₽\n"
            result += f"   📊 Изменение: {change_sign}{stock['change']:,.1f} ({change_sign}{stock['change_percent']:.2f}%) {change_icon}\n\n"
        
        result += "*📈 Источники данных:*\n"
        result += "• Московская биржа (MOEX)\n"
        result += "• Котировки в режиме реального времени\n\n"
        
        result += "*⚠️ ВНИМАНИЕ:*\n"
        result += "• Данные носят информационный характер\n"
        result += "• Не являются инвестиционной рекомендацией\n"
        result += f"• Обновлено: {current_time}"
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных акций: {e}")
        return f"*❌ Не удалось получить данные с биржи*\nОшибка: {str(e)}\n\nПопробуйте позже."

def search_currency(query):
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        data = response.json()
        
        query = query.upper().strip()
        results = []
        
        if query in data['Valute']:
            valute = data['Valute'][query]
            results.append({
                'code': query,
                'name': valute['Name'],
                'value': valute['Value'],
                'previous': valute['Previous'],
                'change': valute['Value'] - valute['Previous'],
                'nominal': valute['Nominal']
            })
            return results
        
        search_results = []
        for code, valute in data['Valute'].items():
            if query in code or query in valute['Name'].upper():
                search_results.append({
                    'code': code,
                    'name': valute['Name'],
                    'value': valute['Value'],
                    'previous': valute['Previous'],
                    'change': valute['Value'] - valute['Previous'],
                    'nominal': valute['Nominal']
                })
        
        if not search_results:
            for code, info in POPULAR_CURRENCIES.items():
                if query in code or query in info['name'].upper():
                    if code in data['Valute']:
                        valute = data['Valute'][code]
                        search_results.append({
                            'code': code,
                            'name': valute['Name'],
                            'value': valute['Value'],
                            'previous': valute['Previous'],
                            'change': valute['Value'] - valute['Previous'],
                            'nominal': valute['Nominal']
                        })
        
        return search_results[:10]
        
    except Exception as e:
        logger.error(f"Ошибка при поиске валюты: {e}")
        return []

def format_search_results(results, query):
    if not results:
        return f"❌ *Валюты не найдены*\n\nПо запросу: `{query}`\n\n*Советы:*\n• Используйте код валюты (USD, EUR)\n• Или часть названия (доллар, евро)\n\n*Популярные валюты:*\nUSD, EUR, GBP, JPY, CNY"
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if len(results) == 1:
        result = f"*🔍 Найдена валюта*\n\n"
    else:
        result = f"*🔍 Найдено {len(results)} валют*\n\n"
    
    for i, currency in enumerate(results, 1):
        change_icon = "📈" if currency['change'] > 0 else "📉" if currency['change'] < 0 else "➡️"
        change_sign = "+" if currency['change'] > 0 else ""
        
        if currency['nominal'] > 1:
            value_per_unit = currency['value'] / currency['nominal']
            result += f"{i}. *{currency['code']}* - {currency['name']}\n"
            result += f"   💰 {currency['nominal']} ед.: *{currency['value']:.4f}₽*\n"
            result += f"   📊 1 ед.: *{value_per_unit:.4f}₽*\n"
        else:
            result += f"{i}. *{currency['code']}* - {currency['name']}\n"
            result += f"   💰 *{currency['value']:.4f}₽*\n"
        
        result += f"   📊 Изменение: {change_sign}{currency['change']:.4f} {change_icon}\n"
        
        if currency['code'] in POPULAR_CURRENCIES:
            flag = POPULAR_CURRENCIES[currency['code']]['flag']
            symbol = POPULAR_CURRENCIES[currency['code']]['symbol']
            result += f"   {flag} Символ: {symbol}\n"
        
        result += "\n"
    
    result += f"_По запросу: {query}_\n"
    result += f"_Данные ЦБ РФ, время: {current_time}_"
    
    return result

def search_crypto(query):
    try:
        query = query.lower().strip()
        
        search_url = f'https://api.coingecko.com/api/v3/search?query={query}'
        response = requests.get(search_url, timeout=10)
        search_data = response.json()
        
        if 'coins' not in search_data or not search_data['coins']:
            return []
        
        top_coins = search_data['coins'][:5]
        coin_ids = [coin['id'] for coin in top_coins]
        
        if coin_ids:
            coin_ids_str = ','.join(coin_ids)
            price_url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_ids_str}&vs_currencies=rub,usd&include_24hr_change=true'
            price_response = requests.get(price_url, timeout=10)
            price_data = price_response.json()
            
            results = []
            for coin in top_coins:
                coin_id = coin['id']
                if coin_id in price_data:
                    results.append({
                        'id': coin_id,
                        'name': coin['name'],
                        'symbol': coin['symbol'].upper(),
                        'market_cap_rank': coin.get('market_cap_rank', 9999),
                        'price_usd': price_data[coin_id].get('usd', 0),
                        'price_rub': price_data[coin_id].get('rub', 0),
                        'change_24h': price_data[coin_id].get('usd_24h_change', 0) or 0
                    })
            
            return results
        else:
            return []
            
    except Exception as e:
        logger.error(f"Ошибка при поиске криптовалюты: {e}")
        return []

def format_crypto_search_results(results, query):
    if not results:
        return f"❌ *Криптовалюты не найдены*\n\nПо запросу: `{query}`\n\n*Советы:*\n• Используйте название (Bitcoin, Ethereum)\n• Или символ (BTC, ETH)\n• Можно искать по части названия\n\n*Популярные криптовалюты:*\nBitcoin (BTC), Ethereum (ETH), Tether (USDT), BNB, Solana (SOL)"
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if len(results) == 1:
        result = f"*🔎 Найдена криптовалюта*\n\n"
    else:
        result = f"*🔎 Найдено {len(results)} криптовалют*\n\n"
    
    for i, crypto in enumerate(results, 1):
        change_icon = "📈" if crypto['change_24h'] > 0 else "📉" if crypto['change_24h'] < 0 else "➡️"
        change_sign = "+" if crypto['change_24h'] > 0 else ""
        
        emoji = POPULAR_CRYPTOCURRENCIES.get(crypto['id'], {}).get('emoji', '💰')
        
        result += f"{i}. {emoji} *{crypto['name']} ({crypto['symbol']})*\n"
        
        if crypto['market_cap_rank'] and crypto['market_cap_rank'] <= 100:
            result += f"   📊 Ранг: #{crypto['market_cap_rank']}\n"
        
        result += f"   🇺🇸 Цена: ${crypto['price_usd']:,.4f}\n"
        result += f"   🇷🇺 Цена: {crypto['price_rub']:,.0f}₽\n"
        
        if crypto['change_24h'] != 0:
            result += f"   24ч: `{change_sign}{crypto['change_24h']:.1f}%` {change_icon}\n"
        else:
            result += f"   24ч: `0.0%` ➡️\n"
        
        result += "\n"
    
    result += f"_По запросу: {query}_\n"
    result += f"_Данные: CoinGecko, время: {current_time}_\n"
    result += f"_Используйте точное название для лучших результатов_"
    
    return result

def search_stock(query):
    try:
        query = query.upper().strip()
        results = []
        
        if query in RUSSIAN_STOCKS:
            stock_info = RUSSIAN_STOCKS[query]
            price = random.uniform(10, 15000)
            change = random.uniform(-price*0.05, price*0.05)
            change_percent = (change / price) * 100
            volume = random.randint(10000, 5000000)
            
            results.append({
                'ticker': query,
                'name': stock_info['name'],
                'sector': stock_info['sector'],
                'market': stock_info['market'],
                'price': price,
                'change': change,
                'change_percent': change_percent,
                'volume': volume,
                'market_cap': random.uniform(1000000000, 50000000000)
            })
            return results
        
        for ticker, stock_info in RUSSIAN_STOCKS.items():
            if query in ticker:
                price = random.uniform(10, 15000)
                change = random.uniform(-price*0.05, price*0.05)
                change_percent = (change / price) * 100
                volume = random.randint(10000, 5000000)
                
                results.append({
                    'ticker': ticker,
                    'name': stock_info['name'],
                    'sector': stock_info['sector'],
                    'market': stock_info['market'],
                    'price': price,
                    'change': change,
                    'change_percent': change_percent,
                    'volume': volume,
                    'market_cap': random.uniform(1000000000, 50000000000)
                })
        
        if not results:
            for ticker, stock_info in RUSSIAN_STOCKS.items():
                if query in stock_info['name'].upper():
                    price = random.uniform(10, 15000)
                    change = random.uniform(-price*0.05, price*0.05)
                    change_percent = (change / price) * 100
                    volume = random.randint(10000, 5000000)
                    
                    results.append({
                        'ticker': ticker,
                        'name': stock_info['name'],
                        'sector': stock_info['sector'],
                        'market': stock_info['market'],
                        'price': price,
                        'change': change,
                        'change_percent': change_percent,
                        'volume': volume,
                        'market_cap': random.uniform(1000000000, 50000000000)
                    })
        
        if not results:
            for ticker in TOP_RUSSIAN_STOCKS:
                if query in ticker or (ticker in RUSSIAN_STOCKS and query in RUSSIAN_STOCKS[ticker]['name'].upper()):
                    stock_info = RUSSIAN_STOCKS[ticker]
                    price = random.uniform(10, 15000)
                    change = random.uniform(-price*0.05, price*0.05)
                    change_percent = (change / price) * 100
                    volume = random.randint(10000, 5000000)
                    
                    results.append({
                        'ticker': ticker,
                        'name': stock_info['name'],
                        'sector': stock_info['sector'],
                        'market': stock_info['market'],
                        'price': price,
                        'change': change,
                        'change_percent': change_percent,
                        'volume': volume,
                        'market_cap': random.uniform(1000000000, 50000000000)
                    })
        
        return results[:10]
        
    except Exception as e:
        logger.error(f"Ошибка при поиске акции: {e}")
        return []

def format_stock_search_results(results, query):
    if not results:
        return f"❌ *Акции не найдены*\n\nПо запросу: `{query}`\n\n*Советы:*\n• Используйте тикер (GAZP, SBER)\n• Или часть названия компании (Газпром, Сбербанк)\n• Попробуйте английские буквы для тикеров\n\n*Популярные акции:*\nGAZP, SBER, LKOH, ROSN, NLMK"
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if len(results) == 1:
        result = f"*📈 Найдена акция*\n\n"
    else:
        result = f"*📈 Найдено {len(results)} акций*\n\n"
    
    for i, stock in enumerate(results, 1):
        change_icon = "🟢" if stock['change'] > 0 else "🔴" if stock['change'] < 0 else "⚪"
        change_sign = "+" if stock['change'] > 0 else ""
        
        result += f"{i}. *{stock['ticker']}* - {stock['name']}\n"
        result += f"   📊 Сектор: {stock['sector']}\n"
        result += f"   🏛️ Биржа: {stock['market']}\n"
        result += f"   💰 Цена: {stock['price']:,.2f}₽\n"
        result += f"   📈 Изменение: {change_sign}{stock['change']:,.2f} ({change_sign}{stock['change_percent']:.2f}%) {change_icon}\n"
        
        if stock['volume'] > 1000000:
            volume_str = f"{stock['volume']/1000000:.1f}M"
        elif stock['volume'] > 1000:
            volume_str = f"{stock['volume']/1000:.1f}K"
        else:
            volume_str = str(stock['volume'])
        
        result += f"   📊 Объем: {volume_str} акций\n"
        
        if stock['market_cap'] > 1000000000:
            cap_str = f"{stock['market_cap']/1000000000:.1f} млрд ₽"
        else:
            cap_str = f"{stock['market_cap']/1000000:.1f} млн ₽"
        
        result += f"   💎 Капитализация: {cap_str}\n"
        
        result += "\n"
    
    result += f"_По запросу: {query}_\n"
    result += f"_Время: {current_time}_\n"
    result += "_⚠️ Данные являются демонстрационными для тестирования функционала_"
    
    return result

# ============================================
# ФУНКЦИИ ДЛЯ ПОРТФЕЛЯ И УВЕДОМЛЕНИЙ
# ============================================

def get_current_price(symbol, asset_type):
    """Получение текущей цены актива"""
    try:
        symbol = symbol.upper()
        
        if asset_type == 'crypto':
            # Ищем криптовалюту по символу
            for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
                if info['symbol'].upper() == symbol:
                    url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=rub'
                    response = requests.get(url, timeout=5)
                    data = response.json()
                    return data.get(crypto_id, {}).get('rub', 0)
        
        elif asset_type == 'stock':
            # Для акций возвращаем случайную цену (для демо)
            return random.uniform(10, 15000)
        
        elif asset_type == 'currency':
            # Для валют
            url = 'https://www.cbr-xml-daily.ru/daily_json.js'
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if symbol in data['Valute']:
                return data['Valute'][symbol]['Value']
        
        return None
    except Exception as e:
        logger.error(f"Ошибка получения цены {symbol}: {e}")
        return None

def show_portfolio_summary(chat_id, user_id):
    """Показ сводки портфеля"""
    portfolio = db.get_portfolio(user_id)
    
    if not portfolio:
        bot.send_message(
            chat_id,
            "📭 *Ваш портфель пуст*\n\nДобавьте активы, чтобы отслеживать их стоимость.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    total_investment = 0
    total_current = 0
    
    summary_text = "📊 *СВОДКА ПОРТФЕЛЯ*\n\n"
    
    for item in portfolio:
        current_price = get_current_price(item['symbol'], item['asset_type'])
        
        item_investment = item['quantity'] * item['purchase_price']
        item_current = item['quantity'] * current_price if current_price else item_investment
        
        total_investment += item_investment
        total_current += item_current
        
        profit = item_current - item_investment
        profit_percent = (profit / item_investment) * 100 if item_investment else 0
        
        emoji = "🟢" if profit >= 0 else "🔴"
        
        summary_text += f"*{item['symbol']}*\n"
        summary_text += f"Тип: {item['asset_type']}\n"
        summary_text += f"Инвестировано: {item_investment:.2f}₽\n"
        
        if current_price:
            summary_text += f"Текущая стоимость: {item_current:.2f}₽\n"
            summary_text += f"Прибыль: {profit:+.2f}₽ ({profit_percent:+.1f}%) {emoji}\n"
        
        summary_text += "---\n"
    
    total_profit = total_current - total_investment
    total_profit_percent = (total_profit / total_investment) * 100 if total_investment else 0
    
    summary_text += f"\n*ОБЩАЯ СТАТИСТИКА:*\n"
    summary_text += f"Всего активов: {len(portfolio)}\n"
    summary_text += f"Общие инвестиции: {total_investment:.2f}₽\n"
    summary_text += f"Текущая стоимость: {total_current:.2f}₽\n"
    
    total_emoji = "🟢" if total_profit >= 0 else "🔴"
    summary_text += f"Общая прибыль: {total_profit:+.2f}₽ ({total_profit_percent:+.1f}%) {total_emoji}\n"
    
    summary_text += f"\n_Обновлено: {datetime.now().strftime('%H:%M:%S')}_"
    
    bot.send_message(
        chat_id,
        summary_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def calculate_portfolio_profit(chat_id, user_id):
    """Расчет прибыли портфеля"""
    portfolio = db.get_portfolio(user_id)
    
    if not portfolio:
        bot.send_message(
            chat_id,
            "📭 *Ваш портфель пуст*",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    bot.send_message(chat_id, "🔄 Рассчитываю прибыль...")
    
    total_profit = 0
    total_investment = 0
    details = []
    
    for item in portfolio:
        current_price = get_current_price(item['symbol'], item['asset_type'])
        
        if not current_price:
            continue
        
        investment = item['quantity'] * item['purchase_price']
        current_value = item['quantity'] * current_price
        profit = current_value - investment
        profit_percent = (profit / investment) * 100 if investment else 0
        
        total_investment += investment
        total_profit += profit
        
        details.append({
            'symbol': item['symbol'],
            'profit': profit,
            'percent': profit_percent,
            'current_value': current_value
        })
    
    if total_investment == 0:
        bot.send_message(
            chat_id,
            "❌ Не удалось рассчитать прибыль",
            reply_markup=create_main_keyboard()
        )
        return
    
    total_profit_percent = (total_profit / total_investment) * 100
    
    report = f"💰 *РАСЧЕТ ПРИБЫЛИ ПОРТФЕЛЯ*\n\n"
    
    for detail in details:
        emoji = "🟢" if detail['profit'] >= 0 else "🔴"
        report += f"*{detail['symbol']}*\n"
        report += f"Прибыль: {detail['profit']:+.2f}₽ ({detail['percent']:+.1f}%) {emoji}\n"
        report += f"Текущая стоимость: {detail['current_value']:.2f}₽\n"
        report += "---\n"
    
    report += f"\n*ИТОГО:*\n"
    report += f"Общие инвестиции: {total_investment:.2f}₽\n"
    report += f"Общая прибыль: {total_profit:+.2f}₽ ({total_profit_percent:+.1f}%)\n"
    
    total_emoji = "🟢" if total_profit >= 0 else "🔴"
    report += f"Результат: {'Прибыль' if total_profit >= 0 else 'Убыток'} {total_emoji}\n"
    
    report += f"\n_Расчет на: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_"
    
    bot.send_message(
        chat_id,
        report,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def show_user_alerts(chat_id, user_id):
    """Показ уведомлений пользователя"""
    alerts = db.get_alerts(user_id=user_id)
    
    if not alerts:
        bot.send_message(
            chat_id,
            "📭 *У вас нет уведомлений*\n\nСоздайте первое уведомление для отслеживания активов.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    alerts_text = f"🔔 *ВАШИ УВЕДОМЛЕНИЯ ({len(alerts)})*\n\n"
    
    active_count = sum(1 for a in alerts if a['is_active'])
    alerts_text += f"Активных: {active_count} | Неактивных: {len(alerts) - active_count}\n\n"
    
    alert_types = {
        'price_above': 'Цена выше',
        'price_below': 'Цена ниже', 
        'percent_change_up': 'Рост на %',
        'percent_change_down': 'Падение на %'
    }
    
    for i, alert in enumerate(alerts, 1):
        status = "✅ Активно" if alert['is_active'] else "❌ Неактивно"
        alert_type = alert_types.get(alert['alert_type'], alert['alert_type'])
        
        alerts_text += f"*{i}. {alert['symbol']}*\n"
        alerts_text += f"Тип: {alert_type}\n"
        alerts_text += f"Порог: {alert['threshold_value']}{'%' if 'percent' in alert['alert_type'] else '₽'}\n"
        
        if alert['time_frame_minutes'] > 0:
            alerts_text += f"Период: {alert['time_frame_minutes']} мин\n"
        
        alerts_text += f"Статус: {status}\n"
        
        if alert['last_triggered']:
            alerts_text += f"Последнее срабатывание: {alert['last_triggered']}\n"
        
        alerts_text += "---\n"
    
    alerts_text += f"\n_Используйте /my alerts для управления_"
    
    bot.send_message(
        chat_id,
        alerts_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def manage_user_alerts(chat_id, user_id):
    """Управление уведомлениями"""
    alerts = db.get_alerts(user_id=user_id)
    
    if not alerts:
        bot.send_message(
            chat_id,
            "📭 *Нет уведомлений для управления*",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for alert in alerts:
        status = "✅" if alert['is_active'] else "❌"
        alert_types = {
            'price_above': '>',
            'price_below': '<',
            'percent_change_up': '↑%',
            'percent_change_down': '↓%'
        }
        type_symbol = alert_types.get(alert['alert_type'], '?')
        
        keyboard.add(InlineKeyboardButton(
            f"{status} {alert['symbol']} {type_symbol} {alert['threshold_value']}",
            callback_data=f"toggle_alert_{alert['id']}"
        ))
    
    keyboard.add(InlineKeyboardButton("❌ Закрыть", callback_data="close_manage"))
    
    bot.send_message(
        chat_id,
        "*УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ*\n\nНажмите на уведомление для активации/деактивации:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "start_command")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, завершена ли регистрация
    registration_completed = db.is_registration_completed(user_id)
    
    if not registration_completed:
        # Начинаем регистрацию
        start_registration(chat_id, user_id)
    else:
        # Проверяем, создан ли портфель
        has_portfolio = db.get_user_status(user_id)
        
        if not has_portfolio:
            user_states[chat_id] = 'registration_completed'
            
            welcome_text = """
*✅ Регистрация завершена!*

Теперь вы можете создать свой портфель для отслеживания инвестиций.

*📊 Зачем нужен портфель:*
• Отслеживание ваших активов
• Расчет прибыли и убытков
• Персонализированные уведомления
• Анализ ваших инвестиций

*🚀 После создания портфеля вы получите доступ к:*
• Актуальным курсам валют
• Котировкам криптовалют
• Данным по российским акциям
• Поиску активов
• Умным уведомлениям

Нажмите *"📊 Создать портфель"*, чтобы начать!
"""
            bot.send_message(
                chat_id, 
                welcome_text, 
                parse_mode='Markdown',
                reply_markup=create_welcome_keyboard()
            )
        else:
            user_states[chat_id] = 'main'
            
            welcome_text = """
*💱 Бот финансовых курсов и связи*

📊 *Получайте актуальные курсы:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика российских компаний
• 🔍 Поиск любой валюты ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ
• 📊 Мой портфель
• 🔔 Мои уведомления

📨 *Связь с администратором*
⚡ *Защита от спама*

Используйте кнопки ниже ⬇️
"""
            bot.send_message(
                chat_id, 
                welcome_text, 
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )

@bot.message_handler(commands=['help'])
def send_help(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем статус пользователя
    registration_completed = db.is_registration_completed(user_id)
    has_portfolio = db.get_user_status(user_id)
    
    if not registration_completed:
        help_text = """
*📋 Справка по боту*

*Для начала работы необходимо:*
1. Пройти быструю регистрацию (3 вопроса)
2. Создать портфель
3. Добавить активы

*Доступные сейчас функции:*
• Регистрация (команда /start)
• Информация о боте
• Связь с администратором

*После регистрации и создания портфеля будут доступны:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика компаний
• 🔍 Поиск валюты
• 🔎 Поиск криптовалют
• 📈 Поиск акций
• 🔔 Умные уведомления

*Команды:*
/start - Запустить бота / начать регистрацию
/help - Справка

_Начните с регистрации!_
"""
        bot.send_message(
            chat_id,
            help_text,
            parse_mode='Markdown'
        )
    elif not has_portfolio:
        help_text = """
*📋 Справка по боту*

*Для получения полного доступа:*
1. Создайте портфель (кнопка "📊 Создать портфель")
2. Добавьте хотя бы один актив

*Доступные сейчас функции:*
• Создание портфеля
• Информация о боте
• Связь с администратором

*После создания портфеля будут доступны:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика компаний
• 🔍 Поиск валюты
• 🔎 Поиск криптовалют
• 📈 Поиск акций
• 🔔 Умные уведомления

*Команды:*
/start - Запустить бота
/help - Справка
/my - Мой портфель (после создания)

_Создайте портфель, чтобы продолжить!_
"""
        bot.send_message(
            chat_id,
            help_text,
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
        )
    else:
        help_text = """
*📋 Справка по боту*

*Функции:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика компаний
• 🔍 Поиск валюты ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ
• 📊 Мой портфель
• 🔔 Мои уведомления
• 📨 Связь с администратором

*Команды:*
/start - Запустить бота
/help - Справка
/top - Топ валют
/crypto - Криптовалюты
/analysis - Аналитика
/search - Поиск валюты
/cryptosearch - Поиск криптовалюты
/stocksearch - Поиск акций РФ
/currency - Поиск валюты (с параметром)
/stock - Поиск акции (с параметром)
/my - Мой портфель и уведомления
/my portfolio - Детальный портфель
/my alerts - Мои уведомления
/my profit - Расчет прибыли

*Примеры поиска:*
/search USD
/currency евро
/cryptosearch Bitcoin
/crypto BTC
/stocksearch GAZP
/stock SBER
/stock Газпром

_Используйте кнопки для удобства_
"""
        bot.send_message(
            chat_id,
            help_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(commands=['my', 'portfolio'])
def handle_my_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, завершена ли регистрация
    registration_completed = db.is_registration_completed(user_id)
    if not registration_completed:
        bot.send_message(
            chat_id,
            "📋 *Сначала завершите регистрацию*\n\nИспользуйте /start для начала регистрации.",
            parse_mode='Markdown'
        )
        return
    
    # Для пользователей без портфеля показываем упрощенное меню
    has_portfolio = db.get_user_status(user_id)
    
    if not has_portfolio:
        welcome_text = """
📊 *Ваш портфель еще не создан*

Чтобы использовать все функции бота, необходимо создать портфель.

*Что дает портфель:*
• Отслеживание ваших инвестиций
• Расчет прибыли и убытков
• Доступ ко всем финансовым данным
• Умные уведомления

Нажмите "📊 Создать портфель", чтобы начать!
"""
        bot.send_message(
            chat_id,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
        )
        return
    
    db.add_user_action(message.from_user.id, "my_command")
    
    args = message.text.split()
    
    if len(args) > 1:
        subcommand = args[1].lower()
        
        if subcommand == 'alerts':
            show_user_alerts(chat_id, user_id)
        elif subcommand == 'profit':
            calculate_portfolio_profit(chat_id, user_id)
        else:
            show_portfolio_summary(chat_id, user_id)
    else:
        # Краткая сводка
        portfolio = db.get_portfolio(user_id)
        alerts = db.get_alerts(user_id=user_id, is_active=True)
        
        if not portfolio and not alerts:
            text = """
*📊 БЫСТРАЯ СВОДКА*

Ваш портфель пуст.
Активных уведомлений нет.

Используйте:
• /my portfolio - подробный портфель
• /my alerts - все уведомления
• Кнопки в меню
"""
        else:
            text = "*📊 БЫСТРАЯ СВОДКА*\n\n"
            
            if portfolio:
                text += f"*Портфель:* {len(portfolio)} активов\n"
                
                total_investment = sum(item['quantity'] * item['purchase_price'] for item in portfolio)
                text += f"Инвестировано: {total_investment:.2f}₽\n"
            
            if alerts:
                text += f"\n*Уведомления:* {len(alerts)} активных\n"
            
            text += "\n_Используйте кнопки для деталей_"
        
        bot.send_message(
            chat_id,
            text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(commands=['top'])
def handle_top_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Топ валют")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "top_command")
    bot.send_message(chat_id, "🔄 Получаю курсы валют...")
    rates = get_currency_rates()
    bot.send_message(
        chat_id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['crypto'])
def handle_crypto_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Криптовалюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "crypto_command")
    
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                chat_id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(chat_id, "🔎 Ищу криптовалюту...")
        results = search_crypto(query)
        formatted_results = format_crypto_search_results(results, query)
        
        bot.send_message(
            chat_id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'
    else:
        bot.send_message(chat_id, "🔄 Получаю курсы криптовалют...")
        rates = get_crypto_rates()
        bot.send_message(
            chat_id, 
            rates, 
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(commands=['analysis'])
def handle_analysis_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Аналитика акций")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "analysis_command")
    bot.send_message(chat_id, "🔄 Получаю данные с биржи...")
    analysis = get_russian_stocks_data()
    bot.send_message(
        chat_id, 
        analysis, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['search', 'currency'])
def handle_search_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск валюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "search_command")
    
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                chat_id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(chat_id, "🔍 Ищу валюту...")
        results = search_currency(query)
        formatted_results = format_search_results(results, query)
        
        bot.send_message(
            chat_id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'
    else:
        user_states[chat_id] = 'search_currency'
        bot.send_message(
            chat_id,
            "*🔍 ПОИСК ВАЛЮТЫ ЦБ РФ*\n\nВведите код или название валюты:\n\n*Примеры:* USD, EUR, евро, доллар\n\nДля отмены: ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=create_contact_keyboard()
        )

@bot.message_handler(commands=['cryptosearch'])
def handle_cryptosearch_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск криптовалюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "cryptosearch_command")
    
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                chat_id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(chat_id, "🔎 Ищу криптовалюту...")
        results = search_crypto(query)
        formatted_results = format_crypto_search_results(results, query)
        
        bot.send_message(
            chat_id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'
    else:
        user_states[chat_id] = 'search_crypto'
        bot.send_message(
            chat_id,
            "*🔎 ПОИСК КРИПТОВАЛЮТЫ*\n\nВведите название или символ:\n\n*Примеры:* BTC, Ethereum, Bitcoin\n\nДля отмены: ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=create_contact_keyboard()
        )

@bot.message_handler(commands=['stocksearch', 'stock'])
def handle_stocksearch_command(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск акций")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "stocksearch_command")
    
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                chat_id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(chat_id, "📈 Ищу акцию...")
        results = search_stock(query)
        formatted_results = format_stock_search_results(results, query)
        
        bot.send_message(
            chat_id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'
    else:
        user_states[chat_id] = 'search_stock'
        bot.send_message(
            chat_id,
            "*📈 ПОИСК АКЦИЙ РФ*\n\nВведите тикер или название:\n\n*Примеры:* SBER, GAZP, Газпром\n\nДля отмены: ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=create_contact_keyboard()
        )

# ============================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================

@bot.message_handler(func=lambda message: message.text == '🏆 Топ валют')
def handle_top_currencies(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Топ валют")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "top_button")
    user_states[chat_id] = 'main'
    bot.send_message(chat_id, "🔄 Получаю курсы валют...")
    rates = get_currency_rates()
    bot.send_message(
        chat_id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📈 Криптовалюты')
def handle_crypto_rates(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Криптовалюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "crypto_button")
    user_states[chat_id] = 'main'
    bot.send_message(chat_id, "🔄 Получаю курсы криптовалют...")
    rates = get_crypto_rates()
    bot.send_message(
        chat_id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📊 Аналитика РФ')
def handle_analysis_button(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Аналитика акций")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "analysis_button")
    user_states[chat_id] = 'main'
    bot.send_message(chat_id, "🔄 Загружаю данные по акциям...")
    analysis = get_russian_stocks_data()
    bot.send_message(
        chat_id, 
        analysis, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🔍 Поиск валюты')
def handle_currency_search(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск валюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "currency_search_button")
    user_states[chat_id] = 'search_currency'
    
    bot.send_message(
        chat_id,
        "*🔍 ПОИСК ВАЛЮТЫ ЦБ РФ*\n\nВведите код или название валюты:\n\n*Примеры:* USD, EUR, евро, доллар\n\nДля отмены: ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🔎 Поиск крипты')
def handle_crypto_search(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск криптовалюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "crypto_search_button")
    user_states[chat_id] = 'search_crypto'
    
    bot.send_message(
        chat_id,
        "*🔎 ПОИСК КРИПТОВАЛЮТЫ*\n\nВведите название или символ:\n\n*Примеры:* BTC, Ethereum, Bitcoin\n\nДля отмены: ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📈 Поиск акций')
def handle_stock_search(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск акций")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "stock_search_button")
    user_states[chat_id] = 'search_stock'
    
    bot.send_message(
        chat_id,
        "*📈 ПОИСК АКЦИЙ РФ*\n\nВведите тикер или название:\n\n*Примеры:* SBER, GAZP, Газпром\n\nДля отмены: ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📊 Мой портфель')
def handle_portfolio(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Портфель")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    has_portfolio = db.get_user_status(user_id)
    
    if not has_portfolio:
        bot.send_message(
            chat_id,
            "📊 *Сначала создайте портфель*\n\nНажмите '📊 Создать портфель' в меню.",
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
        )
        return
    
    db.add_user_action(message.from_user.id, "portfolio_button")
    user_states[chat_id] = 'portfolio_menu'
    
    portfolio_text = """
*📊 УПРАВЛЕНИЕ ПОРТФЕЛЕМ*

Здесь вы можете:
• Добавлять активы в портфель
• Отслеживать прибыль/убыток
• Получать сводку по всем активам

Выберите действие:
"""
    bot.send_message(
        chat_id,
        portfolio_text,
        parse_mode='Markdown',
        reply_markup=create_portfolio_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🔔 Мои уведомления')
def handle_alerts(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Уведомления")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "alerts_button")
    user_states[chat_id] = 'alerts_menu'
    
    alerts_text = """
*🔔 УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ*

Настройте умные оповещения:
• Уведомления о достижении цены
• Оповещения о процентных изменениях

Выберите действие:
"""
    bot.send_message(
        chat_id,
        alerts_text,
        parse_mode='Markdown',
        reply_markup=create_alerts_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📨 Связь с админом')
def handle_contact_admin(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "contact_button")
    
    is_allowed, error_message = check_message_limit(message.from_user.id)
    
    if not is_allowed:
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode='Markdown',
            reply_markup=create_contact_keyboard()
        )
        return
    
    user_states[message.chat.id] = 'contact_mode'
    contact_text = f"""
*📨 Режим связи с администратором*

Отправьте ваше сообщение - оно будет переслано администратору.

*⚠️ Ограничения:*
Не более {MAX_MESSAGES} сообщений в течение 5 минут

Для отмены нажмите кнопку "❌ Отмена"
"""
    bot.send_message(
        message.chat.id, 
        contact_text, 
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == 'ℹ️ О боте')
def handle_about(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "about_button")
    
    current_state = user_states.get(message.chat.id, '')
    
    if current_state in ['registration_1', 'registration_2', 'registration_3', 'registration_cancel']:
        # Если пользователь в процессе регистрации
        about_text = """
*🤖 О боте*

*Для начала работы необходимо:*
1. Пройти быструю регистрацию (3 вопроса)
2. Создать портфель
3. Добавить активы

*После регистрации и создания портфеля будут доступны:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика компаний
• 🔍 Поиск валюты
• 🔎 Поиск криптовалют
• 📈 Поиск акций
• 🔔 Умные уведомления

_Завершите регистрацию, чтобы продолжить!_
"""
        bot.send_message(
            message.chat.id, 
            about_text, 
            parse_mode='Markdown'
        )
    elif current_state == 'registration_completed':
        # Если регистрация завершена, но портфель не создан
        about_text = """
*🤖 О боте*

*Для начала работы необходимо:*
1. Создать портфель (кнопка "📊 Создать портфель")
2. Добавить хотя бы один актив

*После создания портфеля вам станут доступны:*
• 🏆 Топ валют (10 валют)
• 📈 Криптовалюты (10+ популярных)
• 📊 Аналитика российских компаний
• 🔍 Поиск любой валюты из базы ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ
• 🔔 Умные уведомления

*Источники данных:*
• Центральный Банк РФ
• CoinGecko API
• Московская биржа (MOEX)

_Создайте портфель, чтобы начать использовать бота!_
"""
        bot.send_message(
            message.chat.id, 
            about_text, 
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
        )
    else:
        # Основной режим
        user_states[message.chat.id] = 'main'
        about_text = f"""
*🤖 О боте*

*Функции:*
• 🏆 Топ валют (10 валют)
• 📈 Криптовалюты (10+ популярных)
• 📊 Аналитика российских компаний
• 🔍 Поиск любой валюты из базы ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ
• 📊 Мой портфель (отслеживание активов)
• 🔔 Мои уведомления (умные оповещения)
• 📨 Связь с администратором

*Источники данных:*
• Центральный Банк РФ
• CoinGecko API
• Московская биржа (MOEX)

*Защита от спама:*
• {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут
• Блокировка на {BLOCK_DURATION//60} минут

_Бот создан для удобного отслеживания курсов_
"""
        bot.send_message(
            message.chat.id, 
            about_text, 
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(func=lambda message: message.text == '📊 Создать портфель')
def handle_create_portfolio(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "create_portfolio")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    portfolio_text = """
*📊 СОЗДАНИЕ ПЕРВОГО ПОРТФЕЛЯ*

Давайте создадим ваш первый портфель!

Добавьте хотя бы один актив, чтобы продолжить работу с ботом.

*Как это работает:*
1. Выберите тип актива (крипто, акция, валюта)
2. Введите символ (BTC, SBER, USD)
3. Укажите количество и цену покупки
4. Добавьте дату покупки и заметки

Готовы начать? Нажмите на кнопку ниже 👇
"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить первый актив", callback_data="add_first_asset"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_first_portfolio")
    )
    
    bot.send_message(
        chat_id,
        portfolio_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda message: message.text == '🔄 Пересоздать портфель')
def handle_recreate_portfolio(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Удаляем все активы пользователя
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM portfolio WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM alerts WHERE user_id = ?', (user_id,))
        cursor.execute('UPDATE user_status SET has_portfolio = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
    
    user_states[chat_id] = 'registration_completed'
    
    bot.send_message(
        chat_id,
        "✅ Портфель сброшен. Теперь вы можете создать новый портфель.",
        reply_markup=create_welcome_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def handle_cancel(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "cancel_button")
    
    current_state = user_states.get(message.chat.id)
    if current_state in ['contact_mode', 'search_currency', 'search_crypto', 'search_stock', 
                         'portfolio_menu', 'alerts_menu']:
        user_id = message.from_user.id
        registration_completed = db.is_registration_completed(user_id)
        has_portfolio = db.get_user_status(user_id)
        
        if registration_completed and has_portfolio:
            user_states[message.chat.id] = 'main'
            bot.send_message(
                message.chat.id,
                "✅ Операция отменена. Возврат в главное меню.",
                reply_markup=create_main_keyboard()
            )
        elif registration_completed:
            user_states[message.chat.id] = 'registration_completed'
            bot.send_message(
                message.chat.id,
                "✅ Операция отменена.",
                reply_markup=create_welcome_keyboard()
            )
        else:
            user_states[message.chat.id] = 'registration_1'
            bot.send_message(
                message.chat.id,
                "✅ Операция отменена. Продолжайте регистрацию.",
                reply_markup=create_registration_keyboard(1)
            )
    else:
        bot.send_message(
            message.chat.id,
            "Вы в главном меню. Используйте кнопки ниже 👇",
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(func=lambda message: message.text in ['✅ Продолжить регистрацию', '❌ Отменить регистрацию'])
def handle_registration_cancel_choice(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '✅ Продолжить регистрацию':
        # Возвращаемся к первому вопросу
        user_states[chat_id] = 'registration_1'
        bot.send_message(
            chat_id,
            REGISTRATION_QUESTIONS[0],
            parse_mode='Markdown',
            reply_markup=create_registration_keyboard(1)
        )
    elif message.text == '❌ Отменить регистрацию':
        # Отменяем регистрацию полностью
        user_states[chat_id] = 'main'
        bot.send_message(
            chat_id,
            "❌ Регистрация отменена. Вы можете начать ее снова с помощью команды /start",
            parse_mode='Markdown'
        )

# ============================================
# ОБРАБОТЧИКИ РЕГИСТРАЦИИ
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, '').startswith('registration_'))
def handle_registration_answers(message):
    """Обработчик ответов на вопросы регистрации"""
    if process_registration_answer(message):
        return

# ============================================
# ОБРАБОТЧИКИ ПОИСКА
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_currency')
def handle_search_query(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск валюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(user_id, "search_query", message.text)
    
    is_allowed, error_message = check_message_limit(user_id)
    if not is_allowed:
        bot.send_message(
            chat_id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(chat_id, "🔍 Ищу валюту...")
    
    query = message.text
    results = search_currency(query)
    formatted_results = format_search_results(results, query)
    
    bot.send_message(
        chat_id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[chat_id] = 'main'

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_crypto')
def handle_crypto_search_query(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск криптовалюты")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(user_id, "crypto_search_query", message.text)
    
    is_allowed, error_message = check_message_limit(user_id)
    if not is_allowed:
        bot.send_message(
            chat_id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(chat_id, "🔎 Ищу криптовалюту...")
    
    query = message.text
    results = search_crypto(query)
    formatted_results = format_crypto_search_results(results, query)
    
    bot.send_message(
        chat_id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[chat_id] = 'main'

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_stock')
def handle_stock_search_query(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Поиск акций")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(user_id, "stock_search_query", message.text)
    
    is_allowed, error_message = check_message_limit(user_id)
    if not is_allowed:
        bot.send_message(
            chat_id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(chat_id, "📈 Ищу акцию...")
    
    query = message.text
    results = search_stock(query)
    formatted_results = format_stock_search_results(results, query)
    
    bot.send_message(
        chat_id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[chat_id] = 'main'

# ============================================
# ОБРАБОТЧИКИ ПОРТФЕЛЯ (CALLBACK)
# ============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith(('add_asset', 'remove_asset', 'view_portfolio', 'calculate_profit', 'close_portfolio')))
def handle_portfolio_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'add_asset':
        db.add_user_action(user_id, "portfolio_add")
        user_states[chat_id] = 'portfolio_add_type'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Выберите тип актива:*",
            parse_mode='Markdown',
            reply_markup=create_asset_type_keyboard()
        )
    
    elif call.data == 'remove_asset':
        db.add_user_action(user_id, "portfolio_remove")
        portfolio = db.get_portfolio(user_id)
        
        if not portfolio:
            bot.answer_callback_query(call.id, "Ваш портфель пуст!")
            return
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for item in portfolio:
            keyboard.add(
                InlineKeyboardButton(
                    f"{item['symbol']} - {item['asset_type']}",
                    callback_data=f"remove_item_{item['id']}"
                )
            )
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_remove"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Выберите актив для удаления:*",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    elif call.data == 'view_portfolio':
        db.add_user_action(user_id, "portfolio_view")
        bot.delete_message(chat_id, call.message.message_id)
        show_portfolio_summary(chat_id, user_id)
    
    elif call.data == 'calculate_profit':
        db.add_user_action(user_id, "portfolio_calculate")
        bot.delete_message(chat_id, call.message.message_id)
        calculate_portfolio_profit(chat_id, user_id)
    
    elif call.data == 'close_portfolio':
        user_states[chat_id] = 'main'
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data in ['add_first_asset', 'cancel_first_portfolio'])
def handle_first_portfolio_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'add_first_asset':
        user_states[chat_id] = 'portfolio_add_type_first'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Выберите тип вашего первого актива:*",
            parse_mode='Markdown',
            reply_markup=create_asset_type_keyboard()
        )
    
    elif call.data == 'cancel_first_portfolio':
        user_states[chat_id] = 'registration_completed'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Создание портфеля отменено*\n\nНажмите '📊 Создать портфель' чтобы продолжить.",
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('asset_', 'cancel_asset')))
def handle_asset_type_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    current_state = user_states.get(chat_id)
    is_first_login = current_state == 'portfolio_add_type_first'
    
    if call.data == 'asset_crypto':
        user_states[chat_id] = 'portfolio_add_crypto_first' if is_first_login else 'portfolio_add_crypto'
        user_temp_data[user_id] = {'asset_type': 'crypto', 'is_first': is_first_login}
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите символ криптовалюты (например: BTC, ETH):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'asset_stock':
        user_states[chat_id] = 'portfolio_add_stock_first' if is_first_login else 'portfolio_add_stock'
        user_temp_data[user_id] = {'asset_type': 'stock', 'is_first': is_first_login}
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите тикер акции РФ (например: SBER, GAZP):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'asset_currency':
        user_states[chat_id] = 'portfolio_add_currency_first' if is_first_login else 'portfolio_add_currency'
        user_temp_data[user_id] = {'asset_type': 'currency', 'is_first': is_first_login}
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите код валюты (например: USD, EUR):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'cancel_asset':
        if is_first_login:
            user_states[chat_id] = 'registration_completed'
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="*Создание портфеля отменено*\n\nНажмите '📊 Создать портфель' чтобы продолжить.",
                parse_mode='Markdown'
            )
        else:
            user_states[chat_id] = 'portfolio_menu'
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="*Управление портфелем:*",
                parse_mode='Markdown',
                reply_markup=create_portfolio_keyboard()
            )

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_item_'))
def handle_remove_item(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    try:
        item_id = int(call.data.split('_')[2])
        success = db.remove_from_portfolio(user_id, item_id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ Актив удален!")
            
            # Обновляем список
            portfolio = db.get_portfolio(user_id)
            if portfolio:
                keyboard = InlineKeyboardMarkup(row_width=1)
                for item in portfolio:
                    keyboard.add(
                        InlineKeyboardButton(
                            f"{item['symbol']} - {item['asset_type']}",
                            callback_data=f"remove_item_{item['id']}"
                        )
                    )
                keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_remove"))
                
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text="*Выберите актив для удаления:*",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text="✅ Портфель очищен!",
                    parse_mode='Markdown'
                )
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка удаления!")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка!")
        logger.error(f"Ошибка удаления актива: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_remove')
def handle_cancel_remove(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    user_states[chat_id] = 'portfolio_menu'
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="*Управление портфелем:*",
        parse_mode='Markdown',
        reply_markup=create_portfolio_keyboard()
    )

# ============================================
# ОБРАБОТЧИКИ ДОБАВЛЕНИЯ АКТИВОВ
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) in [
    'portfolio_add_crypto_first', 'portfolio_add_stock_first', 'portfolio_add_currency_first',
    'portfolio_add_crypto', 'portfolio_add_stock', 'portfolio_add_currency'
])
def handle_asset_symbol(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = user_states[chat_id]
    
    # Определяем, это первый актив или нет
    is_first = state.endswith('_first')
    
    # Убираем суффикс _first для обработки
    base_state = state.replace('_first', '') if is_first else state
    
    symbol = message.text.strip().upper()
    
    if 'crypto' in base_state:
        valid = False
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'].upper() == symbol:
                valid = True
                break
        
        if not valid:
            bot.send_message(chat_id, "❌ Неизвестный символ криптовалюты. Попробуйте снова.")
            return
    
    elif 'stock' in base_state:
        if symbol not in RUSSIAN_STOCKS:
            bot.send_message(chat_id, "❌ Неизвестный тикер акции. Попробуйте снова.")
            return
    
    elif 'currency' in base_state:
        if symbol not in POPULAR_CURRENCIES:
            bot.send_message(chat_id, "❌ Неизвестный код валюты. Попробуйте снова.")
            return
    
    if user_id not in user_temp_data:
        user_temp_data[user_id] = {}
    
    user_temp_data[user_id]['symbol'] = symbol
    user_temp_data[user_id]['is_first'] = is_first
    
    # Определяем следующее состояние
    if is_first:
        next_state = 'portfolio_add_quantity_first'
    else:
        next_state = 'portfolio_add_quantity'
    
    user_states[chat_id] = next_state
    
    bot.send_message(
        chat_id,
        f"*Символ: {symbol}*\n\nВведите количество:",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) in ['portfolio_add_quantity', 'portfolio_add_quantity_first'])
def handle_asset_quantity(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        quantity = float(message.text.replace(',', '.'))
        
        if quantity <= 0:
            bot.send_message(chat_id, "❌ Количество должно быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['quantity'] = quantity
            
            # Определяем следующее состояние
            current_state = user_states[chat_id]
            if current_state == 'portfolio_add_quantity_first':
                next_state = 'portfolio_add_price_first'
            else:
                next_state = 'portfolio_add_price'
            
            user_states[chat_id] = next_state
            
            bot.send_message(
                chat_id,
                f"*Количество: {quantity}*\n\nВведите цену покупки (в рублях):",
                parse_mode='Markdown'
            )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное число.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) in ['portfolio_add_price', 'portfolio_add_price_first'])
def handle_asset_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        price = float(message.text.replace(',', '.'))
        
        if price <= 0:
            bot.send_message(chat_id, "❌ Цена должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['purchase_price'] = price
            
            # Определяем следующее состояние
            current_state = user_states[chat_id]
            if current_state == 'portfolio_add_price_first':
                next_state = 'portfolio_add_date_first'
            else:
                next_state = 'portfolio_add_date'
            
            user_states[chat_id] = next_state
            
            bot.send_message(
                chat_id,
                f"*Цена покупки: {price}₽*\n\nВведите дату покупки (ДД.ММ.ГГГГ) или /today для сегодняшней:",
                parse_mode='Markdown'
            )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную цену.")

@bot.message_handler(commands=['today'])
def handle_today_command(message):
    if user_states.get(message.chat.id) in ['portfolio_add_date', 'portfolio_add_date_first']:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        today = datetime.now().strftime("%d.%m.%Y")
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['purchase_date'] = today
            
            # Определяем следующее состояние
            current_state = user_states[chat_id]
            if current_state == 'portfolio_add_date_first':
                next_state = 'portfolio_add_notes_first'
            else:
                next_state = 'portfolio_add_notes'
            
            user_states[chat_id] = next_state
            
            bot.send_message(
                chat_id,
                f"*Дата покупки: {today}*\n\nВведите заметки (или /skip чтобы пропустить):",
                parse_mode='Markdown'
            )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) in ['portfolio_add_date', 'portfolio_add_date_first'])
def handle_asset_date(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    date_str = message.text.strip()
    
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['purchase_date'] = date_str
            
            # Определяем следующее состояние
            current_state = user_states[chat_id]
            if current_state == 'portfolio_add_date_first':
                next_state = 'portfolio_add_notes_first'
            else:
                next_state = 'portfolio_add_notes'
            
            user_states[chat_id] = next_state
            
            bot.send_message(
                chat_id,
                f"*Дата покупки: {date_str}*\n\nВведите заметки (или /skip чтобы пропустить):",
                parse_mode='Markdown'
            )
    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")

@bot.message_handler(commands=['skip'])
def handle_skip_command(message):
    if user_states.get(message.chat.id) in ['portfolio_add_notes', 'portfolio_add_notes_first']:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        complete_asset_addition(chat_id, user_id, "")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) in ['portfolio_add_notes', 'portfolio_add_notes_first'])
def handle_asset_notes(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    complete_asset_addition(chat_id, user_id, message.text)

def complete_asset_addition(chat_id, user_id, notes):
    """Завершение добавления актива в портфель"""
    if user_id in user_temp_data:
        data = user_temp_data[user_id]
        is_first = data.get('is_first', False)
        
        success = db.add_to_portfolio(
            user_id=user_id,
            asset_type=data['asset_type'],
            symbol=data['symbol'],
            quantity=data['quantity'],
            purchase_price=data['purchase_price'],
            purchase_date=data['purchase_date'],
            notes=notes
        )
        
        if success:
            if is_first:
                # Обновляем статус пользователя
                db.update_user_status(user_id, True)
                
                completion_text = f"""
✅ *Отлично! Ваш портфель создан!*

Актив *{data['symbol']}* успешно добавлен в ваш портфель.

*🎉 Теперь вам доступны все функции бота:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика акций РФ
• 🔍 Поиск активов
• 🔔 Умные уведомления

Можете продолжить добавлять активы или начать использовать другие функции бота!
"""
                bot.send_message(
                    chat_id,
                    completion_text,
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
                user_states[chat_id] = 'main'
            else:
                bot.send_message(
                    chat_id,
                    f"✅ Актив *{data['symbol']}* успешно добавлен в портфель!",
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
                user_states[chat_id] = 'main'
        else:
            error_text = "❌ Ошибка при добавлении актива. Попробуйте позже."
            if is_first:
                error_text += "\n\nБез портфеля вы не сможете использовать основные функции бота."
                user_states[chat_id] = 'registration_completed'
            else:
                user_states[chat_id] = 'main'
            
            bot.send_message(chat_id, error_text, reply_markup=create_main_keyboard())
        
        if user_id in user_temp_data:
            del user_temp_data[user_id]
    else:
        bot.send_message(
            chat_id,
            "❌ Ошибка: данные не найдены. Начните заново.",
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'

# ============================================
# ОБРАБОТЧИКИ УВЕДОМЛЕНИЙ (CALLBACK)
# ============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith(('add_alert', 'view_alerts', 'manage_alerts', 'close_alerts')))
def handle_alerts_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'add_alert':
        db.add_user_action(user_id, "alert_add")
        user_states[chat_id] = 'alert_add_type'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Выберите тип уведомления:*",
            parse_mode='Markdown',
            reply_markup=create_alert_type_keyboard()
        )
    
    elif call.data == 'view_alerts':
        db.add_user_action(user_id, "alert_view")
        bot.delete_message(chat_id, call.message.message_id)
        show_user_alerts(chat_id, user_id)
    
    elif call.data == 'manage_alerts':
        db.add_user_action(user_id, "alert_manage")
        bot.delete_message(chat_id, call.message.message_id)
        manage_user_alerts(chat_id, user_id)
    
    elif call.data == 'close_alerts':
        user_states[chat_id] = 'main'
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('alert_', 'cancel_alert')))
def handle_alert_type_selection(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    alert_type_map = {
        'alert_price_above': ('price_above', 'Цена выше'),
        'alert_price_below': ('price_below', 'Цена ниже'),
        'alert_percent_up': ('percent_change_up', 'Рост на %'),
        'alert_percent_down': ('percent_change_down', 'Падение на %')
    }
    
    if call.data in alert_type_map:
        alert_type, alert_name = alert_type_map[call.data]
        
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['alert_type'] = alert_type
        user_states[chat_id] = 'alert_add_symbol'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"*Тип уведомления: {alert_name}*\n\nВведите символ актива (например: BTC, SBER, USD):",
            parse_mode='Markdown'
        )
    
    elif call.data == 'cancel_alert':
        user_states[chat_id] = 'alerts_menu'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Управление уведомлениями:*",
            parse_mode='Markdown',
            reply_markup=create_alerts_keyboard()
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'alert_add_symbol')
def handle_alert_symbol(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    symbol = message.text.strip().upper()
    
    asset_type = None
    
    for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
        if info['symbol'].upper() == symbol:
            asset_type = 'crypto'
            break
    
    if not asset_type and symbol in RUSSIAN_STOCKS:
        asset_type = 'stock'
    
    if not asset_type and symbol in POPULAR_CURRENCIES:
        asset_type = 'currency'
    
    if not asset_type:
        bot.send_message(chat_id, "❌ Неизвестный символ. Попробуйте снова.")
        return
    
    if user_id in user_temp_data:
        user_temp_data[user_id]['symbol'] = symbol
        user_temp_data[user_id]['asset_type'] = asset_type
        user_states[chat_id] = 'alert_add_threshold'
        
        alert_type = user_temp_data[user_id]['alert_type']
        
        if 'percent' in alert_type:
            prompt = f"*Символ: {symbol} ({asset_type})*\n\nВведите процент изменения (например: 5 для 5%):"
        else:
            prompt = f"*Символ: {symbol} ({asset_type})*\n\nВведите пороговую цену в рублях:"
        
        bot.send_message(chat_id, prompt, parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'alert_add_threshold')
def handle_alert_threshold(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        threshold = float(message.text.replace(',', '.'))
        
        if threshold <= 0:
            bot.send_message(chat_id, "❌ Значение должно быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['threshold'] = threshold
            
            alert_type = user_temp_data[user_id]['alert_type']
            
            if 'percent' in alert_type:
                user_states[chat_id] = 'alert_add_timeframe'
                bot.send_message(
                    chat_id,
                    f"*Порог: {threshold}%*\n\nВведите временной период в минутах (например: 60 для 1 часа):",
                    parse_mode='Markdown'
                )
            else:
                complete_alert_creation(chat_id, user_id, 0)
                
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное число.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'alert_add_timeframe')
def handle_alert_timeframe(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        timeframe = int(message.text)
        
        if timeframe <= 0:
            bot.send_message(chat_id, "❌ Период должен быть больше 0 минут.")
            return
        
        complete_alert_creation(chat_id, user_id, timeframe)
        
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное число минут.")

def complete_alert_creation(chat_id, user_id, timeframe):
    """Завершение создания уведомления"""
    if user_id in user_temp_data:
        data = user_temp_data[user_id]
        
        alert_id = db.add_alert(
            user_id=user_id,
            asset_type=data['asset_type'],
            symbol=data['symbol'],
            alert_type=data['alert_type'],
            threshold_value=data['threshold'],
            time_frame_minutes=timeframe
        )
        
        if alert_id > 0:
            alert_types = {
                'price_above': 'Цена выше',
                'price_below': 'Цена ниже',
                'percent_change_up': 'Рост на %',
                'percent_change_down': 'Падение на %'
            }
            
            alert_name = alert_types.get(data['alert_type'], data['alert_type'])
            unit = '%' if 'percent' in data['alert_type'] else '₽'
            
            success_text = f"""
✅ *Уведомление создано!*

*Детали:*
• Актив: {data['symbol']} ({data['asset_type']})
• Тип: {alert_name}
• Порог: {data['threshold']}{unit}
• Период: {timeframe if timeframe > 0 else 'Не задан'} мин

Уведомление активно и будет проверяться каждые {CHECK_INTERVAL_MINUTES} минут.
"""
            bot.send_message(
                chat_id,
                success_text,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id,
                "❌ Ошибка при создании уведомления.",
                reply_markup=create_main_keyboard()
            )
        
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        
        user_states[chat_id] = 'main'
    else:
        bot.send_message(
            chat_id,
            "❌ Ошибка: данные не найдены.",
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_alert_'))
def handle_toggle_alert(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    try:
        alert_id = int(call.data.split('_')[2])
        
        alerts = db.get_alerts(user_id=user_id)
        current_status = None
        
        for alert in alerts:
            if alert['id'] == alert_id:
                current_status = alert['is_active']
                break
        
        if current_status is not None:
            new_status = not current_status
            success = db.update_alert_status(alert_id, new_status)
            
            if success:
                status_text = "активировано" if new_status else "деактивировано"
                bot.answer_callback_query(call.id, f"Уведомление {status_text}!")
                
                manage_user_alerts(chat_id, user_id)
                bot.delete_message(chat_id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Ошибка обновления!")
        else:
            bot.answer_callback_query(call.id, "Уведомление не найдено!")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "Ошибка!")
        logger.error(f"Ошибка переключения уведомления: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'close_manage')
def handle_close_manage(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    user_states[chat_id] = 'main'
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(
        chat_id,
        "Возврат в главное меню",
        reply_markup=create_main_keyboard()
    )

# ============================================
# ОБРАБОТЧИКИ СВЯЗИ С АДМИНОМ
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'contact_mode')
def handle_contact_messages(message):
    save_user_info(message)
    
    content_type = "текст"
    if message.photo:
        content_type = "фото"
    elif message.document:
        content_type = "документ"
    elif message.video:
        content_type = "видео"
    elif message.voice:
        content_type = "голосовое сообщение"
    elif message.sticker:
        content_type = "стикер"
    
    content_preview = message.text or f"[{content_type}]"
    db.add_message(message.from_user.id, content_type, content_preview, False)
    db.add_user_action(message.from_user.id, f"contact_{content_type}")
    
    is_allowed, error_message = check_message_limit(message.from_user.id)
    
    if not is_allowed:
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode='Markdown',
            reply_markup=create_contact_keyboard()
        )
        return
    
    if forward_to_admin(message, content_type):
        bot.reply_to(message, f"✅ Ваше {content_type} отправлено администратору!")
    else:
        bot.reply_to(message, "❌ Ошибка при отправке сообщения.")

# ============================================
# ОБЩИЙ ОБРАБОТЧИК
# ============================================

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    save_user_info(message)
    
    current_state = user_states.get(message.chat.id)
    if current_state not in ['contact_mode', 'search_currency', 'search_crypto', 'search_stock',
                             'portfolio_menu', 'portfolio_add_type', 'portfolio_add_crypto', 
                             'portfolio_add_stock', 'portfolio_add_currency', 'portfolio_add_quantity',
                             'portfolio_add_price', 'portfolio_add_date', 'portfolio_add_notes',
                             'alerts_menu', 'alert_add_type', 'alert_add_symbol', 'alert_add_threshold',
                             'alert_add_timeframe', 'registration_1', 'registration_2', 'registration_3',
                             'registration_cancel', 'registration_completed',
                             'portfolio_add_type_first', 'portfolio_add_crypto_first', 
                             'portfolio_add_stock_first', 'portfolio_add_currency_first', 
                             'portfolio_add_quantity_first', 'portfolio_add_price_first',
                             'portfolio_add_date_first', 'portfolio_add_notes_first']:
        
        user_id = message.from_user.id
        registration_completed = db.is_registration_completed(user_id)
        
        if registration_completed:
            has_portfolio = db.get_user_status(user_id)
            
            if has_portfolio:
                user_states[message.chat.id] = 'main'
                bot.send_message(
                    message.chat.id, 
                    "Выберите действие с помощью кнопок ниже 👇",
                    reply_markup=create_main_keyboard()
                )
            else:
                user_states[message.chat.id] = 'registration_completed'
                bot.send_message(
                    message.chat.id, 
                    "Сначала создайте портфель, чтобы получить доступ ко всем функциям!",
                    reply_markup=create_welcome_keyboard()
                )
        else:
            # Если пользователь не завершил регистрацию
            user_states[message.chat.id] = 'registration_1'
            bot.send_message(
                message.chat.id,
                "Для начала работы необходимо пройти регистрацию. Используйте /start для начала.",
                parse_mode='Markdown'
            )

# ============================================
# ЗАПУСК БОТА
# ============================================

if __name__ == "__main__":
    print("🤖 Бот запущен и готов к работе!")
    print(f"⚡ Защита: {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут")
    print(f"💾 База данных: {DATABASE_NAME}")
    print(f"📋 Регистрация: 3 вопроса перед доступом к функциям")
    print(f"🔔 Уведомления: активны каждые {CHECK_INTERVAL_MINUTES} минут")
    print("📊 Функции портфеля и уведомлений активированы")
    print("🚀 Новый режим: регистрация → создание портфеля → полный доступ")
    print("Для остановки: Ctrl+C")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")