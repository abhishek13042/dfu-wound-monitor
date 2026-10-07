# P00-S01 — Project Definition

## 1. Objective

Define the purpose, boundaries, intended use, and high-level behavior of DFU-WoundMonitor.

## 2. Scope

DFU-WoundMonitor is a Computer Vision–based longitudinal diabetic foot wound monitoring prototype. The system is intended to process wound/foot images, assess image quality, localize wound regions, segment wounds, extract quantitative image-derived measurements, store examination records, and compare examinations over time.

The project is an engineering and research prototype for monitoring and decision support.

## 3. Non-Goals

The system is not intended to:

- diagnose a patient;
- prescribe or recommend treatment;
- replace clinician assessment;
- claim clinical validation without supporting evidence;
- infer wound healing solely from a model output;
- convert pixels to physical units without an appropriate scale/calibration method;
- make unsupported claims about infection, ischemia, or tissue viability.

## 4. Requirements

### REQ-P00-S01-001
The project SHALL define a complete end-to-end Computer Vision monitoring workflow.

### REQ-P00-S01-002
The system SHALL distinguish image-derived measurements from clinical interpretation.

### REQ-P00-S01-003
The project SHALL record model outputs and relevant examination metadata in a reproducible manner.

### REQ-P00-S01-004
The final system SHALL expose limitations and failure cases rather than presenting model predictions as clinical truth.

## 5. Assumptions

- Images available to the system are suitable for the relevant computer-vision task unless rejected by image-quality checks.
- Dataset annotations used for model development are treated as reference labels for experimentation.
- Clinical interpretation is outside the model's authority.

## 6. Dependencies

- Project master brief
- Phase 00 scope, dataset, requirements, architecture, and evaluation decisions

## 7. Inputs

- Project requirements
- Candidate datasets
- User-provided wound/foot images during eventual inference

## 8. Outputs

- Defined project objective
- Defined system boundary
- Defined intended use
- Defined high-level workflow
- Explicit limitations

## 9. Technical Design

High-level workflow:

Image
→ Image Quality Assessment
→ Wound Localization / Detection
→ Wound Segmentation
→ Post-processing
→ Quantitative Measurements
→ Optional Tissue Analysis
→ Examination Record
→ Previous Examination Retrieval
→ Longitudinal Comparison
→ Trend Visualization

The eventual application layer will expose this workflow through an API and dashboard.

## 10. Implementation Tasks

1. Create project definition documentation.
2. Establish terminology used across specifications.
3. Record intended-use and non-goal boundaries.
4. Link the definition to downstream requirements.

## 11. Risks / Failure Modes

- Scope drift into diagnosis or treatment.
- Confusion between model output and clinical interpretation.
- Unsupported claims about longitudinal change.
- Unsupported claims about physical wound dimensions.

## 12. Tests / Verification

Review that every major planned capability can be mapped to a downstream specification and that prohibited clinical claims are excluded.

## 13. Acceptance Criteria

- Project purpose is unambiguous.
- Intended use is documented.
- Non-goals are documented.
- High-level workflow is documented.
- Clinical/engineering boundary is explicit.

## 14. Evidence

- Approved specification
- Architecture reference
- Requirement traceability entries

## 15. Reproducibility

This specification is documentation-level and requires no model execution.

## 16. Risks / Limitations

The project definition does not establish clinical validity. Clinical validity must be treated as an open research question unless supported by appropriate evidence.

## 17. Traceability

Requirements introduced here SHALL be referenced by downstream system requirements and acceptance criteria.
