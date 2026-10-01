"""The four screens (Gradio) over pasalkini.service."""

import os

# Set before any module of this package imports Gradio: no usage statistics and no version check
# are sent over the network.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
