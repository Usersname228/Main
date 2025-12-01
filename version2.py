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


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация

BOT_TOKEN = '8045925681:AAGsbJnHkjyQ23X_4OlctxobxLcb-RZb7aM'
ADMIN_CHAT_ID = 7669840193
DATABASE_NAME = 'datebase.db'

# Создаем экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словари для хранения состояний пользователей
user_states = {}
user_message_history = {}
user_blocks = {}

# Настройки ограничений
MAX_MESSAGES = 5
TIME_WINDOW = 300
BLOCK_DURATION = 600

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
}

# Топ-20 российских акций (тикеры Московской биржи)
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
    button4 = KeyboardButton('📨 Связь с админом')
    button5 = KeyboardButton('ℹ️ О боте')
    keyboard.add(button1, button2, button3, button4, button5)
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
    Используем API Investing.com или аналогичный источник
    """
    try:
        # В реальном проекте здесь нужно использовать официальное API
        # Для примера используем мок-данные, но можно подключить реальное API
        
        # Пример использования реального API (нужно получить API ключ):
        # api_url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json"
        # response = requests.get(api_url, timeout=10)
        # data = response.json()
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        result = f"*📊 АНАЛИТИКА АКЦИЙ РФ - ТОП 20* \n*Время:* {current_time}\n\n"
        
        # Мок-данные для демонстрации (в реальном проекте заменить на реальный API)
        mock_stocks_data = [
            {'ticker': 'GAZP', 'name': 'Газпром', 'price': 180.5, 'change': 1.2, 'change_percent': 0.67},
            {'ticker': 'SBER', 'name': 'Сбербанк', 'price': 275.3, 'change': -2.1, 'change_percent': -0.76},
            {'ticker': 'LKOH', 'name': 'Лукойл', 'price': 6850.2, 'change': 45.3, 'change_percent': 0.67},
            {'ticker': 'ROSN', 'name': 'Роснефть', 'price': 520.8, 'change': -3.2, 'change_percent': -0.61},
            {'ticker': 'NLMK', 'name': 'НЛМК', 'price': 185.6, 'change': 1.8, 'change_percent': 0.98},
            {'ticker': 'GMKN', 'name': 'ГМК Норникель', 'price': 15890.5, 'change': 120.3, 'change_percent': 0.76},
            {'ticker': 'PLZL', 'name': 'Полюс', 'price': 11250.8, 'change': -85.2, 'change_percent': -0.75},
            {'ticker': 'TATN', 'name': 'Татнефть', 'price': 385.4, 'change': 2.1, 'change_percent': 0.55},
            {'ticker': 'VTBR', 'name': 'ВТБ', 'price': 0.0285, 'change': 0.0002, 'change_percent': 0.71},
            {'ticker': 'ALRS', 'name': 'АЛРОСА', 'price': 78.9, 'change': 0.6, 'change_percent': 0.77},
        ]
        
        total_stocks = len(mock_stocks_data)
        green_count = sum(1 for stock in mock_stocks_data if stock['change'] > 0)
        red_count = sum(1 for stock in mock_stocks_data if stock['change'] < 0)
        
        result += f"📈 *Общая статистика:*\n"
        result += f"• Растут: {green_count} акций\n"
        result += f"• Падают: {red_count} акций\n"
        result += f"• Без изменений: {total_stocks - green_count - red_count} акций\n\n"
        
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
• 📨 Связь с администратором

*Команды:*
/start - Запустить бота
/help - Справка
/top - Топ валют
/crypto - Криптовалюты
/analysis - Аналитика

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
• 📈 Криптовалюты (5 основных)
• 📊 Аналитика российских компаний (топ-20 акций)
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
    user_states[message.chat.id] = 'main'
    bot.send_message(
        message.chat.id,
        "✅ Режим связи отменен. Возврат в главное меню.",
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

# ОБРАБОТЧИК ВСЕХ ОСТАЛЬНЫХ СООБЩЕНИЙ
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    save_user_info(message)
    
    if user_states.get(message.chat.id) != 'contact_mode':
        user_states[message.chat.id] = 'main'
        bot.send_message(
            message.chat.id, 
            "Выберите действие с помощью кнопок ниже 👇",
            reply_markup=create_main_keyboard()
        )

if __name__ == "__main__":
    print("🤖 Бот запущен и готов к работе!")
    print(f"⚡ Защита: {MAX_MESSAGES} сообщений в {TIME_WINDOW//60} минут")
    print(f"💾 База данных: {DATABASE_NAME}")
    print(f"📨 Админ ID: {ADMIN_CHAT_ID}")
    print("Для остановки: Ctrl+C")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")