#!/usr/bin/env python3
"""Manually start one Box Relay General Task, assigned only to yourself."""

import argparse
import json
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.box_client import BoxClient, BoxError, box_id
from app.config import load_settings


def start_review(client, workflow_id, file_id):
    workflow_id, file_id = box_id(workflow_id), box_id(file_id)
    user_id = box_id(client.identity()["id"])
    selected = client.request("GET", f"/2.0/files/{file_id}", params={"fields": "id,parent,owned_by"})
    if str((selected.get("owned_by") or {}).get("id")) != user_id:
        raise BoxError("This demo helper only starts review on files owned by the authenticated Box user.")
    folder_id = box_id(selected["parent"]["id"])
    tasks = client.request("GET", f"/2.0/files/{file_id}/tasks")
    if any(task.get("is_completed") is not True for task in tasks["entries"]):
        raise BoxError("The file already has a pending task. No duplicate review was started.")
    listing = client.request("GET", "/2.0/workflows", params={"folder_id": folder_id, "limit": 1000})
    matches = [item for item in listing["entries"] if str(item.get("id")) == workflow_id]
    if len(matches) != 1 or matches[0].get("is_enabled") is not True:
        raise BoxError("The specified workflow is not enabled for this file's parent folder.")
    flows = [flow for flow in matches[0].get("flows", [])
             if flow.get("trigger", {}).get("trigger_type") == "WORKFLOW_MANUAL_START"
             and any(scope.get("object", {}).get("type") == "folder"
                     and str(scope["object"].get("id")) == folder_id
                     for scope in flow["trigger"].get("scope", []))]
    if len(flows) != 1 or len(flows[0].get("outcomes", [])) != 1:
        raise BoxError("Use a workflow with one matching Manual Start flow and one General Task outcome.")
    flow, outcome = flows[0], flows[0]["outcomes"][0]
    parameters = outcome.get("outcome_parameters") or {}
    if (outcome.get("action_type") != "assign_task"
            or parameters.get("task_type", {}).get("value") != "GENERAL"
            or parameters.get("task_collaborators", {}).get("type") != "variable"):
        raise BoxError("The workflow must assign a General Task with assignees specified when started.")

    def variable(kind, value):
        return {"type": "variable", "variable_type": kind, "variable_value": value}

    payload = {
        "type": "workflow_parameters", "flow": {"id": box_id(flow["id"]), "type": "flow"},
        "files": [{"type": "file", "id": file_id}], "folder": {"type": "folder", "id": folder_id},
        "outcomes": [{"id": box_id(outcome["id"]), "type": "outcome",
                      "task_collaborators": variable("user_list", [{"type": "user", "id": user_id}]),
                      "completion_rule": variable("task_completion_rule", "all_assignees"),
                      "file_collaborator_role": variable("collaborator_role", "viewer")}],
    }
    # BoxClient.request retries some failures and expects JSON; start returns
    # 204, so submit directly exactly once and never replay an uncertain POST.
    try:
        response = client.http.post(f"https://api.box.com/2.0/workflows/{workflow_id}/start",
                                    headers={"Authorization": "Bearer " + client.token()}, json=payload)
    except httpx.HTTPError:
        raise BoxError("The start result is unknown. Check Box Activity before retrying; the request was not replayed.") from None
    if response.status_code != 204:
        raise BoxError(f"Workflow start returned HTTP {response.status_code}. Check Box Activity before retrying; no automatic retry was made.")
    return {"status": "started", "workflow_id": workflow_id, "file_id": file_id,
            "assignee_id": user_id, "file_url": f"https://app.box.com/file/{file_id}", "review_completed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-id", required=True, help="Enabled Relay workflow with a single Manual Start General Task.")
    parser.add_argument("--file-id", required=True, help="Report file owned by the authenticated Box user.")
    arguments = parser.parse_args()
    client = BoxClient(load_settings())
    try:
        print(json.dumps(start_review(client, arguments.workflow_id, arguments.file_id)))
        return 0
    except BoxError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Review could not be started or its result is unknown. Check Box Activity before retrying. No provider details were logged.", file=sys.stderr)
        return 1
    finally:
        client.http.close()


if __name__ == "__main__":
    raise SystemExit(main())
