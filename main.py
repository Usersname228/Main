import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message
import requests
import json
from datetime import datetime, timedelta
import logging
import time
import sqlite3
import os
import random

from config import Config

# Проверяем конфигурацию перед запуском
Config.validate()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из защищенного config.py
BOT_TOKEN = Config.BOT_TOKEN
ADMIN_CHAT_ID = Config.ADMIN_CHAT_ID
DATABASE_NAME = Config.DATABASE_NAME
MAX_MESSAGES = Config.MAX_MESSAGES
TIME_WINDOW = Config.TIME_WINDOW
BLOCK_DURATION = Config.BLOCK_DURATION

# Создаем экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словари для хранения состояний пользователей
user_states = {}
user_message_history = {}
user_blocks = {}

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

# База данных российских акций с расширенным списком
RUSSIAN_STOCKS = {
    # Голубые фишки
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
    
    # Второй эшелон
    'IRAO': {'name': 'Интер РАО', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'HYDR': {'name': 'РусГидро', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'RTKM': {'name': 'Ростелеком', 'sector': 'Телекоммуникации', 'market': 'MOEX'},
    'FEES': {'name': 'ФСК ЕЭС', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'AFLT': {'name': 'Аэрофлот', 'sector': 'Авиаперевозки', 'market': 'MOEX'},
    'TRNFP': {'name': 'Транснефть (прив.)', 'sector': 'Транспорт', 'market': 'MOEX'},
    'MVID': {'name': 'М.видео', 'sector': 'Розничная торговля', 'market': 'MOEX'},
    'DSKY': {'name': 'Детский мир', 'sector': 'Розничная торговля', 'market': 'MOEX'},
    'LSRG': {'name': 'ЛСР', 'sector': 'Строительство', 'market': 'MOEX'},
    'OZON': {'name': 'Ozon Holdings', 'sector': 'Интернет-ритейл', 'market': 'MOEX'},
    'TCSG': {'name': 'TCS Group', 'sector': 'Финансы', 'market': 'MOEX'},
    'QIWI': {'name': 'QIWI', 'sector': 'Финансы', 'market': 'MOEX'},
    'UPRO': {'name': 'Юнипро', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'ENPG': {'name': 'ЭН+ Групп', 'sector': 'Металлургия/Энергетика', 'market': 'MOEX'},
    'PIKK': {'name': 'ПИК', 'sector': 'Строительство', 'market': 'MOEX'},
    'CBOM': {'name': 'МКБ', 'sector': 'Финансы', 'market': 'MOEX'},
    'FIVE': {'name': 'X5 RetailGroup', 'sector': 'Розничная торговля', 'market': 'MOEX'},
    'OKEY': {'name': 'O`KEY Group', 'sector': 'Розничная торговля', 'market': 'MOEX'},
    'AGRO': {'name': 'Агрохолдинг Русагро', 'sector': 'Сельское хозяйство', 'market': 'MOEX'},
    'SVAV': {'name': 'Соллерс', 'sector': 'Автопром', 'market': 'MOEX'},
    
    # Отраслевые
    'CHMF': {'name': 'Северсталь', 'sector': 'Металлургия', 'market': 'MOEX'},
    'MAGN': {'name': 'ММК', 'sector': 'Металлургия', 'market': 'MOEX'},
    'NMTP': {'name': 'НМТП', 'sector': 'Транспорт', 'market': 'MOEX'},
    'BANEP': {'name': 'Башнефть (прив.)', 'sector': 'Нефть и газ', 'market': 'MOEX'},
    'KZOS': {'name': 'Казаньоргсинтез', 'sector': 'Химическая промышленность', 'market': 'MOEX'},
    'TGKA': {'name': 'ТГК-1', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'TGKB': {'name': 'ТГК-2', 'sector': 'Электроэнергетика', 'market': 'MOEX'},
    'UNAC': {'name': 'Объединенная авиастроительная корпорация', 'sector': 'Авиастроение', 'market': 'MOEX'},
}

# Топ-20 российских акций для быстрого доступа
TOP_RUSSIAN_STOCKS = [
    'GAZP', 'SBER', 'LKOH', 'ROSN', 'NLMK', 'GMKN', 'PLZL', 'TATN', 'VTBR', 'ALRS',
    'MGNT', 'POLY', 'AFKS', 'PHOR', 'SNGS', 'SNGSP', 'MTSS', 'RUAL', 'MOEX', 'YNDX'
]

class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
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
            conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users 
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
    
    def add_message(self, user_id, message_type, content, forwarded=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages 
                (user_id, message_type, content, forwarded_to_admin) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, message_type, content, forwarded))
            conn.commit()
            return cursor.lastrowid
    
    def add_user_action(self, user_id, action_type, details=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_actions 
                (user_id, action_type, details) 
                VALUES (?, ?, ?)
            ''', (user_id, action_type, details))
            conn.commit()

# Инициализация базы данных
db = Database(DATABASE_NAME)

def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button1 = KeyboardButton('🏆 Топ валют')
    button2 = KeyboardButton('📈 Криптовалюты')
    button3 = KeyboardButton('📊 Аналитика РФ')
    button4 = KeyboardButton('🔍 Поиск валюты')
    button5 = KeyboardButton('🔎 Поиск крипты')
    button6 = KeyboardButton('📈 Поиск акций')  # Новая кнопка
    button7 = KeyboardButton('📨 Связь с админом')
    button8 = KeyboardButton('ℹ️ О боте')
    keyboard.add(button1, button2, button3, button4, button5, button6, button7, button8)
    return keyboard

def create_contact_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    button1 = KeyboardButton('❌ Отмена')
    keyboard.add(button1)
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
    """
    Получает данные по топ-20 акциям РФ с Московской биржи
    """
    try:
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        result = f"*📊 АНАЛИТИКА АКЦИЙ РФ - ТОП 20* \n*Время:* {current_time}\n\n"
        
        # Мок-данные для демонстрации (расширенные)
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
            {'ticker': 'MGNT', 'name': 'Магнит', 'price': 5420.3, 'change': 32.1, 'change_percent': 0.60, 'volume': 120000},
            {'ticker': 'POLY', 'name': 'Полиметалл', 'price': 890.4, 'change': -12.3, 'change_percent': -1.36, 'volume': 150000},
            {'ticker': 'AFKS', 'name': 'Система', 'price': 15.78, 'change': 0.12, 'change_percent': 0.77, 'volume': 850000},
            {'ticker': 'PHOR', 'name': 'ФосАгро', 'price': 6450.2, 'change': 45.8, 'change_percent': 0.72, 'volume': 95000},
            {'ticker': 'SNGS', 'name': 'Сургутнефтегаз', 'price': 42.15, 'change': -0.35, 'change_percent': -0.82, 'volume': 2100000},
            {'ticker': 'MTSS', 'name': 'МТС', 'price': 285.6, 'change': 1.8, 'change_percent': 0.63, 'volume': 320000},
            {'ticker': 'RUAL', 'name': 'РУСАЛ', 'price': 45.23, 'change': -0.52, 'change_percent': -1.14, 'volume': 1500000},
            {'ticker': 'MOEX', 'name': 'Московская биржа', 'price': 145.8, 'change': 0.9, 'change_percent': 0.62, 'volume': 180000},
            {'ticker': 'YNDX', 'name': 'Яндекс', 'price': 2850.4, 'change': -25.6, 'change_percent': -0.89, 'volume': 75000},
            {'ticker': 'IRAO', 'name': 'Интер РАО', 'price': 2.145, 'change': 0.012, 'change_percent': 0.56, 'volume': 2500000},
        ]
        
        total_stocks = len(mock_stocks_data)
        green_count = sum(1 for stock in mock_stocks_data if stock['change'] > 0)
        red_count = sum(1 for stock in mock_stocks_data if stock['change'] < 0)
        
        # Рассчитываем общий индекс (условно)
        total_change = sum(stock['change_percent'] for stock in mock_stocks_data)
        avg_change = total_change / total_stocks
        
        result += f"📈 *Общая статистика:*\n"
        result += f"• Растут: {green_count} акций\n"
        result += f"• Падают: {red_count} акций\n"
        result += f"• Без изменений: {total_stocks - green_count - red_count} акций\n"
        result += f"• Среднее изменение: {avg_change:+.2f}%\n\n"
        
        result += f"🏆 *Топ акций (выборочно):*\n"
        
        for i, stock in enumerate(mock_stocks_data[:10], 1):
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

def get_russian_companies_analysis():
    """
    Основная функция для получения аналитики по российским акциям
    """
    try:
        return get_russian_stocks_data()
    except Exception as e:
        return f"*❌ Ошибка при формировании аналитики*\n{str(e)}"

def search_currency(query):
    """
    Ищет валюту по коду или названию в базе ЦБ РФ
    Возвращает список найденных валют
    """
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        data = response.json()
        
        query = query.upper().strip()
        results = []
        
        # Поиск по коду валюты
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
        
        # Поиск по названию (частичное совпадение)
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
        
        # Если не найдено, ищем в популярных валютах
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
        
        return search_results[:10]  # Ограничиваем 10 результатами
        
    except Exception as e:
        logger.error(f"Ошибка при поиске валюты: {e}")
        return []

def format_search_results(results, query):
    """
    Форматирует результаты поиска валют в читаемый вид
    """
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
        
        # Форматируем цену в зависимости от номинала
        if currency['nominal'] > 1:
            value_per_unit = currency['value'] / currency['nominal']
            result += f"{i}. *{currency['code']}* - {currency['name']}\n"
            result += f"   💰 {currency['nominal']} ед.: *{currency['value']:.4f}₽*\n"
            result += f"   📊 1 ед.: *{value_per_unit:.4f}₽*\n"
        else:
            result += f"{i}. *{currency['code']}* - {currency['name']}\n"
            result += f"   💰 *{currency['value']:.4f}₽*\n"
        
        result += f"   📊 Изменение: {change_sign}{currency['change']:.4f} {change_icon}\n"
        
        # Добавляем флаг и символ для популярных валют
        if currency['code'] in POPULAR_CURRENCIES:
            flag = POPULAR_CURRENCIES[currency['code']]['flag']
            symbol = POPULAR_CURRENCIES[currency['code']]['symbol']
            result += f"   {flag} Символ: {symbol}\n"
        
        result += "\n"
    
    result += f"_По запросу: {query}_\n"
    result += f"_Данные ЦБ РФ, время: {current_time}_"
    
    return result

def search_crypto(query):
    """
    Ищет криптовалюту по названию или символу
    """
    try:
        query = query.lower().strip()
        
        # Сначала пробуем получить список всех криптовалют
        search_url = f'https://api.coingecko.com/api/v3/search?query={query}'
        response = requests.get(search_url, timeout=10)
        search_data = response.json()
        
        if 'coins' not in search_data or not search_data['coins']:
            return []
        
        # Берем топ-5 результатов
        top_coins = search_data['coins'][:5]
        coin_ids = [coin['id'] for coin in top_coins]
        
        # Получаем детальную информацию о найденных криптовалютах
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
    """
    Форматирует результаты поиска криптовалют
    """
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
        
        # Получаем эмодзи для популярных криптовалют
        emoji = POPULAR_CRYPTOCURRENCIES.get(crypto['id'], {}).get('emoji', '💰')
        
        result += f"{i}. {emoji} *{crypto['name']} ({crypto['symbol']})*\n"
        
        # Добавляем рейтинг рыночной капитализации, если есть
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
    """
    Ищет акцию РФ по тикеру или названию компании
    """
    try:
        query = query.upper().strip()
        results = []
        
        # Поиск по точному совпадению тикера
        if query in RUSSIAN_STOCKS:
            stock_info = RUSSIAN_STOCKS[query]
            # Генерируем мок-данные для акции
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
        
        # Поиск по частичному совпадению тикера
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
        
        # Поиск по названию компании (русский язык)
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
        
        # Если не найдено, ищем в популярных акциях
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
        
        return results[:10]  # Ограничиваем 10 результатами
        
    except Exception as e:
        logger.error(f"Ошибка при поиске акции: {e}")
        return []

def format_stock_search_results(results, query):
    """
    Форматирует результаты поиска акций
    """
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
        
        # Форматируем объем торгов
        if stock['volume'] > 1000000:
            volume_str = f"{stock['volume']/1000000:.1f}M"
        elif stock['volume'] > 1000:
            volume_str = f"{stock['volume']/1000:.1f}K"
        else:
            volume_str = str(stock['volume'])
        
        result += f"   📊 Объем: {volume_str} акций\n"
        
        # Форматируем капитализацию
        if stock['market_cap'] > 1000000000:
            cap_str = f"{stock['market_cap']/1000000000:.1f} млрд ₽"
        else:
            cap_str = f"{stock['market_cap']/1000000:.1f} млн ₽"
        
        result += f"   💎 Капитализация: {cap_str}\n"
        
        result += "\n"
    
    # Добавляем подсказки для популярных запросов
    result += f"_По запросу: {query}_\n"
    result += f"_Время: {current_time}_\n"
    result += "_⚠️ Данные являются демонстрационными для тестирования функционала_"
    
    return result

def get_popular_stocks_list():
    """
    Возвращает список популярных акций для подсказки
    """
    popular_list = "🏆 *Голубые фишки:*\n"
    for i, ticker in enumerate(TOP_RUSSIAN_STOCKS[:10], 1):
        stock_info = RUSSIAN_STOCKS.get(ticker, {'name': 'Неизвестно'})
        popular_list += f"{i}. {ticker} - {stock_info['name']}\n"
    
    popular_list += "\n🏢 *Второй эшелон:*\n"
    second_tier = ['IRAO', 'HYDR', 'RTKM', 'FEES', 'AFLT', 'MVID', 'LSRG', 'OZON', 'FIVE', 'AGRO']
    for i, ticker in enumerate(second_tier, 1):
        stock_info = RUSSIAN_STOCKS.get(ticker, {'name': 'Неизвестно'})
        popular_list += f"{i}. {ticker} - {stock_info['name']}\n"
    
    return popular_list

def get_popular_crypto_list():
    """
    Возвращает список популярных криптовалют для подсказки
    """
    popular_list = ""
    for i, (crypto_id, crypto_info) in enumerate(POPULAR_CRYPTOCURRENCIES.items(), 1):
        popular_list += f"{i}. {crypto_info['emoji']} {crypto_info['name']} ({crypto_info['symbol']})\n"
    return popular_list

def get_all_currencies_list():
    """
    Возвращает список всех доступных валют с кодами и названиями
    """
    try:
        cbr_url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        response = requests.get(cbr_url, timeout=10)
        data = response.json()
        
        currencies_list = []
        for code, valute in data['Valute'].items():
            currencies_list.append({
                'code': code,
                'name': valute['Name'],
                'value': valute['Value']
            })
        
        # Сортируем по коду
        currencies_list.sort(key=lambda x: x['code'])
        return currencies_list
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка валют: {e}")
        return []

def forward_to_admin(message: Message, content_type="сообщение"):
    try:
        user = message.from_user
        
        content = message.text or message.caption or f"[{content_type}]"
        message_id = db.add_message(user.id, content_type, content, True)
        
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

def check_message_limit(user_id):
    if is_user_blocked(user_id):
        remaining_time = get_remaining_block_time(user_id)
        return False, f"🚫 *Вы превысили лимит сообщений!*\n\nПодождите {remaining_time} минут."
    
    if not update_message_history(user_id):
        remaining_time = get_remaining_block_time(user_id)
        return False, f"🚫 *Слишком много сообщений!*\n\nБлокировка на {remaining_time} минут."
    
    return True, ""

# ОСНОВНЫЕ КОМАНДЫ
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "start_command")
    user_states[message.chat.id] = 'main'
    
    welcome_text = """
*💱 Бот финансовых курсов и связи*

📊 *Получайте актуальные курсы:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика российских компаний
• 🔍 Поиск любой валюты ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ

📨 *Связь с администратором*
⚡ *Защита от спама*

Используйте кнопки ниже ⬇️
"""
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "help_command")
    
    help_text = f"""
*📋 Справка по боту*

*Функции:*
• 🏆 Топ валют
• 📈 Криптовалюты
• 📊 Аналитика компаний
• 🔍 Поиск валюты ЦБ РФ
• 🔎 Поиск криптовалют
• 📈 Поиск акций РФ
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
/crypto - Поиск крипты (с параметром)
/stock - Поиск акции (с параметром)

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
        message.chat.id, 
        help_text, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['top'])
def handle_top_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "top_command")
    bot.send_message(message.chat.id, "🔄 Получаю курсы валют...")
    rates = get_currency_rates()
    bot.send_message(
        message.chat.id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['crypto'])
def handle_crypto_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "crypto_command")
    
    # Проверяем, есть ли аргумент для поиска
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        # Проверка лимита сообщений
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                message.chat.id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(message.chat.id, "🔎 Ищу криптовалюту...")
        results = search_crypto(query)
        formatted_results = format_crypto_search_results(results, query)
        
        bot.send_message(
            message.chat.id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[message.chat.id] = 'main'
    else:
        # Если аргумента нет, показываем топ криптовалют
        bot.send_message(message.chat.id, "🔄 Получаю курсы криптовалют...")
        rates = get_crypto_rates()
        bot.send_message(
            message.chat.id, 
            rates, 
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@bot.message_handler(commands=['analysis'])
def handle_analysis_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "analysis_command")
    bot.send_message(message.chat.id, "🔄 Получаю данные с биржи...")
    analysis = get_russian_companies_analysis()
    bot.send_message(
        message.chat.id, 
        analysis, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['search'])
def handle_search_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "search_command")
    handle_currency_search(message)

@bot.message_handler(commands=['cryptosearch'])
def handle_cryptosearch_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "cryptosearch_command")
    handle_crypto_search(message)

@bot.message_handler(commands=['stocksearch'])
def handle_stocksearch_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "stocksearch_command")
    handle_stock_search(message)

@bot.message_handler(commands=['currency'])
def handle_currency_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "currency_command")
    
    # Проверяем, есть ли аргумент
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        # Проверка лимита сообщений
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                message.chat.id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(message.chat.id, "🔍 Ищу валюту...")
        results = search_currency(query)
        formatted_results = format_search_results(results, query)
        
        bot.send_message(
            message.chat.id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[message.chat.id] = 'main'
    else:
        # Если аргумента нет, показываем инструкцию
        handle_currency_search(message)

@bot.message_handler(commands=['stock'])
def handle_stock_command(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "stock_command")
    
    # Проверяем, есть ли аргумент
    if len(message.text.split()) > 1:
        query = ' '.join(message.text.split()[1:])
        
        # Проверка лимита сообщений
        is_allowed, error_message = check_message_limit(message.from_user.id)
        if not is_allowed:
            bot.send_message(
                message.chat.id,
                error_message,
                parse_mode='Markdown'
            )
            return
        
        bot.send_message(message.chat.id, "📈 Ищу акцию...")
        results = search_stock(query)
        formatted_results = format_stock_search_results(results, query)
        
        bot.send_message(
            message.chat.id,
            formatted_results,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        user_states[message.chat.id] = 'main'
    else:
        # Если аргумента нет, показываем инструкцию
        handle_stock_search(message)

# ОБРАБОТЧИКИ КНОПОК
@bot.message_handler(func=lambda message: message.text == '🏆 Топ валют')
def handle_top_currencies(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "top_button")
    user_states[message.chat.id] = 'main'
    bot.send_message(message.chat.id, "🔄 Получаю курсы валют...")
    rates = get_currency_rates()
    bot.send_message(
        message.chat.id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📈 Криптовалюты')
def handle_crypto_rates(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "crypto_button")
    user_states[message.chat.id] = 'main'
    bot.send_message(message.chat.id, "🔄 Получаю курсы криптовалют...")
    rates = get_crypto_rates()
    bot.send_message(
        message.chat.id, 
        rates, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📊 Аналитика РФ')
def handle_analysis_button(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "analysis_button")
    user_states[message.chat.id] = 'main'
    bot.send_message(message.chat.id, "🔄 Загружаю данные по акциям...")
    analysis = get_russian_companies_analysis()
    bot.send_message(
        message.chat.id, 
        analysis, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🔍 Поиск валюты')
def handle_currency_search(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "currency_search_button")
    user_states[message.chat.id] = 'search_currency'
    
    # Получаем список популярных валют для подсказки
    popular_list = "\n".join([f"• {code} - {info['name']}" for code, info in POPULAR_CURRENCIES.items()])
    
    search_text = f"""
*🔍 ПОИСК ВАЛЮТЫ ЦБ РФ*

Введите код или название валюты:

*Примеры запросов:*
`USD` - Доллар США
`EUR` - Евро
`доллар` - поиск по названию
`евро` - поиск по названию
`йен` - японская йена

*Популярные валюты:*
{popular_list}

*Для отмены:* нажмите /cancel или ❌ Отмена
"""
    bot.send_message(
        message.chat.id,
        search_text,
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()  # Используем ту же клавиатуру с кнопкой отмены
    )

@bot.message_handler(func=lambda message: message.text == '🔎 Поиск крипты')
def handle_crypto_search(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "crypto_search_button")
    user_states[message.chat.id] = 'search_crypto'
    
    # Получаем список популярных криптовалют для подсказки
    popular_list = get_popular_crypto_list()
    
    search_text = f"""
*🔎 ПОИСК КРИПТОВАЛЮТЫ*

Введите название или символ криптовалюты:

*Примеры запросов:*
`Bitcoin` или `BTC` - Bitcoin
`Ethereum` или `ETH` - Ethereum
`Solana` или `SOL` - Solana
`dog` - поиск Dogecoin
`usd` - поиск стейблкоинов

*Популярные криптовалюты:*
{popular_list}

*Для отмены:* нажмите /cancel или ❌ Отмена
"""
    bot.send_message(
        message.chat.id,
        search_text,
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '📈 Поиск акций')
def handle_stock_search(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "stock_search_button")
    user_states[message.chat.id] = 'search_stock'
    
    # Получаем список популярных акций для подсказки
    popular_list = get_popular_stocks_list()
    
    search_text = f"""
*📈 ПОИСК АКЦИЙ РФ*

Введите тикер или название компании:

*Примеры запросов:*
`GAZP` - Газпром
`SBER` - Сбербанк
`Газпром` - поиск по названию
`Сбер` - частичный поиск
`нефть` - поиск нефтегазовых компаний

*Популярные акции:*
{popular_list}

*Для отмены:* нажмите /cancel или ❌ Отмена
"""
    bot.send_message(
        message.chat.id,
        search_text,
        parse_mode='Markdown',
        reply_markup=create_contact_keyboard()
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
            reply_markup=create_main_keyboard()
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
    user_states[message.chat.id] = 'main'
    about_text = f"""
*🤖 О боте*

*Функции:*
• 🏆 Топ валют (10 валют)
• 📈 Криптовалюты (10+ популярных)
• 📊 Аналитика российских компаний (топ-20 акций)
• 🔍 Поиск любой валюты из базы ЦБ РФ
• 🔎 Поиск криптовалют (база CoinGecko)
• 📈 Поиск акций РФ (база MOEX)
• 📨 Связь с администратором

*Источники данных:*
• Центральный Банк РФ
• CoinGecko API
• Московская биржа (MOEX)

*Защита от спама:*
• {MAX_MESSAGES} сообщений в 5 минут
• Блокировка на {BLOCK_DURATION//60} минут

_Бот создан для удобного отслеживания курсов_
"""
    bot.send_message(
        message.chat.id, 
        about_text, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def handle_cancel(message):
    save_user_info(message)
    db.add_user_action(message.from_user.id, "cancel_button")
    
    current_state = user_states.get(message.chat.id)
    if current_state in ['contact_mode', 'search_currency', 'search_crypto', 'search_stock']:
        user_states[message.chat.id] = 'main'
        bot.send_message(
            message.chat.id,
            "✅ Операция отменена. Возврат в главное меню.",
            reply_markup=create_main_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Вы в главном меню. Используйте кнопки ниже 👇",
            reply_markup=create_main_keyboard()
        )

# ОБРАБОТЧИК СООБЩЕНИЙ В РЕЖИМЕ СВЯЗИ
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

# ОБРАБОТЧИК СООБЩЕНИЙ В РЕЖИМЕ ПОИСКА ВАЛЮТЫ
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_currency')
def handle_search_query(message):
    save_user_info(message)
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(message.from_user.id, "search_query", message.text)
    
    # Проверка лимита сообщений
    is_allowed, error_message = check_message_limit(message.from_user.id)
    if not is_allowed:
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(message.chat.id, "🔍 Ищу валюту...")
    
    query = message.text
    results = search_currency(query)
    formatted_results = format_search_results(results, query)
    
    bot.send_message(
        message.chat.id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[message.chat.id] = 'main'

# ОБРАБОТЧИК СООБЩЕНИЙ В РЕЖИМЕ ПОИСКА КРИПТОВАЛЮТ
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_crypto')
def handle_crypto_search_query(message):
    save_user_info(message)
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(message.from_user.id, "crypto_search_query", message.text)
    
    # Проверка лимита сообщений
    is_allowed, error_message = check_message_limit(message.from_user.id)
    if not is_allowed:
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(message.chat.id, "🔎 Ищу криптовалюту...")
    
    query = message.text
    results = search_crypto(query)
    formatted_results = format_crypto_search_results(results, query)
    
    bot.send_message(
        message.chat.id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[message.chat.id] = 'main'

# ОБРАБОТЧИК СООБЩЕНИЙ В РЕЖИМЕ ПОИСКА АКЦИЙ
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'search_stock')
def handle_stock_search_query(message):
    save_user_info(message)
    
    if message.text == '❌ Отмена':
        handle_cancel(message)
        return
    
    db.add_user_action(message.from_user.id, "stock_search_query", message.text)
    
    # Проверка лимита сообщений
    is_allowed, error_message = check_message_limit(message.from_user.id)
    if not is_allowed:
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode='Markdown'
        )
        return
    
    bot.send_message(message.chat.id, "📈 Ищу акцию...")
    
    query = message.text
    results = search_stock(query)
    formatted_results = format_stock_search_results(results, query)
    
    bot.send_message(
        message.chat.id,
        formatted_results,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    
    user_states[message.chat.id] = 'main'

# ОБРАБОТЧИК ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    save_user_info(message)
    
    current_state = user_states.get(message.chat.id)
    if current_state not in ['contact_mode', 'search_currency', 'search_crypto', 'search_stock']:
        user_states[message.chat.id] = 'main'
        bot.send_message(
            message.chat.id, 
            "Выберите действие с помощью кнопок ниже 👇",
            reply_markup=create_main_keyboard()
        )

if __name__ == "__main__":
    config_info = Config.print_config()
    print("🤖 Бот запущен и готов к работе!")
    print(f"⚡ Защита: {config_info['MAX_MESSAGES']} сообщений в {config_info['TIME_WINDOW']//60} минут")
    print(f"💾 База данных: {config_info['DATABASE_NAME']}")
    print(f"🔐 Токен установлен: {'✅' if config_info['BOT_TOKEN_SET'] else '❌'}")
    print(f"👤 Админ ID установлен: {'✅' if config_info['ADMIN_CHAT_ID_SET'] else '❌'}")
    print("Для остановки: Ctrl+C")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
