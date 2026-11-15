import ast
import operator
import json
import math
import os
import threading
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    User,
    PublicAqiDashboard,
    PySparkTrainingMatrix,
    EvaluationAlgorithm,
    SparkJobLog,
    VerifierValidationQueue,
)
from .spark_runner import run_pyspark_job

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}
SAFE_FUNCS = {'max': max, 'min': min, 'round': round, 'abs': abs}


def eval_weather_model(expr: str, weather_ctx: dict) -> float:
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in weather_ctx:
            return float(weather_ctx[node.id] or 0.0)
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCS:
            args = [_eval(arg) for arg in node.args]
            return float(SAFE_FUNCS[node.func.id](*args))
        raise ValueError("Unsupported formula syntax")

    tree = ast.parse(expr, mode='eval')
    return round(_eval(tree.body), 2)


def register_view(request):
    if request.method == 'POST':
        user = User.objects.create_user(
            username=request.POST.get('username'),
            email=request.POST.get('email'),
            password=request.POST.get('password'),
            role=request.POST.get('role', 'scientist'),
            institution=request.POST.get('institution', ''),
        )
        login(request, user)
        messages.success(request, f'Welcome, {user.username}! Account created.')
        return redirect('dashboard')
    return render(request, 'registration/register.html')
def dashboard_view(request):
    from .models import Aqi3nf, AqiCategory

    active_algorithms = list(EvaluationAlgorithm.objects.filter(is_active=True).order_by("-created_at"))
    selected_algo_id = request.GET.get("algorithm_id")
    selected_algo = next(
        (a for a in active_algorithms if str(a.algorithm_id) == str(selected_algo_id)),
        None
    )

    spark_station_preds = {}
    if selected_algo:
        spath = f"spark_outputs/algo_{selected_algo.algorithm_id}_latest.json"
        if os.path.exists(spath):
            with open(spath, "r") as f:
                spark_station_preds = json.load(f).get("station_predictions", {})

    categories = list(AqiCategory.objects.all())

    def get_category(aqi_val):
        for cat in categories:
            if cat.aqi_min <= aqi_val <= cat.aqi_max:
                return cat.health_status, cat.health_color
        if aqi_val > 400:
            return "Severe", "#7f1d1d"
        return "Good", "#10b981"

    locations = PublicAqiDashboard.objects.values_list("location", flat=True).distinct()
    station_list = []

    for loc in locations:
        latest = (
            PublicAqiDashboard.objects
            .filter(location=loc)
            .order_by("-date_ist", "-time_ist", "-id")
            .first()
        )
        if not latest:
            continue

        if selected_algo:
            raw_rec = Aqi3nf.objects.filter(pk=latest.id).first()
            loc_key = str(raw_rec.location_id) if raw_rec else ""
            weather_ctx = {
                "temp_c": raw_rec.temp_c if raw_rec else latest.temp_c,
                "humidity": raw_rec.humidity if raw_rec else latest.humidity,
                "pressure_mb": raw_rec.pressure_mb if raw_rec else 1012,
                "windspeed_kph": raw_rec.windspeed_kph if raw_rec else 8.0,
                "pm2_5": raw_rec.pm2_5 if raw_rec else 0,
                "pm10": raw_rec.pm10 if raw_rec else 0,
                "co": raw_rec.co if raw_rec else 0,
                "no2": raw_rec.no2 if raw_rec else 0,
            }
            try:
                calc_aqi = int(round(eval_weather_model(selected_algo.formula_spec, weather_ctx)))
            except Exception:
                if loc_key in spark_station_preds:
                    calc_aqi = int(spark_station_preds[loc_key])
                else:
                    t = float(weather_ctx["temp_c"] or 25.0)
                    h = float(weather_ctx["humidity"] or 60.0)
                    w = float(weather_ctx["windspeed_kph"] or 8.0)
                    p = float(weather_ctx["pressure_mb"] or 1012.0)
                    calc_aqi = int(round(max(15.0, t * 2.1 + h * 0.65 - w * 2.4 + (p - 1000.0) * 1.2)))

            latest.aqi_index = max(0, calc_aqi)
            latest.health_status, latest.health_color = get_category(latest.aqi_index)

        station_list.append(latest)

    recent_readings = PublicAqiDashboard.objects.order_by("-date_ist", "-time_ist", "-id")[:20]

    map_data = [
        {
            "location": s.location,
            "lat": s.latitude,
            "lng": s.longitude,
            "aqi": s.aqi_index,
            "status": s.health_status or "Unknown",
            "color": s.health_color or "#6b7280",
            "temp": float(s.temp_c) if s.temp_c is not None else None,
            "condition": s.condition_text or "",
        }
        for s in station_list if s.latitude is not None and s.longitude is not None
    ]

    return render(request, "core/dashboard.html", {
        "stations": station_list,
        "recent_readings": recent_readings,
        "map_data_json": json.dumps(map_data),
        "active_algorithms": active_algorithms,
        "selected_algo": selected_algo,
    })


