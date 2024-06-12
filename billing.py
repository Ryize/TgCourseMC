"""
Модуль отвечает за обработку платежей
"""

import os
import uuid
from typing import Union

from yookassa import Configuration, Payment
from yookassa.domain.exceptions import BadRequestError

Configuration.account_id = os.environ.get("SHOP_ID")
Configuration.secret_key = os.environ.get("SECRET_KEY")


def get_payment_url(amount: Union[int, float]) -> tuple[str, str]:
    """
    Функция создает платеж и возвращает URL для подтверждения платежа и
    идентификатор платежа.

    Args:
        amount: сумма платежа.

    Returns:
        tuple: содержит URL для подтверждения платежа и идентификатор платежа.
    """
    idempotence_key = str(uuid.uuid4())
    payment = Payment.create(
        {
            "amount": {"value": f"{amount}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://coursemc.ru/billing/success/",
            },
            "description": "Оплата занятий",
            "receipt": {
                "email": "chekashovmatvey@gmail.com",
                "items": [
                    {
                        "description": "Урок",
                        "amount": {"value": f"{amount}", "currency": "RUB"},
                        "vat_code": 1,
                        "quantity": 1,
                    }
                ],
                "tax_system_id": 1,
            },
        },
        idempotence_key,
    )

    return payment.confirmation.confirmation_url, payment.id


def check_payment(payment_id: str, amount: Union[int, float]) -> str:
    """
    Функция проверяет и осуществляет проведение платежа по заданному
    идентификатору и сумме.

    Args: payment_id: уникальный идентификатор платежа
    amount: сумма платежа

    Returns:
    str: финальный статус платежа после попытки проведения.
    """
    res = Payment.find_one(payment_id)
    if res.status == "pending":
        idempotence_key = str(uuid.uuid4())
        try:
            Payment.capture(
                payment_id,
                {"amount": {"value": f"{amount}", "currency": "RUB"}},
                idempotence_key,
            )
        except BadRequestError:
            pass
    res = Payment.find_one(payment_id)
    return res.status == "succeeded"
