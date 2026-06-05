# MindLift — Depression Support App Plan

## ⚠️ Framing & Responsibility

This plan is for a **depression support app**, not a "cure." No app can "stop"
depression on its own, and overpromising is both clinically irresponsible and a
regulatory/liability risk. Depression is a medical condition that often requires
professional care (therapy, medication, or both).

The product positions itself as an **evidence-based, daily companion** that helps
users:
- Build habits and skills shown to reduce depressive symptoms.
- Notice early warning signs and act on them.
- Stay connected to professional care and crisis support.

**Non-negotiable principles**
1. The app **augments**, never replaces, professional care.
2. **Safety first**: crisis detection and resources are always one tap away.
3. **Evidence-based** only: every feature maps to a recognized therapeutic method.
4. **Privacy by design**: mental health data is highly sensitive.

---

## 1. Goals & Success Metrics

### Primary goal
Help users reduce and manage depressive symptoms through daily, evidence-based
self-care, while routing people in crisis to appropriate help.

### Success metrics
| Category | Metric | Target |
|---|---|---|
| Clinical | Change in PHQ-9 score over 8 weeks | Meaningful reduction (≥5 pts) for engaged users |
| Engagement | 7-day / 30-day retention | 40% / 20% |
| Habit | % users with ≥3 active days/week | 50% |
| Safety | Crisis flows surfaced when risk detected | 100% of detected cases |
| Trust | Users who connect a clinician or support contact | 25% |

> PHQ-9 is a standard, validated depression screening questionnaire. We use it
> for **self-monitoring**, not diagnosis.

---

## 2. Target Users

- **Primary**: Adults (18+) with mild-to-moderate depressive symptoms seeking
  daily structure and skills.
- **Secondary**: People in therapy who want a between-sessions companion.
- **Explicitly out of scope at launch**: Minors, and people in acute crisis as a
  *primary* audience (we still must handle crisis safely, but the app is not an
  emergency service).

---

## 3. Evidence-Based Feature Set

Each feature maps to an established method.

### 3.1 Mood & symptom tracking
- Daily mood check-in (quick emoji/scale + optional note).
- Periodic PHQ-9 self-assessment with trend visualization.
- Triggers, sleep, and activity logging.
- **Method**: self-monitoring, a core component of CBT.

### 3.2 Cognitive Behavioral Therapy (CBT) tools
- Thought records (identify → challenge → reframe negative thoughts).
- Cognitive distortion identification with examples.
- Guided lessons and worksheets.
- **Method**: CBT, the most evidence-backed psychotherapy for depression.

### 3.3 Behavioral Activation
- Activity scheduling and pleasant-activity menus.
- Small, achievable daily goals with gentle nudges.
- "Activation streaks" emphasizing action over mood.
- **Method**: Behavioral Activation, strongly supported for depression.

### 3.4 Mindfulness & relaxation
- Guided meditations, breathing exercises, body scans.
- Sleep hygiene content and wind-down routines.
- **Method**: MBCT (Mindfulness-Based Cognitive Therapy).

### 3.5 Gratitude & positive psychology
- Daily gratitude journaling.
- "Three good things" exercise.
- **Method**: positive psychology interventions.

### 3.6 Connection & support
- Optional trusted-contact / support-buddy invite.
- Directory/links to find licensed therapists and teletherapy.
- Optional, *moderated* peer community (later phase — moderation is a hard
  requirement before launch).

### 3.7 Psychoeducation
- Plain-language library: what depression is, treatment options, myth-busting.
- Medication-adherence reminders (user-configured; no medical advice).

---

## 4. Safety & Crisis Handling (Highest Priority)

This must be designed **before** anything else ships.

- **Always-visible crisis button** on every screen.
- **Region-aware crisis resources** (e.g., 988 Suicide & Crisis Lifeline in the
  US, local equivalents elsewhere; let users set their region).
- **Risk detection**: PHQ-9 item 9 (self-harm), keyword/sentiment signals in
  journaling, sudden mood drops → trigger a supportive crisis flow.
- **Crisis flow**: validate feelings → show hotline/text/chat options →
  safety-planning template → encourage reaching a person now.
- **Clear disclaimers**: not a medical device; not for emergencies; "if you are
  in danger, call emergency services."
- **Escalation, not silence**: never leave a high-risk user on a dead end.
- **Clinical review**: safety flows reviewed by a licensed mental-health
  professional before release.

