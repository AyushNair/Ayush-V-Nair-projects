"""ClearPrompt: a local-first AI data-loss prevention demo."""
import csv
import io
import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from storage import DEFAULT_SETTINGS, clear_audit, get_audit, get_scan_count, get_settings, initialize, record_scan, save_settings
from detector import RULES, inspect_text, redact_text

RULE_LABELS = [rule[0] for rule in RULES]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("CLEARPROMPT_SECRET", "local-demo-only"),
        DATABASE=str(Path(__file__).parent / "instance" / "clearprompt.sqlite3"),
        MAX_CONTENT_LENGTH=1_200_000,
        MAX_TEXT_CHARS=1_000_000,
    )
    if test_config:
        app.config.update(test_config)
    initialize(app.config["DATABASE"])

    @app.get("/")
    def home():
        return render_template("index.html", rule_labels=RULE_LABELS)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "ClearPrompt", "storage": "sqlite"})

    @app.get("/api/stats")
    def api_stats():
        settings = get_settings(app.config["DATABASE"])
        return jsonify({"scan_count": get_scan_count(app.config["DATABASE"]),
                        "active_detectors": len(settings["enabled_detectors"])})

    @app.get("/api/settings")
    def api_get_settings():
        return jsonify(get_settings(app.config["DATABASE"]))

    @app.put("/api/settings")
    def api_save_settings():
        body = request.get_json(silent=True) or {}
        policy = body.get("policy", DEFAULT_SETTINGS["policy"])
        enabled = body.get("enabled_detectors", RULE_LABELS)
        keywords = body.get("custom_keywords", [])
        if policy not in {"warn", "redact", "block"}:
            return jsonify(error="Choose warn, redact, or block."), 400
        if not isinstance(enabled, list) or any(item not in RULE_LABELS for item in enabled):
            return jsonify(error="One or more detector names are invalid."), 400
        if not isinstance(keywords, list) or any(not isinstance(term, str) for term in keywords):
            return jsonify(error="Custom keywords must be a list of text values."), 400
        clean_keywords = list(dict.fromkeys(term.strip() for term in keywords if 2 <= len(term.strip()) <= 100))[:50]
        settings = {"policy": policy, "enabled_detectors": enabled, "custom_keywords": clean_keywords}
        save_settings(app.config["DATABASE"], settings)
        return jsonify(settings)

    def scan_content(text: str, policy: str | None = None, enabled: list[str] | None = None,
                     keywords: list[str] | None = None) -> dict:
        settings = get_settings(app.config["DATABASE"])
        if policy is None:
            policy = settings["policy"]
        if enabled is None:
            enabled = settings["enabled_detectors"]
        if keywords is None:
            keywords = settings["custom_keywords"]
        if policy not in {"warn", "redact", "block"}:
            raise ValueError("Choose warn, redact, or block.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Enter some text to scan.")
        if len(text) > app.config["MAX_TEXT_CHARS"]:
            raise ValueError("Keep submitted text under 1 MB.")
        if not isinstance(enabled, list) or any(item not in RULE_LABELS for item in enabled):
            raise ValueError("One or more detector names are invalid.")
        if not isinstance(keywords, list) or any(not isinstance(item, str) for item in keywords):
            raise ValueError("Custom keywords must be a list of text values.")
        findings = inspect_text(text, set(enabled), keywords)
        if policy == "block" and findings:
            outcome, sanitized = "Blocked", None
        elif policy == "redact" and findings:
            outcome, sanitized = "Redacted", redact_text(text, findings)
        elif findings:
            outcome, sanitized = "Warning", None
        else:
            outcome, sanitized = "Allowed", None
        record_scan(app.config["DATABASE"], policy, outcome, findings)
        return {
            "outcome": outcome,
            "policy": policy,
            "finding_count": len(findings),
            "findings": [{"type": item["type"], "explanation": item["explanation"]} for item in findings],
            "sanitized_text": sanitized,
            "blocked_message": "Content was blocked by the selected policy." if outcome == "Blocked" else None,
        }

    @app.post("/api/scan")
    def api_scan():
        body = request.get_json(silent=True) or {}
        try:
            result = scan_content(
                body.get("content", ""), body.get("policy"),
                body.get("enabled_detectors"), body.get("custom_keywords"),
            )
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(result)

    @app.post("/api/scan-file")
    def api_scan_file():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify(error="Choose a .txt file to scan."), 400
        if not uploaded.filename.lower().endswith(".txt"):
            return jsonify(error="Only plain text (.txt) files are supported."), 400
        raw = uploaded.stream.read(app.config["MAX_TEXT_CHARS"] + 1)
        if len(raw) > app.config["MAX_TEXT_CHARS"]:
            return jsonify(error="Keep files under 1 MB."), 413
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify(error="This file is not valid UTF-8 text."), 400
        try:
            result = scan_content(text)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        result["file_name"] = Path(uploaded.filename.replace("\\", "/")).name
        return jsonify(result)

    @app.get("/api/audit")
    def api_audit():
        return jsonify(get_audit(app.config["DATABASE"], limit=min(request.args.get("limit", 50, type=int), 200)))

    @app.get("/api/audit/export.csv")
    def api_export_audit():
        events = get_audit(app.config["DATABASE"], limit=10_000)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["timestamp_utc", "policy", "outcome", "finding_count", "finding_types"])
        for event in events:
            writer.writerow([event["timestamp"], event["policy"], event["outcome"], event["finding_count"], "; ".join(event["finding_types"])])
        return send_file(io.BytesIO(buffer.getvalue().encode("utf-8-sig")), mimetype="text/csv",
                         as_attachment=True, download_name="clearprompt-audit.csv")

    @app.delete("/api/audit")
    def api_clear_audit():
        clear_audit(app.config["DATABASE"])
        return jsonify({"cleared": True})

    return app


app = create_app()


if __name__ == "__main__":
    import time
    import webbrowser
    from threading import Thread

    def open_browser():
        time.sleep(2)
        url = "http://127.0.0.1:5000"
        if os.name == "nt":
            os.startfile(url)
        else:
            webbrowser.open_new_tab(url)

    Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
