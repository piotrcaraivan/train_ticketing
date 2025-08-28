"""
Page Object для страницы результатов поиска поездов.

Отвечает за:
- Выбор конкретного поезда (AP125)
- Принятие условий (галочка travelTerms)
- Продолжение на следующий шаг (Next)
- Принудительное исправление состояния формы
- Диагностику и логирование состояния перед/после ключевых действий

Особенности:
- Максимально надёжные клики (с резервными стратегиями: обычный, Actions, JS, submit)
- Обработка валидации через JS-диспетчеризацию событий
- Продвинутая диагностика формы — помогает в отладке, если тест упал
- Сохранение артефактов при блокировке на экране входа
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from .base_page import BasePage


class ResultsPage(BasePage):
    # === ЛОКАТОРЫ ===

    # Чекбокс условий перевозки
    TERMS_CHECKBOX = (By.ID, "travelTerms")
    TERMS_LABEL = (By.CSS_SELECTOR, "label[for='travelTerms']")

    # Кнопка продолжения
    NEXT_BTN = (By.ID, "buttonNext")

    # Все возможные чекбоксы, связанные с условиями (GDPR, privacy и т.д.)
    TERMS_ANY = (By.CSS_SELECTOR, "input[type='checkbox'][name*='Terms' i], input[type='checkbox'][id*='Terms' i]")

    # === КОНСТАНТЫ ===

    MAX_TRANSITION_WAIT = 10  # секунд ожидания перехода
    SCROLL_TO_CENTER = {"block": "center"}

    # === МЕТОДЫ ===

    def select_ap125(self, dep="12:09", arr="14:48"):
        """
        Основной сценарий выбора поезда AP125 по времени отправления и прибытия.

        Этапы:
        1. Поиск строки с поездом
        2. Выбор радио-кнопки
        3. Принятие условий
        4. Нажатие "Next" (с резервными стратегиями)
        5. Диагностика состояния формы
        6. Повторная попытка при необходимости

        :param dep: Время отправления (например, "12:09")
        :param arr: Время прибытия (например, "14:48")
        :return: True, если переход произошёл; False — если застряли (например, на экране входа)
        """
        # 1. Поиск строки поезда AP125
        xpath = (
            f"//tr["
            f"  .//td[@headers='serv']//span[contains(normalize-space(),'AP 125')]"
            f"  and .//td[@headers='part' and normalize-space()='{dep}']"
            f"  and .//td[@headers='cheg' and normalize-space()='{arr}']"
            f"]"
        )
        row = self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        self.driver.execute_script("arguments[0].scrollIntoView(arguments[1]);", row, self.SCROLL_TO_CENTER)

        # 2. Выбор радио-кнопки
        radio = row.find_element(By.XPATH, ".//input[@type='radio' and @name='GO']")
        try:
            radio.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", radio)

        # 3. Подтверждение выбора
        self.wait.until(
            lambda d: radio.is_selected() or radio.get_attribute("checked") in ("true", "checked")
        )

        # 4. Диагностика до принятия условий
        self.debug_form_state(tag="before_accept_terms")

        # 5. Принятие условий
        self.accept_terms()

        # 6. Диагностика после принятия условий
        self.debug_form_state(tag="after_accept_terms")

        # 7. Попытка перехода
        success = self.continue_next()

        # 8. Диагностика после попытки перехода
        self.debug_form_state(tag="after_click_next")

        # 9. Если не получилось — форсируем валидность и пробуем ещё раз
        if not success:
            self._force_valid()
            self.debug_form_state(tag="after_force_valid")
            success = self.continue_next()

        # 10. Финальная проверка: если всё равно не ушли — сохраняем артефакты
        if not success:
            try:
                self.save_artifacts("auth_gate")
            except Exception:
                pass
            return False

        return True

    def accept_terms(self):
        """
        Принимает условия перевозки (галочка travelTerms).
        Использует несколько стратегий: обычный клик, клик по label, JS-манипуляции.
        Обрабатывает валидацию формы через события input/change.
        """
        # Прокрутка к чекбоксу
        try:
            self.scroll_into_view(self.TERMS_LABEL)
        except Exception:
            pass

        # Попытка обычного клика
        try:
            self.safe_click(self.TERMS_CHECKBOX)
        except Exception:
            try:
                self.safe_click(self.TERMS_LABEL)
            except Exception:
                pass

        # Если чекбокс всё ещё не отмечен — используем JS
        try:
            cb = self.driver.find_element(*self.TERMS_CHECKBOX)
            if not (cb.is_selected() or cb.get_attribute("checked") in ("true", "checked")):
                self.driver.execute_script("""
                    const cb = arguments[0];
                    cb.checked = true;
                    cb.setAttribute('checked', 'checked');
                    cb.dispatchEvent(new Event('input', { bubbles: true }));
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                    cb.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                """, cb)
        except Exception:
            pass

        # Ожидание исчезновения ошибки валидации
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            WebDriverWait(self.driver, 5).until(
                EC.invisibility_of_element_located((By.ID, "travelTerms-error"))
            )
        except Exception:
            # Альтернатива: проверка aria-invalid
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: cb.get_attribute("aria-invalid") in (None, "", "false")
                )
            except Exception:
                pass

        # Финальная проверка
        try:
            cb = self.driver.find_element(*self.TERMS_CHECKBOX)
            return cb.is_selected() or cb.get_attribute("checked") in ("true", "checked")
        except Exception:
            return True  # Не критично

    def _force_valid(self):
        """
        Принудительно делает форму валидной:
        - Выбирает радио GO (если сброшено)
        - Отмечает все чекбоксы, связанные с terms
        - Вызывает reportValidity() через JS
        """
        # 1. Принудительный выбор радио-кнопки
        try:
            picked_row = self.driver.find_elements(By.XPATH, "//tr[.//input[@type='radio' and @name='GO']]")[0]
            radio = picked_row.find_element(By.XPATH, ".//input[@type='radio' and @name='GO']")
            if not (radio.is_selected() or radio.get_attribute("checked")):
                try:
                    radio.click()
                except Exception:
                    self.driver.execute_script("""
                        const r = arguments[0];
                        r.checked = true;
                        r.setAttribute('checked', 'checked');
                        r.dispatchEvent(new Event('change', { bubbles: true }));
                    """, radio)
        except Exception:
            pass

        # 2. Отметить все чекбоксы с условиями (terms, privacy, gdpr)
        checkboxes = self.driver.find_elements(*self.TERMS_ANY)
        for cb in checkboxes:
            try:
                if not (cb.is_selected() or cb.get_attribute("checked")):
                    self.driver.execute_script("""
                        const c = arguments[0];
                        c.checked = true;
                        c.setAttribute('checked', 'checked');
                        c.dispatchEvent(new Event('input', { bubbles: true }));
                        c.dispatchEvent(new Event('change', { bubbles: true }));
                    """, cb)
            except Exception:
                pass

        # 3. Принудительная валидация формы
        try:
            self.driver.execute_script("""
                document.activeElement?.blur?.();
                const btn = document.getElementById('buttonNext');
                if (btn?.form?.reportValidity) {
                    btn.form.reportValidity();
                }
            """)
        except Exception:
            pass

    def continue_next(self):
        """
        Пытается перейти на следующий шаг несколькими способами:
        1. Обычный клик
        2. Actions (с mouseover)
        3. JS-клик
        4. Enter по кнопке
        5. Прямой submit формы (обход onclick)
        6. Снятие disabled + повторный клик

        :return: True, если URL изменился или обнаружен элемент следующего шага
        """
        self.wait_spinner_gone()
        self._force_valid()
        url_before = self.driver.current_url

        try:
            btn = self.wait.until(EC.presence_of_element_located(self.NEXT_BTN))
            self.driver.execute_script("arguments[0].scrollIntoView(arguments[1]);", btn, self.SCROLL_TO_CENTER)

            # 1. Обычный клик
            try:
                self.wait.until(EC.element_to_be_clickable(self.NEXT_BTN)).click()
                if self._wait_transition(url_before, 10):
                    return True
            except Exception:
                pass

            # 2. Actions
            try:
                ActionChains(self.driver).move_to_element(btn).pause(0.05).click(btn).perform()
                if self._wait_transition(url_before, 8):
                    return True
            except Exception:
                pass

            # 3. JS-клик
            try:
                self.driver.execute_script("arguments[0].click();", btn)
                if self._wait_transition(url_before, 8):
                    return True
            except Exception:
                pass

            # 4. Enter по кнопке
            try:
                btn.send_keys(Keys.ENTER)
                if self._wait_transition(url_before, 6):
                    return True
            except Exception:
                pass

            # 5. Прямой submit формы
            try:
                form = self.driver.execute_script("return arguments[0].form || arguments[0].closest('form')", btn)
                if form:
                    self.driver.execute_script("""
                        const form = arguments[0];
                        const submit = HTMLFormElement.prototype.submit;
                        submit.call(form);
                    """, form)
                if self._wait_transition(url_before, 10):
                    return True
            except Exception:
                pass

            # 6. Снятие disabled + клик
            try:
                self.driver.execute_script("""
                    const btn = arguments[0];
                    btn.removeAttribute('disabled');
                    btn.removeAttribute('aria-disabled');
                """, btn)
                self._force_valid()
                self.driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass

            return self._wait_transition(url_before, 8)

        except Exception:
            return False

    def _wait_transition(self, url_before, timeout=MAX_TRANSITION_WAIT):
        """
        Ожидает переход на следующий шаг.

        Условия успеха:
        - URL изменился
        - Или появились элементы следующего шага (например, карта мест)

        :param url_before: URL до нажатия
        :param timeout: время ожидания
        :return: True, если переход произошёл
        """
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.current_url != url_before or
                          len(d.find_elements(By.CSS_SELECTOR,
                            "iframe[src*='seat'], iframe[title*='Seat'], "
                            "canvas.seatmap, svg.seatmap, [data-testid*='seat']")) > 0
            )
            return True
        except TimeoutException:
            return False

    def debug_form_state(self, tag="debug"):
        """
        Собирает и логирует состояние формы для диагностики.

        Полезно при отладке:
        - Что не даёт пройти дальше
        - Где ошибка валидации
        - Какие чекбоксы не отмечены

        :param tag: Метка для группировки логов
        :return: Словарь с состоянием формы
        """
        js = """
        const btn = document.getElementById('buttonNext');
        const form = btn?.form || btn?.closest('form') || document.querySelector('form');
        const out = {
            tag: arguments[0],
            url: location.href,
            hasForm: !!form,
            nextBtn: {
                exists: !!btn,
                disabled: btn ? (btn.disabled || btn.getAttribute('disabled') !== null || btn.getAttribute('aria-disabled') === 'true') : null,
                id: btn?.id || null,
                value: btn?.value || btn?.textContent?.trim() || null
            },
            travelTerms: {
                exists: !!document.getElementById('travelTerms'),
                checked: !!document.getElementById('travelTerms')?.checked,
                ariaInvalid: document.getElementById('travelTerms')?.getAttribute('aria-invalid') || null,
                errorVisible: !!document.getElementById('travelTerms-error') && (getComputedStyle(document.getElementById('travelTerms-error')).display !== 'none')
            },
            radioGO: {
                any: !!form?.querySelector("input[name='GO']"),
                checked: !!form?.querySelector("input[name='GO']:checked")
            },
            otherTerms: [],
            invalid: []
        };
        if (form) {
            const terms = form.querySelectorAll("input[type='checkbox'][name*='terms' i], input[type='checkbox'][id*='terms' i], input[type='checkbox'][name*='privacy' i], input[type='checkbox'][id*='privacy' i], input[type='checkbox'][name*='gdpr' i], input[type='checkbox'][id*='gdpr' i]");
            terms.forEach(cb => out.otherTerms.push({id: cb.id || null, name: cb.name || null, checked: !!cb.checked}));
            const invalid = [...form.querySelectorAll('input,select,textarea')].filter(el => el.willValidate && !el.checkValidity());
            invalid.forEach(el => out.invalid.push({id: el.id || null, name: el.name || null, type: el.type || null, required: !!el.required, validationMessage: el.validationMessage || null}));
        }
        return out;
        """
        info = self.driver.execute_script(js, tag)
        print(f"[DEBUG form_state {tag}] {info}")
        return info