import type { AnalysisStatus, ErrorCategory, IdentityStatus, MeasurementBasis, ReasonCode, TimestampSource } from "@/lib/api";

export const NOTICE = "Research prototype. Not a medical device.";
export const LIMITATION =
  "Measurements describe the segmented region of a photo. They are not a clinical assessment, and no value here should guide care.";

export const statusCopy: Record<AnalysisStatus, { title: string; short: string; body: string }> = {
  QUEUED: {
    title: "Waiting for a worker",
    short: "Queued",
    body: "The photo is stored and in the queue. The nine checks start when a worker picks it up.",
  },
  RUNNING: {
    title: "Reading the photo",
    short: "Running",
    body: "The nine checks ran first. The accepted photo is now being segmented, which takes about 6 seconds on a CPU.",
  },
  COMPLETED: {
    title: "Photo accepted, region measured",
    short: "Measured",
    body: "The photo passed all nine checks and the segmented region was measured.",
  },
  QUALITY_REJECTED: {
    title: "Photo refused, nothing measured",
    short: "Refused",
    body: "The photo failed the checks below, so it was not segmented and no value exists for it.",
  },
  FAILED: {
    title: "The service could not finish",
    short: "Failed",
    body: "This is a fault on our side, not a problem with the photo. No value was produced.",
  },
};

export const reasonCopy: Record<ReasonCode, { reason: string; retake: string }> = {
  UNREADABLE: { reason: "The file could not be opened as an image.", retake: "Export it again as PNG or JPEG and upload the new file." },
  TOO_SMALL: { reason: "The photo is too small to read.", retake: "Upload the original photo, not a thumbnail or a screenshot." },
  BAD_ASPECT_RATIO: { reason: "The photo is too long and narrow.", retake: "Use the full frame from the camera, without cropping to a strip." },
  INSUFFICIENT_CONTENT: { reason: "Most of the frame is blank.", retake: "Fill more of the frame with the foot and keep the background plain." },
  BLURRY: { reason: "The photo is out of focus or moved.", retake: "Hold the camera still, tap to focus and retake." },
  UNDEREXPOSED: { reason: "The photo is too dark.", retake: "Add light from the front and retake." },
  OVEREXPOSED: { reason: "The photo is too bright.", retake: "Move away from direct light or turn the flash off." },
  LOW_CONTRAST: { reason: "The photo is flat, with little tonal range.", retake: "Use even light and a plain background that differs from the skin." },
  GLARE: { reason: "Bright reflections cover part of the photo.", retake: "Change the camera angle or move the light to the side." },
};

export const errorCopy: Record<ErrorCategory, { status: string; title: string; body: string; action: string; href: string }> = {
  INVALID_INPUT: { status: "400, 413", title: "That file cannot be used", body: "It must be PNG, JPEG, BMP, TIFF or WebP, and no larger than 25 MB.", action: "Choose another file", href: "/analyse" },
  UNAUTHENTICATED: { status: "401", title: "Sign in again", body: "Your session has ended. Nothing you already saved is lost.", action: "Go to sign in", href: "/sign-in" },
  NOT_FOUND: { status: "404", title: "No such record", body: "It may have been deleted, or the link may be wrong.", action: "Back to cases", href: "/cases" },
  CONFLICT: { status: "409", title: "This has already changed", body: "Someone or something updated this record first. Reload to see the current version.", action: "Back to cases", href: "/cases" },
  QUALITY_REJECTED: { status: "422", title: "Photo refused", body: "The photo failed one or more checks, so no measurement exists. The failed checks are named on the analysis.", action: "Retake and upload", href: "/analyse" },
  BUSY: { status: "429", title: "The queue is full", body: "Your photo was not added. Try again once the wait has passed.", action: "Try again in 20 s", href: "/analyse" },
  MODEL_FAILURE: { status: "500", title: "The model failed on this photo", body: "The checks passed but segmentation did not finish. Quote the request ID if this repeats.", action: "Try again", href: "/analyse" },
  MODEL_NOT_READY: { status: "503", title: "The model is not loaded", body: "The service is starting or the weights are missing. Readiness is shown in the side rail.", action: "Check again", href: "/analyse" },
  INFRASTRUCTURE_FAILURE: { status: "503", title: "Storage or queue is unavailable", body: "A service behind the application is down. Your earlier records are unchanged.", action: "Try again", href: "/analyse" },
};

export const trendReasonCopy: Record<string, string> = {
  INSUFFICIENT_POINTS: "A trend needs at least two measured examinations.",
  NO_BASELINE: "No measured examination exists to act as the baseline.",
  MIXED_CASES: "The analyses belong to more than one case.",
  CASE_UNKNOWN: "The case could not be identified.",
  CASE_MISMATCH: "The analysis does not belong to this case.",
  IDENTITY_UNVERIFIED: "The case identity is not verified.",
  TIMESTAMP_MISSING: "The examination has no capture time.",
  MEASUREMENT_MISSING: "No measurement exists, because the photo was refused or the analysis failed.",
  DIFFERENT_CASE: "These analyses belong to different cases.",
  SAME_TIMESTAMP: "Both analyses have the same capture time.",
  MODEL_VERSION_MISMATCH: "The analyses used different model versions.",
  MEASUREMENT_BASIS_MISMATCH: "One analysis is in pixels and the other in millimetres.",
  PIXEL_COMPARISON_DISALLOWED: "Pixel values without calibration cannot be compared in this view.",
};

export const basisCopy: Record<MeasurementBasis, { short: string; long: string }> = {
  PIXEL_BASED: { short: "Pixels", long: "Pixel-based, no physical scale" },
  PHYSICALLY_CALIBRATED: { short: "Calibrated", long: "Physically calibrated" },
};

export const identityCopy: Record<IdentityStatus, string> = {
  VERIFIED: "Verified",
  UNVERIFIED: "Unverified",
  UNKNOWN: "Unknown",
};

export const timestampCopy: Record<TimestampSource, string> = {
  EXIF: "From the photo",
  USER_ENTERED: "Entered by hand",
  DEVICE: "From the device",
  UNKNOWN: "Unknown",
};
