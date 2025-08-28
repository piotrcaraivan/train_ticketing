"""
Page Object для страницы покупки билетов.

Отвечает за:
- Заполнение станций отправления и назначения
- Выбор даты через календарь
- Установку количества пассажиров
- Отправку формы поиска
- Первичное взаимодействие с результатами (выбор поезда)

Особенности:
- Учитывает виртуализацию списка результатов (прокрутка для подгрузки)
- Обрабатывает возможные оверлеи и задержки
- Использует комбинированные стратегии кликов (JS + обычный) для надёжности
"""

from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base_page import BasePage


class BuyPage(BasePage):
    # === ЛОКАТОРЫ ===

    # Поля ввода станций
    FROM_INPUT = (By.CSS_SELECTOR, "input[name='textBoxPartida']")
    FROM_OPTION = (By.XPATH, "//li//a[contains(., 'Lisboa') and contains(., 'Oriente')]")
    TO_INPUT = (By.CSS_SELECTOR, "input[name='textBoxChegada']")
    TO_OPTION = (By.XPATH, "//li//a[contains(., 'Porto') and contains(., 'Campanha')]")

    # Календарь
    DATE_INPUT = (By.CSS_SELECTOR, "input[name='departDate'], input[placeholder*='Date']")
    CAL_PANEL = (By.CSS_SELECTOR, ".picker__frame, .picker__holder")
    CAL_MONTH = (By.CSS_SELECTOR, ".picker__month")
    CAL_YEAR = (By.CSS_SELECTOR, ".picker__year")
    NEXT_BTN = (By.CSS_SELECTOR, ".picker__nav--next")

    # Пассажиры
    PASSENGERS_DROPDOWN = (By.CSS_SELECTOR, "button[data-id='nr_passageiros']")
    FOUR_PASSENGERS_OPT = (By.XPATH, "//span[contains(.,'4 Passengers')]")

    # Кнопка поиска
    SUBMIT_BTN = (By.CSS_SELECTOR, "input[type='submit'][value*='Submit']")

    # Элементы, связанные с результатами (для ожидания)
    RESULT_ROW = (By.CSS_SELECTOR, "[data-testid='solution-row'], .solution-row, .journey-row, table.timetable")
    OVERLAY = (By.CSS_SELECTOR, ".overlay, .spinner, [aria-busy='true'], [data-testid='loading'], .loading")

    # Константы
    MAX_CALENDAR_MONTHS = 12  # Максимум месяцев вперёд для поиска
    MAX_SCROLL_ATTEMPTS = 8  # Максимальное число прокруток для подгрузки результатов
    SCROLL_STEP = 600        # Пикселей за одну прокрутку

    # === МЕТОДЫ ===

    def set_from(self, station_name="Lisboa Oriente"):
        """
        Вводит станцию отправления и выбирает её из выпадающего списка.

        :param station_name: Название станции (по умолчанию — Lisboa Oriente)
        :return: Фактическое значение поля после выбора
        """
        input_field = self.type(self.FROM_INPUT, station_name)
        self.click(self.FROM_OPTION)
        return input_field.get_attribute("value")

    def set_to(self, station_name="Porto Campanha"):
        """
        Вводит станцию назначения и выбирает её из выпадающего списка.

        :param station_name: Название станции (по умолчанию — Porto Campanha)
        :return: Фактическое значение поля после выбора
        """
        input_field = self.type(self.TO_INPUT, station_name)
        self.click(self.TO_OPTION)
        return input_field.get_attribute("value")

    def open_calendar(self):
        """
        Открывает календарь выбора даты.
        Прокручивает к полю и кликает по нему (включая JS-обход, если нужно).
        """
        date_input = self.wait.until(EC.visibility_of_element_located(self.DATE_INPUT))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", date_input)
        try:
            self.click(self.DATE_INPUT)
        except Exception:
            self.driver.execute_script("arguments[0].click();", date_input)
        self.wait.until(EC.visibility_of_element_located(self.CAL_PANEL))

    def pick_date(self, day=24, month_name="September", year=None):
        """
        Выбирает дату в календаре.

        :param day: День (число)
        :param month_name: Название месяца (на английском)
        :param year: Год (по умолчанию — текущий)
        :return: Значение поля даты после выбора
        """
        if year is None:
            year = datetime.now().year

        self.open_calendar()

        # Перелистываем к нужному месяцу
        for _ in range(self.MAX_CALENDAR_MONTHS):
            current_month = self.driver.find_element(*self.CAL_MONTH).text.strip()
            current_year = self.driver.find_element(*self.CAL_YEAR).text.strip()
            if current_month == month_name and str(current_year) == str(year):
                break
            self.click(self.NEXT_BTN)
        else:
            raise RuntimeError(f"Не удалось найти месяц: {month_name} {year}")

        # Выбираем день
        day_locator = (By.XPATH, f"//div[contains(@class,'picker__day') "
                                 f"and not(contains(@class,'disabled')) "
                                 f"and normalize-space()='{day}']")
        self.click(day_locator)

        return self.driver.find_element(*self.DATE_INPUT).get_attribute("value")

    def set_passengers(self, count=4):
        """
        Устанавливает количество пассажиров через выпадающий список.

        :param count: Количество пассажиров (по умолчанию — 4)
        :return: Текст кнопки после выбора (например, "4 Passengers")
        """
        self.click(self.PASSENGERS_DROPDOWN)
        passenger_option = self.wait.until(EC.element_to_be_clickable(self.FOUR_PASSENGERS_OPT))
        passenger_option.click()
        return self.driver.find_element(*self.PASSENGERS_DROPDOWN).text

    def search_trains(self):
        """
        Отправляет форму поиска поездов.

        Обрабатывает:
        - Открытие новой вкладки (если есть)
        - Ожидание полной загрузки страницы
        - Исчезновение спиннеров
        - Появление результатов (с прокруткой, если нужно)

        :return: URL страницы с результатами
        """
        handles_before = self.driver.window_handles[:]

        # Кликаем по кнопке отправки (с резервным вариантом через JS)
        try:
            self.safe_click(self.SUBMIT_BTN)
        except Exception:
            submit_btn = self.wait.until(EC.presence_of_element_located(self.SUBMIT_BTN))
            self.driver.execute_script("arguments[0].click();", submit_btn)

        # Ожидание новой вкладки
        self.wait.until(lambda d: len(d.window_handles) >= len(handles_before))
        if len(self.driver.window_handles) > len(handles_before):
            self.driver.switch_to.window(self.driver.window_handles[-1])

        # Ожидание полной загрузки страницы
        self.safe_wait(lambda d: d.execute_script("return document.readyState") == "complete")

        # Исчезновение оверлеев
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            WebDriverWait(self.driver, 6).until(EC.invisibility_of_element_located(self.OVERLAY))
        except Exception:
            pass  # Оверлея может не быть

        # Проверка наличия результатов
        try:
            self.safe_wait(EC.presence_of_element_located(self.RESULT_ROW), timeout=5)
        except Exception:
            # Пробуем прокруткой пробудить виртуализированный список
            for _ in range(self.MAX_SCROLL_ATTEMPTS):
                self.scroll_by(self.SCROLL_STEP)
                try:
                    self.safe_wait(EC.presence_of_element_located(self.RESULT_ROW), timeout=2)
                    break
                except Exception:
                    continue

        # Прокрутка первого результата к центру (улучшает стабильность)
        try:
            first_row = self.driver.find_elements(*self.RESULT_ROW)[0]
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_row)
        except Exception:
            pass  # Не критично

        return self.driver.current_url

    def pick_train(self, train_no: str, dep_time: str, arr_time: str):
        """
        Выбирает поезд по номеру, времени отправления и прибытия.

        Особенности:
        - Прокручивает страницу, если результаты не видны
        - Обходит оверлеи
        - Использует JS-клик как fallback

        :param train_no: Номер поезда (например, "AP125")
        :param dep_time: Время отправления (например, "12:09")
        :param arr_time: Время прибытия (например, "14:48")
        """
        # Прокрутка для подгрузки результатов
        for _ in range(self.MAX_SCROLL_ATTEMPTS):
            try:
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(., 'AP') and contains(., ':')]")
                ))
                break
            except Exception:
                self.scroll_by(self.SCROLL_STEP)

        # XPATH для поиска строки по содержимому
        xpath_row = (
            f"//*[contains(normalize-space(.), '{train_no}') and "
            f"contains(., '{dep_time}') and contains(., '{arr_time}')]"
            "//ancestor::*[self::tr or self::div][1]"
        )
        row = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath_row)))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)

        # Ожидание исчезновения оверлея перед кликом
        try:
            self.safe_wait(EC.invisibility_of_element_located(self.OVERLAY), timeout=5)
        except Exception:
            pass

        # Поиск радио-кнопки выбора поезда
        try:
            radio = row.find_element(By.CSS_SELECTOR, "input.selectTripGO[name='GO'][type='radio']")
        except Exception:
            radio = row.find_element(By.CSS_SELECTOR, "input[type='radio']")

        # Клик (с резервным JS)
        try:
            radio.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", radio)

        # Нажатие на кнопку "Continue" в строке (если есть)
        buttons = row.find_elements(By.CSS_SELECTOR, "button,[role='button']")
        if buttons:
            try:
                buttons[-1].click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", buttons[-1])