"""Translating proxy: OpenAI Chat Completions in front of Claude deployed in Microsoft Foundry.

Claude deployments in Foundry answer the Anthropic Messages API and the OpenAI Responses API, but return
404 api_not_supported on Chat Completions, the API that OpenAI-compatible clients and Cursor's Azure OpenAI
and Override OpenAI Base URL settings send. This proxy accepts Chat Completions on the paths those clients
use (including the legacy /openai/deployments/<name>/chat/completions form), translates the request to the
Messages API (default) or the Responses API, and translates the answer, streamed or not, back to Chat
Completions, including tool calls and token usage. Requests for an OpenAI deployment pass through.

Clients authenticate with a proxy secret, never with the Foundry key. The proxy calls only the configured
Foundry resource, with its API key (FOUNDRY_API_KEY or `az`) or a Microsoft Entra token, and logs request
shapes, status and token usage, never keys or prompt text. It binds to 127.0.0.1; put a tunnel in front of
it only while testing, because a hosted client such as Cursor calls it from the internet.
"""

import argparse
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from capture_proxy import body_shape
from foundry_client import ROOT, load_config

ANTHROPIC_VERSION = "2023-06-01"
ENTRA_SCOPE = "https://ai.azure.com/.default"
DEFAULT_MAX_TOKENS = 8192
MAX_BODY = 16 * 1024 * 1024
REQUEST_ID_HEADERS = ("apim-request-id", "x-request-id", "request-id", "x-ms-request-id")
STOP_REASONS = {"end_turn": "stop", "stop_sequence": "stop", "pause_turn": "stop", "max_tokens": "length",
                "model_context_window_exceeded": "length", "tool_use": "tool_calls", "refusal": "content_filter"}


class TranslationError(ValueError):
    """The Chat Completions request uses something the target API cannot express."""


def parse_route(path):
    """Map a request path to (kind, deployment). kind is chat, responses, models or None."""
    path = path.rstrip("/")
    match = re.fullmatch(r"/openai/deployments/([^/]+)/(chat/completions|responses)", path)
    if match:
        return ("chat" if match.group(2) == "chat/completions" else "responses"), unquote(match.group(1))
    match = re.fullmatch(r"(?:/openai)?(?:/v1)?/(chat/completions|responses|models)", path)
    if match:
        return {"chat/completions": "chat", "responses": "responses", "models": "models"}[match.group(1)], None
    return None, None


def _text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content
                   if not isinstance(part, dict) or part.get("type") in ("text", "input_text", "output_text"))


def _arguments(raw):
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _image_url(part):
    image = part.get("image_url")
    return image.get("url") if isinstance(image, dict) else image


def _max_tokens(body, default):
    value = body.get("max_completion_tokens") or body.get("max_tokens") or default
    if type(value) is not int or value < 1:
        raise TranslationError("max_tokens must be a positive integer")
    return value


def _check_common(body):
    if (body.get("n") or 1) != 1:
        raise TranslationError("n must be 1: Claude returns one choice per request")
    if not isinstance(body.get("messages"), list) or not body["messages"]:
        raise TranslationError("messages must be a non-empty list")


