
El reporte incluye:

- partidos del día anterior, con resultado, goles, tarjetas y estadísticas si están disponibles;
- partidos del día actual, con horario local de Argentina, estadio, etapa y estado;
- próximos partidos, por defecto los próximos 3 días;
- fallback con OpenFootball si API-FOOTBALL falla, no tiene token, se supera el límite diario o se usa `DRY_RUN=true`.
---

## Fuente principal de datos

La fuente principal es **API-FOOTBALL de API-SPORTS**.

Para el Mundial 2026 se usa:

```text
league=1
season=2026
```

API-FOOTBALL fue elegida porque tiene cobertura específica para el Mundial 2026 y permite consultar fixtures, eventos, estadísticas, lineups, standings y top scorers si esos datos están disponibles para la competición y para el partido.

La API tiene free tier, pero con límite diario de requests. Por eso el proyecto implementa cache local en `.cache/` para evitar gastar requests innecesarios.

---

## Endpoints verificados de API-FOOTBALL

Base URL:

```text
https://v3.football.api-sports.io
```

Header de autenticación:

```text
x-apisports-key: TU_API_KEY
```

Endpoints usados o preparados en el cliente:

| Uso | Endpoint | Parámetros |
|---|---|---|
| Todos los fixtures del Mundial | `/fixtures` | `league=1&season=2026` |
| Fixtures por fecha | `/fixtures` | `league=1&season=2026&date=YYYY-MM-DD&timezone=America/Argentina/Buenos_Aires` |
| Fixture por ID | `/fixtures` | `id=FIXTURE_ID` |
| Eventos del partido | `/fixtures/events` | `fixture=FIXTURE_ID` |
| Estadísticas del partido | `/fixtures/statistics` | `fixture=FIXTURE_ID` |
| Lineups del partido | `/fixtures/lineups` | `fixture=FIXTURE_ID` |
| Standings | `/standings` | `league=1&season=2026` |
| Top scorers | `/players/topscorers` | `league=1&season=2026` |

El proyecto no inventa endpoints. Si alguna consulta devuelve vacío, error, rate limit o datos no disponibles, el script lo maneja sin romper todo el reporte.

Importante: que un endpoint exista no significa que todos los partidos tengan todos los datos inmediatamente. Eventos, estadísticas, xG, lineups y goleadores dependen de la disponibilidad de API-FOOTBALL para ese partido y del momento en que se consulte.

---

## Fallback: OpenFootball

Como fuente alternativa gratuita se usa:

```text
https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json
```

OpenFootball se usa si:

- API-FOOTBALL no responde;
- `API_FOOTBALL_KEY` no está configurada;
- se supera el límite diario;
- una consulta básica de fixtures falla;
- `DRY_RUN=true`.

OpenFootball sirve muy bien para fixtures y horarios básicos, pero no debe tratarse como una fuente de estadísticas en vivo. Normalmente no trae eventos detallados, goleadores actualizados en tiempo real, tarjetas, xG, lineups ni estadísticas completas. El proyecto no inventa esos datos: si no existen, muestra mensajes como:

```text
Estadísticas no disponibles todavía.
Detalle de goles no disponible todavía.
```

---

## Estructura del proyecto

```text
mundial-mailer/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── pytest.ini
├── main.py
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── api_football_client.py
│   ├── openfootball_client.py
│   ├── date_utils.py
│   ├── normalizer.py
│   ├── formatter.py
│   ├── email_sender.py
│   ├── cache.py
│   └── logger.py
├── templates/
│   └── daily_email.html
├── tests/
│   ├── test_date_utils.py
│   ├── test_formatter.py
│   └── test_normalizer.py
└── .github/
    └── workflows/
        └── daily-email.yml
```

---

## Estructura interna de un partido normalizado

Todas las fuentes se convierten a una estructura común parecida a esta:

```python
{
    "source": "api-football",
    "fixture_id": 123,
    "date": "2026-06-11",
    "time_argentina": "16:00",
    "home_team": "Argentina",
    "away_team": "México",
    "home_score": 2,
    "away_score": 1,
    "status": "finalizado",
    "status_raw": "FT",
    "round": "Group Stage - 1",
    "group": "Group A",
    "venue": "MetLife Stadium",
    "city": "East Rutherford",
    "goals": [],
    "cards": [],
    "statistics": {},
    "statistics_pairs": [],
    "has_statistics": False,
    "has_events": False,
    "lineups": [],
    "has_lineups": False,
}
```

