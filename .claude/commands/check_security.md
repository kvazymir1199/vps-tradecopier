# /check-security - Проверка безопасности

Команда для проверки кода на наличие потенциальных проблем безопасности.

## Использование

```
/check-security
```

## Что проверяется

### 1. Hardcoded Credentials

Поиск паттернов:

```bash
grep -rn "password\s*=" Include/ Stage2.mq5
grep -rn "api_key\s*=" Include/ Stage2.mq5
grep -rn "secret\s*=" Include/ Stage2.mq5
grep -rn "token\s*=" Include/ Stage2.mq5
```

### 2. Чувствительные файлы

Проверка наличия в репозитории:

```bash
# Не должны быть в git
find . -name "*.env" -o -name "credentials*" -o -name "*secret*"

# Проверка .gitignore
cat .gitignore | grep -E "(env|credential|secret|key)"
```

### 3. API ключи в коде

```bash
# Поиск паттернов API ключей
grep -rn "[A-Za-z0-9]{32,}" Include/ Stage2.mq5
grep -rn "sk_live_" Include/ Stage2.mq5  # Stripe live keys
grep -rn "pk_live_" Include/ Stage2.mq5  # Stripe public keys
```

### 4. Небезопасные операции

```bash
# Поиск небезопасных функций
grep -rn "Shell(" Include/ Stage2.mq5        # Выполнение команд
grep -rn "WebRequest" Include/ Stage2.mq5    # HTTP запросы
grep -rn "FileOpen" Include/ Stage2.mq5      # Работа с файлами
```

## Чеклист безопасности

- [ ] Нет hardcoded паролей и ключей
- [ ] `.gitignore` содержит `.env`, `credentials*`, `*secret*`
- [ ] Нет API ключей в исходном коде
- [ ] WebRequest использует HTTPS
- [ ] FileOpen не читает системные файлы
- [ ] Shell() не используется (или используется безопасно)

## Рекомендации

### Хранение секретов

Для MQL5 используй:

1. **Файлы конфигурации** (не в git):
   ```cpp
   string ReadConfig(string key) {
      int handle = FileOpen("config.ini", FILE_READ|FILE_TXT|FILE_COMMON);
      // ...
   }
   ```

2. **Переменные окружения** (через внешний скрипт):
   ```cpp
   input string InpApiKey = "";  // Передаётся при запуске
   ```

### Безопасный WebRequest

```cpp
// ХОРОШО: HTTPS
WebRequest("POST", "https://api.example.com/webhook", ...);

// ПЛОХО: HTTP
WebRequest("POST", "http://api.example.com/webhook", ...);
```

## Примечания

- Эта проверка не заменяет полноценный аудит безопасности
- Для production систем рекомендуется внешний код-ревью
- MQL5 имеет ограниченные возможности безопасности по сравнению с серверными языками