def chat_to_messages(body, deployment, default_max_tokens=DEFAULT_MAX_TOKENS):
    """Translate a Chat Completions request body to an Anthropic Messages request body."""
    _check_common(body)
    system, messages = [], []

    def add(role, blocks):
        if not blocks:
            return
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": list(blocks)})

    for message in body["messages"]:
        role, content = message.get("role"), message.get("content")
        if role in ("system", "developer"):
            if _text(content):
                system.append({"type": "text", "text": _text(content)})
        elif role == "user":
            blocks = []
            for part in [content] if isinstance(content, str) else content or []:
                if isinstance(part, str) or part.get("type") == "text":
                    text = part if isinstance(part, str) else part.get("text", "")
                    if text:
                        blocks.append({"type": "text", "text": text})
                elif part.get("type") == "image_url":
                    url = _image_url(part) or ""
                    if url.startswith("data:"):
                        header, _, data = url.partition(",")
                        media_type = header[5:].split(";")[0] or "image/png"
                        blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                                   "data": data}})
                    else:
                        blocks.append({"type": "image", "source": {"type": "url", "url": url}})
                else:
                    raise TranslationError(f"unsupported user content part: {part.get('type')!r}")
            add("user", blocks)
        elif role == "assistant":
            blocks = [{"type": "text", "text": _text(content)}] if _text(content) else []
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                blocks.append({"type": "tool_use", "id": call.get("id"), "name": function.get("name"),
                               "input": _arguments(function.get("arguments"))})
            add("assistant", blocks)
        elif role == "tool":
            result = {"type": "tool_result", "tool_use_id": message.get("tool_call_id")}
            if _text(content):
                result["content"] = _text(content)
            add("user", [result])
        else:
            raise TranslationError(f"unsupported message role: {role!r}")

    out = {"model": deployment, "max_tokens": _max_tokens(body, default_max_tokens), "messages": messages}
    if system:
        out["system"] = system
    tools = []
    for tool in body.get("tools") or []:
        if tool.get("type") != "function":
            raise TranslationError(f"unsupported tool type: {tool.get('type')!r}")
        function = tool.get("function") or {}
        spec = {"name": function.get("name"),
                "input_schema": function.get("parameters") or {"type": "object", "properties": {}}}
        if function.get("description"):
            spec["description"] = function["description"]
        tools.append(spec)
    if tools:
        out["tools"] = tools
        choice = body.get("tool_choice")
        tool_choice = None
        if choice in ("auto", "none"):
            tool_choice = {"type": choice}
        elif choice == "required":
            tool_choice = {"type": "any"}
        elif isinstance(choice, dict) and choice.get("type") == "function":
            tool_choice = {"type": "tool", "name": (choice.get("function") or {}).get("name")}
        if body.get("parallel_tool_calls") is False and (tool_choice or {}).get("type") != "none":
            tool_choice = dict(tool_choice or {"type": "auto"}, disable_parallel_tool_use=True)
        if tool_choice:
            out["tool_choice"] = tool_choice
    # Claude rejects temperature above 1 and, on recent models, temperature together with top_p.
    if body.get("temperature") is not None:
        out["temperature"] = min(float(body["temperature"]), 1.0)
    elif body.get("top_p") is not None:
        out["top_p"] = body["top_p"]
    stop = body.get("stop")
    if stop:
        out["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
    if body.get("stream"):
        out["stream"] = True
    return out


def chat_to_responses(body, deployment, default_max_tokens=DEFAULT_MAX_TOKENS):
    """Translate a Chat Completions request body to a Responses API request body."""
    _check_common(body)
    instructions, items = [], []
    for message in body["messages"]:
        role, content = message.get("role"), message.get("content")
        if role in ("system", "developer"):
            if _text(content):
                instructions.append(_text(content))
        elif role == "user":
            parts = []
            for part in [content] if isinstance(content, str) else content or []:
                if isinstance(part, str) or part.get("type") == "text":
                    text = part if isinstance(part, str) else part.get("text", "")
                    if text:
                        parts.append({"type": "input_text", "text": text})
                elif part.get("type") == "image_url":
                    parts.append({"type": "input_image", "image_url": _image_url(part)})
                else:
                    raise TranslationError(f"unsupported user content part: {part.get('type')!r}")
            if parts:
                items.append({"role": "user", "content": parts})
        elif role == "assistant":
            if _text(content):
                items.append({"type": "message", "role": "assistant",
                              "content": [{"type": "output_text", "text": _text(content)}]})
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                items.append({"type": "function_call", "call_id": call.get("id"), "name": function.get("name"),
                              "arguments": function.get("arguments") or "{}"})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": message.get("tool_call_id"),
                          "output": _text(content)})
        else:
            raise TranslationError(f"unsupported message role: {role!r}")

    out = {"model": deployment, "input": items, "store": False,
           "max_output_tokens": _max_tokens(body, default_max_tokens)}
    if instructions:
        out["instructions"] = "\n\n".join(instructions)
    tools = []
    for tool in body.get("tools") or []:
        if tool.get("type") != "function":
            raise TranslationError(f"unsupported tool type: {tool.get('type')!r}")
        function = tool.get("function") or {}
        spec = {"type": "function", "name": function.get("name"),
                "parameters": function.get("parameters") or {"type": "object", "properties": {}}}
        for key in ("description", "strict"):
            if function.get(key) is not None:
                spec[key] = function[key]
        tools.append(spec)
    if tools:
        out["tools"] = tools
        choice = body.get("tool_choice")
        if choice in ("auto", "none", "required"):
            out["tool_choice"] = choice
        elif isinstance(choice, dict) and choice.get("type") == "function":
            out["tool_choice"] = {"type": "function", "name": (choice.get("function") or {}).get("name")}
        # Claude on Foundry's Responses route merges parallel tool calls into one call that keeps only the
        # last call's arguments, so ask for one call per turn; the client loops until the work is done.
        out["parallel_tool_calls"] = False
    for key in ("temperature", "top_p"):
        if body.get(key) is not None:
            out[key] = body[key]
    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_object":
        out["text"] = {"format": {"type": "json_object"}}
    elif response_format.get("type") == "json_schema":
        schema = response_format.get("json_schema") or {}
        out["text"] = {"format": {"type": "json_schema", "name": schema.get("name", "response"),
                                  "schema": schema.get("schema", {}), "strict": schema.get("strict", False)}}
    if body.get("stream"):
        out["stream"] = True
    return out


