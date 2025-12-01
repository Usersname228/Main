import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class Config:
    # Обязательные переменные
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
    
    # Опциональные переменные с значениями по умолчанию
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'datebase.db')
    MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '5'))
    TIME_WINDOW = int(os.getenv('TIME_WINDOW', '300'))
    BLOCK_DURATION = int(os.getenv('BLOCK_DURATION', '600'))
    
    @classmethod
    def validate(cls):
        """Проверяем, что обязательные переменные установлены"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен. Укажите его в .env файле или переменных окружения")
        
        if not cls.ADMIN_CHAT_ID:
            errors.append("ADMIN_CHAT_ID не установлен. Укажите его в .env файле или переменных окружения")
        else:
            try:
                cls.ADMIN_CHAT_ID = int(cls.ADMIN_CHAT_ID)
            except ValueError:
                errors.append("ADMIN_CHAT_ID должен быть числом")
        
        if errors:
            error_message = "Ошибки конфигурации:\n" + "\n".join(f"• {error}" for error in errors)
            raise ValueError(error_message)
        
        return True
    
    @classmethod
    def print_config(cls):
        """Безопасный вывод конфигурации (без токена)"""
        config_info = {
            "DATABASE_NAME": cls.DATABASE_NAME,
            "MAX_MESSAGES": cls.MAX_MESSAGES,
            "TIME_WINDOW": cls.TIME_WINDOW,
            "BLOCK_DURATION": cls.BLOCK_DURATION,
            "BOT_TOKEN_SET": bool(cls.BOT_TOKEN),
            "ADMIN_CHAT_ID_SET": bool(cls.ADMIN_CHAT_ID)
        }
        return config_info