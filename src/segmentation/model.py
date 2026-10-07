"""
Baseline Segmentation Model — Lightweight UNet — DFU-WoundMonitor.

Spec: P02-S03 — Baseline Model Implementation.

WHAT THIS MODULE IMPLEMENTS:
    A lightweight UNet for binary wound segmentation.
    The UNet is an encoder-decoder architecture with skip connections.
    It is the standard, literature-accepted baseline for medical image segmentation.

WHY UNET?
    1. Encoder-decoder design: The encoder reduces spatial resolution to capture
       global context (what is in the image). The decoder restores spatial resolution
       to produce a pixel-level output map (where is the wound).
    2. Skip connections: High-resolution detail from the encoder is concatenated with
       upsampled features in the decoder. This helps preserve wound boundary accuracy.
    3. Well-documented: UNet is the most cited medical segmentation model (Ronneberger 2015).
       Using it as a baseline is defensible and directly comparable to DFUC2022 literature.
    4. Simpler than Transformer models (SegFormer, Swin), which will be Phase 03+ targets.

ARCHITECTURE (lightweight version, 4 levels):

    Input RGB image (3 × H × W)
        ↓
    Encoder Level 1: Conv → BN → ReLU → Conv → BN → ReLU   [channels: 3→32]
        ↓ MaxPool 2×2
    Encoder Level 2: Conv → BN → ReLU → Conv → BN → ReLU   [channels: 32→64]
        ↓ MaxPool 2×2
    Encoder Level 3: Conv → BN → ReLU → Conv → BN → ReLU   [channels: 64→128]
        ↓ MaxPool 2×2
    Encoder Level 4: Conv → BN → ReLU → Conv → BN → ReLU   [channels: 128→256]
        ↓
    Bottleneck: Conv → BN → ReLU → Conv → BN → ReLU         [channels: 256→256]
        ↓ Upsample 2×2
    Decoder Level 4: skip concat + Conv → BN → ReLU × 2     [channels: 512→128]
        ↓ Upsample 2×2
    Decoder Level 3: skip concat + Conv → BN → ReLU × 2     [channels: 256→64]
        ↓ Upsample 2×2
    Decoder Level 2: skip concat + Conv → BN → ReLU × 2     [channels: 128→32]
        ↓ Upsample 2×2
    Decoder Level 1: skip concat + Conv → BN → ReLU × 2     [channels: 64→32]
        ↓
    Output head: Conv 1×1 → Sigmoid                          [channels: 32→1]
        ↓
    Prediction map (1 × H × W), values in [0, 1]

OUTPUT MEANING:
    Each pixel value is the model's estimated probability that pixel belongs to the wound.
    Values close to 1.0 → likely wound (foreground).
    Values close to 0.0 → likely background.
    A threshold (default 0.5) converts this to a binary mask.

LOSS FUNCTION — Combined BCE + Dice:
    BCEWithLogitsLoss (Binary Cross-Entropy applied before sigmoid):
        Mathematical objective: minimize -[y * log(p) + (1-y) * log(1-p)]
        where y ∈ {0, 1} is the ground truth and p = sigmoid(logit) is the prediction.
        Limitation: BCE treats all pixels equally, so the many background pixels
        dominate the loss gradient when foreground is small (~15% here).

    Dice Loss:
        Mathematical objective: maximize the overlap between prediction and ground truth.
        DiceLoss = 1 - (2 * |P ∩ G|) / (|P| + |G|)
        where P = predicted foreground set, G = ground truth foreground set.
        Advantage: Directly optimizes the Dice coefficient (primary evaluation metric).
        It naturally handles class imbalance by focusing on the foreground class.
        Limitation: Dice loss can be unstable when both P and G are near-zero (empty mask).
                    A small smoothing constant (epsilon) prevents division by zero.

    Combined loss = 0.5 * BCE + 0.5 * Dice
    Rationale: BCE provides stable gradients from all pixels; Dice compensates for
    the imbalance problem and directly optimizes the evaluation metric.

ALTERNATIVES CONSIDERED:
    - Focal Loss: Better for extreme imbalance but more hyperparameters.
    - Pure Dice Loss: Unstable early in training on small batches.
    - Weighted BCE: Requires computing class weights per batch; adds complexity.
    Decision: BCE+Dice is the simplest defensible combined loss for Phase 02.

Coding Style: Beginner-Understandable Python
"""