def messages_usage(usage):
    cached = usage.get("cache_read_input_tokens") or 0
    prompt = (usage.get("input_tokens") or 0) + cached + (usage.get("cache_creation_input_tokens") or 0)
    completion = usage.get("output_tokens") or 0
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion,
            "prompt_tokens_details": {"cached_tokens": cached}}


def responses_usage(usage):
    prompt, completion = usage.get("input_tokens") or 0, usage.get("output_tokens") or 0
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion,
            "prompt_tokens_details": {"cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens") or 0},
            "completion_tokens_details": {
                "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0}}


def _completion(model, message, finish, usage, response_id=None):
    return {"id": "chatcmpl-" + (response_id or uuid.uuid4().hex), "object": "chat.completion",
            "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage}


def messages_to_chat(response, model):
    text, calls = [], []
    for block in response.get("content") or []:
        if block.get("type") == "text":
            text.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            calls.append({"id": block.get("id"), "type": "function",
                          "function": {"name": block.get("name"), "arguments": json.dumps(block.get("input") or {})}})
    message = {"role": "assistant", "content": "".join(text) or None}
    if calls:
        message["tool_calls"] = calls
    finish = STOP_REASONS.get(response.get("stop_reason"), "tool_calls" if calls else "stop")
    return _completion(model, message, finish, messages_usage(response.get("usage") or {}), response.get("id"))


def responses_to_chat(response, model):
    text, calls = [], []
    for item in response.get("output") or []:
        if item.get("type") == "message":
            text.extend(part.get("text", "") for part in item.get("content") or [] if part.get("type") == "output_text")
        elif item.get("type") == "function_call":
            calls.append({"id": item.get("call_id"), "type": "function",
                          "function": {"name": item.get("name"), "arguments": item.get("arguments") or "{}"}})
    message = {"role": "assistant", "content": "".join(text) or None}
    if calls:
        message["tool_calls"] = calls
    finish = "tool_calls" if calls else "stop"
    if response.get("status") == "incomplete":
        reason = (response.get("incomplete_details") or {}).get("reason")
        finish = "content_filter" if reason == "content_filter" else "length"
    return _completion(model, message, finish, responses_usage(response.get("usage") or {}), response.get("id"))


class _StreamTranslator:
    """Turns upstream SSE events into Chat Completions chunks. feed() and close() return chunk dicts."""

    def __init__(self, model, include_usage):
        self.model, self.include_usage = model, include_usage
        self.id, self.created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
        self.tool_calls, self.finish, self.usage, self.done, self.error = 0, None, None, False, None

    def chunk(self, delta, finish=None):
        return {"id": self.id, "object": "chat.completion.chunk", "created": self.created, "model": self.model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}

    def tool_header(self, call_id, name):
        index, self.tool_calls = self.tool_calls, self.tool_calls + 1
        return index, self.chunk({"tool_calls": [{"index": index, "id": call_id, "type": "function",
                                                  "function": {"name": name, "arguments": ""}}]})

    def tool_arguments(self, index, arguments):
        return self.chunk({"tool_calls": [{"index": index, "function": {"arguments": arguments}}]})

    def fail(self, error):
        self.done, self.error = True, error or {"message": "upstream error"}
        return [{"error": self.error}]

    def close(self):
        if self.done:
            return []
        self.done = True
        finish = self.finish or ("tool_calls" if self.tool_calls else "stop")
        self.finish = finish
        chunks = [self.chunk({}, finish)]
        if self.include_usage and self.usage:
            chunks.append({"id": self.id, "object": "chat.completion.chunk", "created": self.created,
                           "model": self.model, "choices": [], "usage": self.usage})
        return chunks


class MessagesStream(_StreamTranslator):
    def __init__(self, model, include_usage):
        super().__init__(model, include_usage)
        self.blocks, self.raw_usage = {}, {}

    def feed(self, event):
        kind = event.get("type")
        if kind == "message_start":
            self.raw_usage.update((event.get("message") or {}).get("usage") or {})
            return [self.chunk({"role": "assistant", "content": ""})]
        if kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                index, header = self.tool_header(block.get("id"), block.get("name"))
                self.blocks[event.get("index")] = {"tool": index, "args": False}
                return [header]
            if block.get("type") == "text" and block.get("text"):
                return [self.chunk({"content": block["text"]})]
            return []
        if kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta" and delta.get("text"):
                return [self.chunk({"content": delta["text"]})]
            block = self.blocks.get(event.get("index"))
            if delta.get("type") == "input_json_delta" and delta.get("partial_json") and block:
                block["args"] = True
                return [self.tool_arguments(block["tool"], delta["partial_json"])]
            return []
        if kind == "content_block_stop":
            block = self.blocks.get(event.get("index"))
            if block and not block["args"]:
                block["args"] = True
                return [self.tool_arguments(block["tool"], "{}")]
            return []
        if kind == "message_delta":
            reason = (event.get("delta") or {}).get("stop_reason")
            if reason:
                self.finish = STOP_REASONS.get(reason, "stop")
            self.raw_usage.update({k: v for k, v in (event.get("usage") or {}).items() if v is not None})
            self.usage = messages_usage(self.raw_usage)
            return []
        if kind == "message_stop":
            return self.close()
        if kind == "error":
            return self.fail(event.get("error"))
        return []


class ResponsesStream(_StreamTranslator):
    def __init__(self, model, include_usage):
        super().__init__(model, include_usage)
        self.items = {}

    def feed(self, event):
        kind = event.get("type")
        if kind == "response.created":
            return [self.chunk({"role": "assistant", "content": ""})]
        if kind == "response.output_text.delta" and event.get("delta"):
            return [self.chunk({"content": event["delta"]})]
        item = event.get("item") or {}
        if kind == "response.output_item.added" and item.get("type") == "function_call":
            index, header = self.tool_header(item.get("call_id"), item.get("name"))
            self.items[event.get("output_index")] = index
            return [header]
        # Argument deltas from Claude on this route do not always add up to the final arguments, so the
        # complete arguments are sent once, from the finished item.
        if kind == "response.output_item.done" and item.get("type") == "function_call":
            index = self.items.get(event.get("output_index"))
            if index is None:
                index, header = self.tool_header(item.get("call_id"), item.get("name"))
                return [header, self.tool_arguments(index, item.get("arguments") or "{}")]
            return [self.tool_arguments(index, item.get("arguments") or "{}")]
        if kind in ("response.completed", "response.incomplete"):
            response = event.get("response") or {}
            self.usage = responses_usage(response.get("usage") or {})
            if kind == "response.incomplete":
                reason = (response.get("incomplete_details") or {}).get("reason")
                self.finish = "content_filter" if reason == "content_filter" else "length"
            return self.close()
        if kind == "response.failed":
            return self.fail((event.get("response") or {}).get("error"))
        if kind == "error":
            return self.fail({"message": event.get("message"), "code": event.get("code")})
        return []


def openai_error(status, raw):
    """Express an upstream error body in the OpenAI error shape that Chat Completions clients parse."""
    try:
        data = json.loads(raw)
    except ValueError:
        return {"error": {"message": raw.decode("utf-8", "replace")[:2000], "type": "upstream_error", "code": status}}
    error = data.get("error", data) if isinstance(data, dict) else data
    if not isinstance(error, dict):
        return {"error": {"message": str(error)[:2000], "type": "upstream_error", "code": status}}
    return {"error": {"message": error.get("message") or json.dumps(error)[:2000],
                      "type": error.get("type") or "upstream_error", "code": error.get("code") or error.get("type") or status}}


def sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "foundry-claude-proxy"

    def log_message(self, *_):
        pass

    def send_json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_chunk(self, data):
        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def authorized(self):
        presented = (self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                     or self.headers.get("api-key", "").strip() or self.headers.get("x-api-key", "").strip())
        return bool(presented) and hmac.compare_digest(presented.encode(), self.server.secret.encode())

    def begin(self):
        parts = urlsplit(self.path)
        return {"time_utc": datetime.now(timezone.utc).isoformat(), "method": self.command, "path": parts.path,
                "query": parts.query, "user_agent": self.headers.get("User-Agent"),
                "via_tunnel": bool(self.headers.get("X-Forwarded-For")),
                "auth_header_style": ("Authorization: Bearer" if self.headers.get("Authorization") else
                                      "api-key" if self.headers.get("api-key") else
                                      "x-api-key" if self.headers.get("x-api-key") else "none")}

    def fail(self, entry, status, message, code):
        entry["result"] = {"status": status, "error": message}
        self.send_json(status, {"error": {"message": message, "type": "invalid_request_error", "code": code}})
        self.server.record(entry)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        entry = self.begin()
        if not self.authorized():
            return self.fail(entry, 401, "invalid proxy secret", "invalid_api_key")
        kind, _ = parse_route(entry["path"])
        if kind != "models":
            return self.fail(entry, 404, "not found", "not_found")
        created = int(time.time())
        self.send_json(200, {"object": "list", "data": [
            {"id": name, "object": "model", "created": created, "owned_by": "microsoft-foundry"}
            for name in sorted(self.server.models)]})
        entry["result"] = {"status": 200}
        self.server.record(entry)

    def do_POST(self):
        started = time.monotonic()
        entry = self.begin()
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.fail(entry, 413, "body too large", "body_too_large")
        raw = self.rfile.read(length) if length else b""
        if not self.authorized():
            return self.fail(entry, 401, "invalid proxy secret", "invalid_api_key")
        kind, path_deployment = parse_route(entry["path"])
        if kind not in ("chat", "responses"):
            return self.fail(entry, 404, "not found", "not_found")
        entry["body"] = body_shape(raw)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self.fail(entry, 400, "body must be a JSON object", "invalid_json")
        requested = path_deployment or body.get("model") or ""
        target = self.server.models.get(requested.lower())
        if not target:
            return self.fail(entry, 404, f"model {requested!r} is not exposed by this proxy; available: "
                                         f"{', '.join(sorted(self.server.models))}", "model_not_found")
        backend, deployment = target
        entry.update(requested_model=requested, deployment=deployment, backend=backend)
        stream = bool(body.get("stream"))
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        api, translate = "chat", None
        try:
            if kind == "responses":
                api, payload = "responses", dict(body, model=deployment)
            elif backend == "openai":
                payload = dict(body, model=deployment)
                if "max_tokens" in payload and "max_completion_tokens" not in payload:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
            elif self.server.claude_api == "messages":
                api, translate = "messages", "messages"
                payload = chat_to_messages(body, deployment, self.server.default_max_tokens)
            else:
                api, translate = "responses", "responses"
                payload = chat_to_responses(body, deployment, self.server.default_max_tokens)
        except (TranslationError, TypeError, ValueError, AttributeError) as error:
            return self.fail(entry, 400, f"cannot translate request: {error}", "translation_error")
        entry["upstream_api"] = api
        try:
            with self.server.upstream(api, payload) as upstream:
                entry["upstream_status"] = upstream.status_code
                request_id = next((upstream.headers[h] for h in REQUEST_ID_HEADERS if h in upstream.headers), None)
                if request_id:
                    entry["upstream_request_id"] = request_id
                if upstream.status_code >= 400:
                    error = openai_error(upstream.status_code, upstream.read())
                    entry["result"] = {"status": upstream.status_code, "error": error["error"]["message"][:400]}
                    self.send_json(upstream.status_code, error)
                elif translate is None:
                    self.relay(upstream, entry)
                elif stream:
                    self.translate_stream(upstream, translate, requested, include_usage, entry)
                else:
                    data = json.loads(upstream.read())
                    result = (messages_to_chat if translate == "messages" else responses_to_chat)(data, requested)
                    self.send_json(200, result)
                    message = result["choices"][0]["message"]
                    entry["result"] = {"status": 200, "finish_reason": result["choices"][0]["finish_reason"],
                                       "tool_calls": len(message.get("tool_calls") or []), "usage": result["usage"]}
        except (httpx.HTTPError, ValueError) as error:
            entry["result"] = {"status": 502, "error": type(error).__name__}
            try:
                self.send_json(502, {"error": {"message": "upstream failure", "type": "upstream_error", "code": 502}})
            except OSError:
                pass
        except OSError as error:
            entry["result"] = dict(entry.get("result") or {}, client_disconnected=type(error).__name__)
        entry["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        self.server.record(entry)

    def relay(self, upstream, entry):
        self.send_response(upstream.status_code)
        for name in ("content-type", "cache-control"):
            if name in upstream.headers:
                self.send_header(name, upstream.headers[name])
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for chunk in upstream.iter_raw():
            if chunk:
                self.write_chunk(chunk)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        entry["result"] = {"status": upstream.status_code, "passthrough": True}

    def translate_stream(self, upstream, translate, model, include_usage, entry):
        translator = (MessagesStream if translate == "messages" else ResponsesStream)(model, include_usage)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for line in upstream.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            for chunk in translator.feed(event):
                self.write_chunk(sse(chunk))
            if translator.done:
                break
        for chunk in translator.close():
            self.write_chunk(sse(chunk))
        self.write_chunk(b"data: [DONE]\n\n")
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        entry["result"] = {"status": 200, "stream": True, "finish_reason": translator.finish,
                           "tool_calls": translator.tool_calls, "usage": translator.usage}
        if translator.error:
            entry["result"]["error"] = str(translator.error.get("message"))[:400]


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config, secret, models, log_path, claude_api="messages", auth="key", key=None,
                 default_max_tokens=DEFAULT_MAX_TOKENS):
        super().__init__(address, Handler)
        self.config, self.secret, self.models, self.log_path = config, secret, models, log_path
        self.claude_api, self.auth, self.key, self.default_max_tokens = claude_api, auth, key, default_max_tokens
        self.http = httpx.Client(timeout=httpx.Timeout(600, connect=15))
        self.credential, self._token = None, None
        self._lock = threading.Lock()

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], ConnectionError):
            return  # a client closing an idle keep-alive connection is not an error
        super().handle_error(request, client_address)

    def credentials(self, api):
        if self.auth == "key":
            return {"x-api-key": self.key} if api == "messages" else {"api-key": self.key}
        with self._lock:
            if self.credential is None:
                from azure.identity import AzureCliCredential
                self.credential = AzureCliCredential(process_timeout=60)
            if self._token is None or self._token.expires_on - time.time() < 300:
                self._token = self.credential.get_token(ENTRA_SCOPE)
            return {"Authorization": f"Bearer {self._token.token}"}

    def upstream(self, api, payload):
        account = self.config["account_name"]
        if api == "messages":
            url = self.config["anthropic_base_url"] + "/v1/messages"
        else:
            url = f"https://{account}.openai.azure.com/openai/v1/" + ("responses" if api == "responses" else "chat/completions")
        headers = {"Content-Type": "application/json", "Accept-Encoding": "identity", **self.credentials(api)}
        if api == "messages":
            headers["anthropic-version"] = ANTHROPIC_VERSION
        return self.http.stream("POST", url, json=payload, headers=headers)

    def record(self, entry):
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        print(line[:400], flush=True)


