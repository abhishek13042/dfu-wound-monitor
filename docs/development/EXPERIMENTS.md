# Experiment records

Every training or evaluation run must leave enough information for someone else to repeat and check it. Results go
in `reports/experiments/`, with a report named after the specification.

## What to record

| Item | Contents |
|---|---|
| Experiment configuration | Hyperparameters, seed, hardware and environment |
| Model configuration | Architecture, encoder, pretrained weights, loss |
| Dataset version | Exact splits, manifest hashes, augmentation |
| Metrics | Macro, pooled, non-empty-subset and boundary scores, per split |
| Visualisations | Representative overlays and error cases |
| Logs | Execution log and training curves |
| Conclusions | Findings, failure analysis, and the decision taken |

## Rules

- Fix the protocol before seeing test results, and score a test set once.
- Tune only on internal validation.
- Keep hypotheses apart from measured results.
- Report unfavourable and null results.
- Label synthetic or constructed data clearly. The `P02-baseline-unet-bce-dice-v1_*` files are a historical synthetic
  run, not evidence.

`reports/experiments/spec_02_03_report.md` is the reference example.
