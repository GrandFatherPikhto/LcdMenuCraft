# ⚙️ Генерируемый C-код: архитектура и встраивание

> В этом документе описано, что генерируют Jinja2-шаблоны, как устроен
> генерируемый C-код, как им пользоваться и как встраивать его в прошивку
> **STM32** или **ESP32**.
>
> Сопутствующие документы: [architect_ru.md](./architect_ru.md) ·
> [changes_ru.md](./changes_ru.md) · [tests_ru.md](./tests_ru.md).

---

## 1. Общее описание

Генератор превращает декларативный конфиг меню в **самодостаточный C-модуль**
системы меню для встраиваемого дисплея LCD1602. Сгенерированный код:

- написан на **C11** и зависит только от стандартной библиотеки C плюс
  необязательного пользовательского заголовка (`pulse_config.h`,
  см. [Пользовательские колбэки](#6-пользовательские-колбэки));
- **не использует** динамическое выделение памяти (`malloc`), **не использует**
  вещественную арифметику и **не зависит** от ОС/RTOS — подходит для bare-metal
  сборки на STM32F103 или ESP32;
- хранит **только для чтения данные во flash** (`static const` таблицы), а в RAM
  держит лишь небольшой изменяемый массив текущих значений;
- управляется через один небольшой публичный API в [`menu.h`](../output/include/menu.h).

Всё построено на **таблицах**: конфигурация узлов, дерево навигационных связей и
таблица значений — это `static const` массивы, а поведение диспетчеризуется через
указатели на функции, хранящиеся в конфигурации узла.

---

## 2. Что получается на выходе

[`config/files.yaml`](../config/files.yaml) сопоставляет каждый Jinja2-шаблон с
выходным файлом. Запуск `python generate_menu.py` из корня проекта записывает в
[`output/`](../output):

| Выходной файл | Шаблон | Назначение |
|---------------|--------|------------|
| `menu.c` / `include/menu.h` | `handle.c.jinja` / `handle.h.jinja` | Верхнеуровневый публичный API |
| `menu_context.c` / `include/menu_context.h` | `context.c.jinja` / `context.h.jinja` | Структура контекста меню + инициализация |
| `include/menu_type.h` | `type.h.jinja` | enum'ы (id, категории, события, состояния), `LCD_STRING_LEN` |
| `include/menu_config.h` | `config.h.jinja` | Структуры конфигурации узлов + typedef'ы колбэков |
| `menu_data_tree.c` / `include/menu_tree.h` | `data_tree.c.jinja` / `tree.h.jinja` | Статическое дерево узлов + связи навигации |
| `menu_data_config.c` / `include/menu_data_config.h` | `data_config.c.jinja` / `data_config.h.jinja` | Статическая таблица конфигураций узлов |
| `menu_data_context.c` / `include/menu_data_context.h` | `data_context.c.jinja` / `data_context.h.jinja` | Доступ к глобальному контексту |
| `menu_data_value.c` / `include/menu_data_value.h` | `data_value.c.jinja` / `data_value.h.jinja` | Изменяемая таблица значений + доступ |
| `menu_data_name.c` / `include/menu_data_name.h` | `data_name.c.jinja` / `data_name.h.jinja` | Таблица имён узлов + поиск |
| `include/menu_value.h` | `value.h.jinja` | Структуры значений по категориям |
| `menu_navigate.c` / `include/menu_navigate.h` | `navigate.c.jinja` / `navigate.h.jinja` | Навигация (position / enter / back) |
| `menu_edit.c` / `include/menu_edit.h` | `edit.c.jinja` + `edit_*.c.jinja` | Колбэки редактирования значений |
| `menu_draw.c` / `include/menu_draw.h` | `draw.c.jinja` + `draw_*.c.jinja` | Отрисовка в буферы title/value |
| `menu_name.c` / `include/menu_name.h` | `name.c.jinja` / `name.h.jinja` | Хелперы поиска имён узлов |
| `menu_value_access.c` / `include/menu_value_access.h` | `value_access.c.jinja` / `value_access.h.jinja` | Общие `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32` |

Дополнительно записываются два отладочных артефакта: `output/flatterned.json`
(плоский список дерева) и `output/functions.json` (реестр функций).

---

## 3. Модель данных генерируемого кода

### 3.1 enum'ы ([`menu_type.h`](../output/include/menu_type.h))

- `LCD_STRING_LEN` (0x20 = 32) и `LCD_NUM_STRINGS` (2) задают буферы дисплея.
- `menu_id_t` — по одному значению на узел меню (`MENU_ID_ROOT = 0`, далее id всех
  узлов, в конце `MENU_ID_COUNT`).
- `menu_category_t` — категория узла (`STRING_FIXED`, `CALLBACK_CALLBACK`,
  `UDWORD_FACTOR`, `UBYTE_SIMPLE`, …). Категория выводится из пары
  `type` + `role` конфига.
- `menu_event_t` — `CHANGE_VALUE`, `FOCUSED`, `UNFOCUSED`, `START_EDIT`,
  `STOP_EDIT`.
- `menu_state_t` — `NAVIGATION` или `EDIT`.

### 3.2 Контекст ([`menu_context.h`](../output/include/menu_context.h))

```c
typedef struct menu_context {
    menu_id_t current;          // текущий узел
    menu_id_t previous;         // узел, из которого пришли
    menu_state_t state;         // NAVIGATION / EDIT
    bool dirty;                 // требуется перерисовка
    bool update;                // перерисовка выполнена, буферы готовы
    menu_node_value_t *values;  // изменяемый массив значений листьев (RAM)
    const menu_node_config_t *configs;  // статическая конфигурация узлов (flash)
    const menu_node_t *nodes;           // статическое дерево (flash)
    const menu_node_name_t *names;      // статическая таблица имён (flash)
    char title_buf[LCD_STRING_LEN];
    char value_buf[LCD_STRING_LEN];
} menu_context_t;
```

### 3.3 Конфигурация узла ([`menu_config.h`](../output/include/menu_config.h))

`menu_node_config_t` содержит id узла, категорию, статический `tag` (см. ниже),
шесть указателей на колбэки и `union` категорие-специфичных статических данных:

- `string_fixed_config_t` — `values[]` (набор строк) + `count` + `default_idx` +
  `raw_values` (см. ниже);
- `udword_factor_config_t` — `min`, `max`, `step`, `default_value`, `factors[]`,
  `count`, `default_idx`;
- `ubyte_simple_config_t` — `default_value`, `step`, `min`, `max`.

Каждая категория с ролью `fixed` также несёт `const int32_t *raw_values;` —
`NULL`, если узел не задал `raw_values:` в menu YAML (массив, параллельный
`values` по индексу, той же длины, с реальным числом за каждой строкой отображения,
например кодом регистра). [`menu_get_int32`/`menu_set_int32`](#41-общий-доступ-к-значению-menuvalueaccesshoutputincludemenuvalueaccessh)
используют его вместо сырого индекса, если он задан; существующие меню, где
это поле не задано, не затрагиваются. Рассинхрон длины с `values` — это ошибка
валидации (`MenuValidator`), а не молчаливый баг, найденный на железе.

`tag` — необязательный `uint32_t`, задаётся ключом `tag:` узла в menu YAML (0,
если не задан) — произвольные статические метаданные, например адрес
аппаратного регистра; позволяет заменить ручной `switch (id)` циклом по
`MENU_ID_COUNT` (например, `if (ctx->configs[id].tag) spi_write_reg(ctx->configs[id].tag, menu_get_int32(ctx, id));`).
Живёт в **статической конфигурации**, а не в изменяемом union значения —
это свойство дерева, а не состояние выполнения.

### 3.4 Значение узла ([`menu_value.h`](../output/include/menu_value.h))

`menu_node_value_t` — единственное **изменяемое** хранилище на узел, с тем же
`union`:

- `string_fixed_value_t` — `idx`;
- `callback_callback_value_t` — `value_ptr`;
- `udword_factor_value_t` — `idx` + `value`;
- `ubyte_simple_value_t` — `value`.

---

## 4. Как работает код во время выполнения

Весь модуль используется через [`menu.h`](../output/include/menu.h):

| Функция | Назначение |
|---------|------------|
| `menu_init()` | Обнуляет контекст и связывает статические таблицы |
| `menu_position(int8_t delta)` | Поворот энкодера → навигация / изменение значения |
| `menu_enter()` | Подтверждение / вход в подменю / начало редактирования; если уже в редактировании — вызывает `click_cb` |
| `menu_back()` | Назад к родителю / выход из режима редактирования |
| `menu_click()` | Короткий клик с учётом состояния: `menu_enter()` вне редактирования, `menu_back()` в редактировании |
| `menu_long_click()` | Долгий клик с учётом состояния: зеркально `menu_click()` — `menu_back()` вне редактирования, `menu_enter()` в редактировании |
| `menu_update()` | Если `dirty` — перерисовка в `title_buf` / `value_buf` |
| `menu_needs_redraw()` / `menu_ack_redraw()` | Проверка и сброс флага перерисовки |
| `menu_title_buf()` / `menu_value_buf()` | Указатели на заполненные буферы |
| `menu_set_dirty()` / `menu_state()` | Принудительная перерисовка / текущее состояние |

Типичное использование в главном цикле прошивки:

```c
// из обработки ввода (ISR кнопки, энкодер):
menu_position(delta);      // поворот энкодера
menu_click();               // короткий клик: войти глубже / выйти из редактирования
menu_long_click();           // долгий клик: уровень выше / сменить множитель в редактировании
menu_set_dirty();          // пометить, что дисплей нужно обновить

// из главного цикла:
menu_update();                          // заполняет title_buf / value_buf если dirty
if (menu_needs_redraw()) {
    lcd_goto(0, 0); lcd_puts(menu_title_buf());
    lcd_goto(0, 1); lcd_puts(menu_value_buf());
    menu_ack_redraw();
}
```

> 💡 `menu_click()`/`menu_long_click()` существуют потому, что `menu_enter()`/
> `menu_back()` уже означают разное в зависимости от `menu_state()` (войти
> глубже vs. сменить множитель, выйти из редактирования vs. уровень выше) —
> они просто выбирают, какой из двух примитивов вызвать под конкретный жест,
> чтобы прошивке не нужно было самой ветвиться по `menu_state()`.
> `menu_enter()`/`menu_back()` по-прежнему доступны напрямую, если нужно
> связать жесты с состоянием как-то иначе.

### 4.1 Общий доступ к значению ([`menu_value_access.h`](../output/include/menu_value_access.h))

Чтение или запись «текущего значения» листа обычно требует знать его
категорию (чтобы выбрать нужный член `union` — `.value` для
`simple`/`factor`, `.idx` для `fixed`). `menu_get_int32`/`menu_set_int32`/
`menu_get_uint32`/`menu_set_uint32` делают эту диспетчеризацию сами через
сгенерированный `switch (ctx->configs[id].category)` — можно пройти циклом
по `MENU_ID_COUNT` вместо ручного `switch` на каждый id узла:

```c
int32_t  menu_get_int32(menu_context_t *ctx, menu_id_t id);
void     menu_set_int32(menu_context_t *ctx, menu_id_t id, int32_t value);
uint32_t menu_get_uint32(menu_context_t *ctx, menu_id_t id);
void     menu_set_uint32(menu_context_t *ctx, menu_id_t id, uint32_t value);
```

Для значений `udword` выше `INT32_MAX` используйте пару `uint32_t` — пара
`int32_t` их некорректно интерпретирует.

Для узлов с ролью `fixed` эти функции читают/пишут `raw_values[idx]`, если у
узла задано `raw_values:`, иначе — сырой `idx` (см. [§3.3](#33-конфигурация-узла-menuconfighoutputincludemenuconfigh));
`menu_set_*` делает линейный поиск по `raw_values` (списки в меню короткие) и
оставляет `idx` без изменений, если значение не найдено — заметное отсутствие
изменения лучше, чем подстановка приблизительного индекса.

Вместе с [`tag`](#33-конфигурация-узла-menuconfighoutputincludemenuconfigh)
свитч отображения id → регистр схлопывается в:

```c
for (menu_id_t id = 0; id < MENU_ID_COUNT; id++) {
    if (ctx->configs[id].tag != 0) {
        hw_write_register(ctx->configs[id].tag, menu_get_int32(ctx, id));
    }
}
```

---

## 5. Модель отрисовки

[`menu_draw.c`](../output/menu_draw.c) предоставляет `menu_draw_update(ctx, id)`,
которая:

1. очищает `title_buf` / `value_buf`;
2. копирует `nodes[id].title` в `title_buf`;
3. для **листа** вызывает `draw_value_cb` узла (автогенерируемый для
   `simple`/`factor`/`fixed`, либо ваш собственный для узлов `callback`);
4. для **ветки** просто записывает `>` в `value_buf`.

Хелпер `menu_draw_line_marker()` дописывает маркер состояния на **правый край**
строки: `>` в режиме навигации, `*` при редактировании. Позиция маркера
вычисляется, а не зашита числом:

```c
#define MENU_LINE_LEN (LCD_STRING_LEN / LCD_NUM_STRINGS)   // 32 / 2 = 16
```

поэтому она остаётся корректной при смене дисплея или `LCD_STRING_LEN`.

---

## 6. Пользовательские колбэки

Колбэки делятся на две группы:

- **Автогенерируемые** — генератор создаёт и подключает их сам (например,
  `menu_draw_string_fixed_value_cb`, `string_fixed_click_cyclic_cb`,
  `udword_factor_position_limit_cb`, `ubyte_simple_position_limit_cb`).
- **Пользовательские** — для узлов с ролью `callback` (или явных кастомных
  колбэков в конфиге) генератор только *объявляет* их; **тела вы должны написать
  сами**.

Для встроенного [`menu/menu.yaml`](../menu/menu.yaml) генератор ссылается на
следующие функции, но **не реализует** их:

| Функция | Объявлена в | Сигнатура |
|---------|-------------|-----------|
| `draw_version_cb` | `menu_draw.h` | `void (menu_context_t *ctx, menu_id_t id)` |
| `pwm_frequency_display_cb` | `menu_draw.h` | `void (menu_context_t *ctx, menu_id_t id)` |
| `pwm_frequency_change_cb` | `menu_edit.h` | `void (menu_context_t *ctx, menu_id_t id, int8_t delta)` |
| `my_event_cb` | **нигде** — объявите сами | `void (menu_context_t *ctx, menu_id_t id, menu_event_t event)` |

> ⚠️ `my_event_cb` используется как `event_cb` для нескольких узлов, но ни один
> сгенерированный заголовок его не объявляет. Объявление и реализацию нужно
> написать самостоятельно.

`menu_data_config.c` подключает пользовательский заголовок `pulse_config.h`
(перечислен в `include_files` в `menu/menu.yaml`). Для встроенного конфига
заголовок должен выглядеть примерно так:

```c
#ifndef PULSE_CONFIG_H
#define PULSE_CONFIG_H

#include "menu_type.h"

void my_event_cb(menu_context_t *ctx, menu_id_t id, menu_event_t event);
void draw_version_cb(menu_context_t *ctx, menu_id_t id);
void pwm_frequency_display_cb(menu_context_t *ctx, menu_id_t id);
void pwm_frequency_change_cb(menu_context_t *ctx, menu_id_t id, int8_t delta);

#endif /* PULSE_CONFIG_H */
```

---

## 7. Встраивание в STM32 / ESP32

1. **Скопируйте модуль** — перенесите `output/*.c` и `output/include/*.h` в дерево
   исходников вашего проекта (например, в папку `menu/`) и добавьте `.c`-файлы в
   сборку (CMake, Makefile, PlatformIO, STM32CubeIDE и т.д.).
2. **Добавьте include-путь** — укажите компилятору папку, где лежат `menu*.h`.
3. **Создайте `pulse_config.h`** (или измените `include_files` в конфиге меню и
   перегенерируйте) с объявлениями и реализациями пользовательских колбэков.
4. **Подключите ввод** — вызывайте `menu_position()` из кода энкодера, а
   `menu_click()`/`menu_long_click()` (либо напрямую `menu_enter()`/`menu_back()`)
   из кода кнопок (ISR или опрашиваемая задача).
5. **Управляйте дисплеем** — в главном цикле вызывайте `menu_update()` и копируйте
   оба буфера на LCD, как показано в [§4](#4-как-работает-код-во-время-выполнения).
6. **Оптимизируйте под целевой контроллер** — для STM32F103 используйте
   `--specs=nano.specs` (newlib-nano); `-fshort-enums` уменьшит размер enum'ов.
   Модуль достаточно автономен, чтобы собираться с `-ffreestanding`, если вы
   предоставите `memcpy`/`strlen`/`snprintf`.

Сгенерированный код не вызывает API HAL/Arduino, поэтому он переносим между STM32,
ESP32 и другими bare-metal платформами; зависимым от железа остаётся только ваша
«обвязка» дисплея и ввода.

---

## 8. Замечания по размеру

- В RAM живут только `s_menu_values[18]` (изменяемый массив `menu_node_value_t`)
  и контекст — примерно **300–350 байт** суммарно для встроенного меню.
- Все таблицы конфигураций/дерева/имён — `static const` и размещаются во **flash**.
- Нет `malloc`, нет рекурсии, нет вещественной арифметики — детерминированно и
  безопасно для небольших микроконтроллеров.
