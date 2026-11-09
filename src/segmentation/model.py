"""Lightweight U-Net and numerically stable binary segmentation loss.

SPEC-02-01 uses a plain four-level U-Net because it is explicit, lightweight,
and appropriate for a first wound-boundary baseline.  The model returns raw
logits; sigmoid is applied by the loss and metric/inference code.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConvBlock(nn.Module):
    """Two ``Conv2d -> BatchNorm2d -> ReLU`` operations."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class EncoderLevel(nn.Module):
    """Convolutional feature extraction followed by 2x2 max pooling."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.double_conv = DoubleConvBlock(in_channels, out_channels)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        skip_features = self.double_conv(x)
        return skip_features, self.pool(skip_features)


class DecoderLevel(nn.Module):
    """Bilinear upsampling, skip concatenation, and double convolution."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.double_conv = DoubleConvBlock(in_channels, out_channels)

    def forward(self, x: torch.Tensor, skip_features: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(
            x,
            size=skip_features.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        return self.double_conv(torch.cat([x, skip_features], dim=1))


class LightweightUNet(nn.Module):
    """Four-level U-Net for one-channel binary wound segmentation.

    Default encoder feature sizes are ``[32, 64, 128, 256]``.  The actual
    SPEC-02-01 CPU run uses a smaller configured ``[16, 32, 64, 128]`` variant
    without changing the architecture.  Input shape is ``(B,3,H,W)`` and
    output shape is ``(B,1,H,W)``.  Bilinear interpolation avoids transposed
    convolution checkerboard artifacts.  The output is a raw logit map.
    """

    def __init__(
        self,
        encoder_channels: list[int] | None = None,
        num_classes: int = 1,
    ) -> None:
        super().__init__()
        channels = list(encoder_channels or [32, 64, 128, 256])
        if len(channels) != 4 or any(type(channel) is not int or channel <= 0 for channel in channels):
            raise ValueError("encoder_channels must contain four positive integers")
        if num_classes != 1:
            raise ValueError("SPEC-02-01 supports exactly one binary output channel")
        self.encoder_channels = channels
        self.num_classes = num_classes

        self.encoder_level_1 = EncoderLevel(3, channels[0])
        self.encoder_level_2 = EncoderLevel(channels[0], channels[1])
        self.encoder_level_3 = EncoderLevel(channels[1], channels[2])
        self.encoder_level_4 = EncoderLevel(channels[2], channels[3])
        self.bottleneck = DoubleConvBlock(channels[3], channels[3])

        self.decoder_level_4 = DecoderLevel(channels[3] * 2, channels[2])
        self.decoder_level_3 = DecoderLevel(channels[2] * 2, channels[1])
        self.decoder_level_2 = DecoderLevel(channels[1] * 2, channels[0])
        self.decoder_level_1 = DecoderLevel(channels[0] * 2, channels[0])
        self.output_conv = nn.Conv2d(channels[0], num_classes, kernel_size=1)
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        """Use explicit Kaiming initialization for ReLU convolution blocks."""

        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.BatchNorm2d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return raw wound logits with the same spatial dimensions as input."""

        if x.ndim != 4 or x.shape[1] != 3:
            raise ValueError(f"Expected input shape (B, 3, H, W), got {tuple(x.shape)}")
        # Four pooling levels leave a 2x2 bottleneck at the configured minimum
        # 32x32 input.  This keeps BatchNorm valid even for a final batch of
        # one image; smaller inputs can collapse to a single bottleneck value.
        if min(x.shape[-2:]) < 32:
            raise ValueError("LightweightUNet requires spatial dimensions of at least 32")
        skip_1, pooled_1 = self.encoder_level_1(x)
        skip_2, pooled_2 = self.encoder_level_2(pooled_1)
        skip_3, pooled_3 = self.encoder_level_3(pooled_2)
        skip_4, pooled_4 = self.encoder_level_4(pooled_3)
        bottleneck = self.bottleneck(pooled_4)
        decoded_4 = self.decoder_level_4(bottleneck, skip_4)
        decoded_3 = self.decoder_level_3(decoded_4, skip_3)
        decoded_2 = self.decoder_level_2(decoded_3, skip_2)
        decoded_1 = self.decoder_level_1(decoded_2, skip_1)
        return self.output_conv(decoded_1)


class BCEDiceLoss(nn.Module):
    """Weighted BCE-with-logits plus per-image soft Dice loss.

    ``BCEWithLogitsLoss`` receives raw logits for numerical stability.  Dice is
    computed independently per image after sigmoid, then averaged over the
    batch.  The smooth term makes an empty target finite; a nearly-background
    prediction receives a low Dice loss when both prediction and target are
    empty, while false positive foreground remains penalized by BCE.
    """

    def __init__(
        self,
        bce_weight: float = 0.5,
        dice_weight: float = 0.5,
        epsilon: float = 1e-6,
    ) -> None:
        super().__init__()
        if bce_weight < 0 or dice_weight < 0 or bce_weight + dice_weight <= 0:
            raise ValueError("Loss weights must be non-negative and not both zero")
        if epsilon <= 0:
            raise ValueError("epsilon must be positive")
        self.bce_weight = float(bce_weight)
        self.dice_weight = float(dice_weight)
        self.epsilon = float(epsilon)
        self.bce_loss_fn = nn.BCEWithLogitsLoss(reduction="mean")

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if predictions.shape != targets.shape:
            raise ValueError(
                f"Shape mismatch: predictions {predictions.shape} vs targets {targets.shape}"
            )
        if predictions.ndim != 4:
            raise ValueError(f"Expected tensors with shape (B,C,H,W), got {predictions.ndim}D")
        targets = targets.float()
        if not predictions.is_floating_point():
            raise ValueError("Segmentation logits must use a floating-point dtype")
        if not torch.isfinite(predictions).all() or not torch.isfinite(targets).all():
            raise ValueError("Segmentation logits and targets must be finite")
        if torch.any((targets < 0) | (targets > 1)):
            raise ValueError("Segmentation targets must contain values in [0, 1]")

        bce_value = self.bce_loss_fn(predictions, targets)
        probabilities = torch.sigmoid(predictions).reshape(predictions.shape[0], -1)
        targets_flat = targets.reshape(targets.shape[0], -1)
        intersection = torch.sum(probabilities * targets_flat, dim=1)
        denominator = torch.sum(probabilities, dim=1) + torch.sum(targets_flat, dim=1)
        dice_scores = (2.0 * intersection + self.epsilon) / (denominator + self.epsilon)
        dice_value = 1.0 - dice_scores.mean()
        return self.bce_weight * bce_value + self.dice_weight * dice_value


def count_model_parameters(model: nn.Module) -> dict[str, int]:
    """Return total, trainable, and non-trainable parameter counts."""

    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {
        "total_parameters": total,
        "trainable_parameters": trainable,
        "non_trainable_parameters": total - trainable,
    }


def verify_model_forward_pass(
    model: nn.Module,
    input_height: int = 256,
    input_width: int = 256,
    batch_size: int = 2,
    device: torch.device | None = None,
) -> dict[str, object]:
    """Verify output shape, finite logits, probability range, and loss."""

    device = device or torch.device("cpu")
    model = model.to(device)
    was_training = model.training
    model.eval()
    synthetic_input = torch.randn(batch_size, 3, input_height, input_width, device=device)
    synthetic_mask = torch.randint(
        0, 2, (batch_size, 1, input_height, input_width), dtype=torch.float32, device=device
    )
    with torch.no_grad():
        logits = model(synthetic_input)
        probabilities = torch.sigmoid(logits)
        loss_value = BCEDiceLoss()(logits, synthetic_mask)
    if was_training:
        model.train()

    expected_shape = (batch_size, 1, input_height, input_width)
    shape_ok = tuple(logits.shape) == expected_shape
    finite_ok = bool(torch.isfinite(logits).all() and torch.isfinite(loss_value))
    range_ok = bool(probabilities.min() >= 0 and probabilities.max() <= 1)
    return {
        "input_shape": tuple(synthetic_input.shape),
        "expected_output_shape": expected_shape,
        "actual_output_shape": tuple(logits.shape),
        "output_type": "raw_logits",
        "logits_min": float(logits.min().item()),
        "logits_max": float(logits.max().item()),
        "probability_min": float(probabilities.min().item()),
        "probability_max": float(probabilities.max().item()),
        "output_shape_correct": shape_ok,
        "logits_finite": finite_ok,
        "probability_range_valid": range_ok,
        "loss_value": float(loss_value.item()),
        "loss_is_finite": bool(torch.isfinite(loss_value).item()),
        "forward_pass_success": shape_ok and finite_ok and range_ok,
        **count_model_parameters(model),
    }