Esto evita que el resto del proyecto dependa directamente del formato de API-FOOTBALL o de OpenFootball.

---

## Cache local

La cache se guarda en:

```text
.cache/
```

La carpeta está en `.gitignore`, así que no se sube a GitHub.

Reglas principales:

- fixtures futuros: 6 horas;
- fixtures de hoy: 15 minutos;
- fixtures pasados/finalizados: 24 horas;
- eventos, estadísticas y lineups: 24 horas;
- si se borra `.cache/`, el proyecto vuelve a crearla automáticamente.

Si API-FOOTBALL falla y existe una cache vieja, el cliente intenta usar esa cache vieja antes de romper.

---

## Instalación local

Crear entorno virtual:

```bash
python -m venv .venv
```

Activarlo en Windows:

```bash
.venv\Scripts\activate
```

Activarlo en macOS/Linux:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

---

## Configurar `.env`

Copiar el ejemplo:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Editar `.env`:

```env
API_FOOTBALL_KEY=tu_api_key_de_api_sports
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_contraseña_de_aplicacion
EMAIL_FROM=tu_email@gmail.com
EMAIL_TO=tu_email@gmail.com
TIMEZONE=America/Argentina/Buenos_Aires
UPCOMING_DAYS=3
DRY_RUN=true
USE_OPENFOOTBALL_FALLBACK=true
```

No subas `.env` a GitHub. Ya está incluido en `.gitignore`.

---

## Cómo registrarse en API-FOOTBALL / API-SPORTS

1. Entrar al dashboard de API-FOOTBALL / API-SPORTS.
2. Crear una cuenta.
3. Elegir el plan gratis.
4. Copiar la API key.
5. Pegarla en `.env`:

```env
API_FOOTBALL_KEY=tu_api_key
```

El plan gratis tiene límite diario. Si lo superás, el script debería usar OpenFootball como fallback si `USE_OPENFOOTBALL_FALLBACK=true`.

---

## Probar localmente sin enviar email

Para probar sin gastar API-FOOTBALL y sin mandar email real:

```env
DRY_RUN=true
USE_OPENFOOTBALL_FALLBACK=true
```

Ejecutar:

```bash
python main.py
```

Esto genera:

```text
output/daily_email_preview.html
```

Abrí ese archivo en el navegador para ver cómo se vería el email.

---

## Enviar email real

Para enviar email real:

```env
DRY_RUN=false
```

Luego ejecutar:

```bash
python main.py
```

Si todo está bien configurado, se enviará un email a `EMAIL_TO`.

---

## Configurar Gmail SMTP

Para Gmail normalmente no sirve usar tu contraseña normal. Lo recomendado es usar una contraseña de aplicación.

Pasos generales:

1. Activar verificación en dos pasos en tu cuenta de Google.
2. Ir a contraseñas de aplicación.
3. Crear una contraseña para este proyecto.
4. Usar esa contraseña en:

```env
SMTP_PASSWORD=contraseña_de_aplicación
```

Configuración típica:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
EMAIL_FROM=tu_email@gmail.com
EMAIL_TO=tu_email@gmail.com
```

---

## Ejecutar tests

```bash
pytest
```

Los tests cubren:

- cálculo de ayer, hoy y próximos días;
- conversión de horario UTC a Argentina;
- parseo de horarios de OpenFootball;
- formateo de marcador;
- renderizado sin partidos;
- renderizado con partidos;
- normalización de fixtures de API-FOOTBALL;
- normalización de partidos de OpenFootball.

---

## GitHub Actions

El workflow está en:

```text
.github/workflows/daily-email.yml
```

Está configurado para ejecutarse todos los días a las 9:00 AM de Argentina:

```yaml
on:
  schedule:
    - cron: "0 9 * * *"
      timezone: "America/Argentina/Buenos_Aires"
  workflow_dispatch:
```

También permite ejecución manual desde la pestaña **Actions** con `workflow_dispatch`.

### Fallback si tu cuenta o configuración no acepta `timezone`

Argentina 9:00 AM equivale a 12:00 UTC. Si necesitás usar cron UTC puro, cambiá el bloque por:

```yaml
on:
  schedule:
    - cron: "0 12 * * *"
  workflow_dispatch:
