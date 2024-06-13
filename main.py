"""
Модуль запуска бота.
"""

if __name__ == "__main__":
    import threading

    from bot import bot
    from thread import get_pay, get_training, review

    print('Бот запущен!')
    threading.Thread(target=get_training).start()
    threading.Thread(target=get_pay).start()
    threading.Thread(target=review).start()
    while True:
        try:
            bot.infinity_polling()
        except:
            pass
