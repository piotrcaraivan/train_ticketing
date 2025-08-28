"""
Page Object для главной страницы сайта CP (Comboios de Portugal).

Содержит:
- URL страницы
- Локатор кнопки 'Buy Tickets'
- Метод открытия страницы

Метод go_to_buy_tickets() удалён, так как:
- Кнопка уже кликается в основном сценарии через WebDriverWait (более надёжно)
- Не нужно дублировать логику ожидания и клика на уровне Page Object, если она уже есть в сценарии
- Это соответствует принципу SRP: Page Object предоставляет локатор, но не обязан его использовать
"""

from selenium.webdriver.common.by import By
from .base_page import BasePage


class HomePage(BasePage):
    # Основной URL главной страницы (очищен от лишних пробелов)
    URL = "https://www.cp.pt/passageiros/en"

    # Локатор кнопки "Buy Tickets"
    # Используется XPATH для точного совпадения по классу и href
    # Класс: btn-nav, ссылка содержит /buy-tickets
    BUY_TICKETS = (
        By.XPATH,
        "//a[contains(@class,'btn-nav') and contains(@href,'/passageiros/en/buy-tickets')]"
    )

    def open(self):
        """
        Открывает главную страницу и разворачивает окно браузера на весь экран.
        Вызывается в начале теста.
        """
        self.driver.get(self.URL)
        self.driver.maximize_window()