from typing import List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================
# BUILDING BLOCK: Double Convolution Block
# ============================================================

class DoubleConvBlock(nn.Module):
    """
    Two consecutive Conv2d → BatchNorm2d → ReLU operations.

    This is the basic building block used in every encoder and decoder level.

    WHY TWO CONVOLUTIONS PER LEVEL?
        One convolution extracts simple features (edges, textures).
        A second convolution then combines those simple features into more
        complex, higher-level representations. This gives the network more
        representational power without adding depth (which would require residual
        connections for stable training).

    WHY BATCH NORMALIZATION?
        Batch normalization (BN) normalizes activations within a mini-batch.
        It helps training stability and convergence speed, especially important
        when training on a small dataset where activation scales can vary widely.

    WHY RELU?
        ReLU (Rectified Linear Unit): output = max(0, x).
        It is the standard non-linearity in modern CNNs. It is fast to compute,
        does not saturate for positive inputs (unlike sigmoid/tanh), and
        empirically works well.

    Inputs to forward():
        x: Tensor of shape (batch_size, in_channels, H, W).

    Outputs of forward():
        Tensor of shape (batch_size, out_channels, H, W).
        Height and width are preserved (padding=1 ensures same spatial size).
    """

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()

        # First convolution: 3×3 kernel, padding=1 to preserve spatial dimensions
        self.conv_1 = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=3,
            padding=1,
            bias=False,  # bias=False because BatchNorm has its own bias term
        )
        self.batch_norm_1 = nn.BatchNorm2d(num_features=out_channels)

        # Second convolution: same configuration
        self.conv_2 = nn.Conv2d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=3,
            padding=1,
            bias=False,
        )
        self.batch_norm_2 = nn.BatchNorm2d(num_features=out_channels)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply: Conv → BN → ReLU → Conv → BN → ReLU."""
        # First conv block
        x = self.conv_1(x)
        x = self.batch_norm_1(x)
        x = self.relu(x)

        # Second conv block
        x = self.conv_2(x)
        x = self.batch_norm_2(x)
        x = self.relu(x)

        return x


# ============================================================
# BUILDING BLOCK: Encoder Level (down step)
# ============================================================

class EncoderLevel(nn.Module):
    """
    One encoder level: DoubleConvBlock followed by MaxPool2d.

    In the UNet architecture, each encoder level does two things:
        1. Process features with DoubleConvBlock.
        2. Save those features as a "skip connection" for the corresponding decoder level.
        3. Downsample with MaxPool2d to reduce spatial resolution (→ captures broader context).

    MaxPool2d with kernel_size=2, stride=2:
        - Input shape: (B, C, H, W)
        - Output shape: (B, C, H/2, W/2)
        - Picks the maximum value in each 2×2 block.
        - Reduces spatial resolution while preserving the strongest activations.

    Usage:
        features, downsampled = encoder_level(x)
        # features: saved as skip connection
        # downsampled: passed to next encoder level
    """

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.double_conv = DoubleConvBlock(in_channels, out_channels)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            skip_features: Output of DoubleConvBlock — saved for skip connection.
            pooled: Output after MaxPool — passed to next encoder level.
        """
        skip_features = self.double_conv(x)
        pooled = self.pool(skip_features)
        return skip_features, pooled


# ============================================================
# BUILDING BLOCK: Decoder Level (up step)
# ============================================================