---

## 5. Privacy, Security & Compliance

- **Data minimization**: collect only what's needed.
- **Encryption** at rest and in transit; sensitive entries encrypted.
- **Local-first option**: let users keep journals on-device where feasible.
- **No selling data, no ad-targeting on health data. Ever.**
- **Compliance**: assess HIPAA (if integrating with providers), GDPR, CCPA, and
  app-store health-data policies. Consult legal counsel.
- **Transparent consent**: clear, readable privacy policy; granular controls;
  easy data export and deletion.
- **Regulatory check**: determine whether any feature crosses into "medical
  device" territory (e.g., FDA SaMD) and adjust scope accordingly.

---

## 6. Technical Architecture

### Platforms
- Mobile-first: **iOS + Android** (React Native or Flutter for shared codebase).
- Lightweight web companion (later).

### Suggested stack
| Layer | Choice | Why |
|---|---|---|
| Client | React Native (TypeScript) | Cross-platform, large ecosystem |
| Backend | Node.js/TypeScript or Python (FastAPI) | Matches existing repo skills |
| Database | PostgreSQL (encrypted) | Reliable, mature |
| Auth | OAuth + secure session, optional biometric lock | Sensitive data |
| Notifications | Push (FCM/APNs), user-configurable | Gentle, non-spammy nudges |
| Analytics | Privacy-preserving, opt-in only | Trust |

### AI assistant (optional, carefully scoped)
- A supportive, **non-diagnostic** chat companion using the Claude API (the repo
  already has `chat.py` / `chat.ts` starting points).
- **Strict guardrails**: never diagnose, never advise on medication, always
  defer to professionals, hard-coded crisis routing on risk signals.
- Heavily system-prompted and tested against unsafe outputs; human-reviewed.

---

## 7. UX Principles

- **Calm, low-pressure design**: soft colors, no guilt-inducing streak loss.
- **Low effort to engage**: a check-in should take <30 seconds.
- **Accessibility**: WCAG-compliant, screen-reader friendly, adjustable text.
- **Encouraging tone**: progress over perfection; celebrate small wins.
- **No dark patterns**: easy to pause, mute, or leave.

---

## 8. Phased Roadmap

### Phase 0 — Foundations (Weeks 1–3)
- Recruit/consult a licensed clinical advisor.
- Finalize safety flows, disclaimers, and privacy/legal review.
- Design system + core navigation.

### Phase 1 — MVP (Weeks 4–10)
- Mood check-ins + PHQ-9 self-assessment + trends.
- One CBT tool (thought record) + Behavioral Activation scheduler.
- Crisis button + region-aware resources + safety plan.
- Accounts, encryption, privacy policy.

### Phase 2 — Core skills (Weeks 11–18)
- Full CBT lesson library, mindfulness/relaxation, gratitude journaling.
- Psychoeducation library, smart reminders.
- Trusted-contact support feature.

### Phase 3 — Companion & community (Weeks 19+)
- Scoped, guardrailed AI companion.
- Therapist directory / teletherapy integrations.
- Moderated peer community (only with real moderation in place).

### Phase 4 — Validation & scale
- Partner with researchers to study outcomes (e.g., PHQ-9 changes).
- Iterate on retention and clinical effectiveness.

---

## 9. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Overpromising a "cure" | Clear, honest framing; clinical review of all copy |
| Harm to at-risk users | Robust crisis detection + always-available resources |
| Privacy breach | Encryption, minimization, audits, no data sale |
| AI gives unsafe advice | Guardrails, refusal patterns, human testing, crisis routing |
| Regulatory non-compliance | Early legal review; medical-device assessment |
| Low engagement | Gentle design, low-effort flows, meaningful personalization |

---

## 10. Immediate Next Steps

1. Engage a **licensed mental-health professional** as clinical advisor.
2. Validate the **crisis/safety flow** design first.
3. Confirm **regional crisis resources** and legal/privacy requirements.
4. Build a clickable prototype of the MVP (mood check-in + thought record +
   crisis button).
5. Run a small, supervised pilot before any public launch.

---

*This document is a product plan, not medical advice. If you or someone you know
is struggling, please reach out to a qualified professional or a local crisis
line. In the US, call or text **988** (Suicide & Crisis Lifeline).*