def model_map(config, aliases=(), openai_deployments=None):
    """Name (lower case) -> (backend, deployment). Claude names translate; OpenAI names pass through."""
    claude = config["claude_deployment_name"]
    models = {claude.lower(): ("claude", claude)}
    for deployment in openai_deployments if openai_deployments is not None else [config["deployment_name"]]:
        models[deployment.lower()] = ("openai", deployment)
    for alias in aliases:
        name, _, deployment = alias.partition("=")
        if not name or not deployment:
            raise ValueError(f"alias must look like NAME=DEPLOYMENT: {alias!r}")
        known = models.get(deployment.lower())
        models[name.lower()] = known if known else ("claude" if "claude" in deployment.lower() else "openai", deployment)
    return models


def load_key(config):
    key = os.environ.get("FOUNDRY_API_KEY")
    if key:
        return key
    result = subprocess.run(
        ["az", "cognitiveservices", "account", "keys", "list", "-g", config["resource_group"],
         "-n", config["account_name"], "--query", "key2", "-o", "tsv"],
        capture_output=True, text=True, shell=os.name == "nt", check=False)
    key = result.stdout.strip()
    if not key:
        sys.exit("No key: set FOUNDRY_API_KEY, sign in with `az login`, or use --upstream-auth entra.")
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--secret", help="Secret clients send as their API key. Defaults to FOUNDRY_PROXY_SECRET, "
                                         "else a new random one, printed once.")
    parser.add_argument("--claude-api", choices=("messages", "responses"), default="messages",
                        help="Foundry API that Claude requests are translated to (default: messages).")
    parser.add_argument("--upstream-auth", choices=("key", "entra"), default="key",
                        help="Call Foundry with the resource key (FOUNDRY_API_KEY or az, key 2) or an Entra token.")
    parser.add_argument("--alias", action="append", default=[], metavar="NAME=DEPLOYMENT",
                        help="Extra model name clients may send, for example foundry-haiku=claude-haiku-5-5.")
    parser.add_argument("--default-max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                        help="max_tokens sent to Claude when the client sets none (Messages requires one).")
    parser.add_argument("--log", type=Path, default=ROOT / "evidence" / "claude-proxy.jsonl")
    args = parser.parse_args()
    config = load_config()
    models = model_map(config, args.alias)
    key = load_key(config) if args.upstream_auth == "key" else None
    secret = args.secret or os.environ.get("FOUNDRY_PROXY_SECRET") or secrets.token_urlsafe(32)
    server = Server(("127.0.0.1", args.port), config, secret, models, args.log, args.claude_api,
                    args.upstream_auth, key, args.default_max_tokens)
    if args.upstream_auth == "entra":
        server.credentials("responses")
    shown = secret if not (args.secret or os.environ.get("FOUNDRY_PROXY_SECRET")) else "(as provided)"
    print(f"Foundry Claude proxy on http://127.0.0.1:{args.port}  claude-api={args.claude_api}  "
          f"upstream-auth={args.upstream_auth}  models={', '.join(sorted(models))}  proxy-secret={shown}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
