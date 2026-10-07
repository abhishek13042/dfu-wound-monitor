# P02-S03 — Baseline Model Implementation

## Purpose
Implement the selected baseline in understandable PyTorch code.

## Requirements
- **REQ-P02-S03-001:** Implement exactly the model selected in P02-S01.
- **REQ-P02-S03-002:** Make input, major blocks, prediction head and output explicit.
- **REQ-P02-S03-003:** Verify output shape/class count/activation/loss compatibility for the chosen task.
- **REQ-P02-S03-004:** Select and explain a single appropriate baseline loss; discuss mathematical objective and limitations.
- **REQ-P02-S03-005:** Report total and trainable parameter counts plus input/output shapes.
- **REQ-P02-S03-006:** Run a forward-pass test with valid data or controlled synthetic input.
- **REQ-P02-S03-007:** Explicitly support the available CPU/GPU device; do not assume GPU availability.
- **REQ-P02-S03-008:** Avoid abstractions that hide important architecture logic.

## Required explanation
Document what the model is, why selected, data flow, major blocks, loss meaning, output meaning, alternatives and weaknesses.

## Acceptance
Initialization, forward pass and loss computation succeed; outputs have expected shapes; parameters are reported; implementation matches the decision record.
