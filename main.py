"""
Модуль запуска бота.
"""
import logging
import threading
import time


def main():
    from bot import bot
    from lesson_solutions import poll_lesson_solutions_forever
    from thread import (get_pay, get_training, review,
                        send_timetable_to_administrator,
                        send_lesson_link_to_group)

    print('Бот запущен!')
    background_tasks = (
        get_training,
        get_pay,
        review,
        send_timetable_to_administrator,
        send_lesson_link_to_group,
    )
    for task in background_tasks:
        threading.Thread(target=task, daemon=True).start()
    threading.Thread(
        target=poll_lesson_solutions_forever,
        args=(bot,),
        name='coursemc-lesson-solutions',
        daemon=True,
    ).start()

    while True:
        try:
            bot.polling(non_stop=True)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            # Telegram request exceptions contain the bot token in their URL.
            # Log only the exception type and retry without exposing secrets.
            logging.warning(
                'Telegram polling temporarily failed: %s',
                type(exc).__name__,
            )
            time.sleep(15)


if __name__ == "__main__":
    main()
