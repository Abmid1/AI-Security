"""Background scan workers.

Scans run OUTSIDE the web server. In production the API spawns a separate OS
process (`python -m app.workers.run_scan <job_id>`); the scan logic itself lives
in runner.run_scan_job so it can also be driven in-process by tests.
"""
