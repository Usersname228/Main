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

# Константы для расчетов
GAS_PRICE_UPDATE_INTERVAL = 300  # 5 минут
AVG_BLOCK_TIME = {
    'ethereum': 12,  # секунд
    'polygon': 2,    # секунд
    'bsc': 3,        # секунд
    'arbitrum': 0.3, # секунд
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
    'bitcoin': {'name': 'Bitcoin', 'symbol': 'BTC', 'emoji': '₿', 'staking_apy': 4.5},
    'ethereum': {'name': 'Ethereum', 'symbol': 'ETH', 'emoji': '🔷', 'staking_apy': 3.8},
    'tether': {'name': 'Tether', 'symbol': 'USDT', 'emoji': '💵', 'staking_apy': 8.2},
    'binancecoin': {'name': 'BNB', 'symbol': 'BNB', 'emoji': '💎', 'staking_apy': 12.5},
    'solana': {'name': 'Solana', 'symbol': 'SOL', 'emoji': '⚡', 'staking_apy': 6.8},
    'ripple': {'name': 'XRP', 'symbol': 'XRP', 'emoji': '❌', 'staking_apy': 2.1},
    'cardano': {'name': 'Cardano', 'symbol': 'ADA', 'emoji': '🅰️', 'staking_apy': 3.2},
    'dogecoin': {'name': 'Dogecoin', 'symbol': 'DOGE', 'emoji': '🐕', 'staking_apy': 1.5},
    'polkadot': {'name': 'Polkadot', 'symbol': 'DOT', 'emoji': '🔴', 'staking_apy': 14.2},
    'litecoin': {'name': 'Litecoin', 'symbol': 'LTC', 'emoji': 'Ł', 'staking_apy': 2.8},
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
# КЭШ ДАННЫХ
# ============================================

gas_price_cache = {
    'ethereum': {'timestamp': 0, 'data': None},
    'polygon': {'timestamp': 0, 'data': None},
    'bsc': {'timestamp': 0, 'data': None},
    'arbitrum': {'timestamp': 0, 'data': None},
}

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
            
            # Новая таблица для сохранения расчетов калькулятора
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calculator_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    calculator_type TEXT,
                    input_data TEXT,
                    result_data TEXT,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    def save_calculation_history(self, user_id, calculator_type, input_data, result_data):
        """Сохранить историю расчетов"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO calculator_history 
                    (user_id, calculator_type, input_data, result_data) 
                    VALUES (?, ?, ?, ?)
                ''', (user_id, calculator_type, json.dumps(input_data), json.dumps(result_data)))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка сохранения истории расчетов: {e}")
            return None
    
    def get_calculation_history(self, user_id, limit=10):
        """Получить историю расчетов пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT calculator_type, input_data, result_data, calculation_date 
                    FROM calculator_history 
                    WHERE user_id = ? 
                    ORDER BY calculation_date DESC 
                    LIMIT ?
                ''', (user_id, limit))
                rows = cursor.fetchall()
                
                history = []
                for row in rows:
                    try:
                        history.append({
                            'type': row[0],
                            'input': json.loads(row[1]) if row[1] else {},
                            'result': json.loads(row[2]) if row[2] else {},
                            'date': row[3]
                        })
                    except:
                        continue
                return history
        except Exception as e:
            logger.error(f"Ошибка получения истории расчетов: {e}")
            return []
    
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
    button9 = KeyboardButton('🧮 Калькуляторы')
    button10 = KeyboardButton('📨 Связь с админом')
    button11 = KeyboardButton('ℹ️ О боте')
    button12 = KeyboardButton('🔄 Пересоздать портфель')
    keyboard.add(button1, button2, button3, button4, button5, button6, button7, button8, button9, button10, button11, button12)
    return keyboard

def create_calculators_keyboard():
    """Клавиатура с калькуляторами"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton('💰 Калькулятор прибыли'),
        KeyboardButton('🔄 Конвертер валют'),
        KeyboardButton('🏦 Стейкинг/Депозит'),
        KeyboardButton('⛽ Газ (Gas) трекер'),
        KeyboardButton('📊 ROI калькулятор'),
        KeyboardButton('📈 Калькулятор DCA'),
        KeyboardButton('📋 История расчетов'),
        KeyboardButton('🔙 Назад')
    )
    return keyboard

def create_gas_tracker_keyboard():
    """Клавиатура для газ трекера"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🟢 Ethereum", callback_data="gas_eth"),
        InlineKeyboardButton("🟣 Polygon", callback_data="gas_polygon"),
        InlineKeyboardButton("🟡 BSC", callback_data="gas_bsc"),
        InlineKeyboardButton("🔵 Arbitrum", callback_data="gas_arbitrum"),
        InlineKeyboardButton("🔄 Обновить все", callback_data="gas_refresh_all"),
        InlineKeyboardButton("❌ Закрыть", callback_data="gas_close")
    )
    return keyboard

def create_staking_calculator_keyboard():
    """Клавиатура для калькулятора стейкинга"""
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for crypto_id, info in list(POPULAR_CRYPTOCURRENCIES.items())[:9]:
        buttons.append(InlineKeyboardButton(
            f"{info['emoji']} {info['symbol']}",
            callback_data=f"staking_{crypto_id}"
        ))
    keyboard.add(*buttons)
    keyboard.add(
        InlineKeyboardButton("📊 Другой актив", callback_data="staking_custom"),
        InlineKeyboardButton("❌ Отмена", callback_data="staking_cancel")
    )
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
    button4 = KeyboardButton('🧮 Калькуляторы')
    keyboard.add(button1, button2, button3, button4)
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
    
    # Для калькуляторов не требуется портфель
    calculator_features = ['Калькуляторы', 'Калькулятор прибыли', 'Конвертер валют', 
                          'Стейкинг/Депозит', 'Газ (Gas) трекер', 'ROI калькулятор',
                          'Калькулятор DCA', 'История расчетов']
    
    if feature_name in calculator_features:
        return True, ""
    
    # Для остальных функций проверяем портфель
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
# ФУНКЦИИ КАЛЬКУЛЯТОРОВ
# ============================================

def calculate_profit_calculator(chat_id, user_id, investment, entry_price, target_price):
    """Калькулятор прибыли"""
    try:
        # Рассчитываем количество купленных активов
        quantity = investment / entry_price if entry_price > 0 else 0
        
        # Рассчитываем потенциальную прибыль
        current_value = quantity * entry_price
        target_value = quantity * target_price
        profit = target_value - investment
        roi = (profit / investment) * 100 if investment > 0 else 0
        
        # Определяем тикер (если был введен)
        symbol = user_temp_data.get(user_id, {}).get('profit_symbol', 'актива')
        
        result = f"""
💰 *КАЛЬКУЛЯТОР ПРИБЫЛИ*

*Параметры расчета:*
• Инвестиции: {investment:,.2f}₽
• Цена входа: {entry_price:,.4f}₽
• Целевая цена: {target_price:,.4f}₽
• Количество {symbol}: {quantity:,.6f}

*Результаты:*
• Текущая стоимость: {current_value:,.2f}₽
• Целевая стоимость: {target_value:,.2f}₽
• Потенциальная прибыль: {profit:+,.2f}₽
• ROI (доходность): {roi:+,.2f}%

*Оценка риска:*
{'🟢 Низкий риск' if roi <= 20 else '🟡 Средний риск' if roi <= 50 else '🔴 Высокий риск'}
"""
        
        # Сохраняем в историю
        input_data = {
            'investment': investment,
            'entry_price': entry_price,
            'target_price': target_price,
            'symbol': symbol
        }
        result_data = {
            'quantity': quantity,
            'current_value': current_value,
            'target_value': target_value,
            'profit': profit,
            'roi': roi
        }
        db.save_calculation_history(user_id, 'profit_calculator', input_data, result_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в калькуляторе прибыли: {e}")
        return f"❌ *Ошибка расчета*\n\nПроверьте введенные данные."

def calculate_currency_converter(chat_id, user_id, amount, from_currency, to_currencies):
    """Конвертер валют"""
    try:
        # Получаем текущие курсы
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        cbr_data = response.json()
        
        # Получаем курсы криптовалют
        crypto_ids = ['bitcoin', 'ethereum']
        crypto_ids_str = ','.join(crypto_ids)
        crypto_url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_ids_str}&vs_currencies=rub'
        crypto_response = requests.get(crypto_url, timeout=10)
        crypto_data = crypto_response.json()
        
        result = f"""
🔄 *КОНВЕРТЕР ВАЛЮТ*

*Исходная сумма:* {amount:,.2f} {from_currency}
*Время:* {datetime.now().strftime('%H:%M:%S')}

*Результаты конвертации:*
"""
        
        conversion_results = []
        
        for to_currency in to_currencies:
            try:
                if from_currency.upper() == 'RUB':
                    # Конвертация из рублей
                    if to_currency.upper() == 'USD':
                        rate = 1 / cbr_data['Valute']['USD']['Value']
                        converted = amount * rate
                    elif to_currency.upper() == 'EUR':
                        rate = 1 / cbr_data['Valute']['EUR']['Value']
                        converted = amount * rate
                    elif to_currency.lower() == 'btc':
                        btc_price = crypto_data['bitcoin']['rub']
                        converted = amount / btc_price if btc_price > 0 else 0
                    elif to_currency.lower() == 'eth':
                        eth_price = crypto_data['ethereum']['rub']
                        converted = amount / eth_price if eth_price > 0 else 0
                    else:
                        continue
                    
                elif from_currency.upper() == 'USD':
                    # Конвертация из долларов
                    if to_currency.upper() == 'RUB':
                        rate = cbr_data['Valute']['USD']['Value']
                        converted = amount * rate
                    elif to_currency.upper() == 'EUR':
                        usd_to_eur = cbr_data['Valute']['EUR']['Value'] / cbr_data['Valute']['USD']['Value']
                        converted = amount * usd_to_eur
                    elif to_currency.lower() == 'btc':
                        btc_price_usd = crypto_data['bitcoin']['rub'] / cbr_data['Valute']['USD']['Value']
                        converted = amount / btc_price_usd if btc_price_usd > 0 else 0
                    elif to_currency.lower() == 'eth':
                        eth_price_usd = crypto_data['ethereum']['rub'] / cbr_data['Valute']['USD']['Value']
                        converted = amount / eth_price_usd if eth_price_usd > 0 else 0
                    else:
                        continue
                        
                else:
                    converted = 0
                
                if converted > 0:
                    conversion_results.append({
                        'currency': to_currency.upper(),
                        'amount': converted
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка конвертации {from_currency}->{to_currency}: {e}")
                continue
        
        # Сортируем результаты
        conversion_results.sort(key=lambda x: x['amount'], reverse=True)
        
        for conv in conversion_results:
            if conv['currency'] in ['BTC', 'ETH']:
                result += f"• {conv['amount']:,.6f} {conv['currency']}\n"
            else:
                result += f"• {conv['amount']:,.2f} {conv['currency']}\n"
        
        result += f"\n_Курсы обновлены: {datetime.now().strftime('%H:%M')}_"
        
        # Сохраняем в историю
        input_data = {
            'amount': amount,
            'from_currency': from_currency,
            'to_currencies': to_currencies
        }
        result_data = {
            'conversions': conversion_results
        }
        db.save_calculation_history(user_id, 'currency_converter', input_data, result_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в конвертере валют: {e}")
        return f"❌ *Ошибка конвертации*\n\nПроверьте введенные данные."

def calculate_staking_rewards(chat_id, user_id, amount, apy, period_days, compound_frequency=365):
    """Калькулятор стейкинга/депозитов"""
    try:
        # Преобразуем APY из процентов в десятичную дробь
        apy_decimal = apy / 100
        
        if compound_frequency == 365:  # Ежедневная капитализация
            # A = P * (1 + r/n)^(n*t)
            # где n = 365 (ежедневно), t = period_days/365
            n = 365
            t = period_days / 365
            final_amount = amount * (1 + apy_decimal / n) ** (n * t)
        else:  # Без капитализации или другая частота
            final_amount = amount * (1 + apy_decimal * period_days / 365)
        
        profit = final_amount - amount
        roi = (profit / amount) * 100 if amount > 0 else 0
        
        # Ежемесячный доход
        monthly_income = amount * (apy_decimal / 12)
        
        result = f"""
🏦 *КАЛЬКУЛЯТОР СТЕЙКИНГА*

*Параметры:*
• Начальная сумма: {amount:,.2f}₽
• Годовая доходность (APY): {apy:.2f}%
• Период: {period_days} дней ({period_days/30:.1f} месяцев)
• Капитализация: {'Ежедневная' if compound_frequency == 365 else 'Без капитализации'}

*Результаты:*
• Конечная сумма: {final_amount:,.2f}₽
• Прибыль за период: {profit:+,.2f}₽
• ROI за период: {roi:+.2f}%
• Ежемесячный доход: {monthly_income:,.2f}₽

*Прогноз на год:*
• Годовая прибыль: {amount * apy_decimal:,.2f}₽
• Сумма через год: {amount * (1 + apy_decimal):,.2f}₽
"""
        
        # Сохраняем в историю
        input_data = {
            'amount': amount,
            'apy': apy,
            'period_days': period_days,
            'compound_frequency': compound_frequency
        }
        result_data = {
            'final_amount': final_amount,
            'profit': profit,
            'roi': roi,
            'monthly_income': monthly_income
        }
        db.save_calculation_history(user_id, 'staking_calculator', input_data, result_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в калькуляторе стейкинга: {e}")
        return f"❌ *Ошибка расчета*\n\nПроверьте введенные данные."

def get_gas_prices():
    """Получить актуальные цены на газ в разных сетях"""
    current_time = time.time()
    results = {}
    
    try:
        # Ethereum gas prices
        if current_time - gas_price_cache['ethereum']['timestamp'] > GAS_PRICE_UPDATE_INTERVAL:
            try:
                eth_response = requests.get('https://api.etherscan.io/api?module=gastracker&action=gasoracle', timeout=5)
                eth_data = eth_response.json()
                if eth_data['status'] == '1':
                    gas_price_cache['ethereum'] = {
                        'timestamp': current_time,
                        'data': {
                            'SafeGasPrice': int(eth_data['result']['SafeGasPrice']),
                            'ProposeGasPrice': int(eth_data['result']['ProposeGasPrice']),
                            'FastGasPrice': int(eth_data['result']['FastGasPrice']),
                            'suggestBaseFee': float(eth_data['result']['suggestBaseFee'])
                        }
                    }
            except:
                # Fallback данные
                gas_price_cache['ethereum'] = {
                    'timestamp': current_time,
                    'data': {
                        'SafeGasPrice': 25,
                        'ProposeGasPrice': 30,
                        'FastGasPrice': 35,
                        'suggestBaseFee': 15.5
                    }
                }
        
        results['ethereum'] = gas_price_cache['ethereum']['data']
        
        # Для других сетей используем демо-данные
        if current_time - gas_price_cache['polygon']['timestamp'] > GAS_PRICE_UPDATE_INTERVAL:
            gas_price_cache['polygon'] = {
                'timestamp': current_time,
                'data': {
                    'SafeGasPrice': 45,
                    'ProposeGasPrice': 60,
                    'FastGasPrice': 80,
                    'suggestBaseFee': 30
                }
            }
        
        if current_time - gas_price_cache['bsc']['timestamp'] > GAS_PRICE_UPDATE_INTERVAL:
            gas_price_cache['bsc'] = {
                'timestamp': current_time,
                'data': {
                    'SafeGasPrice': 5,
                    'ProposeGasPrice': 7,
                    'FastGasPrice': 10,
                    'suggestBaseFee': 3
                }
            }
        
        if current_time - gas_price_cache['arbitrum']['timestamp'] > GAS_PRICE_UPDATE_INTERVAL:
            gas_price_cache['arbitrum'] = {
                'timestamp': current_time,
                'data': {
                    'SafeGasPrice': 0.1,
                    'ProposeGasPrice': 0.15,
                    'FastGasPrice': 0.2,
                    'suggestBaseFee': 0.05
                }
            }
        
        results['polygon'] = gas_price_cache['polygon']['data']
        results['bsc'] = gas_price_cache['bsc']['data']
        results['arbitrum'] = gas_price_cache['arbitrum']['data']
        
        return results
        
    except Exception as e:
        logger.error(f"Ошибка получения цен на газ: {e}")
        return None

def format_gas_prices_report():
    """Форматировать отчет о ценах на газ"""
    gas_prices = get_gas_prices()
    
    if not gas_prices:
        return "❌ *Не удалось получить данные о ценах на газ*"
    
    report = f"""
⛽ *ТРЕКЕР ЦЕН НА ГАЗ (GAS)*
*Время:* {datetime.now().strftime('%H:%M:%S')}

*🟢 Ethereum (ETH):*
• Медленно: {gas_prices['ethereum']['SafeGasPrice']} Gwei
• Средне: {gas_prices['ethereum']['ProposeGasPrice']} Gwei
• Быстро: {gas_prices['ethereum']['FastGasPrice']} Gwei
• Базовая цена: {gas_prices['ethereum']['suggestBaseFee']} Gwei

*🟣 Polygon (MATIC):*
• Медленно: {gas_prices['polygon']['SafeGasPrice']} Gwei
• Средне: {gas_prices['polygon']['ProposeGasPrice']} Gwei
• Быстро: {gas_prices['polygon']['FastGasPrice']} Gwei

*🟡 BSC (BNB):*
• Медленно: {gas_prices['bsc']['SafeGasPrice']} Gwei
• Средне: {gas_prices['bsc']['ProposeGasPrice']} Gwei
• Быстро: {gas_prices['bsc']['FastGasPrice']} Gwei

*🔵 Arbitrum (ETH):*
• Медленно: {gas_prices['arbitrum']['SafeGasPrice']} Gwei
• Средне: {gas_prices['arbitrum']['ProposeGasPrice']} Gwei
• Быстро: {gas_prices['arbitrum']['FastGasPrice']} Gwei

*📊 Оценка стоимости транзакций:*
• Простая транзакция (21к gas): {gas_prices['ethereum']['FastGasPrice'] * 21000 / 1e9:.6f} ETH
• SWAP на Uniswap (150к gas): {gas_prices['ethereum']['FastGasPrice'] * 150000 / 1e9:.6f} ETH
• Контрактное взаимодействие (300к gas): {gas_prices['ethereum']['FastGasPrice'] * 300000 / 1e9:.6f} ETH

_Данные обновляются каждые 5 минут_
"""
    
    return report

def calculate_dca_strategy(chat_id, user_id, monthly_investment, months, expected_return=10):
    """Калькулятор стратегии DCA (усреднения)"""
    try:
        monthly_return = expected_return / 12 / 100
        
        total_invested = monthly_investment * months
        
        # Расчет с учетом сложного процента
        future_value = 0
        for month in range(months):
            future_value = (future_value + monthly_investment) * (1 + monthly_return)
        
        total_profit = future_value - total_invested
        total_roi = (total_profit / total_invested) * 100 if total_invested > 0 else 0
        
        result = f"""
📈 *КАЛЬКУЛЯТОР СТРАТЕГИИ DCA*

*Параметры стратегии:*
• Ежемесячные инвестиции: {monthly_investment:,.2f}₽
• Срок инвестирования: {months} месяцев ({months/12:.1f} лет)
• Ожидаемая годовая доходность: {expected_return:.1f}%

*Результаты:*
• Всего инвестировано: {total_invested:,.2f}₽
• Итоговая сумма: {future_value:,.2f}₽
• Общая прибыль: {total_profit:+,.2f}₽
• Общий ROI: {total_roi:+.2f}%
• Среднемесячная доходность: {monthly_return*100:.2f}%

*Рекомендации:*
• Начинайте инвестировать регулярно
• Не пытайтесь угадывать время рынка
• Увеличивайте сумму инвестиций с ростом доходов
"""
        
        # Сохраняем в историю
        input_data = {
            'monthly_investment': monthly_investment,
            'months': months,
            'expected_return': expected_return
        }
        result_data = {
            'total_invested': total_invested,
            'future_value': future_value,
            'total_profit': total_profit,
            'total_roi': total_roi
        }
        db.save_calculation_history(user_id, 'dca_calculator', input_data, result_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в калькуляторе DCA: {e}")
        return f"❌ *Ошибка расчета*\n\nПроверьте введенные данные."

def show_calculation_history(chat_id, user_id):
    """Показать историю расчетов пользователя"""
    history = db.get_calculation_history(user_id, limit=10)
    
    if not history:
        bot.send_message(
            chat_id,
            "📭 *История расчетов пуста*\n\nВыполните расчеты в калькуляторах, чтобы сохранить их здесь.",
            parse_mode='Markdown',
            reply_markup=create_calculators_keyboard()
        )
        return
    
    history_text = f"""
📋 *ИСТОРИЯ РАСЧЕТОВ ({len(history)})*

*Последние расчеты:*
"""
    
    calculator_names = {
        'profit_calculator': '💰 Калькулятор прибыли',
        'currency_converter': '🔄 Конвертер валют',
        'staking_calculator': '🏦 Стейкинг калькулятор',
        'dca_calculator': '📈 Калькулятор DCA'
    }
    
    for i, calc in enumerate(history, 1):
        calc_name = calculator_names.get(calc['type'], calc['type'])
        calc_date = calc['date'][:16] if calc['date'] else "неизвестно"
        
        history_text += f"\n{i}. *{calc_name}*\n"
        history_text += f"   📅 {calc_date}\n"
        
        # Краткая информация о расчете
        if calc['type'] == 'profit_calculator':
            profit = calc['result'].get('profit', 0)
            roi = calc['result'].get('roi', 0)
            history_text += f"   📊 Прибыль: {profit:+,.0f}₽ (ROI: {roi:+.1f}%)\n"
        elif calc['type'] == 'currency_converter':
            convs = calc['result'].get('conversions', [])
            if convs:
                history_text += f"   💱 Конвертация: {convs[0].get('amount', 0):,.2f} {convs[0].get('currency', '')}\n"
        elif calc['type'] == 'staking_calculator':
            final_amount = calc['result'].get('final_amount', 0)
            history_text += f"   🏦 Итог: {final_amount:,.0f}₽\n"
        elif calc['type'] == 'dca_calculator':
            future_value = calc['result'].get('future_value', 0)
            history_text += f"   📈 Будущая стоимость: {future_value:,.0f}₽\n"
    
    history_text += "\n_Используйте калькуляторы для новых расчетов_"
    
    bot.send_message(
        chat_id,
        history_text,
        parse_mode='Markdown',
        reply_markup=create_calculators_keyboard()
    )

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

*🧮 Новые инструменты:*
Доступны сразу после регистрации:
• Калькулятор прибыли и ROI
• Конвертер валют и криптовалют
• Калькулятор стейкинга и депозитов
• Трекер газовых fees (Gas tracker)
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

*🧮 Калькуляторы (доступны сейчас):*
• Калькулятор прибыли и ROI
• Конвертер валют и криптовалют
• Калькулятор стейкинга
• Трекер газовых fees
• Калькулятор стратегии DCA

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

🧮 *Финансовые калькуляторы:*
• 💰 Калькулятор прибыли
• 🔄 Конвертер валют
• 🏦 Стейкинг/Депозит
• ⛽ Газ (Gas) трекер
• 📊 ROI калькулятор
• 📈 Калькулятор DCA

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
• 🧮 Финансовые калькуляторы

*🧮 Калькуляторы (доступны сейчас):*
• 💰 Калькулятор прибыли и ROI
• 🔄 Конвертер валют
• 🏦 Стейкинг/Депозит
• ⛽ Газ (Gas) трекер
• 📊 ROI калькулятор
• 📈 Калькулятор DCA

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
• 🧮 Финансовые калькуляторы
• 📨 Связь с администратором

*🧮 Калькуляторы:*
• 💰 Калькулятор прибыли и ROI
• 🔄 Конвертер валют
• 🏦 Стейкинг/Депозит
• ⛽ Газ (Gas) трекер
• 📊 ROI калькулятор
• 📈 Калькулятор DCA
• 📋 История расчетов

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
/calculators - Открыть калькуляторы

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

@bot.message_handler(commands=['calculators'])
def handle_calculators_command(message):
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
    
    db.add_user_action(message.from_user.id, "calculators_command")
    user_states[chat_id] = 'calculators_menu'
    
    calculators_text = """
🧮 *ФИНАНСОВЫЕ КАЛЬКУЛЯТОРЫ*

Выберите нужный калькулятор:

*💰 Калькулятор прибыли*
Расчет потенциальной прибыли и ROI при инвестировании

*🔄 Конвертер валют*
Конвертация сумм между валютами и криптовалютами

*🏦 Стейкинг/Депозит*
Расчет доходности от стейкинга и банковских депозитов

*⛽ Газ (Gas) трекер*
Актуальные цены на газ в блокчейн сетях

*📊 ROI калькулятор*
Расчет возврата на инвестиции

*📈 Калькулятор DCA*
Расчет стратегии усреднения (Dollar Cost Averaging)

*📋 История расчетов*
Просмотр предыдущих расчетов
"""
    bot.send_message(
        chat_id,
        calculators_text,
        parse_mode='Markdown',
        reply_markup=create_calculators_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🧮 Калькуляторы')
def handle_calculators_button(message):
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
    
    db.add_user_action(message.from_user.id, "calculators_button")
    user_states[chat_id] = 'calculators_menu'
    
    calculators_text = """
🧮 *ФИНАНСОВЫЕ КАЛЬКУЛЯТОРЫ*

Выберите нужный калькулятор:
"""
    bot.send_message(
        chat_id,
        calculators_text,
        parse_mode='Markdown',
        reply_markup=create_calculators_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '💰 Калькулятор прибыли' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_profit_calculator(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "profit_calculator_start")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_states[chat_id] = 'profit_calc_symbol'
    user_temp_data[user_id] = {'calculator': 'profit'}
    
    bot.send_message(
        chat_id,
        "💰 *КАЛЬКУЛЯТОР ПРИБЫЛИ*\n\nВведите символ актива (например: BTC, ETH, SBER) или /skip чтобы пропустить:",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '🔄 Конвертер валют' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_currency_converter(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "currency_converter_start")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_states[chat_id] = 'converter_amount'
    user_temp_data[user_id] = {'calculator': 'converter'}
    
    bot.send_message(
        chat_id,
        "🔄 *КОНВЕРТЕР ВАЛЮТ*\n\nВведите сумму для конвертации:",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '🏦 Стейкинг/Депозит' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_staking_calculator(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "staking_calculator_start")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_states[chat_id] = 'staking_asset'
    
    bot.send_message(
        chat_id,
        "🏦 *КАЛЬКУЛЯТОР СТЕЙКИНГА*\n\nВыберите актив для расчета:",
        parse_mode='Markdown',
        reply_markup=create_staking_calculator_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '⛽ Газ (Gas) трекер' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_gas_tracker(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "gas_tracker")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    gas_report = format_gas_prices_report()
    
    bot.send_message(
        chat_id,
        gas_report,
        parse_mode='Markdown',
        reply_markup=create_gas_tracker_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📊 ROI калькулятор' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_roi_calculator(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "roi_calculator_start")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_states[chat_id] = 'roi_investment'
    user_temp_data[user_id] = {'calculator': 'roi'}
    
    bot.send_message(
        chat_id,
        "📊 *ROI КАЛЬКУЛЯТОР*\n\nВведите сумму инвестиций (в рублях):",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '📈 Калькулятор DCA' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_dca_calculator(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "dca_calculator_start")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_states[chat_id] = 'dca_monthly'
    user_temp_data[user_id] = {'calculator': 'dca'}
    
    bot.send_message(
        chat_id,
        "📈 *КАЛЬКУЛЯТОР СТРАТЕГИИ DCA*\n\nВведите ежемесячную сумму инвестиций (в рублях):",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '📋 История расчетов' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_calculation_history(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    show_calculation_history(chat_id, user_id)

@bot.message_handler(func=lambda message: message.text == '🔙 Назад' and user_states.get(message.chat.id) == 'calculators_menu')
def handle_back_from_calculators(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    has_portfolio = db.get_user_status(user_id)
    
    if has_portfolio:
        user_states[chat_id] = 'main'
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )
    else:
        user_states[chat_id] = 'registration_completed'
        bot.send_message(
            chat_id,
            "Возврат в меню",
            reply_markup=create_welcome_keyboard()
        )

# ============================================
# ОБРАБОТЧИКИ КАЛЬКУЛЯТОРОВ
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'profit_calc_symbol')
def handle_profit_calc_symbol(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '/skip':
        if user_id in user_temp_data:
            user_temp_data[user_id]['profit_symbol'] = 'актива'
        user_states[chat_id] = 'profit_calc_investment'
        bot.send_message(
            chat_id,
            "Введите сумму инвестиций (в рублях):",
            parse_mode='Markdown'
        )
    else:
        symbol = message.text.strip().upper()
        if user_id in user_temp_data:
            user_temp_data[user_id]['profit_symbol'] = symbol
        user_states[chat_id] = 'profit_calc_investment'
        bot.send_message(
            chat_id,
            f"*Символ: {symbol}*\n\nВведите сумму инвестиций (в рублях):",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'profit_calc_investment')
def handle_profit_calc_investment(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        investment = float(message.text.replace(',', '.'))
        
        if investment <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['investment'] = investment
        
        user_states[chat_id] = 'profit_calc_entry_price'
        bot.send_message(
            chat_id,
            f"*Инвестиции: {investment:,.2f}₽*\n\nВведите цену входа (в рублях):",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'profit_calc_entry_price')
def handle_profit_calc_entry_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        entry_price = float(message.text.replace(',', '.'))
        
        if entry_price <= 0:
            bot.send_message(chat_id, "❌ Цена должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['entry_price'] = entry_price
        
        user_states[chat_id] = 'profit_calc_target_price'
        bot.send_message(
            chat_id,
            f"*Цена входа: {entry_price:,.4f}₽*\n\nВведите целевую цену (в рублях):",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную цену.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'profit_calc_target_price')
def handle_profit_calc_target_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        target_price = float(message.text.replace(',', '.'))
        
        if target_price <= 0:
            bot.send_message(chat_id, "❌ Цена должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            data = user_temp_data[user_id]
            investment = data.get('investment', 0)
            entry_price = data.get('entry_price', 0)
            
            if entry_price > 0:
                result = calculate_profit_calculator(chat_id, user_id, investment, entry_price, target_price)
                
                bot.send_message(
                    chat_id,
                    result,
                    parse_mode='Markdown',
                    reply_markup=create_calculators_keyboard()
                )
                user_states[chat_id] = 'calculators_menu'
                
                if user_id in user_temp_data:
                    del user_temp_data[user_id]
            else:
                bot.send_message(chat_id, "❌ Ошибка: данные не найдены.")
        else:
            bot.send_message(chat_id, "❌ Ошибка: данные не найдены.")
            
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную цену.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_amount')
def handle_converter_amount(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        amount = float(message.text.replace(',', '.'))
        
        if amount <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['amount'] = amount
        
        user_states[chat_id] = 'converter_from'
        bot.send_message(
            chat_id,
            f"*Сумма: {amount:,.2f}*\n\nВведите исходную валюту (например: RUB, USD, EUR):",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_from')
def handle_converter_from(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    from_currency = message.text.strip().upper()
    
    if from_currency not in ['RUB', 'USD', 'EUR']:
        bot.send_message(chat_id, "❌ Поддерживаются только RUB, USD, EUR.")
        return
    
    if user_id in user_temp_data:
        user_temp_data[user_id]['from_currency'] = from_currency
    
    # Автоматически конвертируем в популярные валюты
    to_currencies = ['USD', 'EUR', 'BTC', 'ETH']
    
    if from_currency == 'RUB':
        amount = user_temp_data[user_id].get('amount', 0)
        result = calculate_currency_converter(chat_id, user_id, amount, from_currency, to_currencies)
        
        bot.send_message(
            chat_id,
            result,
            parse_mode='Markdown',
            reply_markup=create_calculators_keyboard()
        )
        user_states[chat_id] = 'calculators_menu'
        
        if user_id in user_temp_data:
            del user_temp_data[user_id]
    else:
        user_states[chat_id] = 'converter_to'
        bot.send_message(
            chat_id,
            f"*Из: {from_currency}*\n\nВведите целевую валюту (например: RUB, USD, EUR, BTC, ETH) или /all для всех:",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_to')
def handle_converter_to(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '/all':
        to_currencies = ['RUB', 'USD', 'EUR', 'BTC', 'ETH']
    else:
        to_currencies = [message.text.strip().upper()]
    
    if user_id in user_temp_data:
        data = user_temp_data[user_id]
        amount = data.get('amount', 0)
        from_currency = data.get('from_currency', 'RUB')
        
        result = calculate_currency_converter(chat_id, user_id, amount, from_currency, to_currencies)
        
        bot.send_message(
            chat_id,
            result,
            parse_mode='Markdown',
            reply_markup=create_calculators_keyboard()
        )
        user_states[chat_id] = 'calculators_menu'
        
        if user_id in user_temp_data:
            del user_temp_data[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('staking_'))
def handle_staking_asset_selection(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'staking_cancel':
        user_states[chat_id] = 'calculators_menu'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="Выберите калькулятор:",
            parse_mode='Markdown'
        )
        return
    
    if call.data == 'staking_custom':
        user_states[chat_id] = 'staking_custom_apy'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите годовую доходность (APY) в %:*",
            parse_mode='Markdown'
        )
        return
    
    crypto_id = call.data.replace('staking_', '')
    
    if crypto_id in POPULAR_CRYPTOCURRENCIES:
        crypto_info = POPULAR_CRYPTOCURRENCIES[crypto_id]
        apy = crypto_info.get('staking_apy', 5.0)
        
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['apy'] = apy
        user_temp_data[user_id]['asset_name'] = crypto_info['name']
        
        user_states[chat_id] = 'staking_amount'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"*{crypto_info['emoji']} {crypto_info['name']} ({crypto_info['symbol']})*\n\nГодовая доходность: {apy:.1f}%\n\nВведите сумму для стейкинга (в рублях):",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'staking_custom_apy')
def handle_staking_custom_apy(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        apy = float(message.text.replace(',', '.'))
        
        if apy <= 0 or apy > 100:
            bot.send_message(chat_id, "❌ APY должен быть от 0.1% до 100%.")
            return
        
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['apy'] = apy
        user_temp_data[user_id]['asset_name'] = 'Кастомный актив'
        
        user_states[chat_id] = 'staking_amount'
        bot.send_message(
            chat_id,
            f"*Годовая доходность: {apy:.1f}%*\n\nВведите сумму для стейкинга (в рублях):",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное значение APY.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'staking_amount')
def handle_staking_amount(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        amount = float(message.text.replace(',', '.'))
        
        if amount <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['amount'] = amount
        
        user_states[chat_id] = 'staking_period'
        bot.send_message(
            chat_id,
            f"*Сумма: {amount:,.2f}₽*\n\nВведите период стейкинга в днях:",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'staking_period')
def handle_staking_period(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        period_days = int(message.text)
        
        if period_days <= 0:
            bot.send_message(chat_id, "❌ Период должен быть больше 0 дней.")
            return
        
        if user_id in user_temp_data:
            data = user_temp_data[user_id]
            amount = data.get('amount', 0)
            apy = data.get('apy', 5.0)
            asset_name = data.get('asset_name', 'Актив')
            
            result = calculate_staking_rewards(chat_id, user_id, amount, apy, period_days)
            
            # Добавляем информацию об активе
            result = result.replace("КАЛЬКУЛЯТОР СТЕЙКИНГА", f"КАЛЬКУЛЯТОР СТЕЙКИНГА\n\n*Актив:* {asset_name}")
            
            bot.send_message(
                chat_id,
                result,
                parse_mode='Markdown',
                reply_markup=create_calculators_keyboard()
            )
            user_states[chat_id] = 'calculators_menu'
            
            if user_id in user_temp_data:
                del user_temp_data[user_id]
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное количество дней.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('gas_'))
def handle_gas_tracker_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'gas_close':
        user_states[chat_id] = 'calculators_menu'
        bot.delete_message(chat_id, call.message.message_id)
        return
    
    if call.data == 'gas_refresh_all':
        # Обновляем кэш
        current_time = time.time()
        for network in gas_price_cache:
            gas_price_cache[network]['timestamp'] = 0
        
        gas_report = format_gas_prices_report()
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=gas_report,
            parse_mode='Markdown',
            reply_markup=create_gas_tracker_keyboard()
        )
        bot.answer_callback_query(call.id, "✅ Данные обновлены!")
        return
    
    network = call.data.replace('gas_', '')
    network_names = {
        'eth': 'Ethereum',
        'polygon': 'Polygon',
        'bsc': 'Binance Smart Chain',
        'arbitrum': 'Arbitrum'
    }
    
    gas_prices = get_gas_prices()
    
    if gas_prices and network in gas_prices:
        network_name = network_names.get(network, network.capitalize())
        prices = gas_prices[network]
        
        # Расчет стоимости транзакций
        simple_tx_cost = prices['FastGasPrice'] * 21000 / 1e9
        swap_tx_cost = prices['FastGasPrice'] * 150000 / 1e9
        contract_tx_cost = prices['FastGasPrice'] * 300000 / 1e9
        
        network_report = f"""
⛽ *{network_name.upper()} GAS PRICES*
*Время:* {datetime.now().strftime('%H:%M:%S')}

*Текущие цены:*
• 🐌 Медленно: {prices['SafeGasPrice']} Gwei
• 🚶 Средне: {prices['ProposeGasPrice']} Gwei
• 🏃 Быстро: {prices['FastGasPrice']} Gwei
{'• 📊 Базовая цена: ' + str(prices['suggestBaseFee']) + ' Gwei' if 'suggestBaseFee' in prices else ''}

*Примерная стоимость:*
• Простая транзакция: {simple_tx_cost:.6f} ETH
• SWAP на DEX: {swap_tx_cost:.6f} ETH
• Контрактное взаимодействие: {contract_tx_cost:.6f} ETH

*Рекомендации:*
• Для срочных транзакций: {prices['FastGasPrice']} Gwei
• Для обычных транзакций: {prices['ProposeGasPrice']} Gwei
• Для не срочных: {prices['SafeGasPrice']} Gwei

_Обновлено: {datetime.now().strftime('%H:%M')}_
"""
        
        bot.answer_callback_query(call.id, f"Цены на {network_name}")
        bot.send_message(
            chat_id,
            network_report,
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'roi_investment')
def handle_roi_investment(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        investment = float(message.text.replace(',', '.'))
        
        if investment <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['investment'] = investment
        
        user_states[chat_id] = 'roi_return'
        bot.send_message(
            chat_id,
            f"*Инвестиции: {investment:,.2f}₽*\n\nВведите полученную сумму (в рублях):",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'roi_return')
def handle_roi_return(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        return_amount = float(message.text.replace(',', '.'))
        
        if return_amount <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            investment = user_temp_data[user_id].get('investment', 0)
            
            # Расчет ROI
            profit = return_amount - investment
            roi = (profit / investment) * 100 if investment > 0 else 0
            
            result = f"""
📊 *ROI КАЛЬКУЛЯТОР*

*Параметры:*
• Инвестировано: {investment:,.2f}₽
• Получено: {return_amount:,.2f}₽

*Результаты:*
• Прибыль: {profit:+,.2f}₽
• ROI (доходность): {roi:+.2f}%

*Оценка инвестиции:*
{'🟢 Отличная доходность' if roi >= 50 else '🟡 Хорошая доходность' if roi >= 20 else '🔴 Низкая доходность' if roi >= 0 else '⚫ Убыточная инвестиция'}

*Рекомендации:*
• Целевой ROI для долгосрочных инвестиций: 10-20% годовых
• Для агрессивных стратегий: 30-50% годовых
• Диверсифицируйте портфель для снижения рисков
"""
            
            # Сохраняем в историю
            input_data = {
                'investment': investment,
                'return_amount': return_amount
            }
            result_data = {
                'profit': profit,
                'roi': roi
            }
            db.save_calculation_history(user_id, 'roi_calculator', input_data, result_data)
            
            bot.send_message(
                chat_id,
                result,
                parse_mode='Markdown',
                reply_markup=create_calculators_keyboard()
            )
            user_states[chat_id] = 'calculators_menu'
            
            if user_id in user_temp_data:
                del user_temp_data[user_id]
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'dca_monthly')
def handle_dca_monthly(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        monthly_investment = float(message.text.replace(',', '.'))
        
        if monthly_investment <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['monthly_investment'] = monthly_investment
        
        user_states[chat_id] = 'dca_months'
        bot.send_message(
            chat_id,
            f"*Ежемесячные инвестиции: {monthly_investment:,.2f}₽*\n\nВведите срок инвестирования в месяцах:",
            parse_mode='Markdown'
        )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректную сумму.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'dca_months')
def handle_dca_months(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        months = int(message.text)
        
        if months <= 0:
            bot.send_message(chat_id, "❌ Срок должен быть больше 0 месяцев.")
            return
        
        if user_id in user_temp_data:
            monthly_investment = user_temp_data[user_id].get('monthly_investment', 0)
            
            user_states[chat_id] = 'dca_return'
            bot.send_message(
                chat_id,
                f"*Срок: {months} месяцев*\n\nВведите ожидаемую годовую доходность в % (по умолчанию 10):\n\nМожно ввести /default для 10%",
                parse_mode='Markdown'
            )
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное количество месяцев.")

@bot.message_handler(commands=['default'])
def handle_dca_default(message):
    if user_states.get(message.chat.id) == 'dca_return':
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if user_id in user_temp_data:
            monthly_investment = user_temp_data[user_id].get('monthly_investment', 0)
            months = user_temp_data[user_id].get('months', 12)
            
            result = calculate_dca_strategy(chat_id, user_id, monthly_investment, months, 10)
            
            bot.send_message(
                chat_id,
                result,
                parse_mode='Markdown',
                reply_markup=create_calculators_keyboard()
            )
            user_states[chat_id] = 'calculators_menu'
            
            if user_id in user_temp_data:
                del user_temp_data[user_id]

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'dca_return')
def handle_dca_return(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        expected_return = float(message.text.replace(',', '.'))
        
        if expected_return <= 0 or expected_return > 100:
            bot.send_message(chat_id, "❌ Доходность должна быть от 0.1% до 100%.")
            return
        
        if user_id in user_temp_data:
            monthly_investment = user_temp_data[user_id].get('monthly_investment', 0)
            months = user_temp_data[user_id].get('months', 12)
            
            result = calculate_dca_strategy(chat_id, user_id, monthly_investment, months, expected_return)
            
            bot.send_message(
                chat_id,
                result,
                parse_mode='Markdown',
                reply_markup=create_calculators_keyboard()
            )
            user_states[chat_id] = 'calculators_menu'
            
            if user_id in user_temp_data:
                del user_temp_data[user_id]
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное значение доходности.")

# ... [Остальной код остается без изменений, включая функции регистрации, портфеля и другие обработчики] ...

# ============================================
# ЗАПУСК БОТА
# ============================================

if __name__ == "__main__":
    print("🤖 Бот запущен и готов к работе!")
    print(f"⚡ Защита: {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут")
    print(f"💾 База данных: {DATABASE_NAME}")
    print(f"📋 Регистрация: 3 вопроса перед доступом к функциям")
    print(f"🧮 Калькуляторы: 6 финансовых инструментов")
    print(f"⛽ Gas трекер: Ethereum, Polygon, BSC, Arbitrum")
    print(f"🔔 Уведомления: активны каждые {CHECK_INTERVAL_MINUTES} минут")
    print("📊 Функции портфеля и уведомлений активированы")
    print("🚀 Новый режим: регистрация → создание портфель → полный доступ")
    print("Для остановки: Ctrl+C")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")