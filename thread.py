import time
import threading
from models import *
from api_worker import get_application
from config import *
TOKEN = os.getenv("TOKEN")

def get_training():
    while True:
        time.sleep(60)
        for i in get_application():
            app = Application.select().where(Application.id_application == i['id']).first()
            if app:
                pass
            else:
                bot.send_message(814401631, f'У вас новая заявка!\n'
                                            f'Имя: {i["name"]}\n'
                                            f'Контакт: {i["contact"]}\n'
                                            f'Почта: {i["email"]}\n'
                                            f'Дата заявки: {i["created_at"]}'
                                 )
                app = Application(id_application=i['id'])

                app.save()


thread = threading.Thread(target=get_training)
thread.start()