```

---

## GitHub Secrets

En tu repo de GitHub:

1. Ir a **Settings**.
2. Entrar en **Secrets and variables**.
3. Entrar en **Actions**.
4. Crear estos secrets:

```text
API_FOOTBALL_KEY
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
TIMEZONE
UPCOMING_DAYS
DRY_RUN
USE_OPENFOOTBALL_FALLBACK
```

Valores sugeridos:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
TIMEZONE=America/Argentina/Buenos_Aires
UPCOMING_DAYS=3
DRY_RUN=false
USE_OPENFOOTBALL_FALLBACK=true
```

Para probar el workflow sin mandar email real, podés poner:

```text
DRY_RUN=true
```

---

## Subir a GitHub

Inicializar repo:

```bash
git init
git add .
git commit -m "Initial mundial mailer"
```

Crear un repo vacío en GitHub y conectar:

```bash
git remote add origin https://github.com/TU_USUARIO/mundial-mailer.git
git branch -M main
git push -u origin main
```

Después cargar los secrets y probar el workflow manualmente.

---

## Ejecutar manualmente el workflow

1. Ir al repo en GitHub.
2. Abrir la pestaña **Actions**.
3. Elegir **Daily World Cup Email**.
4. Tocar **Run workflow**.
5. Elegir la rama `main`.
6. Confirmar.

Si `DRY_RUN=true`, no se manda email. Si `DRY_RUN=false`, intenta mandar el email real.

---

## Cambiar horario

Si GitHub Actions acepta `timezone`, cambiá el cron manteniendo la zona horaria:

```yaml
schedule:
  - cron: "30 8 * * *"
    timezone: "America/Argentina/Buenos_Aires"
```

Eso correría 8:30 AM Argentina.

Si usás UTC puro, recordá convertir el horario. Argentina usa UTC-3, entonces 9:00 Argentina equivale a 12:00 UTC.

---

## Cambiar cantidad de próximos días

En `.env`:

```env
UPCOMING_DAYS=5
```

En GitHub Actions, cambiá el secret `UPCOMING_DAYS`.

---

## Errores comunes

### Token inválido

Revisá:

```env
API_FOOTBALL_KEY=...
```

También verificá que no tenga espacios antes o después.

### Rate limit

El plan gratis tiene límite diario. Si se supera, el script intenta usar OpenFootball si está activo:

```env
USE_OPENFOOTBALL_FALLBACK=true
```

También podés borrar o revisar `.cache/`, aunque normalmente conviene conservarla.

### Gmail bloquea el SMTP

Usá contraseña de aplicación. No uses tu contraseña normal de Gmail.

También revisá:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=contraseña_de_aplicacion
```

### No llegan estadísticas

Puede pasar aunque el partido exista. Las estadísticas dependen de disponibilidad de API-FOOTBALL, del partido y del momento. El proyecto no inventa estadísticas.

### No hay partidos

Puede ser normal si el Mundial todavía no empezó o si no hay partidos en esa fecha. En ese caso el email muestra secciones vacías con mensajes claros.

### Falla API-FOOTBALL y se usa fallback

Esto es esperado si:

- no hay token;
- `DRY_RUN=true`;
- hay rate limit;
- API-FOOTBALL devuelve error;
- una consulta básica falla.

El email mostrará que la fuente usada fue `OpenFootball fallback`. Si estás en `DRY_RUN=true` y tampoco se puede descargar OpenFootball, el proyecto genera una preview vacía en `modo demo sin datos` para que puedas revisar el diseño sin enviar email.

---

## Migrar más adelante a Telegram Bot

No está implementado todavía, pero se puede agregar fácil.

Idea general:

1. Crear un bot con BotFather en Telegram.
2. Obtener `TELEGRAM_BOT_TOKEN`.
3. Obtener `TELEGRAM_CHAT_ID`.
4. Crear `src/telegram_sender.py`.
5. Agregar variables al `.env`:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SEND_EMAIL=true
SEND_TELEGRAM=false
```

6. Modificar `main.py` para enviar por email, Telegram o ambos.

Lo ideal sería reutilizar el mismo contexto normalizado y crear un formatter de texto plano para Telegram.

---

## Notas de diseño

- Código simple y modular.
- Funciones chicas.
- Sin frontend.
- Sin frameworks web.
- Cache JSON local.
- HTML compatible con Gmail.
- Fallback claro.
- No se inventan datos.
- Fácil de modificar.