class DecoderLevel(nn.Module):
    """
    One decoder level: Upsample → Concatenate skip → DoubleConvBlock.

    Each decoder level reverses one encoder level:
        1. Upsample the low-resolution feature map back to the encoder's resolution.
        2. Concatenate with the skip connection from the corresponding encoder level.
           This reintroduces fine-grained spatial detail that was lost in pooling.
        3. Process combined features with DoubleConvBlock.

    WHY SKIP CONNECTIONS?
        During downsampling, detailed spatial information (wound boundaries, textures)
        is gradually discarded in favor of semantic information ("is this a wound?").
        The decoder alone cannot fully recover this lost spatial detail.
        Skip connections provide a direct path from the encoder to the decoder,
        giving the decoder both the high-level context (from the bottom of the U)
        and the spatial detail (from the corresponding encoder level).
        This is the key innovation of UNet that makes it effective for segmentation.

    Upsampling strategy:
        We use bilinear interpolation (not transposed convolution) for simplicity
        and to avoid checkerboard artifacts associated with transposed convolution.

    Channel count after concatenation:
        After upsampling: out_channels channels
        Skip connection: also out_channels channels (from the encoder level)
        After concat: 2 * out_channels channels
        After DoubleConvBlock: out_channels channels
    """

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        # DoubleConvBlock takes the concatenated (upsampled + skip) features
        # Input channels = 2 * out_channels (because we concat two feature maps)
        self.double_conv = DoubleConvBlock(
            in_channels=in_channels,
            out_channels=out_channels,
        )

    def forward(
        self,
        x: torch.Tensor,
        skip_features: torch.Tensor,
    ) -> torch.Tensor:
        """
        Upsample x, concatenate with skip_features, then apply DoubleConvBlock.

        Inputs:
            x: Low-resolution feature map (from previous decoder level or bottleneck).
            skip_features: Corresponding encoder output saved during the forward pass.

        Outputs:
            Processed feature map, same spatial size as skip_features.
        """
        # Upsample x to match skip_features spatial size
        # scale_factor=2 doubles both height and width
        x_upsampled = F.interpolate(
            x,
            size=(skip_features.shape[2], skip_features.shape[3]),
            mode="bilinear",
            align_corners=False,
        )

        # Concatenate along the channel dimension (dim=1)
        # x_upsampled: (B, C_x, H, W)
        # skip_features: (B, C_skip, H, W)
        # combined: (B, C_x + C_skip, H, W)
        combined = torch.cat([x_upsampled, skip_features], dim=1)

        # Apply DoubleConvBlock to process combined features
        output = self.double_conv(combined)
        return output


# ============================================================
# MAIN MODEL: Lightweight UNet
# ============================================================

