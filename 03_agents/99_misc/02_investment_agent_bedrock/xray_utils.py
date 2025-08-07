import datetime
import uuid
import json
import re
import time
import secrets
from dateutil import tz  # Required: pip install python-dateutil

# --- Helper Functions (Unchanged) ---


def _generate_segment_id():
    """Generates a 16-character hex ID compatible with X-Ray."""
    return uuid.uuid4().hex[:16]


def _to_epoch_float(dt):
    """Converts a datetime object to Unix epoch float (seconds.milliseconds)."""
    if not isinstance(dt, datetime.datetime):
        return time.time()  # Fallback

    if dt.tzinfo:
        return dt.astimezone(datetime.timezone.utc).timestamp()
    else:
        # Assume UTC if naive
        return dt.replace(tzinfo=datetime.timezone.utc).timestamp()


def _generate_xray_trace_id(start_epoch_seconds: int) -> str:
    """Generates a compliant X-Ray Trace ID (version-timestamp_hex-guid_hex)."""
    timestamp_hex = format(start_epoch_seconds, "08x")
    guid_hex = secrets.token_hex(12)  # 12 bytes = 24 hex characters
    return f"1-{timestamp_hex}-{guid_hex}"


def _safe_get(data, keys, default=None):
    """Safely get a nested key from a dict."""
    if not isinstance(keys, (list, tuple)):
        keys = [keys]
    current = data
    for key in keys:
        try:
            if isinstance(key, int) and isinstance(current, (list, tuple)):
                current = current[key]
            elif isinstance(current, dict):
                current = current[key]
            else:
                return default
        except (KeyError, TypeError, IndexError, AttributeError):
            return default
    return current


def _truncate_string(text, max_length=500):
    """Truncates string if it exceeds max_length and ensures basic types."""
    if isinstance(text, str) and len(text) > max_length:
        return text[:max_length] + "... (truncated)"
    if not isinstance(text, (str, int, float, bool, list, dict)) and text is not None:
        return str(text)
    return text


# --- Main Function ---


