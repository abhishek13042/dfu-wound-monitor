# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, served equally by one interface:

- **Research evaluators.** Supervisors, examiners, and ML or health-tech reviewers who try the system with sample or constructed data. Their job is to judge what it does, how well, and where it stops being trustworthy.
- **Clinician-researchers.** Wound-care staff in a research setting who photograph a wound and follow a series across visits. Their job is to record an examination quickly, often on a phone or tablet, and read a measurement back with its caveats.

Neither audience uses it to make a care decision.

## Product Purpose

DFU-WoundMonitor takes a photo of a diabetic foot wound, checks image quality, segments the wound, measures it, stores the result, and compares it with earlier examinations. Success is a user who gets a technical measurement and knows exactly what that measurement can and cannot support.

## Positioning

A wound-measurement system that refuses before it measures and shows its own limits. The quality gate rejects a poor photo before the model runs. Every value carries its unit and calibration state. The strongest result (pooled Dice 0.922 in-domain) is always shown beside the weakest (0.256 on an external set).

## Operating Context

- Research prototype and public multi-user research demo. No real patient data.
- The core chain is: upload, decode and validate, quality gate, segmentation, measurement, stored record, comparison and trends. A rejected image is stored with reason codes and the model never runs.
- One analysis takes about 3 to 6 seconds on CPU. Under `/api/v2` it runs as a background job with states `QUEUED`, `RUNNING`, `COMPLETED`, `QUALITY_REJECTED` and `FAILED`.
- Objects: case, examination, analysis. Cases carry an identity status of `UNKNOWN`, `UNVERIFIED` or `VERIFIED`.
- Spec-driven repository. `specs/` is the source of truth, and `specs/MASTER_TRACKER.md` tracks status.

## Capabilities and Constraints

- Frontend is Next.js, TypeScript, Tailwind and shadcn/ui in `web/`, deployed to Vercel, talking only to `/api/v2` with the user's bearer token (P08-S01).
- The current static dashboard at `src/dashboard/index.html` stays as it is: it serves `/api/v1` for local use and the Hugging Face demo.
- Sign-in comes from a managed provider, which is not yet chosen (Clerk or Supabase Auth). Passwords are never stored here.
- Measurements are pixel-based unless a scale is supplied. Pixel values are never shown as millimetres.
- Pixel and calibrated series never share a chart axis. The trend chart uses only `/trend` output and does not recompute change on the client.
- Time is true-spaced on trend charts, and missing visits stay visible as gaps. Comparison views never claim that two photos are aligned.
- Consent is shown before the first upload. Uploads are deleted automatically, and EXIF is stripped (P10-S03, planned).
- WCAG 2.1 AA, and core pages work at 375 px width.

Undecided: the auth provider, the retention period shown to users (the roadmap says "for example 24 h"), and which sample images can ship. FUSeg images are not assumed redistributable, so samples must be synthetic or licensed.

## Brand Commitments

- Name: DFU-WoundMonitor. There is no logo or other brand asset.
- Voice: technical, plain, exact. Say what was measured and what was not.
- The notice "Research prototype. Not a medical device." appears on every page, from a shared layout.
- Results are always called image-derived technical measurements.
- No diagnostic wording in any string. No word may suggest healing, deterioration, treatment, or a clinical recommendation. Uncertainty is called model uncertainty, never a probability of being correct.

## Evidence on Hand

- FUSeg2021 held-out test, 191 images: pooled Dice 0.922, macro Dice 0.841 (`reports/experiments/spec_02_03_report.md`).
- LowerLimb V3 external check, no tuning: pooled Dice 0.256 (`reports/final/phase_06_validation_report.md`). The cause is unproven; a different annotation protocol is a hypothesis only.
- CPU speed: about 5.8 s per image on 2 cores, 97% of it in segmentation (`reports/final/p06_benchmark.json`).
- Model: ImageNet-pretrained ResNet34 U-Net at 512 px with flip TTA, threshold 0.40 (`docs/deployment/MODEL_CARD.md`).

Absent, and never to be fabricated: clinical validation, real longitudinal patient series, users, customers, testimonials, partner institutions, a public URL. Constructed series are always labelled as constructed.

## Product Principles

1. **Refusal is a result.** A rejected photo gets as much care as a measurement: the reason in plain language and how to retake it.
2. **No number travels alone.** A value always appears with its unit, calibration state, and model version.
3. **Limits sit beside results.** The weakest evidence is shown at the same level as the strongest, never in a footnote.
4. **Failure has a name.** Quality rejection, input error, model failure, and infrastructure failure are distinct and look distinct.
5. **Gaps stay visible.** Missing visits, excluded examinations, and fewer-than-two-point trends are shown and explained, never smoothed over.

## Accessibility & Inclusion

WCAG 2.1 AA is required (`REQ-P08-S01-005`). The product is often used with wound photographs on screen, so nothing may rely on colour alone over an image, and the wound image is never shown without user intent on public pages.