class LightweightUNet(nn.Module):
    """
    Lightweight UNet for binary wound segmentation.

    This is the baseline model for Phase 02 of DFU-WoundMonitor.
    It implements the classic UNet architecture (Ronneberger et al., 2015)
    with a smaller channel configuration for CPU-feasible training.

    Architecture summary:
        - 4 encoder levels: [32, 64, 128, 256] channels
        - 1 bottleneck: 256 channels
        - 4 decoder levels: [128, 64, 32, 32] channels
        - 1 output head: 1 channel, sigmoid activation

    Parameters:
        encoder_channels: List of channel counts for each encoder level.
            Default [32, 64, 128, 256] gives ~7.7M parameters.
        num_classes: Number of output channels.
            1 for binary segmentation (wound vs background).

    Input tensor shape:
        (batch_size, 3, height, width) — RGB image, normalized

    Output tensor shape:
        (batch_size, 1, height, width) — wound probability map, values in [0, 1]

    NOTE: The sigmoid activation is applied in the forward() pass.
    The BCEDiceLoss uses raw logits for its BCE component (via BCEWithLogitsLoss),
    but we apply sigmoid here so that the output can be directly compared to
    the ground truth mask (values in [0, 1]) and thresholded.
    The loss function will therefore receive sigmoid-activated probabilities.
    """

    def __init__(
        self,
        encoder_channels: List[int] = None,
        num_classes: int = 1,
    ):
        super().__init__()

        if encoder_channels is None:
            encoder_channels = [32, 64, 128, 256]

        self.num_classes = num_classes
        self.encoder_channels = encoder_channels

        # ---- ENCODER ----
        # Level 1: input RGB (3 channels) → encoder_channels[0]
        self.encoder_level_1 = EncoderLevel(
            in_channels=3,
            out_channels=encoder_channels[0],
        )
        # Level 2: encoder_channels[0] → encoder_channels[1]
        self.encoder_level_2 = EncoderLevel(
            in_channels=encoder_channels[0],
            out_channels=encoder_channels[1],
        )
        # Level 3: encoder_channels[1] → encoder_channels[2]
        self.encoder_level_3 = EncoderLevel(
            in_channels=encoder_channels[1],
            out_channels=encoder_channels[2],
        )
        # Level 4: encoder_channels[2] → encoder_channels[3]
        self.encoder_level_4 = EncoderLevel(
            in_channels=encoder_channels[2],
            out_channels=encoder_channels[3],
        )

        # ---- BOTTLENECK ----
        # Lowest resolution; processes the most abstract features
        self.bottleneck = DoubleConvBlock(
            in_channels=encoder_channels[3],
            out_channels=encoder_channels[3],
        )

        # ---- DECODER ----
        # Each decoder level takes:
        #   (bottleneck or prev decoder output) + skip connection from encoder
        # Input channels = bottleneck channels + encoder skip channels
        # Output channels = encoder skip channels / 2

        # Level 4 decoder: bottleneck (256) + encoder_4 skip (256) → 128
        self.decoder_level_4 = DecoderLevel(
            in_channels=encoder_channels[3] + encoder_channels[3],
            out_channels=encoder_channels[2],
        )
        # Level 3 decoder: decoder_4 (128) + encoder_3 skip (128) → 64
        self.decoder_level_3 = DecoderLevel(
            in_channels=encoder_channels[2] + encoder_channels[2],
            out_channels=encoder_channels[1],
        )
        # Level 2 decoder: decoder_3 (64) + encoder_2 skip (64) → 32
        self.decoder_level_2 = DecoderLevel(
            in_channels=encoder_channels[1] + encoder_channels[1],
            out_channels=encoder_channels[0],
        )
        # Level 1 decoder: decoder_2 (32) + encoder_1 skip (32) → 32
        self.decoder_level_1 = DecoderLevel(
            in_channels=encoder_channels[0] + encoder_channels[0],
            out_channels=encoder_channels[0],
        )

        # ---- OUTPUT HEAD ----
        # 1×1 convolution to project from 32 channels → 1 channel (binary output)
        self.output_conv = nn.Conv2d(
            in_channels=encoder_channels[0],
            out_channels=num_classes,
            kernel_size=1,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass: image tensor → wound probability map.

        Inputs:
            x: Image tensor of shape (batch_size, 3, H, W).

        Outputs:
            Wound probability map of shape (batch_size, 1, H, W).
            Values are in [0, 1] (sigmoid-activated).

        Data flow:
            Input → Encoder (4 levels, each halves resolution) →
            Bottleneck → Decoder (4 levels, each doubles resolution) →
            Output head (1×1 conv) → Sigmoid → Output probabilities
        """
        # ---- ENCODER PASS ----
        # Each EncoderLevel returns (skip_features, pooled)
        # skip_features: saved for skip connection → decoder
        # pooled: passed to next encoder level
        skip_1, pooled_1 = self.encoder_level_1(x)
        skip_2, pooled_2 = self.encoder_level_2(pooled_1)
        skip_3, pooled_3 = self.encoder_level_3(pooled_2)
        skip_4, pooled_4 = self.encoder_level_4(pooled_3)

        # ---- BOTTLENECK ----
        bottleneck_features = self.bottleneck(pooled_4)

        # ---- DECODER PASS ----
        # Each DecoderLevel takes (features_from_below, skip_from_encoder)
        decoded_4 = self.decoder_level_4(bottleneck_features, skip_4)
        decoded_3 = self.decoder_level_3(decoded_4, skip_3)
        decoded_2 = self.decoder_level_2(decoded_3, skip_2)
        decoded_1 = self.decoder_level_1(decoded_2, skip_1)

        # ---- OUTPUT HEAD ----
        # 1×1 conv produces raw logit, then sigmoid converts to probability
        logit = self.output_conv(decoded_1)
        probability_map = torch.sigmoid(logit)

        return probability_map


# ============================================================
# LOSS FUNCTION: Combined BCE + Dice Loss
# ============================================================

class BCEDiceLoss(nn.Module):
    """
    Combined Binary Cross-Entropy + Dice Loss.

    MATHEMATICAL OBJECTIVE:
        total_loss = bce_weight * BCE(predictions, targets)
                   + dice_weight * DiceLoss(predictions, targets)

    BCE component (Binary Cross-Entropy):
        BCE = -[y * log(p) + (1-y) * log(1-p)]
        where:
            y ∈ {0.0, 1.0} = ground truth label for each pixel
            p ∈ [0, 1] = predicted probability (sigmoid output)
        Limitation: All pixels contribute equally. The dominant background
        class (85% of pixels) can overwhelm the wound (15%).

    Dice component:
        Dice = 1 - (2 * sum(p * y) + epsilon) / (sum(p) + sum(y) + epsilon)
        where the sum is over all pixels in the batch.
        epsilon prevents division by zero when both prediction and target are all zeros.
        The Dice loss directly optimizes for overlap between prediction and ground truth.
        It is naturally balanced because it normalizes by the total predicted and target area.

    EDGE CASE HANDLING:
        When ground truth is all background (y = all zeros), both sum(p * y)
        and sum(y) are zero. The epsilon term prevents division by zero.
        The resulting Dice loss will be approximately 1 - (0 + eps) / (sum(p) + eps),
        which penalizes the model for predicting any foreground.

    Parameters:
        bce_weight: Weight for the BCE component (default 0.5).
        dice_weight: Weight for the Dice component (default 0.5).
        epsilon: Small constant to prevent division by zero (default 1e-6).
    """

    def __init__(
        self,
        bce_weight: float = 0.5,
        dice_weight: float = 0.5,
        epsilon: float = 1e-6,
    ):
        super().__init__()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight
        self.epsilon = epsilon

        # BCELoss is applied to sigmoid-activated outputs
        # reduction='mean' averages loss over all pixels and batch items
        self.bce_loss_fn = nn.BCELoss(reduction="mean")

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute combined BCE + Dice loss.

        Inputs:
            predictions: Model output, shape (B, 1, H, W), values in [0, 1].
                         These are sigmoid-activated probabilities.
            targets: Ground truth mask, shape (B, 1, H, W), values in {0.0, 1.0}.

        Outputs:
            Scalar loss tensor (single float value).
        """
        # Validate shapes match
        if predictions.shape != targets.shape:
            raise ValueError(
                f"Shape mismatch: predictions {predictions.shape} vs targets {targets.shape}. "
                "Ensure preprocessing produces correctly shaped tensors."
            )

        # ---- BCE Component ----
        bce_loss_value = self.bce_loss_fn(predictions, targets)

        # ---- Dice Component ----
        # Flatten predictions and targets for batch-level Dice computation
        # Shape: (B, 1, H, W) → (B, H*W)
        batch_size = predictions.shape[0]
        predictions_flat = predictions.view(batch_size, -1)
        targets_flat = targets.view(batch_size, -1)

        # Numerator: 2 * |intersection|
        # intersection = sum of element-wise product (predicted_prob * ground_truth_label)
        intersection = torch.sum(predictions_flat * targets_flat, dim=1)
        numerator = 2.0 * intersection + self.epsilon

        # Denominator: |P| + |G| = sum of predicted + sum of ground truth
        denominator = torch.sum(predictions_flat, dim=1) + torch.sum(targets_flat, dim=1) + self.epsilon

        # Dice score per sample, then averaged over batch
        dice_score_per_sample = numerator / denominator
        mean_dice_score = torch.mean(dice_score_per_sample)

        # Dice LOSS = 1 - Dice SCORE (we want to minimize loss, so we negate the score)
        dice_loss_value = 1.0 - mean_dice_score

        # ---- Combined Loss ----
        total_loss = (self.bce_weight * bce_loss_value) + (self.dice_weight * dice_loss_value)

        return total_loss


# ============================================================
# PARAMETER COUNTING UTILITY
# ============================================================

def count_model_parameters(model: nn.Module) -> dict:
    """
    Count and report model parameters.

    Inputs:
        model: Any PyTorch nn.Module.

    Outputs:
        Dictionary with:
            total_parameters: All parameters (weights + biases).
            trainable_parameters: Only parameters that will be updated by optimizer.
            non_trainable_parameters: Frozen parameters (e.g., pretrained layers).

    Usage:
        param_counts = count_model_parameters(model)
        print(f"Total: {param_counts['total_parameters']:,}")
    """
    total_parameters = sum(p.numel() for p in model.parameters())
    trainable_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    non_trainable_parameters = total_parameters - trainable_parameters

    return {
        "total_parameters": total_parameters,
        "trainable_parameters": trainable_parameters,
        "non_trainable_parameters": non_trainable_parameters,
    }


def verify_model_forward_pass(
    model: nn.Module,
    input_height: int = 256,
    input_width: int = 256,
    batch_size: int = 2,
    device: torch.device = None,
) -> dict:
    """
    Run a forward pass with synthetic input and verify output shape.

    This tests that the model computes without errors and produces
    output of the expected shape (REQ-P02-S03-006).

    Inputs:
        model: LightweightUNet instance.
        input_height: Image height.
        input_width: Image width.
        batch_size: Number of synthetic samples.
        device: Torch device (CPU/CUDA).

    Outputs:
        Dictionary with input_shape, output_shape, parameter counts, and pass/fail.
    """
    if device is None:
        device = torch.device("cpu")

    model = model.to(device)
    model.eval()  # Evaluation mode for the test

    # Create synthetic input: random RGB image batch
    # Shape: (batch_size, 3, H, W) — the expected model input shape
    synthetic_input = torch.randn(batch_size, 3, input_height, input_width, device=device)

    # Create synthetic mask: binary mask batch
    # Shape: (batch_size, 1, H, W)
    synthetic_mask = torch.randint(0, 2, (batch_size, 1, input_height, input_width), dtype=torch.float32, device=device)

    with torch.no_grad():
        output = model(synthetic_input)

    expected_output_shape = (batch_size, 1, input_height, input_width)
    output_shape_correct = tuple(output.shape) == expected_output_shape
    output_range_valid = (output.min().item() >= 0.0) and (output.max().item() <= 1.0)

    # Test loss computation
    loss_fn = BCEDiceLoss()
    loss_value = loss_fn(output, synthetic_mask)
    loss_is_finite = torch.isfinite(loss_value).item()

    param_counts = count_model_parameters(model)

    result = {
        "input_shape": tuple(synthetic_input.shape),
        "expected_output_shape": expected_output_shape,
        "actual_output_shape": tuple(output.shape),
        "output_shape_correct": output_shape_correct,
        "output_min": round(output.min().item(), 4),
        "output_max": round(output.max().item(), 4),
        "output_range_valid": output_range_valid,
        "loss_value": round(loss_value.item(), 6),
        "loss_is_finite": loss_is_finite,
        "forward_pass_success": output_shape_correct and output_range_valid and loss_is_finite,
        **param_counts,
    }

    return result
