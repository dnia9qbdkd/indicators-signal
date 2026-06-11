#!/usr/bin/env python3
"""
Manually trigger a GitHub Actions workflow run
"""
import os
import requests
import sys

REPO = "dnia9qbdkd/indicators-signal"
WORKFLOW_FILE = "trading-signals.yml"

def trigger_workflow(token):
    """Trigger a workflow dispatch"""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "ref": "main"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 204:
            print("✅ Workflow triggered successfully!")
            print(f"Check status at: https://github.com/{REPO}/actions")
            return True
        else:
            print(f"❌ Failed to trigger workflow: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ ERROR: GITHUB_TOKEN environment variable not set")
        print("Please set it with: export GITHUB_TOKEN=<your_github_personal_access_token>")
        sys.exit(1)
    
    trigger_workflow(token)
