"""
Модуль запуска бота
"""

if __name__ == "__main__":
    from bot import bot

    print("Бот запущен!")
    while True:
        try:
            bot.infinity_polling()
        except:
            pass
