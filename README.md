# CP.pt Train Ticket Automation 🎟️

Автоматизация покупки билета на сайте [cp.pt](https://www.cp.pt/passageiros/en) с помощью **Python + Selenium**, реализованная по паттерну **Page Object**.

## 🚀 Сценарий
Тест автоматизирует следующий процесс:
- **Маршрут:** Lisboa Oriente → Porto Campanha  
- **Поезд:** AP 125 (12:09 → 14:48)  
- **Дата:** 24 сентября  
- **Пассажиры:** 2 взрослых + 2 ребёнка  
- **Класс:** Turistic  
- Скрипт доходит до шага выбора мест. Дальнейшее выполнение останавливается на экране авторизации (без тестовой учётной записи пройти нельзя).

## 📂 Структура проекта
train_ticketing/
│
├── pages/ # Модуль Page Object
│ ├── base_page.py # Базовый класс (ожидания, клики, ввод, артефакты)
│ ├── buy_page.py # Страница покупки билета (From/To, дата, пассажиры, submit)
│ ├── results_page.py # Страница результатов (выбор поезда, согласие с условиями, Continue)
│ └── auth_page.py # Экран авторизации (фиксация login-gate)
│
├── main.py # Основной сценарий
├── requirements.txt # Зависимости
└── artifacts/ # Скрины, HTML и логи (игнорируется в git)


## ⚙️ Установка и запуск
```bash
git clone https://github.com/piotrcaraivan/train_ticketing.git
cd train_ticketing
pip install -r requirements.txt
python main.py
