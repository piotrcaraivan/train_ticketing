"""
Автоматизированное тестирование покупки билетов на транспортный сайт.

Логика:
1. Открытие главной страницы
2. Принятие куки
3. Переход на страницу покупки
4. Заполнение маршрута, даты, пассажиров
5. Поиск поездов
6. Выбор подходящего поезда
7. Обработка экрана аутентификации (если появится)

Используется Page Object Model (POM) для чистоты и масштабируемости.
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Импорты страниц — шаблон Page Object Model
from pages.home_page import HomePage
from pages.buy_page import BuyPage
from pages.results_page import ResultsPage
from pages.auth_page import AuthPage


def switch_to_last_window(driver):
    """
    Безопасно переключается на последнюю вкладку.
    Не вызывает ошибку, если вкладок нет.
    """
    try:
        driver.switch_to.window(driver.window_handles[-1])
    except Exception:
        pass


def wait_for_overlays_to_disappear(wait):
    """
    Ожидает исчезновения типичных overlay-элементов: спиннеры, оверлеи, лоадеры.
    Используется как "пылесос" перед взаимодействием с контентом.
    """
    selectors = [
        (By.CSS_SELECTOR, ".overlay, .spinner, [aria-busy='true']"),
        (By.CSS_SELECTOR, "[data-testid='loading'], .loading"),
    ]
    for by, selector in selectors:
        try:
            WebDriverWait(wait._driver, 6).until(EC.invisibility_of_element_located((by, selector)))
        except Exception:
            pass  # Игнорируем — возможно, элемента не было


def scroll_to_reveal_results(driver, max_scrolls=12, scroll_step=600):
    """
    Плавно прокручивает страницу, чтобы "пробудить" виртуализированные элементы.
    Возвращает True, если хотя бы одна строка результатов найдена.
    """
    for _ in range(max_scrolls):
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "[data-testid='solution-row'], .solution-row, .journey-row"
        )
        if rows:
            # Плавно скроллим первый элемент к центру
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", rows[0])
            return True
        driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_step)
        time.sleep(0.2)
    return False


def main():
    """Основной сценарий тестирования покупки билетов."""
    # Настройка драйвера
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 15)

    try:
        # --- Шаг 1: Главная страница ---
        home = HomePage(driver)
        home.open()
        print("[INFO] Главная страница открыта")

        # Принятие куки (если есть)
        try:
            cookie_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Accept all cookies']"))
            )
            cookie_btn.click()
            print("[INFO] Куки приняты")
        except Exception:
            print("[INFO] Баннер с куки не отображается — пропускаем")

        # Переход на страницу покупки билетов
        buy_tickets_btn = wait.until(EC.element_to_be_clickable(HomePage.BUY_TICKETS))
        buy_tickets_btn.click()
        wait.until(EC.url_contains("/buy-tickets"))
        print(f"[OK] Переход на страницу покупки: {driver.current_url}")

        # Критическая пауза после перехода (может быть инициализация данных)
        time.sleep(10)

        # --- Шаг 2: Заполнение маршрута ---
        buy_page = BuyPage(driver)

        from_station = buy_page.set_from("Lisboa Oriente")
        print(f"[OK] Откуда: {from_station}")

        to_station = buy_page.set_to("Porto Campanha")
        print(f"[OK] Куда: {to_station}")

        time.sleep(10)  # Визуальная проверка — можно заменить на ожидание, если есть признак загрузки

        # --- Шаг 3: Выбор даты ---
        print("[STEP] Открываем календарь")
        buy_page.open_calendar()
        selected_date = buy_page.pick_date(day=24, month_name="September")
        print(f"[OK] Дата выбрана: {selected_date}")
        time.sleep(10)

        # --- Шаг 4: Количество пассажиров ---
        passengers = buy_page.set_passengers(4)
        print(f"[OK] Количество пассажиров: {passengers}")
        time.sleep(10)

        # --- Шаг 5: Поиск поездов ---
        print("[STEP] Отправка формы поиска")
        handles_before = driver.window_handles
        search_url = buy_page.search_trains()
        print(f"[OK] Поиск отправлен. URL: {search_url}")

        # Возможное открытие новой вкладки
        time.sleep(0.8)
        if len(driver.window_handles) > len(handles_before):
            switch_to_last_window(driver)
            print("[INFO] Переключились на новую вкладку")

        # Ожидание полной загрузки страницы
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        wait_for_overlays_to_disappear(wait)

        # Ожидание появления результатов
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='solution-row'], .solution-row, .journey-row")
                )
            )
        except Exception:
            print("[INFO] Результаты не загрузились автоматически — пробуем прокруткой")
            scroll_to_reveal_results(driver)

        # Дополнительная прокрутка для "пробуждения" виртуализации
        scroll_to_reveal_results(driver)
        time.sleep(0.5)

        # --- Шаг 6: Выбор поезда ---
        results_page = ResultsPage(driver)
        success = results_page.select_ap125(dep="12:09", arr="14:48")
        print(f"[RESULT] Выбор поезда AP125: {'Успешно' if success else 'Не удалось'}")

        # --- Шаг 7: Обработка экрана входа (если появился) ---
        auth_page = AuthPage(driver)
        if auth_page.is_here():
            auth_success = auth_page.click_continue_and_capture()
            print(f"[INFO] Продолжение на экране входа: {'Успешно' if auth_success else 'Прервано'}")
            if not auth_success:
                print("[INFO] Скриншот/данные сохранены в ./artifacts/ для анализа")

    except Exception as e:
        print(f"[ERROR] Ошибка в основном сценарии: {type(e).__name__}: {str(e)}")
        raise  # Для отладки — можно убрать, если не нужен полный traceback

    finally:
        driver.quit()
        print("[INFO] Драйвер закрыт")


# Запуск теста
if __name__ == "__main__":
    main()