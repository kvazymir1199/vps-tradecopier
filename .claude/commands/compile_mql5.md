# /compile - Компиляция MQL5

Команда для компиляции MQL5 файлов через Pepperstone MetaTrader 5.

## Использование

```
/compile [файл]
```

Если файл не указан, компилируется `Stage2.mq5`.

## Как это работает

MetaTrader 5 работает через Parallels (Windows VM). Компиляция выполняется через `metaeditor64.exe`.

### Команда компиляции

```bash
# Через Parallels prlctl
prlctl exec "Windows 11" "C:\Program Files\Pepperstone MetaTrader 5\metaeditor64.exe" /compile:"<путь_к_файлу>" /log:"compile.log"
```

### Альтернатива: через общую папку

Если файлы синхронизируются через Parallels Shared Folders:

```bash
# Windows путь к проекту
C:\Users\User\MQL5_Dev\Experts\Michael Spiropoulos\Stage2.mq5

# Или через Parallels mount
\\Mac\Home\MQL5_Dev\Experts\Michael Spiropoulos\Stage2.mq5
```

## Что делать

1. **Проверь путь к MT5** — убедись что Pepperstone MT5 установлен
2. **Запусти компиляцию** — используй команду выше
3. **Проверь логи** — `compile.log` содержит ошибки и предупреждения

## Парсинг результатов

После компиляции проверь:

- **0 error(s)** — успешная компиляция
- **X error(s)** — есть ошибки, нужно исправить
- **X warning(s)** — предупреждения (можно игнорировать, но лучше исправить)

## Типичные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `'identifier' - undeclared identifier` | Не объявлена переменная/функция | Проверь include файлы |
| `'=' - l-value required` | Попытка присвоить значение константе | Проверь const модификаторы |
| `cannot open file` | Файл не найден | Проверь путь к include |
| `struct has no members` | Пустая структура | Добавь хотя бы одно поле |

## Примечания

- Компиляция требует запущенной Windows VM в Parallels
- MetaEditor должен быть закрыт во время компиляции через CLI
- Результат сохраняется в `.ex5` файл рядом с исходником
