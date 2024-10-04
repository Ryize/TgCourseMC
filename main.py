"""
Модуль запуска бота.
"""
import multiprocessing
import time

def main():
    import threading

    from bot import bot
    from thread import (get_pay, get_training, review,
                        send_timetable_to_administrator,
                        send_lesson_link_to_group)

    print('Бот запущен!')
    threading.Thread(target=get_training).start()
    threading.Thread(target=get_pay).start()
    threading.Thread(target=review).start()
    threading.Thread(target=send_timetable_to_administrator).start()
    threading.Thread(target=send_lesson_link_to_group).start()
    bot.polling(non_stop=True)


if __name__ == "__main__":
    while True:
        process = multiprocessing.Process(target=main)
        process.start()
        time.sleep(86385)
        process.kill()
        time.sleep(15)
