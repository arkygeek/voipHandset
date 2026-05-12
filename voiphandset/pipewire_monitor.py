"""Monitor PipeWire for streams attached to the speakerphone virtual sink.

Calls a callback whenever the stream-count on the named sink changes
between zero and non-zero. Uses `pw-dump` polled at a low rate (default
1 Hz) which is robust on Ubuntu 24.10 and doesn't require any extra
Python bindings.

The speakerphone virtual sink is created by a PipeWire config that
installs a `module-loopback` node named `handset_speakerphone` (see
conf/60-handset-speakerphone.conf).
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from typing import Callable

log = logging.getLogger("voiphandset.pipewire")

SINK_NODE_NAME = "handset_speakerphone"
POLL_INTERVAL_SEC = 1.0


class PipeWireMonitor(threading.Thread):
    def __init__(self, on_change: Callable[[bool], None]):
        super().__init__(daemon=True, name="pipewire-monitor")
        self.on_change = on_change
        self._stop = threading.Event()
        self._last_active = False

    def stop(self):
        self._stop.set()

    def _dump(self) -> list[dict] | None:
        try:
            r = subprocess.run(
                ["pw-dump"],
                capture_output=True, text=True, timeout=4,
            )
            if r.returncode != 0:
                return None
            return json.loads(r.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            return None

    @staticmethod
    def _sink_node_id(dump: list[dict]) -> int | None:
        for obj in dump:
            if obj.get("type") != "PipeWire:Interface:Node":
                continue
            props = obj.get("info", {}).get("props", {}) or {}
            if props.get("node.name") == SINK_NODE_NAME and props.get("media.class") == "Audio/Sink":
                return obj.get("id")
        return None

    @staticmethod
    def _streams_for_sink(dump: list[dict], sink_id: int) -> int:
        # A stream is "attached" to a sink if a link goes from the stream output
        # to one of the sink's input ports. We count distinct stream nodes.
        sink_input_port_ids = set()
        for obj in dump:
            if obj.get("type") != "PipeWire:Interface:Port":
                continue
            info = obj.get("info", {})
            if info.get("direction") != "input":
                continue
            props = info.get("props", {}) or {}
            if props.get("node.id") == sink_id:
                sink_input_port_ids.add(obj.get("id"))
        if not sink_input_port_ids:
            return 0
        attached_stream_nodes = set()
        for obj in dump:
            if obj.get("type") != "PipeWire:Interface:Link":
                continue
            info = obj.get("info", {})
            if info.get("input-port-id") in sink_input_port_ids:
                attached_stream_nodes.add(info.get("output-node-id"))
        return len(attached_stream_nodes)

    def run(self):
        log.info("PipeWire monitor started (polling every %.1fs for sink %r)",
                 POLL_INTERVAL_SEC, SINK_NODE_NAME)
        while not self._stop.is_set():
            try:
                dump = self._dump()
                active = False
                if dump:
                    sid = self._sink_node_id(dump)
                    if sid is not None:
                        active = self._streams_for_sink(dump, sid) > 0
                if active != self._last_active:
                    self._last_active = active
                    try:
                        self.on_change(active)
                    except Exception as e:
                        log.exception("on_change error: %s", e)
            except Exception as e:
                log.warning("monitor error: %s", e)
            self._stop.wait(POLL_INTERVAL_SEC)
        log.info("PipeWire monitor stopped")
