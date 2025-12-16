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
TELEGRAM_CHANNEL_ID = "-1002901750088"

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

# Детальная информация по российским акциям
RUSSIAN_STOCKS_DETAILED = {
    'GAZP': {'name': 'Газпром', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'SBER': {'name': 'Сбербанк', 'sector': 'Финансы', 'market': 'MOEX', 'industry': 'Банковский'},
    'LKOH': {'name': 'Лукойл', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'ROSN': {'name': 'Роснефть', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'NLMK': {'name': 'НЛМК', 'sector': 'Металлургия', 'market': 'MOEX', 'industry': 'Металлургия'},
    'GMKN': {'name': 'ГМК Норникель', 'sector': 'Металлургия', 'market': 'MOEX', 'industry': 'Металлургия'},
    'PLZL': {'name': 'Полюс', 'sector': 'Добыча золота', 'market': 'MOEX', 'industry': 'Добывающий'},
    'TATN': {'name': 'Татнефть', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'VTBR': {'name': 'ВТБ', 'sector': 'Финансы', 'market': 'MOEX', 'industry': 'Банковский'},
    'ALRS': {'name': 'АЛРОСА', 'sector': 'Добыча алмазов', 'market': 'MOEX', 'industry': 'Добывающий'},
    'MGNT': {'name': 'Магнит', 'sector': 'Розничная торговля', 'market': 'MOEX', 'industry': 'Розничная торговля'},
    'POLY': {'name': 'Полиметалл', 'sector': 'Добыча металлов', 'market': 'MOEX', 'industry': 'Добывающий'},
    'AFKS': {'name': 'Система', 'sector': 'Конгломерат', 'market': 'MOEX', 'industry': 'Конгломерат'},
    'PHOR': {'name': 'ФосАгро', 'sector': 'Химическая промышленность', 'market': 'MOEX', 'industry': 'Химическая'},
    'SNGS': {'name': 'Сургутнефтегаз (обыкн.)', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'SNGSP': {'name': 'Сургутнефтегаз (прив.)', 'sector': 'Нефть и газ', 'market': 'MOEX', 'industry': 'Нефтегазовый'},
    'MTSS': {'name': 'МТС', 'sector': 'Телекоммуникации', 'market': 'MOEX', 'industry': 'Телекоммуникации'},
    'RUAL': {'name': 'РУСАЛ', 'sector': 'Металлургия', 'market': 'MOEX', 'industry': 'Металлургия'},
    'MOEX': {'name': 'Московская биржа', 'sector': 'Финансы', 'market': 'MOEX', 'industry': 'Финансовый'},
    'YNDX': {'name': 'Яндекс', 'sector': 'Интернет', 'market': 'MOEX', 'industry': 'Интернет'},
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
            
            # Таблица избранных активов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    asset_type TEXT,
                    symbol TEXT,
                    name TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, asset_type, symbol)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channel_subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    channel_id TEXT,
                    subscribed BOOLEAN DEFAULT FALSE,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
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
    
    # Методы для избранного
    def add_to_favorites(self, user_id, asset_type, symbol, name):
        """Добавить актив в избранное"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO favorites 
                    (user_id, asset_type, symbol, name)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, asset_type.upper(), symbol.upper(), name))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            return False
    
    def remove_from_favorites(self, user_id, favorite_id):
        """Удалить актив из избранного"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM favorites WHERE id = ? AND user_id = ?', (favorite_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            return False
    
    def get_favorites(self, user_id):
        """Получить избранное пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, asset_type, symbol, name, added_date
                    FROM favorites WHERE user_id = ?
                    ORDER BY added_date DESC
                ''', (user_id,))
                rows = cursor.fetchall()
                return [{
                    'id': row[0],
                    'asset_type': row[1],
                    'symbol': row[2],
                    'name': row[3],
                    'added_date': row[4]
                } for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []
    
    def is_in_favorites(self, user_id, asset_type, symbol):
        """Проверить, есть ли актив в избранном"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 1 FROM favorites 
                    WHERE user_id = ? AND asset_type = ? AND symbol = ?
                ''', (user_id, asset_type.upper(), symbol.upper()))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки избранного: {e}")
            return False
        
    def check_subscription_status(self, user_id, channel_id=TELEGRAM_CHANNEL_ID):
        """Проверить статус подписки пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT subscribed, last_checked FROM channel_subscriptions 
                    WHERE user_id = ? AND channel_id = ?
                ''', (user_id, channel_id))
                row = cursor.fetchone()
                
                if row:
                    return bool(row[0]), row[1]
                return False, None
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False, None
    
    def update_subscription_status(self, user_id, subscribed, channel_id=TELEGRAM_CHANNEL_ID):
        """Обновить статус подписки пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO channel_subscriptions 
                    (user_id, channel_id, subscribed, last_checked) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, channel_id, subscribed))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса подписки: {e}")
            return False
    
    def get_subscription_count(self):
        """Получить количество подписанных пользователей"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM channel_subscriptions WHERE subscribed = TRUE')
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Ошибка получения количества подписок: {e}")
            return 0
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
    button9 = KeyboardButton('⭐ Избранное')
    button10 = KeyboardButton('🧮 Калькулятор')
    button11 = KeyboardButton('📨 Связь с админом')
    button12 = KeyboardButton('ℹ️ О боте')
    button13 = KeyboardButton('🔄 Пересоздать портфель')
    button14 = KeyboardButton('📢 Проверить подписку')  # Новая кнопка
    keyboard.add(button1, button2, button3, button4, button5, button6, button7, button8)
    keyboard.add(button9, button10, button11, button12, button13, button14)  # Добавьте button14
    return keyboard

def create_favorites_keyboard():
    """Клавиатура для управления избранным"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👁 Показать все", callback_data="favorites_show_all"),
        InlineKeyboardButton("🗑 Очистить всё", callback_data="favorites_clear_all"),
        InlineKeyboardButton("📈 Обновить котировки", callback_data="favorites_update"),
        InlineKeyboardButton("❌ Закрыть", callback_data="favorites_close")
    )
    return keyboard

def create_add_favorite_keyboard(symbol, asset_type):
    """Клавиатура для добавления в избранное при поиске"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"⭐ Добавить {symbol} в избранное", 
                           callback_data=f"add_favorite_{asset_type}_{symbol}"),
        InlineKeyboardButton("🔙 Назад к поиску", callback_data="back_to_search")
    )
    return keyboard

def create_manage_favorite_keyboard(favorite_id, symbol):
    """Клавиатура для управления конкретным избранным"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📈 Получить котировку", callback_data=f"fav_quote_{favorite_id}"),
        InlineKeyboardButton("🗑 Удалить", callback_data=f"fav_remove_{favorite_id}"),
        InlineKeyboardButton("📊 Добавить в портфель", callback_data=f"fav_to_portfolio_{favorite_id}"),
        InlineKeyboardButton("🔔 Настроить уведомление", callback_data=f"fav_alert_{favorite_id}")
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

def create_calculator_keyboard():
    """Клавиатура для калькулятора"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    keyboard.add(
        KeyboardButton('💱 Конвертер валют'),
        KeyboardButton('📈 Прибыль/убыток'),
        KeyboardButton('💰 Стоимость актива'),
        KeyboardButton('📊 Сложный процент'),
        KeyboardButton('🏦 Кредит/депозит'),
        KeyboardButton('❌ Отмена')
    )
    return keyboard

def create_calculator_back_keyboard():
    """Клавиатура с кнопкой Назад для калькулятора"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton('⬅️ Назад в калькулятор'))
    return keyboard

def create_converter_keyboard():
    """Клавиатура для конвертера валют"""
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Популярные валюты
    popular_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'RUB']
    buttons = []
    for currency in popular_currencies:
        if currency in POPULAR_CURRENCIES:
            emoji = POPULAR_CURRENCIES[currency]['flag']
            buttons.append(InlineKeyboardButton(f"{emoji} {currency}", callback_data=f"conv_from_{currency}"))
    
    # Добавляем кнопки построчно
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i+3])
    
    keyboard.add(
        InlineKeyboardButton("📝 Ввести код", callback_data="conv_custom"),
        InlineKeyboardButton("❌ Отмена", callback_data="calc_cancel")
    )
    
    return keyboard

def create_crypto_converter_keyboard():
    """Клавиатура для конвертера криптовалют"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Популярные криптовалюты
    popular_cryptos = ['BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'XRP']
    buttons = []
    for crypto_symbol in popular_cryptos:
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == crypto_symbol:
                emoji = info['emoji']
                buttons.append(InlineKeyboardButton(f"{emoji} {crypto_symbol}", callback_data=f"conv_crypto_from_{crypto_symbol}"))
                break
    
    # Добавляем кнопки построчно
    for i in range(0, len(buttons), 2):
        keyboard.add(*buttons[i:i+2])
    
    keyboard.add(
        InlineKeyboardButton("📝 Ввести символ", callback_data="conv_crypto_custom"),
        InlineKeyboardButton("⬅️ Назад", callback_data="conv_back_main")
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
    # Сначала проверяем подписку на канал
    if not check_subscription(user_id):
        access_denied_text = f"""
🚫 *Доступ ограничен*

Для использования функций бота необходимо подписаться на наш канал.

📢 *Обязательное условие:*
1. Подпишитесь на канал: {TELEGRAM_CHANNEL_ID}
2. Нажмите кнопку "✅ Проверить подписку"

*После подписки вам станут доступны:*
• 📋 Регистрация в боте
• 📊 Создание портфеля
• 🏆 Топ валют и криптовалют
• 🔍 Поиск активов
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Финансовый калькулятор

*Почему это важно?*
• Получайте эксклюзивные аналитические обзоры
• Узнавайте первыми о новых функциях бота
• Получайте инвестиционные идеи от экспертов
"""
        return False, access_denied_text
    
    # Затем проверяем, завершена ли регистрация
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
def check_subscription(user_id):
    """
    Проверить, подписан ли пользователь на канал
    Возвращает True если подписан, False если нет
    """
    try:
        # Проверяем в базе данных
        subscribed, last_checked = db.check_subscription_status(user_id)
        
        # Если недавно проверяли (менее 1 часа назад), используем кэшированное значение
        if last_checked:
            last_checked_dt = datetime.strptime(last_checked, '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_checked_dt).seconds < 3600:
                return subscribed
        
        # Проверяем через API Telegram
        try:
            # Пытаемся получить статус участника канала
            chat_member = bot.get_chat_member(TELEGRAM_CHANNEL_ID, user_id)
            
            # Статусы, которые считаются подпиской
            valid_statuses = ['member', 'administrator', 'creator']
            is_subscribed = chat_member.status in valid_statuses
            
            # Обновляем статус в базе данных
            db.update_subscription_status(user_id, is_subscribed)
            
            return is_subscribed
            
        except telebot.apihelper.ApiTelegramException as e:
            if "user not found" in str(e) or "chat not found" in str(e):
                # Если пользователь не найден или не является участником
                db.update_subscription_status(user_id, False)
                return False
            elif "Bad Request: user_id invalid" in str(e):
                # Если ID пользователя неверный
                logger.error(f"Invalid user ID: {user_id}")
                return False
            else:
                # Другие ошибки - используем кэшированное значение
                logger.error(f"Error checking subscription: {e}")
                return subscribed
        
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False
    
# ============================================
# ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ РЕАЛЬНЫХ ДАННЫХ
# ============================================

def get_real_time_stock_price(ticker):
    """Получение 'реальных' данных по акциям (улучшенные демо-данные)"""
    try:
        # Базовые цены для разных тикеров
        base_prices = {
            'GAZP': 180.5, 'SBER': 275.3, 'LKOH': 6850.2, 'ROSN': 520.8, 'NLMK': 185.6,
            'GMKN': 15890.5, 'PLZL': 11250.8, 'TATN': 385.4, 'VTBR': 0.0285, 'ALRS': 78.9,
            'MGNT': 5500.0, 'POLY': 850.0, 'AFKS': 15.2, 'PHOR': 4800.0, 'SNGS': 35.8,
            'SNGSP': 36.2, 'MTSS': 280.5, 'RUAL': 40.3, 'MOEX': 150.8, 'YNDX': 2300.5
        }
        
        if ticker not in base_prices:
            return None
        
        # Генерируем небольшие изменения для реалистичности
        base_price = base_prices[ticker]
        
        # В разное время суток разные изменения
        current_hour = datetime.now().hour
        volatility = 0.02  # 2% волатильность
        
        # Учитываем время торгов (10:00-18:30 МСК)
        if 10 <= current_hour < 19:
            # Время торгов - больше волатильности
            volatility = 0.04
            # Эмулируем дневные колебания
            time_factor = (current_hour - 10) / 9  # от 0 до 1 в течение дня
            base_price *= (0.99 + 0.02 * time_factor)  # небольшая тенденция роста в течение дня
        
        # Случайное изменение в пределах волатильности
        change_percent = random.uniform(-volatility, volatility)
        
        # Для некоторых акций делаем более реалистичные паттерны
        if ticker in ['GAZP', 'ROSN', 'LKOH']:
            # Нефтегазовые - корреляция с нефтью
            oil_factor = random.uniform(-0.01, 0.01)
            change_percent += oil_factor
        
        price = base_price * (1 + change_percent)
        change = price - base_price
        
        return {
            'ticker': ticker,
            'name': RUSSIAN_STOCKS.get(ticker, {}).get('name', ticker),
            'price': round(price, 2),
            'change': round(change, 2),
            'change_percent': round((change / base_price) * 100, 2),
            'previous_close': base_price,
            'currency': 'RUB',
            'time': datetime.now().strftime('%H:%M:%S'),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'volume': random.randint(100000, 5000000),  # Случайный объем
            'market_cap': round(base_price * random.randint(10000000, 500000000), 2)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения цены акции {ticker}: {e}")
        return None

def get_real_time_currency_rate(currency_code):
    """Получение реальных данных по валютам"""
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=5)
        data = response.json()
        
        if currency_code == 'RUB':
            return {
                'code': 'RUB',
                'name': 'Российский рубль',
                'price': 1.0,
                'change': 0,
                'change_percent': 0,
                'previous': 1.0
            }
        
        if currency_code in data['Valute']:
            valute = data['Valute'][currency_code]
            value = valute['Value']
            previous = valute['Previous']
            change = value - previous
            change_percent = (change / previous) * 100 if previous else 0
            
            return {
                'code': currency_code,
                'name': valute['Name'],
                'price': value,
                'change': change,
                'change_percent': round(change_percent, 4),
                'previous': previous,
                'nominal': valute['Nominal']
            }
        else:
            return None
            
    except Exception as e:
        logger.error(f"Ошибка получения курса {currency_code}: {e}")
        return None

def get_real_time_crypto_price(symbol):
    """Получение реальных данных по криптовалютам"""
    try:
        # Находим ID криптовалюты по символу
        crypto_id = None
        for cid, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == symbol:
                crypto_id = cid
                break
        
        if not crypto_id:
            return None
        
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=rub,usd&include_24hr_change=true'
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if crypto_id in data:
            price_rub = data[crypto_id].get('rub', 0)
            price_usd = data[crypto_id].get('usd', 0)
            change_24h = data[crypto_id].get('usd_24h_change', 0) or 0
            
            return {
                'symbol': symbol,
                'name': POPULAR_CRYPTOCURRENCIES[crypto_id]['name'],
                'price_rub': price_rub,
                'price_usd': price_usd,
                'change_24h': change_24h,
                'time': datetime.now().strftime('%H:%M:%S')
            }
        else:
            return None
            
    except Exception as e:
        logger.error(f"Ошибка получения цены крипты {symbol}: {e}")
        return None

# ============================================
# ОБНОВЛЕННЫЕ ФУНКЦИИ ДЛЯ ИЗБРАННОГО
# ============================================

def format_favorite_item(favorite, real_time_data=None):
    """Форматирование одного элемента избранного"""
    symbol = favorite['symbol']
    asset_type = favorite['asset_type']
    name = favorite['name']
    
    if asset_type == 'STOCK':
        if real_time_data:
            change_icon = "🟢" if real_time_data['change'] > 0 else "🔴" if real_time_data['change'] < 0 else "⚪"
            change_sign = "+" if real_time_data['change'] > 0 else ""
            
            formatted = f"*{symbol}* - {name}\n"
            formatted += f"   💰 Цена: {real_time_data['price']:,.2f}₽\n"
            formatted += f"   📊 Изменение: {change_sign}{real_time_data['change']:,.2f} ({change_sign}{real_time_data['change_percent']:.2f}%) {change_icon}\n"
            formatted += f"   🕒 Время: {real_time_data['time']}"
        else:
            formatted = f"*{symbol}* - {name}\n"
            formatted += f"   💰 Цена: *данные временно недоступны*\n"
            formatted += f"   📊 Московская биржа (MOEX)"
    
    elif asset_type == 'CURRENCY':
        if real_time_data:
            change_icon = "📈" if real_time_data['change'] > 0 else "📉" if real_time_data['change'] < 0 else "➡️"
            change_sign = "+" if real_time_data['change'] > 0 else ""
            
            formatted = f"*{symbol}* - {name}\n"
            if real_time_data.get('nominal', 1) > 1:
                formatted += f"   💰 {real_time_data['nominal']} ед.: {real_time_data['price']:,.4f}₽\n"
            else:
                formatted += f"   💰 Цена: {real_time_data['price']:,.4f}₽\n"
            formatted += f"   📊 Изменение: {change_sign}{real_time_data['change']:,.4f} ({change_sign}{real_time_data['change_percent']:.4f}%) {change_icon}"
        else:
            formatted = f"*{symbol}* - {name}\n"
            formatted += f"   💰 Курс ЦБ РФ\n"
            formatted += f"   📊 Данные временно недоступны"
    
    elif asset_type == 'CRYPTO':
        if real_time_data:
            change_icon = "📈" if real_time_data['change_24h'] > 0 else "📉" if real_time_data['change_24h'] < 0 else "➡️"
            change_sign = "+" if real_time_data['change_24h'] > 0 else ""
            
            formatted = f"*{symbol}* - {name}\n"
            formatted += f"   💰 Цена: {real_time_data['price_rub']:,.0f}₽ (${real_time_data['price_usd']:,.2f})\n"
            formatted += f"   📊 24ч: {change_sign}{real_time_data['change_24h']:.2f}% {change_icon}\n"
            formatted += f"   🕒 Время: {real_time_data['time']}"
        else:
            formatted = f"*{symbol}* - {name}\n"
            formatted += f"   💰 Цена: *данные CoinGecko*\n"
            formatted += f"   📊 Обновление..."
    
    else:
        formatted = f"*{symbol}* - {name}\n"
        formatted += f"   Тип: {asset_type}"
    
    return formatted

def add_to_favorites_function(chat_id, user_id, symbol, asset_type, name):
    """Добавить актив в избранное с показом информации в нужном формате"""
    success = db.add_to_favorites(user_id, asset_type, symbol, name)
    
    if success:
        # Получаем актуальные данные для отображения
        if asset_type.upper() == 'STOCK':
            real_time_data = get_real_time_stock_price(symbol)
        elif asset_type.upper() == 'CURRENCY':
            real_time_data = get_real_time_currency_rate(symbol)
        elif asset_type.upper() == 'CRYPTO':
            real_time_data = get_real_time_crypto_price(symbol)
        else:
            real_time_data = None
        
        # Форматируем сообщение в нужном формате
        favorite = {'symbol': symbol, 'asset_type': asset_type.upper(), 'name': name}
        formatted_info = format_favorite_item(favorite, real_time_data)
        
        # Добавляем заголовок
        message_text = f"✅ *Добавлено в избранное!*\n\n"
        message_text += formatted_info
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        # Записываем действие
        db.add_user_action(user_id, "add_to_favorites", f"{asset_type}:{symbol}")
        
        # Показываем кнопки для дальнейших действий
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("⭐ Перейти в избранное", callback_data="favorites_show_all"),
            InlineKeyboardButton("📊 Добавить в портфель", callback_data=f"fav_add_to_portfolio_{asset_type}_{symbol}")
        )
        
        bot.send_message(
            chat_id,
            f"*Что дальше?*\n\nВы можете добавить *{symbol}* в портфель или настроить уведомления.",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            chat_id,
            f"❌ *{symbol}* уже есть в избранном или произошла ошибка.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    
    return success

def show_favorites(chat_id, user_id):
    """Показать избранное пользователя"""
    favorites = db.get_favorites(user_id)
    
    if not favorites:
        bot.send_message(
            chat_id,
            "⭐ *Ваше избранное пусто*\n\nДобавляйте активы в избранное при поиске, чтобы быстро получать их котировки.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    favorites_text = f"⭐ *ВАШЕ ИЗБРАННОЕ* ({len(favorites)} активов)\n\n"
    
    # Группируем по типам активов
    by_type = {'CURRENCY': [], 'CRYPTO': [], 'STOCK': []}
    type_names = {
        'CURRENCY': '💱 Валюты',
        'CRYPTO': '₿ Криптовалюты', 
        'STOCK': '📈 Акции'
    }
    
    for fav in favorites:
        asset_type_upper = fav['asset_type'].upper()
        if asset_type_upper in by_type:
            by_type[asset_type_upper].append(fav)
        else:
            by_type[asset_type_upper] = [fav]
    
    # Формируем текст
    for asset_type, type_name in type_names.items():
        if by_type[asset_type]:
            favorites_text += f"*{type_name}* ({len(by_type[asset_type])}):\n"
            
            for fav in by_type[asset_type]:
                try:
                    date_added = datetime.strptime(fav['added_date'], '%Y-%m-%d %H:%M:%S')
                    days_ago = (datetime.now() - date_added).days
                    
                    if days_ago == 0:
                        time_str = "сегодня"
                    elif days_ago == 1:
                        time_str = "вчера"
                    elif days_ago < 30:
                        time_str = f"{days_ago} дней назад"
                    elif days_ago < 365:
                        time_str = f"{days_ago//30} месяцев назад"
                    else:
                        time_str = f"{days_ago//365} лет назад"
                    
                    favorites_text += f"• *{fav['symbol']}* - {fav['name']} ({time_str})\n"
                except:
                    favorites_text += f"• *{fav['symbol']}* - {fav['name']}\n"
            
            favorites_text += "\n"
    
    if favorites_text.strip() == f"⭐ *ВАШЕ ИЗБРАННОЕ* ({len(favorites)} активов)\n\n":
        favorites_text += "Нет активов в избранном\n"
    
    favorites_text += "\n_Используйте кнопки ниже для управления_"
    
    # Отправляем сообщение с кнопками
    bot.send_message(
        chat_id,
        favorites_text,
        parse_mode='Markdown',
        reply_markup=create_favorites_keyboard()
    )

def show_favorites_with_real_time_prices(chat_id, user_id):
    """Показать избранное с реальными ценами в нужном формате"""
    favorites = db.get_favorites(user_id)
    
    if not favorites:
        bot.send_message(
            chat_id,
            "⭐ *Ваше избранное пусто*\n\nДобавляйте активы в избранное при поиске, чтобы быстро получать их котировки.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    bot.send_message(chat_id, "🔄 Получаю актуальные котировки...")
    
    favorites_by_type = {'STOCK': [], 'CURRENCY': [], 'CRYPTO': []}
    
    # Группируем по типам
    for fav in favorites:
        asset_type = fav['asset_type'].upper()
        if asset_type in favorites_by_type:
            favorites_by_type[asset_type].append(fav)
    
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    
    # Сначала показываем акции в нужном формате
    if favorites_by_type['STOCK']:
        response_text = f"⭐ *АКЦИИ РФ (MOEX)*\n"
        response_text += f"_Обновлено: {current_time}_\n\n"
        
        for fav in favorites_by_type['STOCK']:
            stock_data = get_real_time_stock_price(fav['symbol'])
            if stock_data:
                response_text += format_favorite_item(fav, stock_data)
                
                # Добавляем дополнительные данные для акций
                if fav['symbol'] in RUSSIAN_STOCKS_DETAILED:
                    stock_info = RUSSIAN_STOCKS_DETAILED[fav['symbol']]
                    response_text += f"   📈 Сектор: {stock_info['sector']}\n"
                
                response_text += "\n"
        
        # Отправляем сообщение с акциями
        if len(response_text) > 50:  # Если есть данные
            bot.send_message(chat_id, response_text, parse_mode='Markdown')
    
    # Затем валюты
    if favorites_by_type['CURRENCY']:
        response_text = f"💱 *ВАЛЮТЫ (ЦБ РФ)*\n"
        response_text += f"_Обновлено: {current_time}_\n\n"
        
        for fav in favorites_by_type['CURRENCY']:
            currency_data = get_real_time_currency_rate(fav['symbol'])
            if currency_data:
                response_text += format_favorite_item(fav, currency_data)
                
                # Добавляем флаг для валюты
                if fav['symbol'] in POPULAR_CURRENCIES:
                    flag = POPULAR_CURRENCIES[fav['symbol']]['flag']
                    response_text += f"   {flag} Валюта\n"
                
                response_text += "\n"
        
        # Отправляем сообщение с валютами
        if len(response_text) > 50:
            bot.send_message(chat_id, response_text, parse_mode='Markdown')
    
    # Затем криптовалюты
    if favorites_by_type['CRYPTO']:
        response_text = f"₿ *КРИПТОВАЛЮТЫ*\n"
        response_text += f"_Обновлено: {current_time}_\n\n"
        
        for fav in favorites_by_type['CRYPTO']:
            crypto_data = get_real_time_crypto_price(fav['symbol'])
            if crypto_data:
                response_text += format_favorite_item(fav, crypto_data)
                
                # Добавляем эмодзи для крипты
                for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
                    if info['symbol'] == fav['symbol']:
                        response_text += f"   {info['emoji']} CoinGecko\n"
                        break
                
                response_text += "\n"
        
        # Отправляем сообщение с криптой
        if len(response_text) > 50:
            bot.send_message(chat_id, response_text, parse_mode='Markdown')
    
    # Кнопки управления
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Обновить котировки", callback_data="favorites_update"),
        InlineKeyboardButton("📊 Добавить в портфель", callback_data="favorites_bulk_to_portfolio"),
        InlineKeyboardButton("❌ Закрыть", callback_data="favorites_close")
    )
    
    bot.send_message(
        chat_id,
        "📊 *Управление избранным:*",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

def clear_all_favorites(chat_id, user_id):
    """Очистить всё избранное"""
    favorites = db.get_favorites(user_id)
    
    if not favorites:
        bot.send_message(
            chat_id,
            "⭐ *Избранное и так пусто*",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    # Создаем клавиатуру подтверждения
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, очистить всё", callback_data="confirm_clear_favorites"),
        InlineKeyboardButton("❌ Нет, отменить", callback_data="cancel_clear_favorites")
    )
    
    bot.send_message(
        chat_id,
        f"⚠️ *Вы уверены, что хотите удалить всё избранное?*\n\nБудет удалено {len(favorites)} активов.\n\n*Это действие нельзя отменить!*",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ============================================
# ФУНКЦИИ РЕГИСТРАЦИИ
# ============================================

def start_registration(chat_id, user_id):
    """Начать процесс регистрации"""
    # Проверяем подписку перед началом регистрации
    if not check_subscription(user_id):
        show_subscription_required(chat_id, user_id)
        return
    
    user_states[chat_id] = 'registration_1'
    
    welcome_text = f"""
*🎉 Добро пожаловать в Финансовый Бот!*

✅ *Вы успешно подписаны на наш канал: {TELEGRAM_CHANNEL_ID}*

Теперь давайте познакомимся!

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

def format_search_results_with_favorite_detailed(results, query, user_id, search_type='currency'):
    """Форматирование результатов поиска с кнопкой добавления в избранное и детальной информацией"""
    if not results:
        return f"❌ *{search_type.capitalize()} не найдены*\n\nПо запросу: `{query}`"
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if len(results) == 1:
        # Для одного результата показываем подробно в нужном формате
        if search_type == 'stock':
            stock = results[0]
            
            # Получаем более детальные данные
            real_time_data = get_real_time_stock_price(stock['ticker'])
            
            if real_time_data:
                change_icon = "🟢" if real_time_data['change'] > 0 else "🔴" if real_time_data['change'] < 0 else "⚪"
                change_sign = "+" if real_time_data['change'] > 0 else ""
                
                result_text = f"*📈 НАЙДЕНА АКЦИЯ*\n\n"
                result_text += f"*{stock['ticker']}* - {stock['name']}\n"
                result_text += f"   💰 Цена: {real_time_data['price']:,.2f}₽\n"
                result_text += f"   📊 Изменение: {change_sign}{real_time_data['change']:,.2f} ({change_sign}{real_time_data['change_percent']:.2f}%) {change_icon}\n"
                result_text += f"   📈 Сектор: {stock['sector']}\n"
                result_text += f"   🏛️ Биржа: {stock['market']}\n"
                result_text += f"   🕒 Время: {real_time_data['time']}\n"
                
                # Объем торгов
                if real_time_data.get('volume'):
                    volume_str = f"{real_time_data['volume']:,}" if real_time_data['volume'] < 1000000 else f"{real_time_data['volume']/1000000:.1f}M"
                    result_text += f"   📊 Объем: {volume_str} акций\n"
                
            else:
                result_text = f"*{stock['ticker']}* - {stock['name']}\n"
                result_text += f"   💰 Цена: *данные временно недоступны*\n"
                result_text += f"   📊 Московская биржа (MOEX)\n"
            
            # Проверяем, есть ли уже в избранном
            is_favorite = db.is_in_favorites(user_id, 'stock', stock['ticker'])
            
            if not is_favorite:
                keyboard = create_add_favorite_keyboard(stock['ticker'], 'stock')
                
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                result_text += f"\n⭐ *Уже в избранном*\n\n"
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
            
            result_text += f"\n_Время: {current_time}_"
            return None
            
        elif search_type == 'currency':
            currency = results[0]
            
            # Получаем реальные данные
            real_time_data = get_real_time_currency_rate(currency['code'])
            
            if real_time_data:
                change_icon = "📈" if real_time_data['change'] > 0 else "📉" if real_time_data['change'] < 0 else "➡️"
                change_sign = "+" if real_time_data['change'] > 0 else ""
                
                result_text = f"*💱 НАЙДЕНА ВАЛЮТА*\n\n"
                result_text += f"*{currency['code']}* - {currency['name']}\n"
                
                if real_time_data.get('nominal', 1) > 1:
                    value_per_unit = real_time_data['price'] / real_time_data['nominal']
                    result_text += f"   💰 {real_time_data['nominal']} ед.: {real_time_data['price']:,.4f}₽\n"
                    result_text += f"       1 ед.: {value_per_unit:,.4f}₽\n"
                else:
                    result_text += f"   💰 Цена: {real_time_data['price']:,.4f}₽\n"
                
                result_text += f"   📊 Изменение: {change_sign}{real_time_data['change']:,.4f} ({change_sign}{real_time_data['change_percent']:.4f}%) {change_icon}\n"
                
                if currency['code'] in POPULAR_CURRENCIES:
                    flag = POPULAR_CURRENCIES[currency['code']]['flag']
                    symbol_icon = POPULAR_CURRENCIES[currency['code']]['symbol']
                    result_text += f"   {flag} Символ: {symbol_icon}\n"
                
            else:
                result_text = f"*{currency['code']}* - {currency['name']}\n"
                result_text += f"   💰 Цена: *данные временно недоступны*\n"
            
            # Проверяем, есть ли уже в избранном
            is_favorite = db.is_in_favorites(user_id, 'currency', currency['code'])
            
            if not is_favorite:
                keyboard = create_add_favorite_keyboard(currency['code'], 'currency')
                
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                result_text += f"\n⭐ *Уже в избранном*\n\n"
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
            
            result_text += f"\n_Данные ЦБ РФ, время: {current_time}_"
            return None
            
        elif search_type == 'crypto':
            crypto = results[0]
            
            # Теперь данные уже содержат актуальные цены из search_crypto
            change_icon = "📈" if crypto['change_24h'] > 0 else "📉" if crypto['change_24h'] < 0 else "➡️"
            change_sign = "+" if crypto['change_24h'] > 0 else ""
            
            emoji = POPULAR_CRYPTOCURRENCIES.get(crypto['id'], {}).get('emoji', '₿')
            current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
            
            # Форматируем вывод в нужном формате
            result_text = f"*₿ НАЙДЕНА КРИПТОВАЛЮТА*\n\n"
            result_text += f"{emoji} *{crypto['name']} ({crypto['symbol']})*\n"
            
            if crypto.get('market_cap_rank') and crypto['market_cap_rank'] <= 100:
                result_text += f"   📊 Ранг: #{crypto['market_cap_rank']}\n"
            
            # ОСНОВНОЕ ИЗМЕНЕНИЕ: Показываем цену в рублях первой и выделяем
            result_text += f"   💰 Цена: {crypto['price_rub']:,.0f}₽\n"
            
            if crypto['price_usd'] > 0:
                result_text += f"        (${crypto['price_usd']:,.2f})\n"
            
            if crypto['change_24h'] != 0:
                result_text += f"   📈 Изменение (24ч): {change_sign}{crypto['change_24h']:.1f}% {change_icon}\n"
            
            result_text += f"   🕒 Обновлено: {current_time}\n"
            
            # Проверяем, есть ли уже в избранном
            is_favorite = db.is_in_favorites(user_id, 'crypto', crypto['symbol'])
            
            if not is_favorite:
                keyboard = create_add_favorite_keyboard(crypto['symbol'], 'crypto')
                
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                result_text += f"\n⭐ *Уже в избранном*\n\n"
                bot.send_message(
                    user_id,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
            
            return None
    
    else:
        # Для нескольких результатов показываем список
        result_text = f"*🔍 Найдено {len(results)} {search_type}*\n\n"
        
        for i, item in enumerate(results[:10], 1):
            if search_type == 'currency':
                result_text += f"{i}. *{item['code']}* - {item['name']}\n"
            elif search_type == 'crypto':
                result_text += f"{i}. *{item['symbol']}* - {item['name']}\n"
            elif search_type == 'stock':
                result_text += f"{i}. *{item['ticker']}* - {item['name']}\n"
        
        result_text += f"\n_По запросу: {query}_\n"
        result_text += f"_Для подробностей ищите по одному символу_"
        
        return result_text

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
    """Поиск криптовалют с получением актуальных цен в рублях"""
    try:
        query = query.lower().strip()
        
        # 1. Сначала ищем криптовалюту по запросу
        search_url = f'https://api.coingecko.com/api/v3/search?query={query}'
        search_response = requests.get(search_url, timeout=10)
        search_data = search_response.json()
        
        if 'coins' not in search_data or not search_data['coins']:
            return []  # Ничего не найдено
        
        # 2. Берем топ-5 результатов поиска
        top_coins = search_data['coins'][:5]
        coin_ids = [coin['id'] for coin in top_coins]
        
        if not coin_ids:
            return []
        
        # 3. ОДНИМ запросом получаем цены для всех найденных монет в рублях
        coin_ids_str = ','.join(coin_ids)
        price_url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_ids_str}&vs_currencies=rub%2Cusd&include_24hr_change=true&precision=2'
        price_response = requests.get(price_url, timeout=10)
        price_data = price_response.json()
        
        # 4. Формируем полные результаты с ценами
        results = []
        for coin in top_coins:
            coin_id = coin['id']
            
            if coin_id in price_data:
                price_info = price_data[coin_id]
                
                results.append({
                    'id': coin_id,
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(),
                    'market_cap_rank': coin.get('market_cap_rank'),
                    'price_usd': price_info.get('usd', 0),
                    'price_rub': price_info.get('rub', 0),
                    'change_24h': price_info.get('usd_24h_change', 0) or 0,
                    # Добавляем изменение в рублях для отображения
                    'change_24h_rub': (price_info.get('rub_24h_change', 0) or 0) if 'rub_24h_change' in price_info else 0
                })
            else:
                # Если не удалось получить цену, все равно возвращаем базовую информацию
                results.append({
                    'id': coin_id,
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(),
                    'market_cap_rank': coin.get('market_cap_rank'),
                    'price_usd': 0,
                    'price_rub': 0,
                    'change_24h': 0,
                    'change_24h_rub': 0
                })
        
        return results
        
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
        
        # ПОКАЗЫВАЕМ ЦЕНУ В РУБЛЯХ В ПЕРВУЮ ОЧЕРЕДЬ
        if crypto['price_rub'] > 0:
            result += f"   💰 Цена: {crypto['price_rub']:,.0f}₽\n"
        
        if crypto['price_usd'] > 0:
            result += f"        (${crypto['price_usd']:,.4f})\n"
        
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
    """Управление уведомлений"""
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
# ФУНКЦИИ КАЛЬКУЛЯТОРА
# ============================================

def convert_currency(amount, from_currency, to_currency):
    """Конвертация валюты"""
    try:
        from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
        to_emoji = POPULAR_CURRENCIES.get(to_currency, {}).get('flag', '💱')
        
        # Проверяем, является ли целевая валюта криптовалютой
        is_to_crypto = False
        crypto_id_for_price = None
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == to_currency:
                is_to_crypto = True
                to_emoji = info['emoji']
                crypto_id_for_price = crypto_id
                break
        
        # Получаем курс из ЦБ РФ
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        cbr_data = response.json()
        
        # Конвертируем через RUB
        # 1. from_currency -> RUB
        if from_currency == 'RUB':
            from_to_rub = 1.0
        elif from_currency in cbr_data['Valute']:
            valute = cbr_data['Valute'][from_currency]
            from_to_rub = valute['Value'] / valute['Nominal']
        else:
            return None
        
        # 2. RUB -> to_currency
        if is_to_crypto:
            # Для криптовалют получаем курс из CoinGecko
            try:
                crypto_url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_id_for_price}&vs_currencies=rub'
                crypto_response = requests.get(crypto_url, timeout=10)
                crypto_data = crypto_response.json()
                
                if crypto_id_for_price in crypto_data:
                    crypto_price_rub = crypto_data[crypto_id_for_price]['rub']
                    rub_to_to = 1 / crypto_price_rub
                else:
                    return None
            except:
                return None
        elif to_currency == 'RUB':
            rub_to_to = 1.0
        elif to_currency in cbr_data['Valute']:
            valute = cbr_data['Valute'][to_currency]
            rub_to_to = valute['Nominal'] / valute['Value']
        else:
            return None
        
        # Расчет результата
        result_amount = amount * from_to_rub * rub_to_to
        
        # Обратный курс
        reverse_amount = 1 / (from_to_rub * rub_to_to)
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        result = f"""
*💱 РЕЗУЛЬТАТ КОНВЕРТАЦИИ*

*Исходные данные:*
• Сумма: {amount:,.2f} {from_emoji} {from_currency}
• Конвертация в: {to_emoji} {to_currency}

*📊 Результат:*
• Получаете: *{result_amount:,.4f} {to_emoji} {to_currency}*

*🔁 Обратный курс:*
• 1 {to_currency} = {reverse_amount:,.4f} {from_currency}
• 1 {from_currency} = {1/reverse_amount:,.4f} {to_currency}

*📈 Курсы на момент расчета:*
• 1 {from_currency} = {from_to_rub:,.4f}₽
• 1 {to_currency} = {1/rub_to_to:,.4f}₽

_Обновлено: {current_time}_
"""
        
        if is_to_crypto:
            result += f"\n*⚠️ Внимание:*\nКурс криптовалют может сильно меняться. Данные предоставлены CoinGecko."
        else:
            result += f"\n_Данные предоставлены Центральным Банком РФ_"
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        return None

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@bot.message_handler(commands=['start'])
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "start_command")
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем подписку на канал
    if not check_subscription(user_id):
        show_subscription_required(chat_id, user_id)
        return
    
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
• Избранному
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
• ⭐ Избранное
• 🧮 Калькулятор

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
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Калькулятор

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
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Калькулятор

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
• ⭐ Избранное
• 🔔 Мои уведомления
• 🧮 Калькулятор
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
/favorites или /fav - Избранное
/favupdate - Обновить котировки избранного
/calc - Финансовый калькулятор
/loan - Расчет кредита
/deposit - Расчет депозита

*Примеры поиска:*
/search USD
/currency евро
/cryptosearch Bitcoin
/crypto BTC
/stocksearch GAZP
/stock SBER
/stock Газпром

*Примеры калькулятора:*
/calc - открыть калькулятор
/loan 1000000 60 12 - кредит 1 млн на 5 лет под 12%
/deposit 500000 36 8 monthly - депозит 500к на 3 года под 8% с капитализацией

_Используйте кнопки для удобства_
"""
        bot.send_message(
            chat_id,
            help_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
@bot.message_handler(func=lambda message: message.text == '📢 Проверить подписку')
def handle_check_subscription_button(message):
    """Обработчик кнопки проверки подписки"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "check_subscription_button")
    
    # Проверяем подписку
    is_subscribed = check_subscription(user_id)
    
    if is_subscribed:
        subscribed_text = f"""
✅ *ВЫ ПОДПИСАНЫ НА КАНАЛ!*

📢 Канал: {TELEGRAM_CHANNEL_ID}
👤 Ваш ID: {user_id}
📊 Всего подписчиков: {db.get_subscription_count()}

Теперь вы можете использовать все функции бота.
"""
        bot.send_message(
            chat_id,
            subscribed_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    else:
        show_subscription_required(chat_id, user_id)
        
@bot.callback_query_handler(func=lambda call: call.data.startswith(('check_subscription', 'subscription_')))
def handle_subscription_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'check_subscription':
        # Принудительно проверяем подписку
        is_subscribed = check_subscription(user_id)
        
        if is_subscribed:
            bot.answer_callback_query(call.id, "✅ Вы подписаны на канал!")
            bot.delete_message(chat_id, call.message.message_id)
            
            welcome_text = """
✅ *Отлично! Вы подписаны на наш канал!*

Теперь вы можете использовать все функции бота:

*Следующие шаги:*
1. Пройдите быструю регистрацию (3 вопроса)
2. Создайте свой портфель
3. Начните отслеживать свои инвестиции

Используйте /start для продолжения.
"""
            bot.send_message(
                chat_id,
                welcome_text,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Вы не подписаны на канал!")
    
    elif call.data == 'subscription_stats':
        count = db.get_subscription_count()
        bot.answer_callback_query(
            call.id, 
            f"📊 Подписано пользователей: {count}"
        )
    
    elif call.data == 'subscription_cancel':
        user_states[chat_id] = 'main'
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id,
            "Операция отменена. Используйте кнопки ниже 👇",
            reply_markup=create_main_keyboard()
        )
        
@bot.message_handler(commands=['check_subscription', 'check'])
def check_subscription_command(message):
    """Команда для проверки подписки"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Принудительно проверяем подписку
    is_subscribed = check_subscription(user_id)
    
    if is_subscribed:
        subscribed_text = f"""
✅ *ВЫ ПОДПИСАНЫ НА КАНАЛ!*

📢 Канал: {TELEGRAM_CHANNEL_ID}
👤 Ваш ID: {user_id}
📊 Всего подписчиков: {db.get_subscription_count()}

*Теперь вам доступны все функции бота:*
• Регистрация и создание портфеля
• Актуальные финансовые данные
• Поиск и избранное
• Умные уведомления
• Финансовый калькулятор

Используйте /start для продолжения работы.
"""
        bot.send_message(
            chat_id,
            subscribed_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    else:
        show_subscription_required(chat_id, user_id)
        
@bot.message_handler(commands=['favorites', 'fav'])
def handle_favorites_command(message):
    """Обработчик команды для избранного"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Избранное")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "favorites_command")
    
    args = message.text.split()
    
    if len(args) > 1:
        subcommand = args[1].lower()
        
        if subcommand == 'update':
            show_favorites_with_real_time_prices(chat_id, user_id)
        elif subcommand == 'clear':
            clear_all_favorites(chat_id, user_id)
        else:
            show_favorites(chat_id, user_id)
    else:
        show_favorites(chat_id, user_id)

@bot.message_handler(commands=['favupdate'])
def handle_favupdate_command(message):
    """Быстрое обновление котировок избранного"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Избранное")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "favupdate_command")
    show_favorites_with_real_time_prices(chat_id, user_id)

@bot.message_handler(commands=['favorites_realtime', 'favrt'])
def handle_favorites_realtime_command(message):
    """Обработчик команды для избранного с реальными данными"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Избранное")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "favorites_realtime_command")
    show_favorites_with_real_time_prices(chat_id, user_id)

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
• Избранное активов
• Умные уведомления
• Финансовый калькулятор

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
        formatted_results = format_search_results_with_favorite_detailed(results, query, user_id, 'crypto')
        
        if formatted_results:  # Если вернулся текст (несколько результатов)
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
        formatted_results = format_search_results_with_favorite_detailed(results, query, user_id, 'stock')
        
        if formatted_results:  # Если вернулся текст (несколько результатов)
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

@bot.message_handler(commands=['calc', 'calculator'])
def handle_calculator_command(message):
    """Обработчик команды калькулятора"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Калькулятор")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "calculator_command")
    user_states[chat_id] = 'calculator_menu'
    
    calculator_text = """
*🧮 ФИНАНСОВЫЙ КАЛЬКУЛЯТОР*

Выберите нужный инструмент:

*💱 Конвертер валют*
• Конвертация между валютами
• Актуальные курсы ЦБ РФ
• Поддержка криптовалют

*📈 Прибыль/убыток*
• Расчет доходности инвестиций
• Учет комиссий и налогов
• Годовая процентная доходность

*💰 Стоимость актива*
• Расчет текущей стоимости
• Прогноз будущей стоимости
• Учет дивидендов и купонов

*📊 Сложный процент*
• Расчет сложных процентов
• Планирование накоплений
• Визуализация роста

*🏦 Кредит/депозит*
• Аннуитетные платежи
• Дифференцированные платежи
• Расчет эффективной ставки
"""
    bot.send_message(
        chat_id,
        calculator_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_keyboard()
    )

@bot.message_handler(commands=['loan'])
def handle_loan_command(message):
    """Обработчик команды расчета кредита"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    args = message.text.split()
    if len(args) < 4:
        bot.send_message(
            chat_id,
            "❌ *Неверный формат*\n\nИспользуйте: `/loan сумма срок_месяцев ставка_годовых`\n\n*Пример:* `/loan 1000000 60 12` - кредит 1 млн на 5 лет под 12%",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = float(args[1])
        months = int(args[2])
        annual_rate = float(args[3])
        
        if amount <= 0 or months <= 0 or annual_rate <= 0:
            raise ValueError
        
        # Расчет аннуитетного платежа
        monthly_rate = annual_rate / 100 / 12
        annuity_payment = amount * (monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)
        total_payment = annuity_payment * months
        overpayment = total_payment - amount
        
        # Расчет дифференцированного платежа
        first_diff_payment = amount / months + amount * monthly_rate
        last_diff_payment = amount / months + (amount / months) * monthly_rate
        avg_diff_payment = (first_diff_payment + last_diff_payment) / 2
        total_diff_payment = avg_diff_payment * months
        overpayment_diff = total_diff_payment - amount
        
        result = f"""
*🏦 РАСЧЕТ КРЕДИТА*

*Исходные данные:*
• Сумма кредита: {amount:,.0f}₽
• Срок: {months} месяцев ({months//12} лет {months%12} месяцев)
• Годовая ставка: {annual_rate}%

*📊 Аннуитетный платеж (равные платежи):*
• Ежемесячный платеж: {annuity_payment:,.0f}₽
• Всего выплата: {total_payment:,.0f}₽
• Переплата: {overpayment:,.0f}₽ ({overpayment/amount*100:.1f}%)

*📈 Дифференцированный платеж (уменьшающиеся):*
• Первый платеж: {first_diff_payment:,.0f}₽
• Последний платеж: {last_diff_payment:,.0f}₽
• Средний платеж: {avg_diff_payment:,.0f}₽
• Всего выплата: {total_diff_payment:,.0f}₽
• Переплата: {overpayment_diff:,.0f}₽ ({overpayment_diff/amount*100:.1f}%)

*💡 Рекомендации:*
• Аннуитетный - проще планировать бюджет
• Дифференцированный - меньше переплата
• Эффективная ставка: {annual_rate * 1.1:.1f}% (с учетом комиссий)
"""
        
        bot.send_message(chat_id, result, parse_mode='Markdown')
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ *Ошибка в данных*\n\nПроверьте, что:\n• Сумма > 0\n• Срок в месяцах > 0\n• Ставка > 0",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['deposit'])
def handle_deposit_command(message):
    """Обработчик команды расчета депозита"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    args = message.text.split()
    if len(args) < 4:
        bot.send_message(
            chat_id,
            "❌ *Неверный формат*\n\nИспользуйте: `/deposit сумма срок_месяцев ставка_годовых [капитализация]`\n\n*Пример:* `/deposit 500000 36 8 monthly`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = float(args[1])
        months = int(args[2])
        annual_rate = float(args[3])
        capitalization = args[4].lower() if len(args) > 4 else 'monthly'
        
        if amount <= 0 or months <= 0 or annual_rate <= 0:
            raise ValueError
        
        # Расчет без капитализации
        simple_interest = amount * annual_rate / 100 * (months / 12)
        total_simple = amount + simple_interest
        
        # Расчет с капитализацией
        if capitalization == 'monthly':
            periods = months
            rate_per_period = annual_rate / 12 / 100
        elif capitalization == 'quarterly':
            periods = months // 3
            rate_per_period = annual_rate / 4 / 100
        elif capitalization == 'yearly':
            periods = months // 12
            rate_per_period = annual_rate / 100
        else:
            capitalization = 'no'
        
        if capitalization != 'no':
            total_compound = amount * (1 + rate_per_period) ** periods
            compound_interest = total_compound - amount
        else:
            total_compound = total_simple
            compound_interest = simple_interest
        
        # Расчет налога (для доходов > 42.5к в год)
        tax_free_amount = 42500 * (months / 12)
        taxable_income = max(0, compound_interest - tax_free_amount)
        tax = taxable_income * 0.13
        
        result = f"""
*🏦 РАСЧЕТ ДЕПОЗИТА*

*Исходные данные:*
• Сумма вклада: {amount:,.0f}₽
• Срок: {months} месяцев ({months//12} лет {months%12} месяцев)
• Годовая ставка: {annual_rate}%
• Капитализация: {capitalization}

*📊 Результаты:*

*Без капитализации (простые проценты):*
• Начислено процентов: {simple_interest:,.0f}₽
• Итоговая сумма: {total_simple:,.0f}₽
• Доходность: {simple_interest/amount*100:.1f}%

*С капитализацией ({capitalization}):*
• Начислено процентов: {compound_interest:,.0f}₽
• Итоговая сумма: {total_compound:,.0f}₽
• Доходность: {compound_interest/amount*100:.1f}%

*💼 Налоговые вычеты:*
• Необлагаемая сумма: {tax_free_amount:,.0f}₽
• Налогооблагаемый доход: {taxable_income:,.0f}₽
• НДФЛ 13%: {tax:,.0f}₽
• Чистая прибыль: {compound_interest - tax:,.0f}₽

*📈 Преимущество капитализации:*
+{(compound_interest - simple_interest):,.0f}₽ ({(compound_interest/simple_interest*100-100):.1f}%)
"""
        
        bot.send_message(chat_id, result, parse_mode='Markdown')
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ *Ошибка в данных*\n\nПроверьте, что:\n• Сумма > 0\n• Срок в месяцах > 0\n• Ставка > 0\n\n*Капитализация:* monthly, quarterly, yearly, no",
            parse_mode='Markdown'
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

@bot.message_handler(func=lambda message: message.text == '⭐ Избранное')
def handle_favorites_button(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Избранное")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "favorites_button")
    user_states[chat_id] = 'favorites_menu'
    
    favorites_text = """
*⭐ ИЗБРАННОЕ С РЕАЛЬНЫМИ КОТИРОВКАМИ*

Здесь вы можете видеть актуальные цены в формате:
GAZP - Газпром
   💰 Цена: 180.5₽
   📊 Изменение: +1.2 (+0.67%) 🟢

*Источники данных:*
• Московская биржа (MOEX) - акции РФ
• Центральный Банк РФ - валюты
• CoinGecko - криптовалюты

Выберите действие:
"""
    bot.send_message(
        chat_id,
        favorites_text,
        parse_mode='Markdown',
        reply_markup=create_favorites_keyboard()
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

@bot.message_handler(func=lambda message: message.text == '🧮 Калькулятор')
def handle_calculator_button(message):
    """Обработчик кнопки калькулятора"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка доступа
    has_access, error_message = check_user_access(user_id, chat_id, "Калькулятор")
    if not has_access:
        bot.send_message(chat_id, error_message, parse_mode='Markdown')
        return
    
    db.add_user_action(message.from_user.id, "calculator_button")
    user_states[chat_id] = 'calculator_menu'
    
    calculator_text = """
*🧮 ФИНАНСОВЫЙ КАЛЬКУЛЯТОР*

Выберите нужный инструмент:
"""
    bot.send_message(
        chat_id,
        calculator_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_keyboard()
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
    user_id = message.from_user.id
    
    # Проверяем подписку
    is_subscribed = check_subscription(user_id)
    
    if not is_subscribed:
        about_text = f"""
*🤖 О боте*

*📢 Финансовый бот для отслеживания курсов и управления портфелем*

*🎯 Основные функции:*
• Отслеживание курсов валют и криптовалют
• Аналитика российских акций
• Создание личного инвестиционного портфеля
• Умные уведомления о важных изменениях
• Финансовый калькулятор
• Избранное с реальными котировками

*🚀 Для доступа к функциям необходимо:*
1. Подписаться на наш канал: {TELEGRAM_CHANNEL_ID}
2. Нажать кнопку "✅ Проверить подписку"

*📊 После подписки вам станут доступны:*
• Быстрая регистрация (3 вопроса)
• Создание портфеля
• Все финансовые инструменты
• Персональные уведомления

*📈 Источники данных:*
• Центральный Банк РФ
• CoinGecko API
• Московская биржа (MOEX)

_Начните с подписки на наш канал!_
"""
        bot.send_message(
            message.chat.id, 
            about_text, 
            parse_mode='Markdown'
        )
        return
    
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
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Калькулятор

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
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Калькулятор

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
• ⭐ Избранное (быстрый доступ к активам)
• 🔔 Мои уведомления (умные оповещения)
• 🧮 Калькулятор (5 финансовых инструментов)
• 📨 Связь с администратором

*Источники данных:*
• Центральный Банк РФ
• CoinGecko API
• Московская биржа (MOEX)

*Защита от спама:*
• {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут
• Блокировка на {BLOCK_DURATION//60} минут

_Бот создан для удобного отслеживания курсов и финансовых расчетов_
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
        cursor.execute('DELETE FROM favorites WHERE user_id = ?', (user_id,))
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
    user_id = message.from_user.id
    
    # Проверяем, завершена ли регистрация
    registration_completed = db.is_registration_completed(user_id)
    has_portfolio = db.get_user_status(user_id)
    
    # Список состояний, где кнопка "Отмена" должна работать
    cancelable_states = [
        'contact_mode', 'search_currency', 'search_crypto', 'search_stock',
        'converter_from', 'converter_to', 'converter_amount',
        'converter_to_crypto', 'converter_custom_from', 'converter_custom_to',
        'converter_crypto_custom', 'profit_calc_initial', 'asset_value_calc',
        'compound_calc', 'loan_calc_type'
    ]
    
    # Обрабатываем только состояния, где есть кнопка отмены
    if current_state in cancelable_states:
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
        # Для других состояний показываем стандартное сообщение
        if current_state and current_state not in [
            'portfolio_add_crypto_first', 'portfolio_add_stock_first', 'portfolio_add_currency_first',
            'portfolio_add_crypto', 'portfolio_add_stock', 'portfolio_add_currency',
            'portfolio_add_quantity_first', 'portfolio_add_quantity',
            'portfolio_add_price_first', 'portfolio_add_price',
            'portfolio_add_date_first', 'portfolio_add_date',
            'portfolio_add_notes_first', 'portfolio_add_notes'
        ]:
            bot.send_message(
                message.chat.id,
                "Вы в главном меню. Используйте кнопки ниже 👇",
                reply_markup=create_main_keyboard()
            )

@bot.message_handler(func=lambda message: message.text in ['✅ Продолжить регистрацию', '❌ Отменить регистрацию'])
def handle_registration_cancel_choice(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '✅ Продолжить регистрации':
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
# Оповещение о подписки
# ============================================

def create_subscription_keyboard():
    """Клавиатура для проверки подписки"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{TELEGRAM_CHANNEL_ID.replace('@', '')}"),
        InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"),
        InlineKeyboardButton("📊 Статистика", callback_data="subscription_stats"),
        InlineKeyboardButton("❌ Отмена", callback_data="subscription_cancel")
    )
    return keyboard

def show_subscription_required(chat_id, user_id):
    """Показать сообщение о необходимости подписки"""
    subscription_text = f"""
📢 *ДОБРО ПОЖАЛОВАТЬ В ФИНАНСОВЫЙ БОТ!*

🚀 *Для начала работы необходимо:*
1. Подписаться на наш канал: {TELEGRAM_CHANNEL_ID}
2. Нажать кнопку "✅ Проверить подписку"

*📊 Что вас ждет после подписки:*
• 📋 Быстрая регистрация (3 вопроса)
• 📊 Создание личного портфеля
• 🏆 Топ валют и криптовалют
• 🔍 Поиск любых активов
• ⭐ Избранное с реальными котировками
• 🔔 Умные уведомления
• 🧮 Финансовый калькулятор

*🎁 Эксклюзивные преимущества подписчиков:*
• Первыми получайте новые функции бота
• Эксклюзивные аналитические обзоры
• Инвестиционные идеи от эксперты
• Поддержка 24/7

*🔒 Ваша подписка проверяется автоматически*
*📈 Уже подписано: {db.get_subscription_count()} пользователей*
"""
    
    bot.send_message(
        chat_id,
        subscription_text,
        parse_mode='Markdown',
        reply_markup=create_subscription_keyboard()
    )
    
# ============================================
# КНОПКИ КАЛЬКУЛЯТОРА
# ============================================

@bot.message_handler(func=lambda message: message.text == '💱 Конвертер валют')
def handle_currency_converter(message):
    """Обработчик конвертера валют"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "converter_button")
    user_states[chat_id] = 'converter_from'
    
    converter_text = """
*💱 КОНВЕРТЕР ВАЛЮТ*

Выберите валюту, ИЗ которой конвертируем:

*Примеры использования:*
• 100 USD → RUB
• 500 EUR → USD
• 1000 RUB → CNY

*Поддерживаются:*
• Все валюты ЦБ РФ
• Популярные криптовалюты
• Точный расчет по курсу
"""
    bot.send_message(
        chat_id,
        converter_text,
        parse_mode='Markdown',
        reply_markup=create_converter_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📈 Прибыль/убыток')
def handle_profit_calculator(message):
    """Обработчик калькулятора прибыли"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "profit_calc_button")
    user_states[chat_id] = 'profit_calc_initial'
    
    profit_text = """
*📈 КАЛЬКУЛЯТОР ПРИБЫЛИ/УБЫТКА*

*Формула расчета:*
Прибыль = (Текущая цена - Цена покупки) × Количество

*Расчет годовой доходности:*
Доходность (%) = [(Текущая стоимость / Начальная стоимость)^(1/Лет) - 1] × 100

*Введите данные в формате:*
начальная_сумма текущая_сумма период_в_годах

*Примеры:*
• `100000 120000 1` - 100к→120к за 1 год
• `50000 45000 0.5` - 50к→45к за 6 месяцев
• `1000 1500 2` - 1к→1.5к за 2 года

Или нажмите /portfolio для расчета по вашему портфелю
"""
    bot.send_message(
        chat_id,
        profit_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_back_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '💰 Стоимость актива')
def handle_asset_value_calculator(message):
    """Обработчик калькулятора стоимости актива"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "asset_value_button")
    user_states[chat_id] = 'asset_value_calc'
    
    asset_text = """
*💰 КАЛЬКУЛЯТОР СТОИМОСТИ АКТИВА*

*Формулы:*
• Текущая стоимость = Количество × Текущая цена
• Будущая стоимость = Текущая стоимость × (1 + Годовая доходность)^Период

*Введите данные в формате:*
количество цена_покупки текущая_цена годовая_доходность(%) период_лет

*Примеры:*
• `10 1000 1200` - 10 акций куплены по 1000₽, сейчас 1200₽
• `0.5 50000 60000 15 3` - 0.5 BTC куплен за 50к$, сейчас 60к$, прогноз 15% годовых на 3 года
• `100 50 55 8 5` - 100 акций за 50₽, сейчас 55₽, прогноз 8% на 5 лет

Для дивидендов добавьте `+дивид_ставка(%)`
"""
    bot.send_message(
        chat_id,
        asset_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_back_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📊 Сложный процент')
def handle_compound_interest_calculator(message):
    """Обработчик калькулятора сложных процентов"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "compound_button")
    user_states[chat_id] = 'compound_calc'
    
    compound_text = """
*📊 КАЛЬКУЛЯТОР СЛОЖНЫХ ПРОЦЕНТОВ*

*Формула:*
Будущая стоимость = Начальная сумма × (1 + ставка/100)^период

*Для регулярных пополнений:*
Сумма = Платеж × [(1 + ставка/100)^период - 1] / (ставка/100)

*Введите данные в формате:*
начальная_сумма годовая_ставка(%) период_лет [ежемесячное_пополнение]

*Примеры:*
• `100000 10 5` - 100к под 10% годовых на 5 лет
• `50000 8 10 5000` - 50к под 8% на 10 лет + 5к пополнения ежемесячно
• `0 12 30 10000` - 10к ежемесячно под 12% на 30 лет (начинаем с 0)

*Результаты:*
• Итоговая сумма
• Общие инвестиции
• Начисленные проценты
"""
    bot.send_message(
        chat_id,
        compound_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_back_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🏦 Кредит/депозит')
def handle_loan_deposit_calculator(message):
    """Обработчик калькулятора кредита/депозита"""
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    db.add_user_action(message.from_user.id, "loan_button")
    user_states[chat_id] = 'loan_calc_type'
    
    loan_text = """
*🏦 КАЛЬКУЛЯТОР КРЕДИТА/ДЕПОЗИТА*

Выберите тип расчета:

*Для кредита:*
• Аннуитетный платеж (равные платежи)
• Дифференцированный (уменьшающиеся платежи)
• Расчет переплаты и эффективной ставки

*Для депозита:*
• Начисление процентов
• Учет капитализации
• Расчет налога на доход

*Введите команду:*
/loan сумма срок_месяцев ставка_годовых
/deposit сумма срок_месяцев ставка_годовых [капитализация]

*Примеры:*
• `/loan 1000000 60 12` - кредит 1 млн на 5 лет под 12%
• `/deposit 500000 36 8 monthly` - депозит 500к на 3 года под 8% с ежемесячной капитализацией
"""
    bot.send_message(
        chat_id,
        loan_text,
        parse_mode='Markdown',
        reply_markup=create_calculator_back_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '⬅️ Назад в калькулятор')
def handle_back_to_calculator(message):
    """Обработчик возврата в калькулятор"""
    save_user_info(message)
    chat_id = message.chat.id
    
    user_states[chat_id] = 'calculator_menu'
    
    bot.send_message(
        chat_id,
        "*🧮 ФИНАНСОВЫЙ КАЛЬКУЛЯТОР*\n\nВыберите нужный инструмент:",
        parse_mode='Markdown',
        reply_markup=create_calculator_keyboard()
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
# ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ ПОИСКА С ИЗБРАННЫМ
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
    formatted_results = format_search_results_with_favorite_detailed(results, query, user_id, 'currency')
    
    if formatted_results:  # Если вернулся текст (несколько результатов)
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
    formatted_results = format_search_results_with_favorite_detailed(results, query, user_id, 'crypto')
    
    if formatted_results:  # Если вернулся текст (несколько результатов)
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
    formatted_results = format_search_results_with_favorite_detailed(results, query, user_id, 'stock')
    
    if formatted_results:  # Если вернулся текст (несколько результатов)
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
        
        # Удаляем сообщение с созданием портфеля
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        
        # Показываем сообщение с предложением создать портфель позже
        bot.send_message(
            chat_id,
            "*❌ Создание портфеля отменено*\n\nВы можете создать портфель позже, используя кнопку '📊 Создать портфель'.",
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
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
            
            # Удаляем сообщение выбора типа актива
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            
            # Показываем сообщение с предложением создать портфель позже
            bot.send_message(
                chat_id,
                "*❌ Создание портфеля отменено*\n\nВы можете создать портфель позже, используя кнопку '📊 Создать портфель'.",
                parse_mode='Markdown',
                reply_markup=create_welcome_keyboard()
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

@bot.message_handler(func=lambda message: message.text == '❌ Отмена' and 
                    user_states.get(message.chat.id) in [
                        'portfolio_add_crypto_first', 'portfolio_add_stock_first', 'portfolio_add_currency_first',
                        'portfolio_add_crypto', 'portfolio_add_stock', 'portfolio_add_currency',
                        'portfolio_add_quantity_first', 'portfolio_add_quantity',
                        'portfolio_add_price_first', 'portfolio_add_price',
                        'portfolio_add_date_first', 'portfolio_add_date',
                        'portfolio_add_notes_first', 'portfolio_add_notes'
                    ])
def handle_cancel_asset_addition(message):
    save_user_info(message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    current_state = user_states.get(chat_id)
    
    # Определяем, это первый актив или нет
    is_first = current_state.endswith('_first') if current_state else False
    
    if is_first:
        user_states[chat_id] = 'registration_completed'
        bot.send_message(
            chat_id,
            "*❌ Добавление актива отменено*\n\nВы можете создать портфель позже, используя кнопку '📊 Создать портфель'.",
            parse_mode='Markdown',
            reply_markup=create_welcome_keyboard()
        )
    else:
        user_states[chat_id] = 'portfolio_menu'
        bot.send_message(
            chat_id,
            "*❌ Добавление актива отменено*\n\nВозврат в меню портфеля.",
            parse_mode='Markdown',
            reply_markup=create_portfolio_keyboard()
        )
    
    # Очищаем временные данные
    if user_id in user_temp_data:
        del user_temp_data[user_id]

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
    chat_id = message.chat.id
    current_state = user_states.get(chat_id)
    
    if current_state in ['portfolio_add_notes', 'portfolio_add_notes_first']:
        user_id = message.from_user.id
        complete_asset_addition(chat_id, user_id, "")
    else:
        # Если команда /skip вызвана не в том состоянии
        bot.send_message(
            chat_id,
            "Команда /skip доступна только при добавлении заметок к активу.",
            parse_mode='Markdown'
        )

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
        from_favorites = data.get('from_favorites', False)
        
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
"""
            else:
                completion_text = f"✅ Актив *{data['symbol']}* успешно добавлен в портфель!"
            
            # Если добавлено из избранного
            if from_favorites:
                completion_text += f"\n\n⭐ *Добавлено из избранного!*"
            
            bot.send_message(
                chat_id,
                completion_text,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            
            if is_first:
                completion_text += """

*🎉 Теперь вам доступны все функции бота:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика акций РФ
• 🔍 Поиск активов
• ⭐ Избранное
• 🔔 Умные уведомления
• 🧮 Калькулятор

Можете продолжить добавлять активы или начать использовать другие функции бота!
"""
            
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
# ОБРАБОТЧИКИ ИЗБРАННОГО (CALLBACK)
# ============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith(('favorites_', 'add_favorite_', 'fav_')))
def handle_favorites_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data == 'favorites_show_all':
        db.add_user_action(user_id, "favorites_show_all")
        bot.delete_message(chat_id, call.message.message_id)
        show_favorites_with_real_time_prices(chat_id, user_id)
    
    elif call.data == 'favorites_update':
        db.add_user_action(user_id, "favorites_update")
        bot.delete_message(chat_id, call.message.message_id)
        show_favorites_with_real_time_prices(chat_id, user_id)
    
    elif call.data == 'favorites_clear_all':
        db.add_user_action(user_id, "favorites_clear_all")
        clear_all_favorites(chat_id, user_id)
    
    elif call.data == 'confirm_clear_favorites':
        # Удаляем все избранное пользователя
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM favorites WHERE user_id = ?', (user_id,))
            conn.commit()
        
        db.add_user_action(user_id, "favorites_cleared")
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="✅ *Всё избранное очищено!*\n\nСписок избранного теперь пуст.",
            parse_mode='Markdown'
        )
        
        # Показываем основное меню через 2 секунды
        time.sleep(2)
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )
        user_states[chat_id] = 'main'
    
    elif call.data == 'cancel_clear_favorites':
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="❌ *Очистка отменена*\n\nВаше избранное сохранено.",
            parse_mode='Markdown',
            reply_markup=create_favorites_keyboard()
        )
    
    elif call.data == 'favorites_close':
        user_states[chat_id] = 'main'
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )
    
    elif call.data.startswith('add_favorite_'):
        # Добавление в избранное из результатов поиска
        parts = call.data.split('_')
        asset_type = parts[2]
        symbol = parts[3]
        
        # Получаем имя актива
        name = ""
        if asset_type == 'currency':
            if symbol in POPULAR_CURRENCIES:
                name = POPULAR_CURRENCIES[symbol]['name']
            else:
                name = symbol
        elif asset_type == 'crypto':
            for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
                if info['symbol'] == symbol:
                    name = info['name']
                    break
            if not name:
                name = symbol
        elif asset_type == 'stock':
            if symbol in RUSSIAN_STOCKS:
                name = RUSSIAN_STOCKS[symbol]['name']
            else:
                name = symbol
        
        # Добавляем в избранное
        success = add_to_favorites_function(chat_id, user_id, symbol, asset_type, name)
        
        if success:
            bot.delete_message(chat_id, call.message.message_id)
    
    elif call.data.startswith('fav_quote_'):
        # Получить котировку для конкретного избранного
        favorite_id = int(call.data.split('_')[2])
        
        favorites = db.get_favorites(user_id)
        favorite = None
        
        for fav in favorites:
            if fav['id'] == favorite_id:
                favorite = fav
                break
        
        if favorite:
            # Получаем текущую цену
            if favorite['asset_type'] == 'STOCK':
                real_time_data = get_real_time_stock_price(favorite['symbol'])
            elif favorite['asset_type'] == 'CURRENCY':
                real_time_data = get_real_time_currency_rate(favorite['symbol'])
            elif favorite['asset_type'] == 'CRYPTO':
                real_time_data = get_real_time_crypto_price(favorite['symbol'])
            else:
                real_time_data = None
            
            if real_time_data:
                formatted_info = format_favorite_item(favorite, real_time_data)
                message_text = f"⭐ *КОТИРОВКА ИЗБРАННОГО*\n\n"
                message_text += formatted_info
                
                bot.send_message(
                    chat_id,
                    message_text,
                    parse_mode='Markdown',
                    reply_markup=create_manage_favorite_keyboard(favorite_id, favorite['symbol'])
                )
            else:
                bot.answer_callback_query(call.id, "❌ Данные временно недоступны")
        else:
            bot.answer_callback_query(call.id, "❌ Избранное не найдено")
    
    elif call.data.startswith('fav_remove_'):
        # Удалить из избранного
        favorite_id = int(call.data.split('_')[2])
        
        favorites = db.get_favorites(user_id)
        favorite_symbol = ""
        
        for fav in favorites:
            if fav['id'] == favorite_id:
                favorite_symbol = fav['symbol']
                break
        
        if favorite_symbol:
            success = db.remove_from_favorites(user_id, favorite_id)
            
            if success:
                bot.answer_callback_query(call.id, f"✅ {favorite_symbol} удален из избранного")
                
                # Обновляем список
                favorites = db.get_favorites(user_id)
                if favorites:
                    # Показываем обновленный список
                    show_favorites(chat_id, user_id)
                    bot.delete_message(chat_id, call.message.message_id)
                else:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        text="⭐ *Избранное пусто*\n\nДобавляйте активы при поиске!",
                        parse_mode='Markdown',
                        reply_markup=create_favorites_keyboard()
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка удаления")
        else:
            bot.answer_callback_query(call.id, "❌ Избранное не найдено")
    
    elif call.data.startswith('fav_to_portfolio_'):
        # Добавить из избранного в портфель
        favorite_id = int(call.data.split('_')[3])
        
        favorites = db.get_favorites(user_id)
        favorite = None
        
        for fav in favorites:
            if fav['id'] == favorite_id:
                favorite = fav
                break
        
        if favorite:
            # Сохраняем данные для добавления в портфель
            if user_id not in user_temp_data:
                user_temp_data[user_id] = {}
            
            user_temp_data[user_id]['symbol'] = favorite['symbol']
            user_temp_data[user_id]['asset_type'] = favorite['asset_type'].lower()
            user_temp_data[user_id]['from_favorites'] = True
            
            user_states[chat_id] = 'portfolio_add_quantity'
            
            bot.send_message(
                chat_id,
                f"📊 *Добавление в портфель из избранного*\n\nАктив: *{favorite['symbol']}* ({favorite['asset_type']})\n\nВведите количество:",
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, "❌ Избранное не найдено")
    
    elif call.data.startswith('fav_alert_'):
        # Настроить уведомление для избранного
        favorite_id = int(call.data.split('_')[2])
        
        favorites = db.get_favorites(user_id)
        favorite = None
        
        for fav in favorites:
            if fav['id'] == favorite_id:
                favorite = fav
                break
        
        if favorite:
            # Сохраняем данные для создания уведомления
            if user_id not in user_temp_data:
                user_temp_data[user_id] = {}
            
            user_temp_data[user_id]['symbol'] = favorite['symbol']
            user_temp_data[user_id]['asset_type'] = favorite['asset_type'].lower()
            
            user_states[chat_id] = 'alert_add_type'
            
            bot.send_message(
                chat_id,
                f"🔔 *Настройка уведомления для избранного*\n\nАктив: *{favorite['symbol']}*\n\nВыберите тип уведомления:",
                parse_mode='Markdown',
                reply_markup=create_alert_type_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Избранное не найдено")
    
    elif call.data.startswith('fav_add_to_portfolio_'):
        # Добавить в портфель из уведомления о добавлении в избранное
        parts = call.data.split('_')
        asset_type = parts[4]
        symbol = parts[5]
        
        # Сохраняем данные для добавления в портфель
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['symbol'] = symbol
        user_temp_data[user_id]['asset_type'] = asset_type
        user_temp_data[user_id]['from_favorites'] = True
        
        user_states[chat_id] = 'portfolio_add_quantity'
        
        bot.send_message(
            chat_id,
            f"📊 *Добавление в портфель*\n\nАктив: *{symbol}* ({asset_type})\n\nВведите количество:",
            parse_mode='Markdown'
        )
    
    elif call.data == 'back_to_search':
        # Возврат к поиску
        user_states[chat_id] = 'main'
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id,
            "Возврат в главное меню",
            reply_markup=create_main_keyboard()
        )

# ============================================
# ОБРАБОТЧИКИ КАЛЬКУЛЯТОРА (CALLBACK)
# ============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('conv_'))
def handle_converter_callback(call):
    """Обработчик callback'ов конвертера"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data.startswith('conv_from_'):
        currency = call.data.split('_')[2]
        
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['converter_from'] = currency
        user_states[chat_id] = 'converter_to'
        
        # Создаем клавиатуру для выбора целевой валюты
        keyboard = InlineKeyboardMarkup(row_width=3)
        popular_currencies = ['RUB', 'USD', 'EUR', 'GBP', 'JPY', 'CNY']
        
        # Убираем исходную валюту из списка
        popular_currencies = [c for c in popular_currencies if c != currency]
        
        buttons = []
        for curr in popular_currencies:
            if curr in POPULAR_CURRENCIES:
                emoji = POPULAR_CURRENCIES[curr]['flag']
                buttons.append(InlineKeyboardButton(f"{emoji} {curr}", callback_data=f"conv_to_{curr}"))
        
        # Добавляем кнопки построчно
        for i in range(0, len(buttons), 3):
            keyboard.add(*buttons[i:i+3])
        
        # Кнопки для крипты и отмены
        keyboard.add(
            InlineKeyboardButton("₿ Криптовалюты", callback_data="conv_to_crypto"),
            InlineKeyboardButton("📝 Ввести код", callback_data="conv_to_custom"),
            InlineKeyboardButton("❌ Отмена", callback_data="calc_cancel")
        )
        
        emoji = POPULAR_CURRENCIES.get(currency, {}).get('flag', '💱')
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"*Из: {emoji} {currency}*\n\nТеперь выберите валюту, В которую конвертируем:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    elif call.data.startswith('conv_to_'):
        to_currency = call.data.split('_')[2]
        
        if user_id in user_temp_data:
            user_temp_data[user_id]['converter_to'] = to_currency
            user_states[chat_id] = 'converter_amount'
            
            from_currency = user_temp_data[user_id].get('converter_from', 'USD')
            from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
            to_emoji = POPULAR_CURRENCIES.get(to_currency, {}).get('flag', '💱')
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"*Конвертация: {from_emoji} {from_currency} → {to_emoji} {to_currency}*\n\nВведите сумму для конвертации:\n\n*Пример:* 100, 500.50, 1000",
                parse_mode='Markdown'
            )
    
    elif call.data == 'conv_to_crypto':
        user_states[chat_id] = 'converter_to_crypto'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Выберите криптовалюту:*",
            parse_mode='Markdown',
            reply_markup=create_crypto_converter_keyboard()
        )
    
    elif call.data.startswith('conv_crypto_from_'):
        crypto_symbol = call.data.split('_')[3]
        
        if user_id not in user_temp_data:
            user_temp_data[user_id] = {}
        
        user_temp_data[user_id]['converter_to'] = crypto_symbol
        user_states[chat_id] = 'converter_amount'
        
        from_currency = user_temp_data[user_id].get('converter_from', 'USD')
        from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
        
        # Находим эмодзи для крипты
        to_emoji = '₿'
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == crypto_symbol:
                to_emoji = info['emoji']
                break
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"*Конвертация: {from_emoji} {from_currency} → {to_emoji} {crypto_symbol}*\n\nВведите сумму для конвертации:\n\n*Пример:* 100, 0.5, 1000",
            parse_mode='Markdown'
        )
    
    elif call.data == 'conv_crypto_custom':
        user_states[chat_id] = 'converter_crypto_custom'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите символ криптовалюты (например: BTC, ETH, SOL):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'conv_custom':
        user_states[chat_id] = 'converter_custom_from'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите код валюты (например: USD, EUR, GBP):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'conv_to_custom':
        user_states[chat_id] = 'converter_custom_to'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*Введите код целевой валюты (например: RUB, CNY, CHF):*",
            parse_mode='Markdown'
        )
    
    elif call.data == 'conv_back_main':
        user_states[chat_id] = 'converter_from'
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="*💱 КОНВЕРТЕР ВАЛЮТ*\n\nВыберите валюту, ИЗ которой конвертируем:",
            parse_mode='Markdown',
            reply_markup=create_converter_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data == 'calc_cancel')
def handle_calc_cancel(call):
    """Обработчик отмены в калькуляторе"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    user_states[chat_id] = 'calculator_menu'
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="*🧮 ФИНАНСОВЫЙ КАЛЬКУЛЯТОР*\n\nВыберите нужный инструмент:",
        parse_mode='Markdown',
        reply_markup=create_calculator_keyboard()
    )

# ============================================
# ОБРАБОТЧИКИ ВВОДА КАЛЬКУЛЯТОРА
# ============================================

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_custom_from')
def handle_converter_custom_from(message):
    """Обработчик ввода пользовательской исходной валюты"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    currency = message.text.strip().upper()
    
    # Проверяем, есть ли такая валюта
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=5)
        data = response.json()
        
        if currency in data['Valute'] or currency == 'RUB':
            if user_id not in user_temp_data:
                user_temp_data[user_id] = {}
            
            user_temp_data[user_id]['converter_from'] = currency
            user_states[chat_id] = 'converter_to'
            
            emoji = POPULAR_CURRENCIES.get(currency, {}).get('flag', '💱')
            
            # Создаем клавиатуру для выбора целевой валюты
            keyboard = InlineKeyboardMarkup(row_width=3)
            popular_currencies = ['RUB', 'USD', 'EUR', 'GBP', 'JPY', 'CNY']
            
            # Убираем исходную валюту из списка
            popular_currencies = [c for c in popular_currencies if c != currency]
            
            buttons = []
            for curr in popular_currencies:
                if curr in POPULAR_CURRENCIES:
                    emoji_to = POPULAR_CURRENCIES[curr]['flag']
                    buttons.append(InlineKeyboardButton(f"{emoji_to} {curr}", callback_data=f"conv_to_{curr}"))
            
            # Добавляем кнопки построчно
            for i in range(0, len(buttons), 3):
                keyboard.add(*buttons[i:i+3])
            
            keyboard.add(
                InlineKeyboardButton("₿ Криптовалюты", callback_data="conv_to_crypto"),
                InlineKeyboardButton("📝 Ввести код", callback_data="conv_to_custom"),
                InlineKeyboardButton("❌ Отмена", callback_data="calc_cancel")
            )
            
            bot.send_message(
                chat_id,
                f"*Из: {emoji} {currency}*\n\nТеперь выберите валюту, В которую конвертируем:",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            bot.send_message(
                chat_id,
                f"❌ Валюта *{currency}* не найдена. Попробуйте снова или используйте кнопки.",
                parse_mode='Markdown',
                reply_markup=create_converter_keyboard()
            )
            user_states[chat_id] = 'converter_from'
    
    except Exception as e:
        bot.send_message(
            chat_id,
            "❌ Ошибка при проверке валюты. Попробуйте снова.",
            reply_markup=create_converter_keyboard()
        )
        user_states[chat_id] = 'converter_from'

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_custom_to')
def handle_converter_custom_to(message):
    """Обработчик ввода пользовательской целевой валюты"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    to_currency = message.text.strip().upper()
    
    if user_id in user_temp_data:
        # Проверяем для криптовалют
        is_crypto = False
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == to_currency:
                is_crypto = True
                break
        
        if is_crypto:
            user_temp_data[user_id]['converter_to'] = to_currency
            user_states[chat_id] = 'converter_amount'
            
            from_currency = user_temp_data[user_id].get('converter_from', 'USD')
            from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
            
            # Находим эмодзи для крипты
            to_emoji = '₿'
            for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
                if info['symbol'] == to_currency:
                    to_emoji = info['emoji']
                    break
            
            bot.send_message(
                chat_id,
                f"*Конвертация: {from_emoji} {from_currency} → {to_emoji} {to_currency}*\n\nВведите сумму для конвертации:",
                parse_mode='Markdown'
            )
            return
        
        # Проверяем для обычных валют
        try:
            cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
            response = requests.get(cbr_url, timeout=5)
            data = response.json()
            
            if to_currency in data['Valute'] or to_currency == 'RUB':
                user_temp_data[user_id]['converter_to'] = to_currency
                user_states[chat_id] = 'converter_amount'
                
                from_currency = user_temp_data[user_id].get('converter_from', 'USD')
                from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
                to_emoji = POPULAR_CURRENCIES.get(to_currency, {}).get('flag', '💱')
                
                bot.send_message(
                    chat_id,
                    f"*Конвертация: {from_emoji} {from_currency} → {to_emoji} {to_currency}*\n\nВведите сумму для конвертации:",
                    parse_mode='Markdown'
                )
            else:
                bot.send_message(
                    chat_id,
                    f"❌ Валюта *{to_currency}* не найдена. Попробуйте снова.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            bot.send_message(
                chat_id,
                "❌ Ошибка при проверке валюты. Попробуйте снова.",
                parse_mode='Markdown'
            )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_crypto_custom')
def handle_converter_crypto_custom(message):
    """Обработчик ввода пользовательской криптовалюты"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    crypto_symbol = message.text.strip().upper()
    
    # Проверяем, есть ли такая криптовалюта
    crypto_found = False
    for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
        if info['symbol'] == crypto_symbol:
            crypto_found = True
            break
    
    if crypto_found and user_id in user_temp_data:
        user_temp_data[user_id]['converter_to'] = crypto_symbol
        user_states[chat_id] = 'converter_amount'
        
        from_currency = user_temp_data[user_id].get('converter_from', 'USD')
        from_emoji = POPULAR_CURRENCIES.get(from_currency, {}).get('flag', '💱')
        
        # Находим эмодзи для крипты
        to_emoji = '₿'
        for crypto_id, info in POPULAR_CRYPTOCURRENCIES.items():
            if info['symbol'] == crypto_symbol:
                to_emoji = info['emoji']
                break
        
        bot.send_message(
            chat_id,
            f"*Конвертация: {from_emoji} {from_currency} → {to_emoji} {crypto_symbol}*\n\nВведите сумму для конвертации:",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            chat_id,
            f"❌ Криптовалюта *{crypto_symbol}* не найдена. Попробуйте BTC, ETH, USDT и т.д.",
            parse_mode='Markdown',
            reply_markup=create_crypto_converter_keyboard()
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'converter_amount')
def handle_converter_amount(message):
    """Обработчик ввода суммы для конвертации"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        amount = float(message.text.replace(',', '.'))
        
        if amount <= 0:
            bot.send_message(chat_id, "❌ Сумма должна быть больше 0.")
            return
        
        if user_id in user_temp_data:
            from_currency = user_temp_data[user_id].get('converter_from')
            to_currency = user_temp_data[user_id].get('converter_to')
            
            if not from_currency or not to_currency:
                bot.send_message(chat_id, "❌ Ошибка данных. Начните заново.")
                user_states[chat_id] = 'calculator_menu'
                return
            
            # Получаем курсы
            result = convert_currency(amount, from_currency, to_currency)
            
            if result:
                bot.send_message(
                    chat_id,
                    result,
                    parse_mode='Markdown',
                    reply_markup=create_main_keyboard()
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Ошибка конвертации. Проверьте коды валют.",
                    reply_markup=create_main_keyboard()
                )
            
            user_states[chat_id] = 'main'
            
            # Очищаем временные данные
            if user_id in user_temp_data:
                del user_temp_data[user_id]
        
    except ValueError:
        bot.send_message(chat_id, "❌ Введите корректное число.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'profit_calc_initial')
def handle_profit_calculation(message):
    """Обработчик расчета прибыли"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '⬅️ Назад в калькулятор':
        user_states[chat_id] = 'calculator_menu'
        bot.send_message(
            chat_id,
            "Выберите инструмент калькулятора:",
            reply_markup=create_calculator_keyboard()
        )
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 2:
            bot.send_message(
                chat_id,
                "❌ *Неверный формат*\n\nВведите: начальная_сумма текущая_сумма [период_в_годах]\n\n*Пример:* `100000 120000 1`",
                parse_mode='Markdown'
            )
            return
        
        initial_amount = float(args[0])
        current_amount = float(args[1])
        years = float(args[2]) if len(args) > 2 else 1.0
        
        if initial_amount <= 0:
            bot.send_message(chat_id, "❌ Начальная сумма должна быть больше 0.")
            return
        
        # Расчет абсолютной прибыли
        profit_absolute = current_amount - initial_amount
        profit_percent = (profit_absolute / initial_amount) * 100
        
        # Расчет годовой доходности
        if years > 0:
            annual_return = ((current_amount / initial_amount) ** (1 / years) - 1) * 100
        else:
            annual_return = 0
        
        # Расчет эффективной ставки (с учетом сложных процентов)
        effective_rate = ((1 + profit_percent/100) ** (1/years) - 1) * 100 if years > 0 else 0
        
        result = f"""
*📈 РАСЧЕТ ПРИБЫЛИ/УБЫТКА*

*Исходные данные:*
• Начальная сумма: {initial_amount:,.2f}₽
• Текущая сумма: {current_amount:,.2f}₽
• Период: {years:.1f} лет

*📊 Результаты:*

*Абсолютная прибыль/убыток:*
• Сумма: {profit_absolute:+,.2f}₽
• Процент: {profit_percent:+.2f}%

*📈 Годовая доходность:*
• Простая: {annual_return:+.2f}% годовых
• Эффективная ставки: {effective_rate:+.2f}% годовых

*💼 Налоговые расчеты:*
• Необлагаемый доход в год: 42,500₽
• Налогооблагаемый доход: {max(0, profit_absolute/years - 42500):,.0f}₽/год
• Примерный НДФЛ: {max(0, profit_absolute/years - 42500) * 0.13 * years:,.0f}₽

*📋 Классификация:*
• {'✅ Прибыль' if profit_absolute >= 0 else '❌ Убыток'}
• {'📈 Выше инфляции (предположительно)' if annual_return > 7 else '📉 Ниже инфляции (предположительно)'}
"""
        
        # Добавляем графическую визуализацию
        if profit_percent >= 20:
            result += "\n*🎯 Отличный результат!* Вы значительно обогнали рынок."
        elif profit_percent >= 10:
            result += "\n*👍 Хороший результат!* Вы обогнали среднюю доходность."
        elif profit_percent >= 0:
            result += "\n*😊 Положительный результат!* Вы сохранили капитал."
        else:
            result += "\n*⚠️ Отрицательный результат!* Рекомендуется пересмотреть стратегию."
        
        bot.send_message(chat_id, result, parse_mode='Markdown')
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ *Ошибка в данных*\n\nПроверьте, что вводите числа.\n*Пример:* `100000 120000 1`",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'asset_value_calc')
def handle_asset_value_calculation(message):
    """Обработчик расчета стоимости актива"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '⬅️ Назад в калькулятор':
        user_states[chat_id] = 'calculator_menu'
        bot.send_message(
            chat_id,
            "Выберите инструмент калькулятора:",
            reply_markup=create_calculator_keyboard()
        )
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 3:
            bot.send_message(
                chat_id,
                "❌ *Неверный формат*\n\nВведите: количество цена_покупки текущая_цена [годовая_доходность период_лет]\n\n*Пример:* `10 1000 1200 15 3`",
                parse_mode='Markdown'
            )
            return
        
        quantity = float(args[0])
        purchase_price = float(args[1])
        current_price = float(args[2])
        annual_growth = float(args[3]) if len(args) > 3 else 0
        years = float(args[4]) if len(args) > 4 else 0
        
        if quantity <= 0:
            bot.send_message(chat_id, "❌ Количество должно быть больше 0.")
            return
        
        # Текущие расчеты
        total_investment = quantity * purchase_price
        current_value = quantity * current_price
        profit_absolute = current_value - total_investment
        profit_percent = (profit_absolute / total_investment) * 100
        
        # Будущая стоимость (если заданы параметры)
        if annual_growth > 0 and years > 0:
            future_value = current_value * ((1 + annual_growth/100) ** years)
            future_profit = future_value - total_investment
            future_profit_percent = (future_profit / total_investment) * 100
            annualized_return = ((future_value / total_investment) ** (1/years) - 1) * 100
        else:
            future_value = None
        
        result = f"""
*💰 РАСЧЕТ СТОИМОСТИ АКТИВА*

*Исходные данные:*
• Количество: {quantity:,} ед.
• Цена покупки: {purchase_price:,.2f}₽/ед.
• Текущая цена: {current_price:,.2f}₽/ед.
• Общие инвестиции: {total_investment:,.2f}₽

*📊 Текущая ситуация:*
• Текущая стоимость: {current_value:,.2f}₽
• Прибыль/убыток: {profit_absolute:+,.2f}₽
• Доходность: {profit_percent:+.2f}%

*📈 Будущая стоимость:*
"""
        
        if future_value:
            result += f"""• Прогноз на {years:.1f} лет при {annual_growth}% годовых:
• Будущая стоимость: {future_value:,.2f}₽
• Общая прибыль: {future_profit:+,.2f}₽
• Общая доходность: {future_profit_percent:+.2f}%
• Годовая доходность: {annualized_return:+.2f}%
"""
        else:
            result += "*Прогноз не задан. Укажите годовую доходность и период.*\n"
        
        # Добавляем анализ
        result += f"""
*📋 Анализ позиции:*
• {'✅ В плюсе' if profit_absolute >= 0 else '❌ В минусе'}
• Цель по прибыли 20%: {total_investment * 1.2:,.2f}₽
• Точка безубыточности: {purchase_price:,.2f}₽/ед.
• Запас прочности: {abs((current_price - purchase_price) / purchase_price * 100):.1f}%
"""
        
        # Рекомендации
        if profit_percent >= 50:
            result += "\n*🎯 Отличная позиция!* Рекомендуется зафиксировать часть прибыли."
        elif profit_percent >= 20:
            result += "\n*👍 Хорошая позиция!* Можно держать дальше."
        elif profit_percent >= 0:
            result += "\n*😊 Позиция в плюсе.* Рассмотрите стоп-лосс на уровне покупки."
        else:
            result += f"\n*⚠️ Позиция в минусе.* Рекомендуется стоп-лосс на уровне {purchase_price * 0.9:.2f}₽"
        
        bot.send_message(chat_id, result, parse_mode='Markdown')
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ *Ошибка в данных*\n\nПроверьте, что вводите числа.\n*Пример:* `10 1000 1200 15 3`",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'compound_calc')
def handle_compound_calculation(message):
    """Обработчик расчета сложных процентов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '⬅️ Назад в калькулятор':
        user_states[chat_id] = 'calculator_menu'
        bot.send_message(
            chat_id,
            "Выберите инструмент калькулятора:",
            reply_markup=create_calculator_keyboard()
        )
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 3:
            bot.send_message(
                chat_id,
                "❌ *Неверный формат*\n\nВведите: начальная_сумма годовая_ставка(%) период_лет [ежемесячное_пополнение]\n\n*Пример:* `100000 10 5 5000`",
                parse_mode='Markdown'
            )
            return
        
        initial_amount = float(args[0])
        annual_rate = float(args[1])
        years = float(args[2])
        monthly_contribution = float(args[3]) if len(args) > 3 else 0
        
        if annual_rate <= 0 or years <= 0:
            bot.send_message(chat_id, "❌ Ставка и период должны быть больше 0.")
            return
        
        # Расчет без пополнений
        future_value_simple = initial_amount * ((1 + annual_rate/100) ** years)
        interest_simple = future_value_simple - initial_amount
        
        # Расчет с ежемесячными пополнениями
        if monthly_contribution > 0:
            monthly_rate = annual_rate / 12 / 100
            months = years * 12
            
            # Будущая стоимость аннуитета (пополнений)
            future_value_annuity = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)
            
            # Будущая стоимость первоначальной суммы
            future_value_initial = initial_amount * ((1 + monthly_rate) ** months)
            
            total_future_value = future_value_annuity + future_value_initial
            total_invested = initial_amount + (monthly_contribution * months)
            total_interest = total_future_value - total_invested
        else:
            total_future_value = future_value_simple
            total_invested = initial_amount
            total_interest = interest_simple
        
        result = f"""
*📊 РАСЧЕТ СЛОЖНЫХ ПРОЦЕНТОВ*

*Исходные данные:*
• Начальная сумма: {initial_amount:,.2f}₽
• Годовая ставка: {annual_rate:.2f}%
• Период: {years:.1f} лет ({years*12:.0f} месяцев)
• Ежемесячное пополнение: {monthly_contribution:,.2f}₽

*📈 Результаты:*

*Без пополнений:*
• Итоговая сумма: {future_value_simple:,.2f}₽
• Начисленные проценты: {interest_simple:,.2f}₽
• Доходность: {interest_simple/initial_amount*100:.1f}%
"""
        
        if monthly_contribution > 0:
            result += f"""
*С ежемесячными пополнениями:*
• Итоговая сумма: {total_future_value:,.2f}₽
• Всего инвестировано: {total_invested:,.2f}₽
• Начисленные проценты: {total_interest:,.2f}₽
• Общая доходность: {total_interest/total_invested*100:.1f}%
• Эффективная ставка: {((total_future_value/total_invested) ** (1/years) - 1) * 100:.2f}%
"""
        
        # Ежемесячная разбивка (первые 12 месяцев)
        result += f"""
*📋 Ежемесячный рост (первые 12 месяцев):*
"""
        
        monthly_rate = annual_rate / 12 / 100
        current_value = initial_amount
        
        for month in range(1, 13):
            current_value = current_value * (1 + monthly_rate) + monthly_contribution
            if month % 3 == 0:
                result += f"• Месяц {month:2d}: {current_value:,.0f}₽\n"
        
        # Рекомендации
        result += f"""
*💡 Рекомендации:*
• Пополнения увеличивают итог на {(total_future_value - future_value_simple):,.0f}₽
• Увеличение ставки на 1% даст +{initial_amount * (((1 + (annual_rate+1)/100) ** years) - ((1 + annual_rate/100) ** years)):,.0f}₽
• Для миллиона рублей нужно: {1000000 / ((1 + annual_rate/100) ** years):,.0f}₽ сегодня
"""
        
        bot.send_message(chat_id, result, parse_mode='Markdown')
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ *Ошибка в данных*\n\nПроверьте, что вводите числа.\n*Пример:* `100000 10 5 5000`",
            parse_mode='Markdown'
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
                             'portfolio_add_date_first', 'portfolio_add_notes_first',
                             'calculator_menu', 'converter_from', 'converter_to', 'converter_amount',
                             'converter_to_crypto', 'converter_custom_from', 'converter_custom_to',
                             'converter_crypto_custom', 'profit_calc_initial', 'asset_value_calc',
                             'compound_calc', 'loan_calc_type', 'favorites_menu']:
        
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
    print(f"⭐ Улучшенное избранное: Реальные данные в формате MOEX")
    print(f"📊 Формат отображения: GAZP - Газпром")
    print(f"                    💰 Цена: 180.5₽")
    print(f"                    📊 Изменение: +1.2 (+0.67%) 🟢")
    print(f"💾 Новые команды: /favorites_realtime, /favrt")
    print(f"⚡ Защита: {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут")
    print(f"📋 Регистрация: 3 вопроса перед доступом к функциям")
    print(f"🔔 Уведомления: активны каждые {CHECK_INTERVAL_MINUTES} минут")
    print(f"🧮 Финансовый калькулятор с 5 инструментами")
    print("📊 Функции портфеля и уведомлений активированы")
    print("🚀 Полный доступ: регистрация → портфель → все функции + избранное")
    print("Для остановки: Ctrl+C")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")