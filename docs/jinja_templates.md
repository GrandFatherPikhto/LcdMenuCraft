# ⚙️ Generated C Code: Architecture & Integration

> This document describes what the Jinja2 templates generate, how the generated C
> code is structured, how to use it, and how to integrate it into an **STM32** or
> **ESP32** firmware.
>
> Companion docs: [architect.md](./architect.md) · [changes.md](./changes.md) ·
> [tests.md](./tests.md).

---

## 1. Overview

The generator turns the declarative menu configuration into a **self-contained C
module** for an embedded LCD1602 menu system. The generated code:

- is plain **C11** and depends only on the C standard library plus an optional,
  user-supplied header (`pulse_config.h`, see [User callbacks](#6-user-callbacks));
- uses **no dynamic memory allocation** (`malloc`), **no floating point**, and **no
  OS/RTOS primitives** — it fits a bare-metal STM32F103 or ESP32 build;
- keeps **read-only data in flash** (`static const` tables) and only a small mutable
  array of current values in RAM;
- is driven through one small public API in [`menu.h`](../output/include/menu.h).

Everything is **table-driven**: per-node configuration, the tree of navigation links
and the value table are `static const` arrays, and behaviour is dispatched through
function pointers stored in the node config.

---

## 2. What the generator produces

[`config/files.yaml`](../config/files.yaml) maps every Jinja2 template to an output
file. Running `python generate_menu.py` from the project root writes into
[`output/`](../output):

| Output file | Template | Purpose |
|-------------|----------|---------|
| `menu.c` / `include/menu.h` | `handle.c.jinja` / `handle.h.jinja` | Top-level public API |
| `menu_context.c` / `include/menu_context.h` | `context.c.jinja` / `context.h.jinja` | Menu context struct + init |
| `include/menu_type.h` | `type.h.jinja` | Enums (ids, categories, events, states), `LCD_STRING_LEN` |
| `include/menu_config.h` | `config.h.jinja` | Per-node config structs + callback typedefs |
| `menu_data_tree.c` / `include/menu_tree.h` | `data_tree.c.jinja` / `tree.h.jinja` | Static tree of nodes + navigation links |
| `menu_data_config.c` / `include/menu_data_config.h` | `data_config.c.jinja` / `data_config.h.jinja` | Static per-node config table |
| `menu_data_context.c` / `include/menu_data_context.h` | `data_context.c.jinja` / `data_context.h.jinja` | Global context accessor |
| `menu_data_value.c` / `include/menu_data_value.h` | `data_value.c.jinja` / `data_value.h.jinja` | Mutable value table + accessor |
| `menu_data_name.c` / `include/menu_data_name.h` | `data_name.c.jinja` / `data_name.h.jinja` | Node name table + lookup |
| `include/menu_value.h` | `value.h.jinja` | Per-category value structs |
| `menu_navigate.c` / `include/menu_navigate.h` | `navigate.c.jinja` / `navigate.h.jinja` | Navigation (position / enter / back) |
| `menu_edit.c` / `include/menu_edit.h` | `edit.c.jinja` + `edit_*.c.jinja` | Value editing callbacks |
| `menu_draw.c` / `include/menu_draw.h` | `draw.c.jinja` + `draw_*.c.jinja` | Drawing into title/value buffers |
| `menu_name.c` / `include/menu_name.h` | `name.c.jinja` / `name.h.jinja` | Node-name lookup helpers |
| `menu_value_access.c` / `include/menu_value_access.h` | `value_access.c.jinja` / `value_access.h.jinja` | Generic `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32` |

Two debug artifacts are also written: `output/flatterned.json` (the flattened tree)
and `output/functions.json` (the function inventory).

---

## 3. Generated data model

### 3.1 Enums ([`menu_type.h`](../output/include/menu_type.h))

- `LCD_STRING_LEN` (0x20 = 32) and `LCD_NUM_STRINGS` (2) define the display buffers.
- `menu_id_t` — one value per menu node (`MENU_ID_ROOT = 0`, then every node id, then
  `MENU_ID_COUNT`).
- `menu_category_t` — category of each node (`STRING_FIXED`, `CALLBACK_CALLBACK`,
  `UDWORD_FACTOR`, `UBYTE_SIMPLE`, …). The category is derived from the config
  `type` + `role` pair.
- `menu_event_t` — `CHANGE_VALUE`, `FOCUSED`, `UNFOCUSED`, `START_EDIT`,
  `STOP_EDIT`.
- `menu_state_t` — `NAVIGATION` or `EDIT`.

### 3.2 Context ([`menu_context.h`](../output/include/menu_context.h))

```c
typedef struct menu_context {
    menu_id_t current;          // currently focused node
    menu_id_t previous;         // node we came from
    menu_state_t state;         // NAVIGATION / EDIT
    bool dirty;                 // needs redraw
    bool update;                // redraw done, buffers ready
    menu_node_value_t *values;  // mutable array of leaf values (RAM)
    const menu_node_config_t *configs;  // static per-node config (flash)
    const menu_node_t *nodes;           // static tree (flash)
    const menu_node_name_t *names;      // static node-name table (flash)
    char title_buf[LCD_STRING_LEN];
    char value_buf[LCD_STRING_LEN];
} menu_context_t;
```

### 3.3 Node config ([`menu_config.h`](../output/include/menu_config.h))

`menu_node_config_t` holds the node id, category, a static `tag` (see below), six
callback pointers and a `union` of category-specific static data:

- `string_fixed_config_t` — `values[]` (string set) + `count` + `default_idx` +
  `raw_values` (see below);
- `udword_factor_config_t` — `min`, `max`, `step`, `default_value`, `factors[]`,
  `count`, `default_idx`;
- `ubyte_simple_config_t` — `default_value`, `step`, `min`, `max`.

Every `fixed`-role category also carries `const int32_t *raw_values;` — `NULL`
unless the node sets `raw_values:` in the menu YAML (an array parallel to
`values` by index, same length, holding the real number behind each display
entry, e.g. a register code). [`menu_get_int32`/`menu_set_int32`](#41-generic-value-access-menuvalueaccesshoutputincludemenuvalueaccessh)
use it instead of the raw index when present; existing menus that never set it
are unaffected. A length mismatch against `values` is a validation error
(`MenuValidator`), not a silent bug found on hardware.

`tag` is an optional `uint32_t` set from the node's `tag:` key in the menu YAML
(0 if unset) — arbitrary static metadata such as a hardware register id, meant
to let integrators replace a hand-written `switch (id)` with a loop over
`MENU_ID_COUNT` (e.g. `if (ctx->configs[id].tag) spi_write_reg(ctx->configs[id].tag, menu_get_int32(ctx, id));`).
It lives in the **static config**, not the mutable value union, because it's a
tree property, not runtime state.

### 3.4 Node value ([`menu_value.h`](../output/include/menu_value.h))

`menu_node_value_t` is the only **mutable** per-node storage and mirrors the same
union:

- `string_fixed_value_t` — `idx`;
- `callback_callback_value_t` — `value_ptr`;
- `udword_factor_value_t` — `idx` + `value`;
- `ubyte_simple_value_t` — `value`.

---

## 4. Runtime flow

The whole module is used through [`menu.h`](../output/include/menu.h):

| Function | Purpose |
|----------|---------|
| `menu_init()` | Zero the context and bind the static tables |
| `menu_position(int8_t delta)` | Encoder turn → navigate / change value |
| `menu_enter()` | Confirm / enter sub-menu / start editing; if already editing, calls `click_cb` |
| `menu_back()` | Back to parent / leave edit mode |
| `menu_click()` | State-aware short click: `menu_enter()` outside edit mode, `menu_back()` while editing |
| `menu_long_click()` | State-aware long click: the mirror image of `menu_click()` — `menu_back()` outside edit mode, `menu_enter()` while editing |
| `menu_update()` | If `dirty`, redraw into `title_buf` / `value_buf` |
| `menu_needs_redraw()` / `menu_ack_redraw()` | Check & consume the redraw flag |
| `menu_title_buf()` / `menu_value_buf()` | Pointers to the filled buffers |
| `menu_set_dirty()` / `menu_state()` | Force redraw / read current state |

Typical use in a firmware main loop:

```c
// from input handling (button ISR, encoder):
menu_position(delta);      // encoder turn
menu_click();               // short click: drill in / exit edit mode
menu_long_click();           // long click: up a level / change factor while editing
menu_set_dirty();          // mark that the display should be refreshed

// from the main loop:
menu_update();                          // fills title_buf / value_buf if dirty
if (menu_needs_redraw()) {
    lcd_goto(0, 0); lcd_puts(menu_title_buf());
    lcd_goto(0, 1); lcd_puts(menu_value_buf());
    menu_ack_redraw();
}
```

> 💡 `menu_click()`/`menu_long_click()` exist because `menu_enter()`/`menu_back()`
> already mean different things depending on `menu_state()` (drill-in vs.
> change-factor, exit-edit vs. up-a-level) — they just pick which of the two
> primitives to call for a given gesture, so firmware code never has to branch
> on `menu_state()` itself. `menu_enter()`/`menu_back()` are still exposed
> directly if you want to wire gestures to state some other way.

### 4.1 Generic value access ([`menu_value_access.h`](../output/include/menu_value_access.h))

Reading or writing "the current value" of a leaf normally means knowing its
category (to pick the right `union` member — `.value` for `simple`/`factor`,
`.idx` for `fixed`). `menu_get_int32`/`menu_set_int32`/`menu_get_uint32`/`menu_set_uint32`
do that dispatch for you via a generated `switch (ctx->configs[id].category)`,
so integrators can loop over `MENU_ID_COUNT` instead of hand-writing one
`switch` arm per node id:

```c
int32_t  menu_get_int32(menu_context_t *ctx, menu_id_t id);
void     menu_set_int32(menu_context_t *ctx, menu_id_t id, int32_t value);
uint32_t menu_get_uint32(menu_context_t *ctx, menu_id_t id);
void     menu_set_uint32(menu_context_t *ctx, menu_id_t id, uint32_t value);
```

Use the `uint32_t` pair for `udword` values above `INT32_MAX` — the `int32_t`
pair would misinterpret them.

For `fixed`-role nodes, these functions read/write `raw_values[idx]` when the
node set `raw_values:`, or the raw `idx` otherwise (see
[§3.3](#33-node-config-menuconfighoutputincludemenuconfigh)); `menu_set_*`
does a linear search over `raw_values` for a matching entry (fixed lists are
short) and leaves `idx` untouched if the value isn't found — silent-but-visible
rather than snapping to an approximate index.

Combined with [`tag`](#33-node-config-menuconfighoutputincludemenuconfigh),
a per-id register-mapping `switch` collapses into:

```c
for (menu_id_t id = 0; id < MENU_ID_COUNT; id++) {
    if (ctx->configs[id].tag != 0) {
        hw_write_register(ctx->configs[id].tag, menu_get_int32(ctx, id));
    }
}
```

---

## 5. Drawing model

[`menu_draw.c`](../output/menu_draw.c) exposes `menu_draw_update(ctx, id)`, which:

1. clears `title_buf` / `value_buf`;
2. copies `nodes[id].title` into `title_buf`;
3. for a **leaf** calls the node's `draw_value_cb` (auto-generated for
   `simple`/`factor`/`fixed`, or your own for `callback` nodes);
4. for a **branch** just writes `>` into `value_buf`.

A helper `menu_draw_line_marker()` appends a state marker at the **right edge** of the
line: `>` in navigation, `*` while editing. The marker column is derived, not
hard-coded:

```c
#define MENU_LINE_LEN (LCD_STRING_LEN / LCD_NUM_STRINGS)   // 32 / 2 = 16
```

so it stays correct if the display or `LCD_STRING_LEN` changes.

---

## 6. User callbacks

Callbacks fall into two groups:

- **Auto-generated** — the generator emits and wires them (e.g.
  `menu_draw_string_fixed_value_cb`, `string_fixed_click_cyclic_cb`,
  `udword_factor_position_limit_cb`, `ubyte_simple_position_limit_cb`).
- **User-provided** — for `callback` role nodes (or explicit custom callbacks in the
  config) the generator only *declares* them; **you must implement the bodies**.

For the bundled [`menu/menu.yaml`](../menu/menu.yaml) these functions are referenced
but **not implemented** by the generator:

| Function | Declared in | Signature |
|----------|-------------|-----------|
| `draw_version_cb` | `menu_draw.h` | `void (menu_context_t *ctx, menu_id_t id)` |
| `pwm_frequency_display_cb` | `menu_draw.h` | `void (menu_context_t *ctx, menu_id_t id)` |
| `pwm_frequency_change_cb` | `menu_edit.h` | `void (menu_context_t *ctx, menu_id_t id, int8_t delta)` |
| `my_event_cb` | **none** — declare it yourself | `void (menu_context_t *ctx, menu_id_t id, menu_event_t event)` |

> ⚠️ `my_event_cb` is used as the `event_cb` for several nodes, but no generated
> header declares it. Provide both the declaration and the implementation in your
> own code.

`menu_data_config.c` includes the user-supplied `pulse_config.h` (listed under
`include_files` in `menu/menu.yaml`). For the bundled config the header must look
something like:

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

## 7. Integrating into STM32 / ESP32

1. **Copy the module** — copy `output/*.c` and `output/include/*.h` into your
   project's source tree (e.g. a `menu/` folder) and add the `.c` files to your
   build (CMake, Makefile, PlatformIO, STM32CubeIDE, …).
2. **Add the include path** — point the compiler at the folder that contains
   `menu*.h`.
3. **Provide `pulse_config.h`** (or change `include_files` in the menu config and
   regenerate) with the user-callback declarations and implementations.
4. **Wire input** — call `menu_position()` from your encoder code, and
   `menu_click()`/`menu_long_click()` (or `menu_enter()`/`menu_back()` directly)
   from your button code (ISR or polling task).
5. **Drive the display** — in the main loop call `menu_update()` and copy the two
   buffers to the LCD as shown in [§4](#4-runtime-flow).
6. **Optimise for the target** — for STM32F103 use `--specs=nano.specs`
   (newlib-nano); `-fshort-enums` reduces enum sizes. The module is freestanding
   enough to compile with `-ffreestanding` if you provide `memcpy`/`strlen`/`snprintf`.

The generated code does not call into HAL/Arduino APIs, so it is portable between
STM32, ESP32 and other bare-metal targets; only your display/input glue is
target-specific.

---

## 8. Sizing notes

- Only `s_menu_values[18]` (the mutable `menu_node_value_t` array) and the context
  live in RAM — roughly **300–350 bytes** total for the bundled menu.
- All config/tree/name tables are `static const` and go to **flash**.
- No `malloc`, no recursion, no floating point — deterministic and safe for small
  microcontrollers.
