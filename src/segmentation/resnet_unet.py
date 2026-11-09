"""U-Net with a torchvision ResNet encoder for SPEC-02-03.

ImageNet-pretrained encoders are the standard, well-evidenced choice for small
medical segmentation datasets such as FUSeg2021 (793 labeled training images):
the published FUSeg2021 top entries all use pretrained encoders.  The
randomly-initialised SPEC-02-01 ``LightweightUNet`` remains the reference
baseline that this model must beat on the same held-out split.

Encoder feature strides for an input of size ``S``:

    stem   (conv1/bn/relu)   S/2    64 channels
    layer1 (after maxpool)   S/4    64
    layer2                   S/8    128
    layer3                   S/16   256
    layer4                   S/32   512

The decoder upsamples by 2 at each step, concatenates the matching encoder
feature and applies two 3x3 conv-BN-ReLU blocks.  Input sides must be
divisible by 32.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

SUPPORTED_ENCODERS = {
    "resnet18": (models.resnet18, models.ResNet18_Weights.IMAGENET1K_V1, (64, 64, 128, 256, 512)),
    "resnet34": (models.resnet34, models.ResNet34_Weights.IMAGENET1K_V1, (64, 64, 128, 256, 512)),
    "resnet50": (models.resnet50, models.ResNet50_Weights.IMAGENET1K_V2, (64, 256, 512, 1024, 2048)),
}
DEFAULT_DECODER_CHANNELS = (256, 128, 64, 32, 16)


class ConvBNReLU(nn.Sequential):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )


class DecoderBlock(nn.Module):
    """Upsample x2, concatenate the skip feature (if any), two conv blocks."""

    def __init__(self, in_channels: int, skip_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = ConvBNReLU(in_channels + skip_channels, out_channels)
        self.conv2 = ConvBNReLU(out_channels, out_channels)

    def forward(self, features: torch.Tensor, skip: torch.Tensor | None) -> torch.Tensor:
        features = F.interpolate(features, scale_factor=2.0, mode="nearest")
        if skip is not None:
            features = torch.cat([features, skip], dim=1)
        return self.conv2(self.conv1(features))


class ResNetUNet(nn.Module):
    """Binary segmentation U-Net returning raw logits of shape ``(B,1,H,W)``."""

    def __init__(
        self,
        encoder_name: str = "resnet34",
        pretrained: bool = True,
        num_classes: int = 1,
        decoder_channels: Sequence[int] = DEFAULT_DECODER_CHANNELS,
    ) -> None:
        super().__init__()
        if encoder_name not in SUPPORTED_ENCODERS:
            raise ValueError(f"Unsupported encoder '{encoder_name}'. Choose from {sorted(SUPPORTED_ENCODERS)}")
        if len(decoder_channels) != 5 or any(int(channel) <= 0 for channel in decoder_channels):
            raise ValueError("decoder_channels must contain five positive integers")
        builder, weights, encoder_channels = SUPPORTED_ENCODERS[encoder_name]
        backbone = builder(weights=weights if pretrained else None)
        self.encoder_name = encoder_name
        self.pretrained = pretrained
        self.stem = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu)
        self.pool = backbone.maxpool
        self.layer1, self.layer2 = backbone.layer1, backbone.layer2
        self.layer3, self.layer4 = backbone.layer3, backbone.layer4

        # Skips for decoder steps 1..4 are layer3, layer2, layer1, stem; the
        # last step restores full resolution without a skip.
        skip_channels = [encoder_channels[3], encoder_channels[2], encoder_channels[1], encoder_channels[0], 0]
        in_channels = [encoder_channels[4], *decoder_channels[:-1]]
        self.decoder = nn.ModuleList(
            DecoderBlock(int(in_ch), int(skip_ch), int(out_ch))
            for in_ch, skip_ch, out_ch in zip(in_channels, skip_channels, decoder_channels)
        )
        self.head = nn.Conv2d(int(decoder_channels[-1]), num_classes, kernel_size=1)
        for module in [*self.decoder.modules(), self.head]:
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def encoder_parameters(self) -> list[nn.Parameter]:
        return [
            parameter
            for module in (self.stem, self.layer1, self.layer2, self.layer3, self.layer4)
            for parameter in module.parameters()
        ]

    def decoder_parameters(self) -> list[nn.Parameter]:
        return [*self.decoder.parameters(), *self.head.parameters()]

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        if images.ndim != 4 or images.shape[1] != 3:
            raise ValueError(f"Expected input (B,3,H,W), got {tuple(images.shape)}")
        if images.shape[-2] % 32 or images.shape[-1] % 32:
            raise ValueError("ResNetUNet input height and width must be divisible by 32")
        stem = self.stem(images)
        layer1 = self.layer1(self.pool(stem))
        layer2 = self.layer2(layer1)
        layer3 = self.layer3(layer2)
        features = self.layer4(layer3)
        for block, skip in zip(self.decoder, (layer3, layer2, layer1, stem, None)):
            features = block(features, skip)
        return self.head(features)
