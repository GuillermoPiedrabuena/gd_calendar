from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import calendar
from collections import defaultdict
from fastapi.responses import JSONResponse
import threading
import time

app = FastAPI()

# Configuración de Jinja2
templates = Jinja2Templates(directory="templates")

# Variable global para el horario
schedule = {}
lock = threading.Lock()  # Para manejar accesos concurrentes a la variable `schedule`

def create_monthly_schedule(start_date, days=30, start_hour=8, end_hour=19):
    """
    Crea un horario desde una fecha inicial por una cantidad específica de días,
    con intervalos de 30 minutos.
    """
    schedule = []

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        year, month, day = current_date.year, current_date.month, current_date.day
        weekday = calendar.weekday(year, month, day)
        weekday_name = calendar.day_name[weekday]
        month_name = calendar.month_name[month]  # Nombre del mes en inglés
        
        translation_dict = {
            # Días de la semana
            "Monday": "Lunes",
            "Tuesday": "Martes",
            "Wednesday": "Miércoles",
            "Thursday": "Jueves",
            "Friday": "Viernes",
            "Saturday": "Sábado",
            "Sunday": "Domingo",
            
            # Meses del año
            "January": "Enero",
            "February": "Febrero",
            "March": "Marzo",
            "April": "Abril",
            "May": "Mayo",
            "June": "Junio",
            "July": "Julio",
            "August": "Agosto",
            "September": "Septiembre",
            "October": "Octubre",
            "November": "Noviembre",
            "December": "Diciembre",
        }

        # Generar intervalos de 30 minutos para cada día
        for hour in range(start_hour, end_hour):
            for minute in (0, 30):  # Intervalos de 30 minutos
                time_slot = f"{hour:02d}:{minute:02d}"
                schedule.append({
                    "occupied": "",
                    "weekday": translation_dict[weekday_name],
                    "time": time_slot,
                    "day": day,
                    "month": month,
                    "month_name": translation_dict[month_name],
                    "year": year,
                })
    
    return schedule

def group_by_day(schedule):
    grouped = defaultdict(list)
    for entry in schedule:
        day = entry.get('day')
        grouped[day].append(entry)
    return dict(grouped)

def group_by_week(grouped_by_day):
    """
    Agrupa los días en semanas basándose en su número de semana.
    """
    weeks = defaultdict(list)
    for day, entries in grouped_by_day.items():
        # Obtener la fecha completa del primer entry para calcular el número de semana
        first_entry = entries[0]
        current_date = datetime(first_entry["year"], first_entry["month"], first_entry["day"])
        week_number = (current_date.day - 1) // 7 + 1
        weeks[week_number].append({
            "day": first_entry["day"],
            "data": entries
        })
    return dict(weeks)

def schedule_updater():
    """
    Función en un hilo paralelo para actualizar el horario cada día.
    """
    while True:
        time.sleep(24 * 60 * 60)  # Esperar un día completo (24 horas)
        with lock:
            today = datetime.now()
            
            # Filtrar días futuros
            updated_schedule = {}
            for week_number, days in schedule.items():
                filtered_days = [
                    entry for entry in days
                    if datetime(entry["data"][0]["year"], entry["data"][0]["month"], entry["data"][0]["day"]) >= today
                ]
                if filtered_days:
                    updated_schedule[week_number] = filtered_days

            # Generar días nuevos hasta completar los 30 días
            days_remaining = 30 - sum(len(days) for days in updated_schedule.values())
            if days_remaining > 0:
                new_schedule = create_monthly_schedule(today, days=days_remaining)
                grouped_by_day = group_by_day(new_schedule)
                new_weeks = group_by_week(grouped_by_day)
                updated_schedule.update(new_weeks)

            schedule = updated_schedule

@app.on_event("startup")
async def initialize_schedule():
    """
    Inicializa el horario global y lanza el hilo de actualización diaria.
    """
    global schedule
    today = datetime.now()
    monthly_schedule = create_monthly_schedule(today, days=30)
    grouped_by_day = group_by_day(monthly_schedule)
    schedule = group_by_week(grouped_by_day)
    
    # Lanzar el hilo para actualizar el horario
    updater_thread = threading.Thread(target=schedule_updater, daemon=True)
    updater_thread.start()

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
    """
    with lock:
        if week_number not in schedule:
            return JSONResponse(
                content={"error": f"La semana {week_number} no existe en el horario."},
                status_code=400
            )

        week_data = schedule[week_number]
        day_entry = next((entry for entry in week_data if entry["day"] == day), None)

        if not day_entry:
            return JSONResponse(
                content={"error": f"El día {day} no existe en la semana {week_number}."},
                status_code=400
            )

        hour_entry = next((hour for hour in day_entry["data"] if hour["time"] == time), None)

        if not hour_entry:
            return JSONResponse(
                content={"error": f"La hora {time} no existe para el día {day} en la semana {week_number}."},
                status_code=400
            )

        hour_entry["occupied"] = value

    return JSONResponse(content={"message": "Horario actualizado con éxito.", "schedule": schedule})
