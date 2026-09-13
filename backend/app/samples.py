"""Sample scenarios, backend-owned. Seeded into the store so users can select
and reset them; user edits live in the DB, samples only fill in missing rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Scenario

if TYPE_CHECKING:
    from .store import Store

SAMPLE_SCENARIOS: list[Scenario] = [
    Scenario.model_validate(
        {
            "id": "hiring-panel-v1",
            "title": "Senior Backend Engineer: John vs. Sally",
            "brief": "The panel must recommend exactly one candidate for a senior backend role on a payments team. Each panelist attended different parts of the interview loop and holds different evidence.",
            "isSample": True,
            "candidates": [
                {"id": "john", "name": "John", "blurb": "Polished, confident, eight years of Go"},
                {
                    "id": "sally",
                    "name": "Sally",
                    "blurb": "Nervous in the panel, has never written Go",
                },
            ],
            "agents": [
                {
                    "id": "dana",
                    "name": "Dana",
                    "role": "Hiring manager",
                    "style": "direct and decisive; wants to close the loop",
                },
                {
                    "id": "marcus",
                    "name": "Marcus",
                    "role": "Staff engineer",
                    "style": "precise, evidence-first, dislikes vibes",
                },
                {
                    "id": "priya",
                    "name": "Priya",
                    "role": "Recruiter",
                    "style": "warm, focused on references and team fit",
                },
                {
                    "id": "tom",
                    "name": "Tom",
                    "role": "QA lead",
                    "style": "skeptical, asks what could go wrong",
                },
                {
                    "id": "rachel",
                    "name": "Rachel",
                    "role": "Product manager",
                    "style": "pragmatic; user- and roadmap-focused",
                },
            ],
            "facts": [
                # ---- shared: strong, vivid John lead + mild Sally signal ----
                {
                    "id": "J1",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 3,
                    "text": "John's reference from his last CTO: 'the best engineer I have managed in 15 years, full stop.'",
                },
                {
                    "id": "J2",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 3,
                    "text": "In the work-sample round John live-coded a Go payments-reconciliation prototype and caught a flaw in our own sample schema.",
                },
                {
                    "id": "J3",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 2,
                    "text": "John has eight years of Go in production payments systems.",
                },
                {
                    "id": "J4",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 2,
                    "text": "John led a six-person platform team through a launch that held 99.99% availability.",
                },
                {
                    "id": "J5",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 2,
                    "text": "Every interviewer scored John 'strong yes' on communication and executive presence.",
                },
                {
                    "id": "J16",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 1,
                    "text": "John is available to start immediately.",
                },
                {
                    "id": "S10",
                    "candidateId": "sally",
                    "valence": "con",
                    "weight": 3,
                    "text": "Sally was visibly nervous in the panel: she rambled through two answers and stalled completely on a third.",
                },
                {
                    "id": "S11",
                    "candidateId": "sally",
                    "valence": "con",
                    "weight": 2,
                    "text": "Sally has never written Go and described our primary backend language as 'something I would pick up quickly.'",
                },
                {
                    "id": "S12",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 1,
                    "text": "Sally's written exercise was clean and well-organized.",
                },
                {
                    "id": "S13",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 1,
                    "text": "Sally asked thoughtful questions about on-call load and team health.",
                },
                # ---- dana's uniques ----
                {
                    "id": "S1",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 3,
                    "text": "Sally's former director: her postmortem process cut repeat incidents org-wide by half within a year.",
                },
                {
                    "id": "J8",
                    "candidateId": "john",
                    "valence": "con",
                    "weight": 3,
                    "text": "John's last two roles ended mid-project; both managers described the hand-offs as abrupt.",
                },
                {
                    "id": "J6",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 1,
                    "text": "John spoke our domain's language fluently - settlement, netting, idempotency - without prompting.",
                },
                # ---- marcus's uniques ----
                {
                    "id": "S2",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 3,
                    "text": "In the debugging session Sally isolated a silent data-loss bug, including the race that caused it, in under 20 minutes.",
                },
                {
                    "id": "J9",
                    "candidateId": "john",
                    "valence": "con",
                    "weight": 3,
                    "text": "John's take-home is near-identical to a public blog-post solution, down to variable names and an unusual comment.",
                },
                {
                    "id": "S14",
                    "candidateId": "sally",
                    "valence": "con",
                    "weight": 1,
                    "text": "Sally leaned on an editor and external docs even for routine API questions in the take-home debrief.",
                },
                # ---- priya's uniques ----
                {
                    "id": "S3",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 3,
                    "text": "Four engineers Sally mentored were promoted within two years; two now lead teams.",
                },
                {
                    "id": "J10",
                    "candidateId": "john",
                    "valence": "con",
                    "weight": 3,
                    "text": "Three of John's six reports left within a year; two cited John directly in exit interviews.",
                },
                {
                    "id": "J7",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 1,
                    "text": "John's references all described him as the most dependable person on their on-call rota.",
                },
                # ---- tom's uniques ----
                {
                    "id": "S4",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 3,
                    "text": "Sally's design answer anticipated the double-spend failure mode and proposed idempotency keys before being prompted.",
                },
                {
                    "id": "J11",
                    "candidateId": "john",
                    "valence": "con",
                    "weight": 3,
                    "text": "John claimed he 'led the platform migration'; a former colleague says he was one of twelve contributors.",
                },
                {
                    "id": "S15",
                    "candidateId": "sally",
                    "valence": "con",
                    "weight": 1,
                    "text": "Sally's references took three days to reply and one declined to comment.",
                },
                # ---- rachel's uniques ----
                {
                    "id": "S5",
                    "candidateId": "sally",
                    "valence": "pro",
                    "weight": 3,
                    "text": "Sally rewrote her team's batch settlement job, cut infrastructure cost 40%, and documented the pattern others still reuse.",
                },
                {
                    "id": "J12",
                    "candidateId": "john",
                    "valence": "con",
                    "weight": 3,
                    "text": "Asked about his product's users, John pivoted to architecture; in closing he raised only title and compensation.",
                },
                {
                    "id": "J13",
                    "candidateId": "john",
                    "valence": "pro",
                    "weight": 1,
                    "text": "John's former PM: 'the engineer I would rehire first for a messy roadmap.'",
                },
            ],
            "distribution": {
                "dana": [
                    "J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13",
                    "S1", "J8", "J6",
                ],
                "marcus": [
                    "J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13",
                    "S2", "J9", "S14",
                ],
                "priya": [
                    "J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13",
                    "S3", "J10", "J7",
                ],
                "tom": [
                    "J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13",
                    "S4", "J11", "S15",
                ],
                "rachel": [
                    "J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13",
                    "S5", "J12", "J13",
                ],
            },
        }
    ),
    Scenario.model_validate(
        {
            "id": "incident-review-v1",
            "title": "Post-mortem Panel: Deploy vs. Database",
            "brief": "Five engineers must agree on the root cause of Tuesday's payments outage before writing the postmortem. Each saw different dashboards and logs during the incident.",
            "isSample": True,
            "candidates": [
                {"id": "deploy", "name": "Deploy", "blurb": "The Tuesday config deploy, rolled out nine minutes before errors began"},
                {"id": "db", "name": "Ledger DB", "blurb": "Connection-pool exhaustion in the ledger database"},
            ],
            "agents": [
                {"id": "kai", "name": "Kai", "role": "SRE on-call", "style": "incident-scarred, timeline-obsessed"},
                {"id": "lena", "name": "Lena", "role": "DB engineer", "style": "slow and methodical, trusts audit logs"},
                {"id": "omar", "name": "Omar", "role": "Release manager", "style": "process-minded, keeps receipts"},
                {"id": "mei", "name": "Mei", "role": "Backend lead", "style": "reads code first, argues second"},
                {"id": "jules", "name": "Jules", "role": "Support lead", "style": "customer-impact focused, plain-spoken"},
            ],
            "facts": [
                # ---- shared: evidence points at the deploy ----
                {"id": "D1", "candidateId": "deploy", "valence": "pro", "weight": 3,
                 "text": "The error spike began nine minutes after the Tuesday config deploy hit 40% of the fleet."},
                {"id": "D2", "candidateId": "deploy", "valence": "pro", "weight": 2,
                 "text": "The deploy touched the config namespace that gates DB connection settings."},
                {"id": "D3", "candidateId": "deploy", "valence": "pro", "weight": 2,
                 "text": "A deploy-caused outage hit this same service eight months ago and everyone remembers it."},
                {"id": "D4", "candidateId": "deploy", "valence": "pro", "weight": 2,
                 "text": "The deploy diff shows a changed line in the pool configuration file."},
                {"id": "D5", "candidateId": "deploy", "valence": "pro", "weight": 1,
                 "text": "The deploy dashboard shows error rate climbing in lock-step with rollout percentage."},
                {"id": "D12", "candidateId": "deploy", "valence": "con", "weight": 1,
                 "text": "The deploy passed canary checks and staged rollout without any error signals."},
                {"id": "B10", "candidateId": "db", "valence": "con", "weight": 1,
                 "text": "The ledger DB's CPU and disk metrics stayed nominal throughout the incident window."},
                # ---- kai's uniques ----
                {"id": "B1", "candidateId": "db", "valence": "pro", "weight": 3,
                 "text": "Kai's on-call log: pool 'wait queue' alarms fired forty minutes BEFORE the deploy pipeline started."},
                {"id": "D6", "candidateId": "deploy", "valence": "con", "weight": 3,
                 "text": "The changed line in the pool config file was a comment-only edit; the effective pool.max_size never changed."},
                {"id": "D7", "candidateId": "deploy", "valence": "pro", "weight": 1,
                 "text": "Two other services that took the same deploy showed briefly elevated error rates."},
                # ---- lena's uniques ----
                {"id": "B2", "candidateId": "db", "valence": "pro", "weight": 3,
                 "text": "Lena pulled the ledger DB audit log: pool checkout latency doubled at 09:12, before the deploy ran."},
                {"id": "D8", "candidateId": "deploy", "valence": "con", "weight": 2,
                 "text": "Rolling back the deploy at 10:05 did not reduce errors; they kept climbing for another hour."},
                {"id": "D9", "candidateId": "deploy", "valence": "pro", "weight": 1,
                 "text": "The deploy coincided with a documented change-freeze violation."},
                # ---- omar's uniques ----
                {"id": "B3", "candidateId": "db", "valence": "pro", "weight": 3,
                 "text": "Omar's records: the 'deploy-caused' outage eight months ago was re-attributed to pool exhaustion; the postmortem was amended."},
                {"id": "D10", "candidateId": "deploy", "valence": "con", "weight": 2,
                 "text": "The pipeline's own health gate auto-rolled-back the deploy mid-incident, yet the outage continued."},
                {"id": "B4", "candidateId": "db", "valence": "con", "weight": 1,
                 "text": "A pool-saturation metric was disabled in a dashboard migration two weeks earlier, so direct evidence is missing."},
                # ---- mei's uniques ----
                {"id": "B5", "candidateId": "db", "valence": "pro", "weight": 3,
                 "text": "Mei found a silent pool-size regression merged three sprints ago - maxSize halved - unrelated to Tuesday's deploy."},
                {"id": "B6", "candidateId": "db", "valence": "pro", "weight": 2,
                 "text": "Mei's traces show request timeouts correlate with pool wait, not with config reloads."},
                {"id": "D11", "candidateId": "deploy", "valence": "pro", "weight": 1,
                 "text": "The deploy author admitted the change 'should have been split into two.'"},
                # ---- jules's uniques ----
                {"id": "B7", "candidateId": "db", "valence": "pro", "weight": 3,
                 "text": "Jules matched support tickets: 'duplicate charge' reports began Monday night, a day before the deploy."},
                {"id": "B8", "candidateId": "db", "valence": "pro", "weight": 2,
                 "text": "Customer-impact timestamps align with pool-saturation spikes, not with rollout percentage."},
                {"id": "D13", "candidateId": "deploy", "valence": "pro", "weight": 1,
                 "text": "Support volume spiked hardest in the regions that received the deploy first."},
            ],
            "distribution": {
                "kai":   ["D1", "D2", "D3", "D4", "D5", "D12", "B10", "B1", "D6", "D7"],
                "lena":  ["D1", "D2", "D3", "D4", "D5", "D12", "B10", "B2", "D8", "D9"],
                "omar":  ["D1", "D2", "D3", "D4", "D5", "D12", "B10", "B3", "D10", "B4"],
                "mei":   ["D1", "D2", "D3", "D4", "D5", "D12", "B10", "B5", "B6", "D11"],
                "jules": ["D1", "D2", "D3", "D4", "D5", "D12", "B10", "B7", "B8", "D13"],
            },
        }
    ),
    Scenario.model_validate(
        {
            "id": "vendor-selection-v1",
            "title": "Procurement Committee: Northwind vs. Contoso",
            "brief": "A five-person committee must pick one SaaS vendor for the company's workflow platform. Each member did a different part of the evaluation.",
            "isSample": True,
            "candidates": [
                {"id": "northwind", "name": "Northwind", "blurb": "Glossy demo, aggressive pricing, fast onboarding"},
                {"id": "contoso", "name": "Contoso", "blurb": "Stodgier sales process, deeper platform"},
            ],
            "agents": [
                {"id": "vera", "name": "Vera", "role": "Procurement lead", "style": "contract-focused, allergic to fine print"},
                {"id": "eli", "name": "Eli", "role": "Security reviewer", "style": "paranoid by profession"},
                {"id": "ingrid", "name": "Ingrid", "role": "Solutions architect", "style": "integration-first, dislikes slideware"},
                {"id": "noah", "name": "Noah", "role": "Finance analyst", "style": "spreadsheet-minded, hunts hidden costs"},
                {"id": "sofia", "name": "Sofia", "role": "Operations lead", "style": "speaks for the end users"},
            ],
            "facts": [
                # ---- shared: Northwind looks great ----
                {"id": "N1", "candidateId": "northwind", "valence": "pro", "weight": 3,
                 "text": "Northwind's demo was flawless - polished UI, every requested workflow shown live."},
                {"id": "N2", "candidateId": "northwind", "valence": "pro", "weight": 3,
                 "text": "Northwind's quoted price is 22% below Contoso's for the same seat count."},
                {"id": "N3", "candidateId": "northwind", "valence": "pro", "weight": 2,
                 "text": "Northwind committed to our full feature checklist in writing."},
                {"id": "N4", "candidateId": "northwind", "valence": "pro", "weight": 2,
                 "text": "Two peer companies gave glowing references (both provided by Northwind)."},
                {"id": "N5", "candidateId": "northwind", "valence": "pro", "weight": 2,
                 "text": "Northwind promises go-live in 6 weeks versus Contoso's 14."},
                {"id": "C10", "candidateId": "contoso", "valence": "con", "weight": 2,
                 "text": "Contoso's demo needed a broken-environment reschedule and showed last year's UI."},
                {"id": "C11", "candidateId": "contoso", "valence": "con", "weight": 1,
                 "text": "Contoso's sales team took a week to answer a simple pricing question."},
                {"id": "C12", "candidateId": "contoso", "valence": "pro", "weight": 1,
                 "text": "Contoso's documentation is unusually thorough."},
                {"id": "C13", "candidateId": "contoso", "valence": "pro", "weight": 1,
                 "text": "Contoso supports self-hosting, which Northwind does not."},
                # ---- vera's uniques ----
                {"id": "C1", "candidateId": "contoso", "valence": "pro", "weight": 3,
                 "text": "Contoso's contract draft includes penalty-backed SLAs and audited uptime reporting."},
                {"id": "N6", "candidateId": "northwind", "valence": "con", "weight": 3,
                 "text": "Northwind's contract auto-renews into a three-year lock-in and caps liability at one month's fees."},
                {"id": "N7", "candidateId": "northwind", "valence": "pro", "weight": 1,
                 "text": "Northwind agreed to fixed pricing for two years."},
                # ---- eli's uniques ----
                {"id": "N8", "candidateId": "northwind", "valence": "con", "weight": 3,
                 "text": "Northwind failed last year's SOC 2 follow-up audit on access-control findings; remediation is still open."},
                {"id": "C2", "candidateId": "contoso", "valence": "pro", "weight": 2,
                 "text": "Contoso passed our pen-test review with zero critical findings."},
                {"id": "N9", "candidateId": "northwind", "valence": "pro", "weight": 1,
                 "text": "Northwind holds a current ISO 27001 certification."},
                # ---- ingrid's uniques ----
                {"id": "N10", "candidateId": "northwind", "valence": "con", "weight": 3,
                 "text": "Northwind's API is rate-limited to 60 req/min with no bulk export - below our documented peak needs."},
                {"id": "C3", "candidateId": "contoso", "valence": "pro", "weight": 2,
                 "text": "Contoso's API covers every integration in our architecture review, including webhooks."},
                {"id": "N11", "candidateId": "northwind", "valence": "pro", "weight": 1,
                 "text": "Northwind's mobile app is the best-reviewed in the category."},
                # ---- noah's uniques ----
                {"id": "N12", "candidateId": "northwind", "valence": "con", "weight": 2,
                 "text": "Northwind's '22% cheaper' quote excludes a mandatory implementation package adding 18% to year one."},
                {"id": "C4", "candidateId": "contoso", "valence": "pro", "weight": 3,
                 "text": "Contoso's three-year TCO is 15% lower once implementation and seat growth are priced in."},
                {"id": "C5", "candidateId": "contoso", "valence": "con", "weight": 1,
                 "text": "Contoso charges separately for premium support."},
                # ---- sofia's uniques ----
                {"id": "N13", "candidateId": "northwind", "valence": "con", "weight": 2,
                 "text": "A Northwind-provided reference quietly revealed a painful nine-month rollout, not the promised six weeks."},
                {"id": "C6", "candidateId": "contoso", "valence": "pro", "weight": 3,
                 "text": "In our ops pilot, Contoso hit 96% task success versus Northwind's 71% under identical conditions."},
                {"id": "N14", "candidateId": "northwind", "valence": "pro", "weight": 1,
                 "text": "Northwind offers a free admin-training package."},
            ],
            "distribution": {
                "vera":   ["N1", "N2", "N3", "N4", "N5", "C10", "C11", "C12", "C13", "C1", "N6", "N7"],
                "eli":    ["N1", "N2", "N3", "N4", "N5", "C10", "C11", "C12", "C13", "N8", "C2", "N9"],
                "ingrid": ["N1", "N2", "N3", "N4", "N5", "C10", "C11", "C12", "C13", "N10", "C3", "N11"],
                "noah":   ["N1", "N2", "N3", "N4", "N5", "C10", "C11", "C12", "C13", "N12", "C4", "C5"],
                "sofia":  ["N1", "N2", "N3", "N4", "N5", "C10", "C11", "C12", "C13", "N13", "C6", "N14"],
            },
        }
    ),
    Scenario.model_validate(
        {
            "id": "hiring-weak-profile-v1",
            "title": "Senior Backend Engineer: John vs. Sally (weak profile)",
            "brief": "The panel must recommend exactly one candidate for a senior backend role on a payments team. Each panelist attended different parts of the interview loop and holds different evidence.",
            "isSample": True,
            "candidates": [
                {"id": "john", "name": "John", "blurb": "Polished, confident, eight years of Go"},
                {"id": "sally", "name": "Sally", "blurb": "Nervous in the panel, has never written Go"},
            ],
            "agents": [
                {"id": "dana", "name": "Dana", "role": "Hiring manager", "style": "direct and decisive; wants to close the loop"},
                {"id": "marcus", "name": "Marcus", "role": "Staff engineer", "style": "precise, evidence-first, dislikes vibes"},
                {"id": "priya", "name": "Priya", "role": "Recruiter", "style": "warm, focused on references and team fit"},
                {"id": "tom", "name": "Tom", "role": "QA lead", "style": "skeptical, asks what could go wrong"},
                {"id": "rachel", "name": "Rachel", "role": "Product manager", "style": "pragmatic; user- and roadmap-focused"},
            ],
            "facts": [
                # ---- shared ----
                {"id": "J1", "candidateId": "john", "valence": "pro", "weight": 3,
                 "text": "John's reference from his last CTO: 'the best engineer I have managed in 15 years, full stop.'"},
                {"id": "J2", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John has eight years of Go in production payments systems."},
                {"id": "J3", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John led a six-person platform team through a launch that held 99.99% availability."},
                {"id": "J4", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "Every interviewer scored John 'strong yes' on communication and executive presence."},
                {"id": "S10", "candidateId": "sally", "valence": "con", "weight": 1,
                 "text": "Sally was visibly nervous in the panel and rambled through two answers."},
                {"id": "S12", "candidateId": "sally", "valence": "pro", "weight": 1,
                 "text": "Sally's written exercise was clean and well-organized."},
                {"id": "S13", "candidateId": "sally", "valence": "pro", "weight": 1,
                 "text": "Sally asked thoughtful questions about on-call load and team health."},
                # ---- uniques (fewer, lighter) ----
                {"id": "S1", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "In the debugging session Sally isolated a silent data-loss bug, including the race, in under 20 minutes."},
                {"id": "S2", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "Sally's former director: 'the person I would hire first for an ambiguous, under-specified problem.'"},
                {"id": "J8", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "John's take-home is near-identical to a public blog-post solution, down to variable names."},
                {"id": "J9", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "Three of John's six reports left within a year; two cited John directly in exit interviews."},
                {"id": "J10", "candidateId": "john", "valence": "pro", "weight": 1,
                 "text": "John's references all described him as the most dependable person on their on-call rota."},
                {"id": "S14", "candidateId": "sally", "valence": "con", "weight": 1,
                 "text": "Sally's written exercise arrived two days after the deadline."},
            ],
            "distribution": {
                "dana":   ["J1", "J2", "J3", "J4", "S10", "S12", "S13", "S1"],
                "marcus": ["J1", "J2", "J3", "J4", "S10", "S12", "S13", "S2", "J10"],
                "priya":  ["J1", "J2", "J3", "J4", "S10", "S12", "S13", "J8", "S14"],
                "tom":    ["J1", "J2", "J3", "J4", "S10", "S12", "S13", "J9"],
                "rachel": ["J1", "J2", "J3", "J4", "S10", "S12", "S13"],
            },
        }
    ),
    Scenario.model_validate(
        {
            "id": "hiring-adversarial-v1",
            "title": "Senior Backend Engineer: John vs. Sally (biased stakeholder)",
            "brief": "The panel must recommend exactly one candidate for a senior backend role on a payments team. One panelist is John's would-be manager and only saw John's best moments; the other four each saw different parts of the loop.",
            "isSample": True,
            "candidates": [
                {"id": "john", "name": "John", "blurb": "Polished, confident, eight years of Go"},
                {"id": "sally", "name": "Sally", "blurb": "Nervous in the panel, has never written Go"},
            ],
            "agents": [
                {"id": "gabe", "name": "Gabe", "role": "Engineering director (John's would-be manager)", "style": "champions John openly; impatient with process"},
                {"id": "dana", "name": "Dana", "role": "Hiring manager", "style": "direct and decisive; wants to close the loop"},
                {"id": "marcus", "name": "Marcus", "role": "Staff engineer", "style": "precise, evidence-first, dislikes vibes"},
                {"id": "priya", "name": "Priya", "role": "Recruiter", "style": "warm, focused on references and team fit"},
                {"id": "tom", "name": "Tom", "role": "QA lead", "style": "skeptical, asks what could go wrong"},
            ],
            "facts": [
                # ---- shared (same lead as hiring-panel-v1) ----
                {"id": "J1", "candidateId": "john", "valence": "pro", "weight": 3,
                 "text": "John's reference from his last CTO: 'the best engineer I have managed in 15 years, full stop.'"},
                {"id": "J2", "candidateId": "john", "valence": "pro", "weight": 3,
                 "text": "In the work-sample round John live-coded a Go payments-reconciliation prototype and caught a flaw in our own sample schema."},
                {"id": "J3", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John has eight years of Go in production payments systems."},
                {"id": "J4", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John led a six-person platform team through a launch that held 99.99% availability."},
                {"id": "J5", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "Every interviewer scored John 'strong yes' on communication and executive presence."},
                {"id": "J16", "candidateId": "john", "valence": "pro", "weight": 1,
                 "text": "John is available to start immediately."},
                {"id": "S10", "candidateId": "sally", "valence": "con", "weight": 3,
                 "text": "Sally was visibly nervous in the panel: she rambled through two answers and stalled completely on a third."},
                {"id": "S11", "candidateId": "sally", "valence": "con", "weight": 2,
                 "text": "Sally has never written Go and described our primary backend language as 'something I would pick up quickly.'"},
                {"id": "S12", "candidateId": "sally", "valence": "pro", "weight": 1,
                 "text": "Sally's written exercise was clean and well-organized."},
                {"id": "S13", "candidateId": "sally", "valence": "pro", "weight": 1,
                 "text": "Sally asked thoughtful questions about on-call load and team health."},
                # ---- gabe's uniques: ONLY pro-John evidence ----
                {"id": "J14", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "In the architecture round John whiteboarded a payments ledger design unprompted that matched our internal one almost exactly."},
                {"id": "J15", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John's former PM told Gabe directly: 'the engineer I would rehire first for a messy roadmap.'"},
                {"id": "J17", "candidateId": "john", "valence": "pro", "weight": 2,
                 "text": "John negotiated a rival offer transparently and gave us a firm start date."},
                # ---- dana's uniques ----
                {"id": "S1", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "Sally's former director: her postmortem process cut repeat incidents org-wide by half within a year."},
                {"id": "J8", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "John's last two roles ended mid-project; both managers described the hand-offs as abrupt."},
                # ---- marcus's uniques ----
                {"id": "S2", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "In the debugging session Sally isolated a silent data-loss bug, including the race that caused it, in under 20 minutes."},
                {"id": "S3", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "Four engineers Sally mentored were promoted within two years; two now lead teams."},
                {"id": "J9", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "John's take-home is near-identical to a public blog-post solution, down to variable names and an unusual comment."},
                {"id": "S14", "candidateId": "sally", "valence": "con", "weight": 1,
                 "text": "Sally leaned on an editor and external docs even for routine API questions in the take-home debrief."},
                # ---- priya's uniques ----
                {"id": "S4", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "Sally's design answer anticipated the double-spend failure mode and proposed idempotency keys before being prompted."},
                {"id": "J10", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "Three of John's six reports left within a year; two cited John directly in exit interviews."},
                # ---- tom's uniques ----
                {"id": "S5", "candidateId": "sally", "valence": "pro", "weight": 3,
                 "text": "Sally rewrote her team's batch settlement job, cut infrastructure cost 40%, and documented the pattern others still reuse."},
                {"id": "J11", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "John claimed he 'led the platform migration'; a former colleague says he was one of twelve contributors."},
                {"id": "J12", "candidateId": "john", "valence": "con", "weight": 3,
                 "text": "Asked about his product's users, John pivoted to architecture; in closing he raised only title and compensation."},
                {"id": "J18", "candidateId": "john", "valence": "pro", "weight": 1,
                 "text": "John's references all described him as the most dependable person on their on-call rota."},
            ],
            "distribution": {
                "gabe":   ["J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13", "J14", "J15", "J17"],
                "dana":   ["J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13", "S1", "J8"],
                "marcus": ["J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13", "S2", "S3", "J9", "S14"],
                "priya":  ["J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13", "S4", "J10"],
                "tom":    ["J1", "J2", "J3", "J4", "J5", "J16", "S10", "S11", "S12", "S13", "S5", "J11", "J12", "J18"],
            },
        }
    ),
]

SAMPLES_BY_ID: dict[str, Scenario] = {s.id: s for s in SAMPLE_SCENARIOS}


def ensure_samples(store: Store) -> int:
    """Insert samples that are missing; never overwrite an existing row."""
    existing = {s.id for s in store.list_scenarios()}
    inserted = 0
    for sample in SAMPLE_SCENARIOS:
        if sample.id not in existing:
            store.upsert_scenario(sample)
            inserted += 1
    return inserted
