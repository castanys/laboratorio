# laboratorio

**Que las sesiones desatendidas de Claude Code no se coman tu cuota semanal, y un WhatsApp cuando una te necesite.** La parte de la cuota que dejas a las sesiones se reparte entre los 7 días de la semana; al llegar al tope de hoy no se lanza nada hasta mañana. Como extra, una sesión puede terminar su propio pull request: trabaja un ítem de un `STATUS.md` y mergea solo con el CI en verde. Gratis y abierto; sin servicio, sin cuenta, sin telemetría.

[Read in English](README.md)

## Por qué un tope sobre la cuota y no sobre dólares

`claude --max-budget-usd` cuenta dólares de API. En un plan Pro o Max ha cortado ejecuciones que no costaban nada (issue #85400 de claude-code) mientras la barra semanal sigue llenándose, y esa barra es la que te acaba la semana antes de tiempo. El tope de aquí trabaja sobre el porcentaje que enseña tu plan, así que protege lo que de verdad se agota.

## Qué trae

- **Tope semanal** (`scripts/weekly_cap.py`): el `100 - reserva` por ciento de la cuota semanal queda para las sesiones (la reserva es tuya, para trabajar a mano) y se reparte por días, más un pequeño margen para un día cargado. Sale con 0 si hay sitio para lanzar y con 1 y el motivo si no. Lee el porcentaje semanal y la hora de renovación que enseña `/usage` con el login que ya guarda `claude` (ninguna otra credencial; el token no se imprime ni se guarda); sale con 2 si no puede leerlos.
- **Avisos por WhatsApp** (`scripts/notify_whatsapp.py`): vale cualquier pasarela que acepte `POST /send {"recipient", "message"}`. Sale con 0 solo si la pasarela confirma el envío: un fallo silencioso no puede pasar por aviso entregado.
- **Extra: sesiones que terminan su PR**
  - **Pasadas** (`scripts/session_pass.py`): una pasada = un ítem. Coge el primer ítem abierto que alguien pidió (`[origin human|plan|failure]`), mira el tope semanal, lanza `claude -p` en su propio worktree con un techo en dólares y comunica `DONE` / `ASK` / `BLOCKED`. Un ítem sin origen no se lanza nunca: las sesiones que se inventan y se puntúan su trabajo son por donde se va el gasto desatendido.
  - **Cierre en una llamada** (`scripts/session_close.py`): push, abre el PR, pasa el ítem de ABIERTO a HECHO en `STATUS.md`, espera al CI y mergea con squash. Idempotente: tras un CI en rojo se arregla y se relanza igual. Nunca mergea con un check rojo, ni sin checks en un repo con workflows.
  - **Guarda `pre-push`** (`hooks/pre-push`): main/master no se actualizan ni se borran en el remoto. Solo rama y PR. Funciona sin plan de pago de GitHub.
  - **Formato de `STATUS.md`** (`scripts/status_format.py`): ítems de un renglón con id estable, un `wins:` comprobable y un `[impact N]`, con tope de 60 líneas. Cabe en una pantalla: la sesión lee lo abierto sin bajar.

## Instalación

```sh
git clone https://github.com/castanys/laboratorio ~/laboratorio
claude plugin marketplace add ~/laboratorio
claude plugin install laboratorio@laboratorio
```

El clon es donde viven los scripts, en una ruta que no cambia entre versiones (cron y el hook de git apuntan a ella); el plugin añade los comandos `/laboratorio:*`. Se actualiza con `git -C ~/laboratorio pull && claude plugin marketplace update laboratorio`.

## Uso

**Tope.** Con la sesión de `claude` iniciada en la misma máquina:

```sh
python3 ~/laboratorio/scripts/weekly_cap.py && echo "hay sitio para lanzar"
```

Imprime el porcentaje de la semana, el tope de hoy y la hora de renovación. Por defecto `--reserve 15` (se te guarda a ti) y `--margin 5`; `--pct 42 --renews 2026-10-11T18:00:00+00:00` sustituye la lectura. Ponlo delante de lo que lance tus sesiones (cron, un script, `session_pass.py`).

**WhatsApp.** Pon `WHATSAPP_API_URL` y `WHATSAPP_RECIPIENT` en el entorno o en un `.env` fuera de git (no hay URL por defecto, a propósito) y luego `python3 ~/laboratorio/scripts/notify_whatsapp.py "texto"`.

**Extra: sesiones que terminan su PR.** En el repo que quieras proteger, `bash ~/laboratorio/scripts/install_hooks.sh` (imprime la única línea `git config core.hooksPath …` que ejecuta; se deshace con `git config --unset core.hooksPath`). Parte de la forma de `STATUS.md` que valida `status_format.py`:

```
GOAL: una frase
## OPEN (1)
1. `APP-01` wins: `make test` sale con 0 sobre el parser nuevo; serves GOAL: ship v1 [impact 7] [origin human]
## DECISIONS (0)
## DONE (0)
```

(Las cabeceras van en inglés, `GOAL`, `OPEN`, `DECISIONS`, `DONE`, para que el validador sea el mismo en todos los idiomas.)

- `python3 ~/laboratorio/scripts/session_pass.py REPO` lanza una pasada si el tope semanal lo permite (y ninguna si no puede leer la cuota).
- `/laboratorio:close ITEM-ID "feat: título"` cierra la tarea que acabas de terminar.
- `/laboratorio:check-status` valida `STATUS.md`.

## Desarrollo

`bash .claude/test.sh` pasa la suite; `bash scripts/comprueba_privacidad.sh` es la barrera de privacidad (sale con 1 si encuentra una ruta del directorio personal, un correo, un teléfono, un token o un término de `.privacy-deny`). Requiere `git`, `gh`, `python3 >= 3.9` y `claude`.

Licencia MIT.