@login_required
def scientist_workspace_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_algorithm':
            EvaluationAlgorithm.objects.create(
                algorithm_name=request.POST.get('algorithm_name'),
                version=request.POST.get('version'),
                formula_spec=request.POST.get('formula_spec'),
                developer_user_id=request.user.id,
                is_active=True,
            )
            messages.success(request, 'New weather-forecasting algorithm saved.')

        elif action == 'trigger_spark_job':
            algo_id = int(request.POST.get('algorithm_id'))
            algo = get_object_or_404(EvaluationAlgorithm, pk=algo_id)

            job = SparkJobLog.objects.create(
                algorithm_id=algo_id,
                executed_by_user_id=request.user.id,
                status='running',
                records_processed=0,
            )

            thread = threading.Thread(
                target=run_pyspark_job,
                args=(job.job_id, algo.algorithm_id, algo.formula_spec),
                daemon=True,
            )
            thread.start()
            messages.info(request, f'PySpark job #{job.job_id} started in background.')

        return redirect('scientist_workspace')

    algorithms = EvaluationAlgorithm.objects.order_by('-created_at')
    job_logs = SparkJobLog.objects.select_related('algorithm').order_by('-execution_start')[:25]

    return render(request, 'core/scientist_workspace.html', {
        'algorithms': algorithms,
        'job_logs': job_logs,
    })
