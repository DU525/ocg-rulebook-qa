from flask import Blueprint, jsonify, request
from app.core.monitoring_scheduler import (
    get_monitoring_status,
    get_schedule_info,
    run_job_now,
)

monitoring = Blueprint("monitoring", __name__, url_prefix="/api/v1/monitoring")


@monitoring.route("/status", methods=["GET"])
def monitoring_status():
    status = get_monitoring_status()
    return jsonify({"success": True, "data": status})


@monitoring.route("/schedule", methods=["GET"])
def monitoring_schedule():
    schedule = get_schedule_info()
    return jsonify({"success": True, "data": schedule})


@monitoring.route("/run-now", methods=["POST"])
def run_now():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    if not job_id:
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "job_id is required"},
        }), 400

    result = run_job_now(job_id)
    if result.get("success"):
        return jsonify({"success": True, "data": result})
    return jsonify({
        "success": False,
        "error": {"code": "EXECUTION_FAILED", "message": result.get("error", "Unknown error")},
    }), 500
