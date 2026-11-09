# Hand-off: what is left and who does it

Written 2026-11-09. Everything that needs no account, login or money is done. What remains needs you: a login, a camera, a decision or a paid service. Every item below is free unless it says otherwise.

## 1. Commit the prepared changes

These files are changed but not committed:

| File | What changed |
|---|---|
| `specs/phase-07/06-onnx-export-and-serving.md`, `specs/MASTER_TRACKER.md` | P07-S06 marked `COMPLETED`: its ONNX tests ran (not skipped) in CI run 42626597989 |
| `web/vercel.json`, `web/package.json`, `docs/deployment/VERCEL.md` | Free Vercel deployment of the dashboard in demonstration mode |
| `scripts/measurement/mark_object_ends.py`, `tests/measurement/test_marker.py`, `docs/measurement/PHOTO_PROTOCOL.md`, `specs/phase-09/01-reference-marker-calibration.md` | The tool and shot list for the real marker photos |
| `docs/HANDOFF.md` | This page |

Do not commit `.claude/launch.json`, `signal-lab/`, `signal-lab.zip` or `Signal_Lab_Project_Report.pdf`.

```bash
git add specs/phase-07/06-onnx-export-and-serving.md specs/MASTER_TRACKER.md
```

```bash
git commit -m "Close P07-S06 on the passing CI run"
```

```bash
git add web/vercel.json web/package.json docs/deployment/VERCEL.md
```

```bash
git commit -m "Add a free Vercel deployment of the dashboard in demonstration mode"
```

```bash
git add scripts/measurement/mark_object_ends.py tests/measurement/test_marker.py docs/measurement/PHOTO_PROTOCOL.md specs/phase-09/01-reference-marker-calibration.md docs/HANDOFF.md
```

```bash
git commit -m "Add the marker photo protocol and the end-point marking tool"
```

```bash
git push
```

## 2. Deploy the dashboard on Vercel (free, about 10 minutes)

Follow `docs/deployment/VERCEL.md`. In short: sign in at vercel.com with GitHub on the Hobby plan, import the repository, set Root Directory to `web`, add no environment variables, deploy. The site shows the demonstration data with a banner saying so. Afterwards, add the URL to `README.md` and the P08-S04 evidence.

## 3. Take the marker photos (free, about an hour)

Follow `docs/measurement/PHOTO_PROTOCOL.md`: print the sheet at 100%, check the 50 mm square, photograph a ruler and a card beside it at 20, 30 and 40 cm and 0°, 15° and 30°, mark the end points with `mark_object_ends.py`, and run `run_marker_validation.py`. This unblocks REQ-P09-S01-003 and P09-S01.

## 4. Approve or change the design (P08-S04)

Run the dashboard locally with `npm --prefix web run dev:mock`, or look at the Vercel deployment, and decide whether the design direction in `DESIGN.md` is accepted. If it is, record the approval and the date in `specs/phase-08/04-design-system-and-screens.md`, section 16.

## 5. Things that stay blocked without money or outside help

| Spec | Blocked on | Free route? |
|---|---|---|
| P07-S01 REQ-004 | The Docker Space needs Hugging Face PRO | No. The free static Space already gives a working demo |
| P07-S03 | A hosted S3 bucket and browser CORS | No free bucket without a card |
| P08-S02, P08-S03 | A staging deployment of the API, worker and Redis | No: needs always-on hosting |
| P09-S04 REQ-002/003/005 | A new external dataset or relabelled masks, then GPU time | Kaggle's free GPU covers the training, but the data has to exist first |
| P10-S01 | Sentry and Grafana Cloud accounts | Both have free tiers without a card; the account is yours to create |
| P10-S02, P10-S04 | A staging deployment with separate workers | No |
