"""
Webhook Route
Handles Twilio status callbacks for call tracking and logging.
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/call-status", methods=["POST"])
def call_status():
    """Receives Twilio call status updates (completed, failed, busy, etc.)."""
    call_sid = request.form.get("CallSid", "N/A")
    call_status = request.form.get("CallStatus", "unknown")
    duration = request.form.get("CallDuration", "0")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(
        f"[{timestamp}] CallSid={call_sid} | Status={call_status} | Duration={duration}s"
    )

    return jsonify({"status": "received"}), 200


@webhook_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint — useful to verify ngrok tunnel is working."""
    return jsonify({"status": "ok", "service": "Hospital AI Voice Assistant"}), 200
