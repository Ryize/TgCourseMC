"""
Модуль запуска бота.
"""

if __name__ == "__main__":
    import threading

    from bot import bot
    from thread import get_pay, get_training, review

    print("Бот запущен!")
    thread = threading.Thread(target=get_training)
    thread.start()
    thread = threading.Thread(target=get_pay)
    thread.start()
    thread = threading.Thread(target=review)
    thread.start()
    while True:
        try:
            bot.infinity_polling()
        except:
            pass
