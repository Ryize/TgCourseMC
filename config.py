import os

import telebot

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
