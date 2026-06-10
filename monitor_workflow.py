#!/usr/bin/env python3
"""
Monitor GitHub Actions workflow for successful runs and log results
"""
import requests
import json
import time
from datetime import datetime

REPO = "dnia9qbdkd/indicators-signal"
WORKFLOW_NAME = "Binance Trading Signals - Debug Test"
CHECK_INTERVAL = 60  # Check every 60 seconds
OUTPUT_FILE = "workflow_monitor.txt"

def get_latest_run():
    """Fetch latest workflow run"""
    url = f"https://api.github.com/repos/{REPO}/actions/runs"
    try:
        response = requests.get(url, params={"per_page": 1})
        response.raise_for_status()
        runs = response.json().get("workflow_runs", [])
        return runs[0] if runs else None
    except Exception as e:
        print(f"Error fetching workflow run: {e}")
        return None

def get_run_artifacts(run_id):
    """Fetch artifacts from a workflow run"""
    url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/artifacts"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("artifacts", [])
    except Exception as e:
        print(f"Error fetching artifacts: {e}")
        return []

def log_message(message):
    """Log message to console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(OUTPUT_FILE, "a") as f:
        f.write(log_entry + "\n")

def monitor_workflow():
    """Monitor workflow for successful runs"""
    log_message("Starting workflow monitor...")
    log_message(f"Repository: {REPO}")
    log_message(f"Workflow: {WORKFLOW_NAME}")
    log_message("=" * 80)
    
    last_run_id = None
    
    while True:
        try:
            run = get_latest_run()
            
            if not run:
                log_message("No workflow runs found.")
                time.sleep(CHECK_INTERVAL)
                continue
            
            run_id = run["id"]
            status = run["status"]
            conclusion = run["conclusion"]
            run_number = run["run_number"]
            
            # Check if this is a new run
            if run_id != last_run_id:
                log_message(f"\n🔄 New run detected: Run #{run_number} (ID: {run_id})")
                log_message(f"   Status: {status} | Conclusion: {conclusion}")
                last_run_id = run_id
            
            # Check for success
            if status == "completed" and conclusion == "success":
                log_message(f"\n✅ SUCCESS! Run #{run_number} completed successfully!")
                log_message(f"   Run URL: https://github.com/{REPO}/actions/runs/{run_id}")
                
                # Get artifacts
                artifacts = get_run_artifacts(run_id)
                if artifacts:
                    log_message(f"\n📦 Artifacts found ({len(artifacts)}):")
                    for artifact in artifacts:
                        log_message(f"   - {artifact['name']} (expires: {artifact['expires_at']})")
                        log_message(f"     Download: {artifact['url']}")
                else:
                    log_message("\n⚠️  No artifacts found in this run.")
                
                log_message("\n" + "=" * 80)
                log_message("🎉 WORKFLOW SUCCESS - Ready for Telegram integration!")
                log_message("=" * 80)
                break
            
            elif status == "completed" and conclusion == "failure":
                log_message(f"❌ Run #{run_number} FAILED")
                log_message(f"   Run URL: https://github.com/{REPO}/actions/runs/{run_id}")
            
            time.sleep(CHECK_INTERVAL)
        
        except Exception as e:
            log_message(f"❌ Error in monitoring loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Clear previous log
    open(OUTPUT_FILE, "w").close()
    monitor_workflow()
