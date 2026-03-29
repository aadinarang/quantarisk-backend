from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


if TORCH_AVAILABLE:
    class LSTMModel(nn.Module):
        def __init__(self, input_size, hidden_size, num_layers, output_size, dropout_prob):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout_prob,
                batch_first=True,
            )
            self.fc = nn.Linear(hidden_size, output_size)

        def forward(self, x):
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size, device=x.device)
            out, _ = self.lstm(x, (h0, c0))
            out = self.fc(out[:, -1, :])
            return out
else:
    class LSTMModel:
        pass


@dataclass
class LoadedModel:
    model: object
    version: str
    source_path: str
    input_size: int
    hidden_size: int
    num_layers: int
    output_size: int
    dropout_prob: float
    sequence_length: int


class ModelRegistry:
    def __init__(self) -> None:
        self._default_model: Optional[LoadedModel] = None
        self._status: str = "not_loaded"
        self._reason: str = "startup not run"

    def load_startup_models(self) -> None:
        models_dir = os.getenv("MODELS_DIR", "./models")
        model_path = os.path.join(models_dir, "model.pth")

        if not TORCH_AVAILABLE:
            self._status = "not_loaded"
            self._reason = "torch not installed"
            return

        if not os.path.exists(model_path):
            self._status = "not_loaded"
            self._reason = f"model file not found: {model_path}"
            return

        try:
            model = LSTMModel(
                input_size=5, hidden_size=100,
                num_layers=3, output_size=1, dropout_prob=0.2,
            )
            state_obj = torch.load(model_path, map_location=torch.device("cpu"))
            state_dict = state_obj.get("state_dict", state_obj) if isinstance(state_obj, dict) else state_obj
            model.load_state_dict(state_dict)
            model.eval()

            self._default_model = LoadedModel(
                model=model, version="lstm-v1", source_path=model_path,
                input_size=5, hidden_size=100, num_layers=3,
                output_size=1, dropout_prob=0.2, sequence_length=60,
            )
            self._status = "loaded"
            self._reason = "ok"
        except Exception as exc:
            self._default_model = None
            self._status = "not_loaded"
            self._reason = f"failed to load model: {exc}"

    def get_default_model(self) -> Optional[LoadedModel]:
        return self._default_model

    def is_model_loaded(self) -> bool:
        return self._default_model is not None

    def health_payload(self) -> dict:
        return {
            "model_loaded": self.is_model_loaded(),
            "model_status": self._status,
            "model_reason": self._reason,
            "model_version": self._default_model.version if self._default_model else "math-v1",
            "model_source_path": self._default_model.source_path if self._default_model else "",
        }


model_registry = ModelRegistry()