@login_required
def algorithm_visualizer_view(request):
    algorithms = list(EvaluationAlgorithm.objects.order_by('-is_active', '-created_at'))
    selected_id = request.GET.get('algorithm_id')
    selected_location = request.GET.get('location')

    selected_algo = next(
        (a for a in algorithms if str(a.algorithm_id) == str(selected_id)),
        algorithms[0] if algorithms else None
    )

    locations = list(
        PublicAqiDashboard.objects.values_list('location', flat=True).distinct()
    )
    if not selected_location and locations:
        selected_location = locations[0]

    history_qs = PublicAqiDashboard.objects.all()
    if selected_location:
        history_qs = history_qs.filter(location=selected_location)
    recent_obs = list(history_qs.order_by('-date_ist', '-time_ist')[:24])
    recent_obs.reverse()

    matrix_rows = list(PySparkTrainingMatrix.objects.order_by('-id')[:60])
    matrix_rows.reverse()

    backtest_labels = []
    actual_series = []
    predicted_series = []
    sq_errors = []
    abs_errors = []
    rmse = None
    mae = None
    formula_error = None

    spark_result_path = (
        f"spark_outputs/algo_{selected_algo.algorithm_id}_latest.json"
        if selected_algo else ""
    )
    if spark_result_path and os.path.exists(spark_result_path):
        with open(spark_result_path, "r") as f:
            spark_data = json.load(f)
        rmse = spark_data.get("rmse")
        mae = spark_data.get("mae")
        samples = spark_data.get("samples", [])
        backtest_labels = [f"#{s['id']}" for s in samples]
        actual_series = [s["actual"] for s in samples]
        predicted_series = [s["predicted"] for s in samples]
    else:
        for row in matrix_rows:
            backtest_labels.append(f"#{row.id}")
            actual_series.append(row.benchmark_aqi)

            weather_ctx = {
                'temp_c': row.temp_c,
                'humidity': row.humidity,
                'pressure_mb': row.pressure_mb,
                'windspeed_kph': row.windspeed_kph,
                'pm2_5': row.pm2_5,
                'pm10': row.pm10,
                'co': row.co,
                'no2': row.no2,
            }

            if selected_algo and selected_algo.formula_spec:
                try:
                    pred = eval_weather_model(selected_algo.formula_spec, weather_ctx)
                    predicted_series.append(pred)
                    err = pred - row.benchmark_aqi
                    sq_errors.append(err ** 2)
                    abs_errors.append(abs(err))
                except Exception as exc:
                    formula_error = str(exc)
                    predicted_series.append(None)

        rmse = round(math.sqrt(sum(sq_errors) / len(sq_errors)), 2) if sq_errors else None
        mae = round(sum(abs_errors) / len(abs_errors), 2) if abs_errors else None

    forecast_labels = []
    forecast_actual = []
    forecast_projected = []

    for obs in recent_obs[-12:]:
        forecast_labels.append(f"{obs.time_ist.strftime('%H:%M')}")
        forecast_actual.append(obs.aqi_index)
        forecast_projected.append(None)

    if recent_obs:
        latest = recent_obs[-1]
        base_dt = datetime.combine(latest.date_ist, latest.time_ist)
        forecast_projected[-1] = latest.aqi_index

        for step in range(1, 13):
            future_dt = base_dt + timedelta(hours=step)
            forecast_labels.append(f"+{step}h ({future_dt.strftime('%H:%M')})")
            forecast_actual.append(None)

            sim_temp = float(latest.temp_c or 25.0) + 2.5 * math.sin(step * math.pi / 12)
            sim_humidity = min(100, max(15, float(latest.humidity or 55) - 4.0 * math.sin(step * math.pi / 12)))
            sim_wind = max(1.0, 8.0 + 3.0 * math.cos(step * math.pi / 12))
            sim_pressure = 1012.0

            sim_ctx = {
                'temp_c': sim_temp,
                'humidity': sim_humidity,
                'windspeed_kph': sim_wind,
                'pressure_mb': sim_pressure,
            }
            if selected_algo and selected_algo.formula_spec and not formula_error:
                try:
                    val = eval_weather_model(selected_algo.formula_spec, sim_ctx)
                except Exception:
                    val = latest.aqi_index
            else:
                val = round(latest.aqi_index + (12 - sim_wind) * 1.8, 1)

            forecast_projected.append(val)

    scatter_wind = [{'x': float(r.windspeed_kph or 0), 'y': r.benchmark_aqi} for r in matrix_rows]
    scatter_temp = [{'x': float(r.temp_c or 0), 'y': r.benchmark_aqi} for r in matrix_rows]
    scatter_humidity = [{'x': float(r.humidity or 0), 'y': r.benchmark_aqi} for r in matrix_rows]

    chart_payload = {
        'forecast_labels': forecast_labels,
        'forecast_actual': forecast_actual,
        'forecast_projected': forecast_projected,
        'backtest_labels': backtest_labels,
        'actual_series': actual_series,
        'predicted_series': predicted_series,
        'scatter_wind': scatter_wind,
        'scatter_temp': scatter_temp,
        'scatter_humidity': scatter_humidity,
    }

    return render(request, 'core/algorithm_visualizer.html', {
        'algorithms': algorithms,
        'selected_algo': selected_algo,
        'locations': locations,
        'selected_location': selected_location,
        'rmse': rmse,
        'mae': mae,
        'formula_error': formula_error,
        'chart_payload_json': json.dumps(chart_payload),
    })
@login_required
def verifier_queue_view(request):
    if request.method == 'POST':
        queue_id = request.POST.get('queue_id')
        resolution_action = request.POST.get('resolution_action')

        item = get_object_or_404(VerifierValidationQueue, pk=queue_id)
        item.resolution_action = resolution_action
        item.is_resolved = True
        item.assigned_verifier_id = request.user.id
        item.save()

        messages.success(request, f'Queue #{queue_id} marked as {resolution_action}.')
        return redirect('verifier_queue')

    pending_items = (
        VerifierValidationQueue.objects
        .select_related('aqi_record')
        .filter(is_resolved=False)
        .order_by('queue_id')
    )
    resolved_items = (
        VerifierValidationQueue.objects
        .select_related('aqi_record')
        .filter(is_resolved=True)
        .order_by('-queue_id')[:15]
    )

    return render(request, 'core/verifier_queue.html', {
        'pending_items': pending_items,
        'resolved_items': resolved_items,
    })