def create_xray_segments_from_events(events: list) -> list[str]:
    """
    Converts Bedrock Agent trace events into X-Ray segment documents,
    linking subsegments sequentially and using unique, descriptive names.

    Args:
        events: List of Bedrock Agent trace event dictionaries, ordered chronologically.

    Returns:
        List of JSON strings (X-Ray segment documents). Empty list on failure.
    """
    XRAY_ORIGIN = "AWS::Bedrock::Agent"
    segment_documents = []

    if not events or not isinstance(events, list):
        print("Warning: Input 'events' is not a valid list.")
        return []

    # --- Validate time info & Generate IDs ---
    first_event = events[0]
    last_event = events[-1]
    if not isinstance(
        _safe_get(first_event, ["eventTime"]), datetime.datetime
    ) or not isinstance(_safe_get(last_event, ["eventTime"]), datetime.datetime):
        print(
            "Warning: First or last event is missing a valid 'eventTime'. Cannot process."
        )
        return []

    parent_start_time = _to_epoch_float(first_event["eventTime"])
    parent_end_time = _to_epoch_float(last_event["eventTime"])
    base_trace_id = _generate_xray_trace_id(int(parent_start_time))
    parent_segment_id = _generate_segment_id()

    if parent_end_time < parent_start_time:
        parent_end_time = parent_start_time + 0.001

    agent_id = _safe_get(first_event, ["agentId"])
    session_id = _safe_get(first_event, ["sessionId"])
    agent_version = _safe_get(first_event, ["agentVersion"])
    agent_alias_id = _safe_get(first_event, ["agentAliasId"])

    # --- Create Subsegments with Sequential Linking and Unique Names ---
    previous_segment_or_subsegment_id = parent_segment_id

    for i, event in enumerate(events):
        event_time_obj = _safe_get(event, ["eventTime"])
        if not isinstance(event_time_obj, datetime.datetime):
            print(
                f"Warning: Skipping event at index {i} due to missing or invalid 'eventTime'."
            )
            continue

        current_subsegment_id = _generate_segment_id()
        start_time = _to_epoch_float(event_time_obj)

        # Determine end time
        if i + 1 < len(events):
            next_event_time_obj = _safe_get(events[i + 1], ["eventTime"])
            if isinstance(next_event_time_obj, datetime.datetime):
                end_time = _to_epoch_float(next_event_time_obj)
            else:
                end_time = max(parent_end_time, start_time + 0.001)
        else:
            end_time = parent_end_time

        if end_time < start_time:
            end_time = start_time + 0.001

        # --- Extract details and Determine BASE Subsegment Name ---
        orch_trace = _safe_get(event, ["trace", "orchestrationTrace"], {})
        base_subsegment_name = "OrchestrationStep"  # Default name
        annotations = {}
        metadata = {"bedrock_agent_details": {}}

        # Common annotations
        if agent_id:
            annotations["agentId"] = agent_id
        if session_id:
            annotations["sessionId"] = session_id
        if agent_version:
            annotations["agentVersion"] = agent_version
        if agent_alias_id:
            annotations["agentAliasId"] = agent_alias_id

        # --- Type-specific extraction and BASE NAME setting ---
        if "modelInvocationInput" in orch_trace:
            base_subsegment_name = "ModelInvocationInput"
            # ... (extract modelInput details - same as before) ...
            step_data = orch_trace["modelInvocationInput"]
            model_id = _safe_get(step_data, ["foundationModel"])
            if model_id:
                annotations["foundationModel"] = model_id
            inv_type = _safe_get(step_data, ["type"])
            if inv_type:
                annotations["invocationType"] = inv_type
            metadata["bedrock_agent_details"]["inferenceConfiguration"] = _safe_get(
                step_data, ["inferenceConfiguration"]
            )
            metadata["bedrock_agent_details"]["inputText"] = _truncate_string(
                _safe_get(step_data, ["text"]), 1024
            )

        elif "modelInvocationOutput" in orch_trace:
            base_subsegment_name = "ModelInvocationOutput"
            # ... (extract modelOutput details - same as before) ...
            step_data = orch_trace["modelInvocationOutput"]
            usage = _safe_get(step_data, ["metadata", "usage"])
            if usage:
                if _safe_get(usage, ["inputTokens"]) is not None:
                    annotations["inputTokens"] = usage["inputTokens"]
                if _safe_get(usage, ["outputTokens"]) is not None:
                    annotations["outputTokens"] = usage["outputTokens"]
                metadata["bedrock_agent_details"]["usage"] = usage

            raw_response_str = _safe_get(step_data, ["rawResponse"])
            metadata["bedrock_agent_details"]["rawResponse"] = _truncate_string(
                raw_response_str, 2048
            )
            if isinstance(raw_response_str, str):
                try:
                    raw_response_json = json.loads(raw_response_str)
                    stop_reason = _safe_get(raw_response_json, ["stop_reason"])
                    if stop_reason:
                        annotations["stopReason"] = stop_reason
                    content_list = _safe_get(raw_response_json, ["content"], [])
                    if isinstance(content_list, list):
                        for content_item in content_list:
                            if (
                                isinstance(content_item, dict)
                                and _safe_get(content_item, ["type"]) == "tool_use"
                            ):
                                tool_name = _safe_get(content_item, ["name"])
                                tool_use_id = _safe_get(content_item, ["id"])
                                tool_input = _safe_get(content_item, ["input"])
                                if tool_name:
                                    annotations["requestedToolName"] = tool_name
                                if tool_use_id:
                                    annotations["requestedToolUseId"] = tool_use_id
                                if tool_input is not None:
                                    metadata["bedrock_agent_details"][
                                        "requestedToolInput"
                                    ] = tool_input
                                break
                except (json.JSONDecodeError, TypeError):
                    pass

        elif "rationale" in orch_trace:
            base_subsegment_name = "Rationale"
            # ... (extract rationale details - same as before) ...
            step_data = orch_trace["rationale"]
            metadata["bedrock_agent_details"]["rationaleText"] = _truncate_string(
                _safe_get(step_data, ["text"])
            )

        elif "invocationInput" in orch_trace:
            # *** RENAMED based on feedback ***
            base_subsegment_name = "ActionGroupInvocation"
            step_data = orch_trace["invocationInput"]
            invocation_type = _safe_get(step_data, ["invocationType"])
            if invocation_type:
                annotations["invocationType"] = invocation_type

            if invocation_type == "ACTION_GROUP":
                action_input = _safe_get(step_data, ["actionGroupInvocationInput"], {})
                action_group_name = _safe_get(action_input, ["actionGroupName"])
                api_path = _safe_get(action_input, ["apiPath"])
                verb = _safe_get(action_input, ["verb"])
                params = _safe_get(action_input, ["parameters"])
                if action_group_name:
                    annotations["actionGroupName"] = action_group_name
                if api_path:
                    annotations["actionGroupApi"] = api_path
                if verb:
                    annotations["actionGroupVerb"] = verb
                if params:
                    metadata["bedrock_agent_details"]["parameters"] = params

        elif "observation" in orch_trace:
            step_data = orch_trace["observation"]
            observation_type = _safe_get(step_data, ["type"])
            if observation_type:
                annotations["observationType"] = observation_type

            # *** Set specific BASE names based on observation type ***
            if observation_type == "ACTION_GROUP":
                # RENAMED
                base_subsegment_name = "ActionGroupObservation"
                action_output = _safe_get(
                    step_data, ["actionGroupInvocationOutput"], {}
                )
                output_text = _safe_get(action_output, ["text"])
                metadata["bedrock_agent_details"]["actionGroupOutputText"] = (
                    _truncate_string(output_text, 1024)
                )
            elif observation_type == "FINISH":
                base_subsegment_name = "FinalResponse"
                final_response = _safe_get(step_data, ["finalResponse"], {})
                response_text = _safe_get(final_response, ["text"])
                metadata["bedrock_agent_details"]["finalResponseText"] = (
                    _truncate_string(response_text, 2048)
                )
            else:
                base_subsegment_name = "Observation"  # Fallback if type unknown

        # --- Create UNIQUE Subsegment Name ---
        try:
            start_dt_utc = datetime.datetime.fromtimestamp(
                start_time, tz=datetime.timezone.utc
            )
            # Format: HHMMSS_milliseconds (e.g., 191650_354)
            time_suffix = start_dt_utc.strftime("%H%M%S_%f")[:-3]
        except Exception:
            time_suffix = current_subsegment_id[:6]  # Fallback using part of unique ID

        # *** Use unique name ***
        unique_subsegment_name = f"{base_subsegment_name}-{time_suffix}"

        # Common Metadata Field (callerChain)
        caller_chain = _safe_get(event, ["callerChain"])
        if caller_chain:
            # Ensure metadata dict exists before adding
            if "bedrock_agent_details" not in metadata:
                metadata["bedrock_agent_details"] = {}
            metadata["bedrock_agent_details"][
                "callerChain"
            ] = caller_chain  # Add here for context

        # Clean annotations and metadata
        cleaned_annotations = {
            k: v
            for k, v in annotations.items()
            if isinstance(v, (str, int, float, bool)) and v is not None
        }
        cleaned_metadata = {
            k: _truncate_string(v, 1024) for k, v in metadata.items()
        }  # Includes bedrock_agent_details

        # --- Build Subsegment Document ---
        subsegment_doc = {
            "id": current_subsegment_id,
            "trace_id": base_trace_id,
            "parent_id": previous_segment_or_subsegment_id,
            "name": unique_subsegment_name,  # Use the unique name
            "start_time": start_time,
            "end_time": end_time,
            "origin": XRAY_ORIGIN,
            "service": {"version": agent_version} if agent_version else {},
            "annotations": cleaned_annotations,
            "metadata": cleaned_metadata,
            "in_progress": False,
        }
        try:
            segment_documents.append(json.dumps(subsegment_doc))
            # *** Update previous ID for next iteration ***
            previous_segment_or_subsegment_id = current_subsegment_id
        except TypeError as e:
            print(
                f"Warning: Could not serialize subsegment at index {i} to JSON: {e}. Skipping."
            )
            print(f"Problematic subsegment data: {subsegment_doc}")

    # --- Create Parent Segment Document (logic unchanged) ---
    parent_annotations = {}
    if agent_id:
        parent_annotations["agentId"] = agent_id
    if session_id:
        parent_annotations["sessionId"] = session_id
    if agent_version:
        parent_annotations["agentVersion"] = agent_version
    if agent_alias_id:
        parent_annotations["agentAliasId"] = agent_alias_id
    parent_annotations["eventCount"] = sum(
        1
        for evt in events
        if isinstance(_safe_get(evt, ["eventTime"]), datetime.datetime)
    )

    cleaned_parent_annotations = {
        k: v
        for k, v in parent_annotations.items()
        if isinstance(v, (str, int, float, bool)) and v is not None
    }
    parent_metadata = {}
    first_caller_chain = _safe_get(first_event, ["callerChain"])
    if first_caller_chain:
        parent_metadata["callerChain"] = first_caller_chain

    parent_segment_doc = {
        "id": parent_segment_id,
        "trace_id": base_trace_id,
        "name": f"BedrockAgent-{agent_id or 'Unknown'}",
        "start_time": parent_start_time,
        "end_time": parent_end_time,
        "origin": XRAY_ORIGIN,
        "service": {"version": agent_version} if agent_version else {},
        "annotations": cleaned_parent_annotations,
        "metadata": parent_metadata,
        "in_progress": False,
    }
    try:
        segment_documents.append(json.dumps(parent_segment_doc))
    except TypeError as e:
        print(
            f"Warning: Could not serialize parent segment to JSON: {e}. Skipping parent."
        )
        print(f"Problematic parent segment data: {parent_segment_doc}")

    return segment_documents
