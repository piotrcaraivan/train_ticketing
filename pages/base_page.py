"""
Базовый класс для всех Page Object'ов.

Предоставляет:
- Унифицированные методы ожидания
- Надёжные действия (клик, ввод, скролл)
- Обработку фреймов и окон
- Сбор артефактов (скриншоты, HTML, логи) для диагностики

Особенности:
- Использует гибридные стратегии (ожидание + fallback)
- Устойчив к StaleElement, intercept и другим типичным проблемам
- Поддерживает диагностику при ошибках — критично для CI/CD и отладки
"""
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException
)
import os
import json
import time


class BasePage:
    # === КОНСТАНТЫ ===
    DEFAULT_TIMEOUT = 15
    SPINNER_TIMEOUT = 6
    POLL_FREQUENCY = 0.25
    ARTIFACTS_DIR = "artifacts"
    DEFAULT_SCROLL_BLOCK = "center"

    # Селекторы для типичных оверлеев (лоадеры, спиннеры)
    OVERLAY_SELECTORS = (
        ".overlay, .spinner, [aria-busy='true'], "
        "[data-testid='loading'], .loading, [class*='loading']"
    )

    def __init__(self, driver, timeout=DEFAULT_TIMEOUT):
        """
        Инициализация базовой страницы.

        :param driver: WebDriver instance
        :param timeout: Глобальное время ожидания элементов
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout, poll_frequency=self.POLL_FREQUENCY)

    # === ОЖИДАНИЯ ===

    def safe_wait(self, condition, timeout=None, poll_frequency=None, ignored_exceptions=None):
        """
        Универсальное ожидание с защитой от типичных исключений.

        :param condition: Условие для ожидания (например, EC.visibility_of_element_located)
        :param timeout: Время ожидания (по умолчанию — self.wait._timeout)
        :param poll_frequency: Частота опроса (по умолчанию — 0.25)
        :param ignored_exceptions: Исключения, которые игнорируются
        :return: Результат условия
        """
        if ignored_exceptions is None:
            ignored_exceptions = (StaleElementReferenceException, ElementClickInterceptedException)

        w = WebDriverWait(
            self.driver,
            timeout or self.wait._timeout,
            poll_frequency=poll_frequency or self.POLL_FREQUENCY,
            ignored_exceptions=ignored_exceptions
        )
        return w.until(condition)

    def wait_ready(self):
        """
        Ожидает, пока document.readyState не станет 'complete'.

        :return: True, если страница загружена
        """
        return self.safe_wait(lambda d: d.execute_script("return document.readyState") == "complete")

    def wait_spinner_gone(self, css=None):
        """
        Ожидает исчезновения типичных оверлеев (спиннеры, лоадеры).

        :param css: CSS-селектор оверлея (по умолчанию — стандартные)
        """
        css = css or self.OVERLAY_SELECTORS
        try:
            WebDriverWait(self.driver, self.SPINNER_TIMEOUT).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, css))
            )
        except Exception:
            pass  # Игнорируем — возможно, оверлея не было

    # === ДЕЙСТВИЯ ===

    def click(self, locator):
        """
        Кликает по элементу после ожидания его кликабельности.

        :param locator: (By, selector)
        :return: Элемент
        """
        el = self.wait.until(EC.element_to_be_clickable(locator))
        el.click()
        return el

    def safe_click(self, locator):
        """
        Надёжный клик с резервными стратегиями:
        1. Обычный клик
        2. Прокрутка + клик
        3. JS-клик (fallback)

        :param locator: (By, selector)
        :return: Элемент
        """
        el = self.wait.until(EC.presence_of_element_located(locator))
        try:
            self.wait.until(EC.element_to_be_clickable(locator)).click()
            return el
        except Exception:
            pass

        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: arguments[1]});",
                el, self.DEFAULT_SCROLL_BLOCK
            )
            time.sleep(0.1)
            el.click()
            return el
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)
            return el

    def type(self, locator, text, clear_first=True):
        """
        Вводит текст в поле ввода.

        :param locator: (By, selector)
        :param text: Текст для ввода
        :param clear_first: Очистить поле перед вводом
        :return: Элемент
        """
        el = self.wait.until(EC.visibility_of_element_located(locator))
        if clear_first:
            el.clear()
        el.send_keys(text)
        return el

    # === СКРОЛЛЫ ===

    def scroll_by(self, y=600):
        """
        Прокручивает страницу на указанное количество пикселей по вертикали.

        :param y: Пиксели (положительное значение — вниз)
        """
        self.driver.execute_script("window.scrollBy(0, arguments[0]);", y)

    def scroll_into_view(self, locator, block=DEFAULT_SCROLL_BLOCK):
        """
        Прокручивает страницу так, чтобы элемент оказался в области просмотра.

        :param locator: (By, selector)
        :param block: Положение элемента ('start', 'center', 'end', 'nearest')
        :return: Элемент
        """
        el = self.wait.until(EC.presence_of_element_located(locator))
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: arguments[1]});",
            el, block
        )
        return el

    # === ОКНА / ФРЕЙМЫ ===

    def switch_to_last_window(self):
        """
        Переключается на последнюю вкладку.
        Не падает, если вкладок нет.
        """
        try:
            self.driver.switch_to.window(self.driver.window_handles[-1])
        except Exception:
            pass

    def switch_into_iframe_if_present(self, css):
        """
        Переключается во фрейм, если он присутствует.

        :param css: CSS-селектор фрейма
        :return: True, если переключение произошло
        """
        frames = self.driver.find_elements(By.CSS_SELECTOR, css)
        if frames:
            self.driver.switch_to.frame(frames[0])
            return True
        return False

    # === АРТЕФАКТЫ (ДЛЯ ДИАГНОСТИКИ) ===

    def save_artifacts(self, tag="debug"):
        """
        Сохраняет артефакты для анализа при ошибках:
        - Скриншот
        - HTML страницы
        - Логи браузера
        - Текстовый отчёт

        Артефакты сохраняются в ./artifacts/

        :param tag: Метка для группировки (например, 'auth_gate')
        :return: Словарь с путями к артефактам
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs(self.ARTIFACTS_DIR, exist_ok=True)

        # URL
        url = "<unknown>"
        try:
            url = self.driver.current_url
        except Exception:
            pass

        # Пути
        html_path = f"{self.ARTIFACTS_DIR}/{timestamp}_{tag}.html"
        png_path = f"{self.ARTIFACTS_DIR}/{timestamp}_{tag}.png"
        log_path = f"{self.ARTIFACTS_DIR}/{timestamp}_{tag}_console.json"
        txt_path = f"{self.ARTIFACTS_DIR}/{timestamp}_{tag}.txt"

        # HTML
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source or "")
        except Exception:
            html_path = "<html fail>"

        # Скриншот
        try:
            self.driver.save_screenshot(png_path)
        except WebDriverException:
            png_path = "<shot fail>"

        # Логи браузера
        logs = []
        try:
            logs = [entry for entry in self.driver.get_log("browser")]
        except Exception:
            pass

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "logs": logs}, f, ensure_ascii=False, indent=2)
        except Exception:
            log_path = "<log fail>"

        # Текстовый отчёт
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"URL: {url}\nTag: {tag}\nHTML: {html_path}\nScreenshot: {png_path}\nConsole: {log_path}\n")
        except Exception:
            txt_path = "<txt fail>"

        print(f"[ART] {tag} -> {png_path} | {html_path} | {log_path} | {txt_path}")

        return {
            "url": url,
            "html": html_path,
            "png": png_path,
            "log": log_path,
            "txt": txt_path
        }