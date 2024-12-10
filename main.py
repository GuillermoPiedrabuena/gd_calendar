from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import calendar
from collections import defaultdict
from fastapi.responses import JSONResponse

app = FastAPI()

# Configuración de Jinja2
templates = Jinja2Templates(directory="templates")

# Variable global para el horario
schedule = {}

def create_monthly_schedule(start_hour=8, end_hour=18):
    """
    Crea un horario desde el día de hoy hasta el último día del mes actual.

    Args:
        start_hour (int): Hora de inicio del horario (formato 24 horas, default es 8).
        end_hour (int): Hora de fin del horario (formato 24 horas, default es 18).

    Returns:
        list: Lista de diccionarios donde cada diccionario representa un intervalo horario.
    """
    # Obtener la fecha actual y los datos del mes
    current_date = datetime.now()
    year, month = current_date.year, current_date.month
    start_day = current_date.day  # Comienza desde hoy
    days_in_month = calendar.monthrange(year, month)[1]  # Total de días en el mes

    # Inicializar la lista
    schedule = []

    # Generar horarios desde el día actual hasta el último día del mes
    for day in range(start_day, days_in_month + 1):
        weekday = calendar.weekday(year, month, day)
        weekday_name = calendar.day_name[weekday]
        schedule.extend([
            {
                "occupied": "",
                "weekday": weekday_name,
                "time": f"{hour:02d}:00",
                "day": day
            }
            for hour in range(start_hour, end_hour)
        ])

    return schedule
def group_by_day(schedule):
    grouped = defaultdict(list)
    for entry in schedule:
        day = entry.get('day')
        grouped[day].append(entry)
    return dict(grouped)

def group_by_week(grouped_by_day):
    weeks = defaultdict(list)
    for day in sorted(grouped_by_day.keys()):
        week_number = (day - 1) // 7 + 1
        weeks[week_number].append({
            "day": day,
            "data": grouped_by_day[day]
        })
    return dict(weeks)

@app.on_event("startup")
async def initialize_schedule():
    """
    Inicializa el horario global cuando el servidor inicia.
    """
    global schedule
    monthly_schedule = create_monthly_schedule()
    schedule = group_by_week(group_by_day(monthly_schedule))

@app.get("/", response_class=HTMLResponse)
async def ver_calendario(request: Request):
    today = datetime.today()
    year, month = today.year, today.month
    cal = calendar.Calendar()
    days = list(cal.itermonthdays2(year, month))
    month_name = calendar.month_name[month]
    days_in_month = calendar.monthrange(year, month)[1]

    return templates.TemplateResponse(
        "calendar.html",
        {
            "request": request,
            "year": year,
            "month": month,
            "month_name": month_name,
            "days": days,
            "enumerate": enumerate,
            "days_in_month": days_in_month,
            "schedule": schedule,
            "datetime": datetime,
            "calendar": calendar,
        },
    )

@app.post("/update-schedule")
async def update_schedule(
    value: str = Body(...),
    week_number: int = Body(...),
    day: int = Body(...),
    time: str = Body(...)
):
    """
    Actualiza el campo `occupied` del horario global `schedule` con el valor proporcionado.
    Los parámetros incluyen:
    - value: Nuevo valor para el campo `occupied`.
    - week_number: Número de la semana.
    - day: Día del mes.
    - time: Hora específica.
    """

    # Validar si week_number existe en schedule
    if week_number not in schedule:
        return JSONResponse(
            content={"error": f"La semana {week_number} no existe en el horario."},
            status_code=400
        )

    # Buscar el día en la semana
    week_data = schedule[week_number]
    day_entry = next((entry for entry in week_data if entry["day"] == day), None)

    if not day_entry:
        return JSONResponse(
            content={"error": f"El día {day} no existe en la semana {week_number}."},
            status_code=400
        )

    # Buscar la entrada de tiempo específica
    hour_entry = next((hour for hour in day_entry["data"] if hour["time"] == time), None)

    if not hour_entry:
        return JSONResponse(
            content={"error": f"La hora {time} no existe para el día {day} en la semana {week_number}."},
            status_code=400
        )

    # Actualizar el campo `occupied` con el valor proporcionado
    hour_entry["occupied"] = value

    return JSONResponse(content={"message": "Horario actualizado con éxito.", "schedule": schedule})
