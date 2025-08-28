from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from .base_page import BasePage


class AuthPage(BasePage):
    # === ЛОКАТОРЫ ===

    # Кнопка "Continue" на экране входа
    NEXT_BTN = (By.ID, "buttonNext")

    # === КОНСТАНТЫ ===

    # Ключевые слова в URL, указывающие на экран аутентификации
    AUTH_INDICATORS = ["login", "signin", "mycp", "registo"]

    # CSS-селекторы полей ввода, характерных для формы входа
    LOGIN_INPUTS = (
        "input[type='email'], "
        "input[name*='user' i], "
        "input[name*='mail' i], "
        "input[type='password']"
    )

    # Время ожидания перехода после клика
    TRANSITION_TIMEOUT = 6

    # Тег по умолчанию для артефактов
    DEFAULT_ARTIFACT_TAG = "auth_gate_login"

    # === МЕТОДЫ ===

    def is_here(self):
        """
        Определяет, отображается ли экран аутентификации.

        Использует три эвристики:
        1. URL содержит ключевые слова (login, signin и т.д.)
        2. Присутствует кнопка "Continue"
        3. Есть поля ввода для email/логина/пароля

        :return: True, если, вероятно, мы на экране входа
        """
        # Проверка URL
        try:
            current_url = self.driver.current_url.lower()
            if any(indicator in current_url for indicator in self.AUTH_INDICATORS):
                return True
        except Exception:
            pass  # Игнорируем ошибки получения URL

        # Проверка наличия кнопки "Continue"
        if self.driver.find_elements(*self.NEXT_BTN):
            return True

        # Проверка наличия полей ввода (email, password и т.д.)
        login_inputs = self.driver.find_elements(By.CSS_SELECTOR, self.LOGIN_INPUTS)
        return len(login_inputs) > 0

    def click_continue_and_capture(self, tag=None):
        """
        Пытается нажать кнопку "Continue", чтобы пропустить экран входа.

        Если переход не происходит:
        - Сохраняет артефакты (скриншот, HTML, логи)
        - Возвращает False

        Использует резервные стратегии:
        1. Обычный клик
        2. JS-клик
        3. Прямой submit формы (обход onclick)

        :param tag: Метка для артефактов (по умолчанию — "auth_gate_login")
        :return: True, если URL изменился; False — если застряли
        """
        tag = tag or self.DEFAULT_ARTIFACT_TAG
        url_before = self.driver.current_url

        # Если кнопки нет — сразу сохраняем артефакты
        if not self.driver.find_elements(*self.NEXT_BTN):
            self.save_artifacts(tag)
            return False

        # Прокрутка к кнопке
        try:
            self.scroll_into_view(self.NEXT_BTN)
        except Exception:
            pass

        # Попытка кликнуть (обычный → JS)
        clicked = False
        try:
            self.click(self.NEXT_BTN)
            clicked = True
        except Exception:
            try:
                btn = self.driver.find_element(*self.NEXT_BTN)
                self.driver.execute_script("arguments[0].click();", btn)
                clicked = True
            except Exception:
                pass

        # Если не удалось кликнуть — сохраняем состояние
        if not clicked:
            self.save_artifacts(tag)
            return False

        # Ожидание перехода
        try:
            WebDriverWait(self.driver, self.TRANSITION_TIMEOUT).until(
                lambda d: d.current_url != url_before
            )
            return True
        except Exception:
            pass  # Переход не произошёл — пробуем обход

        # Финальная попытка: прямой submit формы
        try:
            btn = self.driver.find_element(*self.NEXT_BTN)
            form = self.driver.execute_script(
                "return arguments[0].form || arguments[0].closest('form')",
                btn
            )
            if form:
                self.driver.execute_script("""
                    const f = arguments[0];
                    const submit = HTMLFormElement.prototype.submit;
                    submit.call(f);
                """, form)
        except Exception:
            pass

        # Финальная проверка
        try:
            WebDriverWait(self.driver, self.TRANSITION_TIMEOUT).until(
                lambda d: d.current_url != url_before
            )
            return True
        except Exception:
            self.save_artifacts(tag)
            return False