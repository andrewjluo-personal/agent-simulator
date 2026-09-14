# S5 scenario audit

Method: WIF authentication with `claude-haiku-4-5`, balanced cyclic candidate rotation, 8 samples/cell for 2-candidate scenarios and 6 samples/cell for 3-candidate scenarios, under both naive and default prompts. G0 used twin-null scenarios with 3 seeds × 6 = 18 ballots/cell and a null band of 1/k ± 15 percentage points (`[0.18, 0.48]` for k=3). Total cost: G1/G2 $1.69 for 25 scenarios × 2 prompts; G0 $0.66 first pass + $0.19 company rerun.

## Main table

| scenario | k | agents | static pooled margin | static min alone margin | G1 naive alone-wrong | G1 default alone-wrong | G2 naive pooled-right | G2 default pooled-right | G0 pooled naive/default | verdict | served |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | --- | :---: |
| hiddenbench-baker-2010 | 3 | 4 | - | 2 | NA/NA/NA/NA | NA/NA/NA/NA | NA | NA | not run / not run | FAIL-G2 | no |
| hiddenbench-company-acquisition-decision | 3 | 4 | 8 | 0 | 100%/83%/100%/100% | 100%/100%/100%/100% | 100% | 100% | option-a-biomedical-startup 17%, option-b-ai-hardware-startup 17%, option-c-logistics-software-company 67% / option-a-biomedical-startup 6%, option-b-ai-hardware-startup 61%, option-c-logistics-software-company 33% | FAILS-G0 | yes |
| hiddenbench-critical-hospital-transfer | 3 | 4 | 3 | 0 | 100%/33%/100%/17% | 100%/33%/100%/50% | 100% | 100% | not run / not run | FAIL-G1/G2 | no |
| hiddenbench-evacuation-west-city | 3 | 4 | 4 | 0 | 100%/100%/100%/100% | 100%/100%/100%/100% | 33% | 0% | not run / not run | FAIL-G1/G2 | no |
| hiddenbench-graetz-et-al-1998 | 3 | 4 | - | — | NA/NA/NA/NA | NA/NA/NA/NA | NA | NA | not run / not run | FAIL-G2 | no |
| hiddenbench-laboratory-theft-deduction | 3 | 4 | 2 | — | 100%/100%/100%/100% | 100%/100%/100%/83% | 83% | 83% | lab-alpha 6%, lab-beta 0%, lab-gamma 28% / lab-alpha 0%, lab-beta 0%, lab-gamma 61% | FAILS-G0 | yes |
| hiddenbench-schulz-hardt-mojzisch-2012 | 4 | 3 | - | — | NA/NA/NA | NA/NA/NA | NA | NA | not run / not run | FAIL-G2 | no |
| hiddenbench-stasser-stewart-1992 | 3 | 3 | 2 | 0 | 67%/100%/83% | 100%/100%/100% | 33% | 0% | not run / not run | FAIL-G1/G2 | no |
| hiddenbench-the-lead-investor-decision | 3 | 3 | 1 | — | 83%/33%/100% | 83%/17%/100% | 100% | 100% | not run / not run | FAIL-G1/G2 | no |
| hiddenbench-toma-butera-2009 | 4 | 3 | 2 | -1 | 50%/50%/25% | 25%/50%/25% | 100% | 100% | not run / not run | FAIL-G1/G2 | no |
| hiring-adversarial-v1 | 2 | 5 | 4 | 5 | 100%/0%/0%/0%/0% | 100%/12%/50%/62%/50% | 100% | 100% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-panel-3 | 2 | 3 | 4 | 4 | 12%/0%/0% | 88%/50%/12% | 100% | 88% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-panel-7 | 2 | 7 | 4 | 7 | 62%/25%/75%/0%/12%/62%/0% | 100%/88%/62%/88%/75%/88%/62% | 100% | 88% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-panel-9 | 2 | 9 | 4 | 7 | 75%/25%/12%/38%/75%/75%/25%/100%/0% | 100%/88%/62%/100%/100%/100%/75%/100%/75% | 100% | 88% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-panel-flat | 2 | 5 | 3 | 5 | 100%/100%/75%/75%/100% | 100%/100%/88%/100%/100% | 50% | 25% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-panel-flat-v2 | 2 | 5 | 11 | 4 | 88%/38%/25%/12%/100% | 100%/75%/62%/100%/100% | 100% | 100% | not run / not run | FAIL-G1/G2 (pre-#30 5-panelist S5; re-tuned in #30) | yes |
| hiring-panel-null | 2 | 5 | - | 0 | NA/NA/NA/NA/NA | NA/NA/NA/NA/NA | NA | NA | not run / not run | FAIL-G2 (pre-#30 5-panelist S5; re-tuned in #30) | yes |
| hiring-panel-v1 | 2 | 5 | 4 | 6 | 12%/0%/38%/0%/50% | 88%/25%/62%/100%/100% | 100% | 100% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| hiring-weak-profile-v1 | 2 | 5 | 2 | 5 | 0%/100%/12%/75%/100% | 62%/88%/75%/100%/100% | 100% | 100% | not run / not run | FAIL-G1/G2 (retired by #30) | no |
| incident-review-v1 | 2 | 5 | 4 | 7 | 88%/25%/75%/88%/75% | 100%/25%/25%/25%/50% | 100% | 100% | not run / not run | FAIL-G1/G2 | no |
| stasser-1985-hidden | 3 | 4 | 4 | 5 | 100%/100%/100%/100% | 100%/100%/100%/100% | 100% | 83% | a 56%, b 28%, c 17% / a 50%, b 28%, c 22% | FAILS-G0 | yes |
| stasser-1985-shared | 3 | 4 | 4 | 0 | 17%/0%/17%/17% | 17%/17%/0%/67% | 100% | 83% | not run / not run | FAIL-G1/G2 | no |
| stasser-1992-judge | 3 | 3 | 1 | 2 | 83%/50%/100% | 67%/67%/100% | 100% | 100% | not run / not run | FAIL-G1/G2 | no |
| stasser-1992-solve | 3 | 3 | 1 | 2 | 67%/67%/83% | 83%/33%/100% | 83% | 100% | not run / not run | FAIL-G1/G2 | no |
| vendor-selection-v1 | 2 | 5 | 4 | 7 | 75%/88%/75%/100%/100% | 88%/100%/100%/100%/88% | 100% | 75% | not run / not run | FAIL-G1/G2 | no |

## Survivor detail

### hiddenbench-company-acquisition-decision

#### G1/G2 — naive
Correct candidate: `option-c-logistics-software-company`; shared-only verdict: `option-c-logistics-software-company`.

| cell | option-a-biomedical-startup | option-b-ai-hardware-startup | option-c-logistics-software-company |
| --- | --- | --- | --- |
| pooled | option-a-biomedical-startup: {'option-c-logistics-software-company': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-c-logistics-software-company': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-c-logistics-software-company': 2} (100% [34%–100%]) |
| p1 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p2 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-c-logistics-software-company': 1, 'option-b-ai-hardware-startup': 1} (50% [9%–91%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p3 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p4 | option-a-biomedical-startup: {'option-a-biomedical-startup': 1, 'option-b-ai-hardware-startup': 1} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |

Reason excerpts (pooled):
- Option C has experienced founders, a recoverable revenue base (lost customer will return if founders stay), and avoids the crippling risks facing A (expired patents, legal disputes) and B (non-transfe
- Option C has experienced founders capable of retaining its lost major customer post-acquisition, whereas Option B faces immediate loss of its chief engineer and non-transferable client contracts, and
Reason excerpts (p1):
- Despite the key engineer departure risk, Option B shows stable revenue, strong sales growth, and VC interest in its sector, making it more viable than Option A's IP disputes or Option C's lost major c
- Option B has stable revenue, strong sales growth, and VC interest in its sector, despite the concerning loss of its chief engineer post-acquisition.

#### G0 twin-null — naive
Null band: [0.18, 0.48].

| cell | option-a-biomedical-startup | option-b-ai-hardware-startup | option-c-logistics-software-company |
| --- | --- | --- | --- |
| pooled | {'option-b-ai-hardware-startup': 3, 'option-a-biomedical-startup': 2, 'option-c-logistics-software-company': 1}; option-a-biomedical-startup 33% [10%–70%]; option-b-ai-hardware-startup 50% [19%–81%]; option-c-logistics-software-company 17% [3%–56%] | {'option-c-logistics-software-company': 5, 'option-a-biomedical-startup': 1}; option-a-biomedical-startup 17% [3%–56%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 83% [44%–97%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] |
| p1 | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-a-biomedical-startup': 6}; option-a-biomedical-startup 100% [61%–100%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 0% [0%–39%] |
| p2 | {'option-b-ai-hardware-startup': 4, 'option-c-logistics-software-company': 1, 'option-a-biomedical-startup': 1}; option-a-biomedical-startup 17% [3%–56%]; option-b-ai-hardware-startup 67% [30%–90%]; option-c-logistics-software-company 17% [3%–56%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-c-logistics-software-company': 4, 'option-a-biomedical-startup': 2}; option-a-biomedical-startup 33% [10%–70%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 67% [30%–90%] |
| p3 | {'option-b-ai-hardware-startup': 5, 'option-c-logistics-software-company': 1}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 83% [44%–97%]; option-c-logistics-software-company 17% [3%–56%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-a-biomedical-startup': 5, 'option-b-ai-hardware-startup': 1}; option-a-biomedical-startup 83% [44%–97%]; option-b-ai-hardware-startup 17% [3%–56%]; option-c-logistics-software-company 0% [0%–39%] |
| p4 | {'option-b-ai-hardware-startup': 5, 'option-a-biomedical-startup': 1}; option-a-biomedical-startup 17% [3%–56%]; option-b-ai-hardware-startup 83% [44%–97%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-a-biomedical-startup': 5, 'option-c-logistics-software-company': 1}; option-a-biomedical-startup 83% [44%–97%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 17% [3%–56%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

#### G1/G2 — default
Correct candidate: `option-c-logistics-software-company`; shared-only verdict: `option-c-logistics-software-company`.

| cell | option-a-biomedical-startup | option-b-ai-hardware-startup | option-c-logistics-software-company |
| --- | --- | --- | --- |
| pooled | option-a-biomedical-startup: {'option-c-logistics-software-company': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-c-logistics-software-company': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-c-logistics-software-company': 2} (100% [34%–100%]) |
| p1 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p2 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p3 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |
| p4 | option-a-biomedical-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-b-ai-hardware-startup: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) | option-c-logistics-software-company: {'option-b-ai-hardware-startup': 2} (100% [34%–100%]) |

Reason excerpts (pooled):
- Option C has experienced founders, a recoverable revenue base (lost customer willing to return), while Option A faces patent expiration and Option B has key person risk plus non-transferable client co
- Option C has experienced founders, a recoverable major customer (contingent on founder retention), and no imminent IP expiry or key-person flight risk unlike Options A and B.
Reason excerpts (p1):
- Option B has stable revenue, strong sales growth, and VC interest in its sector, despite the chief engineer departure risk being a significant concern that needs discussion.
- Option B has stable revenue and announced strong sales growth, though the chief engineer's planned resignation is a serious risk that needs clarification from other panelists.

#### G0 twin-null — default
Null band: [0.18, 0.48].

| cell | option-a-biomedical-startup | option-b-ai-hardware-startup | option-c-logistics-software-company |
| --- | --- | --- | --- |
| pooled | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-b-ai-hardware-startup': 2, 'option-c-logistics-software-company': 4}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 33% [10%–70%]; option-c-logistics-software-company 67% [30%–90%] | {'option-b-ai-hardware-startup': 3, 'option-a-biomedical-startup': 1, 'option-c-logistics-software-company': 2}; option-a-biomedical-startup 17% [3%–56%]; option-b-ai-hardware-startup 50% [19%–81%]; option-c-logistics-software-company 33% [10%–70%] |
| p1 | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-a-biomedical-startup': 3, 'option-b-ai-hardware-startup': 3}; option-a-biomedical-startup 50% [19%–81%]; option-b-ai-hardware-startup 50% [19%–81%]; option-c-logistics-software-company 0% [0%–39%] |
| p2 | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 5, 'option-b-ai-hardware-startup': 1}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 17% [3%–56%]; option-c-logistics-software-company 83% [44%–97%] | {'option-c-logistics-software-company': 4, 'option-a-biomedical-startup': 2}; option-a-biomedical-startup 33% [10%–70%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 67% [30%–90%] |
| p3 | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 0% [0%–39%]; option-c-logistics-software-company 100% [61%–100%] | {'option-a-biomedical-startup': 3, 'option-b-ai-hardware-startup': 3}; option-a-biomedical-startup 50% [19%–81%]; option-b-ai-hardware-startup 50% [19%–81%]; option-c-logistics-software-company 0% [0%–39%] |
| p4 | {'option-b-ai-hardware-startup': 6}; option-a-biomedical-startup 0% [0%–39%]; option-b-ai-hardware-startup 100% [61%–100%]; option-c-logistics-software-company 0% [0%–39%] | {'option-c-logistics-software-company': 4, 'option-a-biomedical-startup': 1, 'option-b-ai-hardware-startup': 1}; option-a-biomedical-startup 17% [3%–56%]; option-b-ai-hardware-startup 17% [3%–56%]; option-c-logistics-software-company 67% [30%–90%] | {'option-a-biomedical-startup': 5, 'option-b-ai-hardware-startup': 1}; option-a-biomedical-startup 83% [44%–97%]; option-b-ai-hardware-startup 17% [3%–56%]; option-c-logistics-software-company 0% [0%–39%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

### hiddenbench-laboratory-theft-deduction

#### G1/G2 — naive
Correct candidate: `lab-gamma`; shared-only verdict: `lab-alpha`.

| cell | lab-alpha | lab-beta | lab-gamma |
| --- | --- | --- | --- |
| pooled | lab-alpha: {'lab-gamma': 2} (100% [34%–100%]) | lab-beta: {'lab-gamma': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 1, 'lab-gamma': 1} (50% [9%–91%]) |
| p1 | lab-alpha: {'lab-beta': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p2 | lab-alpha: {'lab-alpha': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p3 | lab-alpha: {'lab-alpha': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p4 | lab-alpha: {'lab-beta': 2} (100% [34%–100%]) | lab-beta: {'lab-beta': 2} (100% [34%–100%]) | lab-gamma: {'lab-beta': 2} (100% [34%–100%]) |

Reason excerpts (pooled):
- Lab Gamma reported a missing staff member during the theft window with only three authorized badge entries, suggesting one person may have bypassed normal checkout procedures or remained in the vault
- Lab Gamma has a documented missing person during the theft window with only three badge entries recorded, creating an unaccounted gap that suggests someone may have exited without proper logging or us
Reason excerpts (p1):
- Lab Alpha's code machine never left their lab and is accounted for, while Lab Gamma had staff present with corridor movement recorded, leaving Lab Beta as the most likely candidate by process of elimi
- Lab Alpha has the only specialized code machine required for the theft, a documented history of security violations, and their equipment never left the lab during the theft window—suggesting inside ac

#### G0 twin-null — naive
Null band: [0.18, 0.48].

| cell | lab-alpha | lab-beta | lab-gamma |
| --- | --- | --- | --- |
| pooled | {'undecided': 3, 'lab-gamma': 3}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 50% [19%–81%] | {'undecided': 4, 'lab-alpha': 1, 'lab-gamma': 1}; lab-alpha 17% [3%–56%]; lab-beta 0% [0%–39%]; lab-gamma 17% [3%–56%] | {'lab-gamma': 1, 'undecided': 5}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 17% [3%–56%] |
| p1 | {'undecided': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] |
| p2 | {'lab-alpha': 6}; lab-alpha 100% [61%–100%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 3, 'lab-beta': 3}; lab-alpha 0% [0%–39%]; lab-beta 50% [19%–81%]; lab-gamma 0% [0%–39%] | {'lab-gamma': 3, 'undecided': 2, 'lab-beta': 1}; lab-alpha 0% [0%–39%]; lab-beta 17% [3%–56%]; lab-gamma 50% [19%–81%] |
| p3 | {'lab-gamma': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 100% [61%–100%] | {'lab-beta': 2, 'lab-gamma': 4}; lab-alpha 0% [0%–39%]; lab-beta 33% [10%–70%]; lab-gamma 67% [30%–90%] | {'lab-gamma': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 100% [61%–100%] |
| p4 | {'lab-alpha': 1, 'undecided': 5}; lab-alpha 17% [3%–56%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

#### G1/G2 — default
Correct candidate: `lab-gamma`; shared-only verdict: `lab-alpha`.

| cell | lab-alpha | lab-beta | lab-gamma |
| --- | --- | --- | --- |
| pooled | lab-alpha: {'lab-gamma': 2} (100% [34%–100%]) | lab-beta: {'lab-gamma': 1, 'lab-alpha': 1} (50% [9%–91%]) | lab-gamma: {'lab-gamma': 2} (100% [34%–100%]) |
| p1 | lab-alpha: {'lab-beta': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p2 | lab-alpha: {'lab-alpha': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p3 | lab-alpha: {'lab-alpha': 2} (100% [34%–100%]) | lab-beta: {'lab-alpha': 2} (100% [34%–100%]) | lab-gamma: {'lab-alpha': 2} (100% [34%–100%]) |
| p4 | lab-alpha: {'lab-beta': 2} (100% [34%–100%]) | lab-beta: {'lab-beta': 2} (100% [34%–100%]) | lab-gamma: {'lab-gamma': 1, 'lab-beta': 1} (50% [9%–91%]) |

Reason excerpts (pooled):
- Lab Gamma reported a missing staff member during the theft window despite security logs showing only three authorized badge entries, suggesting potential unauthorized movement or falsified headcount.
- Lab Gamma has a missing person from headcount during the theft window, while Beta's staff never left and Alpha's staff were documented in their break room; only Gamma has an unexplained absence matchi
Reason excerpts (p1):
- Lab Alpha's code machine was logged as never leaving their lab during the theft window, and Lab Gamma had staff present on-site with corridor movement recorded; Lab Beta is the remaining option, thoug
- Lab Alpha had the specialized code machine documented on-site during the theft window and has a history of security violations, making them the only lab with both means and demonstrated access vulnera

#### G0 twin-null — default
Null band: [0.18, 0.48].

| cell | lab-alpha | lab-beta | lab-gamma |
| --- | --- | --- | --- |
| pooled | {'lab-gamma': 4, 'undecided': 2}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 67% [30%–90%] | {'lab-gamma': 4, 'undecided': 2}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 67% [30%–90%] | {'lab-gamma': 3, 'undecided': 3}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 50% [19%–81%] |
| p1 | {'lab-alpha': 2, 'undecided': 4}; lab-alpha 33% [10%–70%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 3, 'lab-beta': 3}; lab-alpha 0% [0%–39%]; lab-beta 50% [19%–81%]; lab-gamma 0% [0%–39%] | {'undecided': 5, 'lab-gamma': 1}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 17% [3%–56%] |
| p2 | {'lab-alpha': 6}; lab-alpha 100% [61%–100%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'lab-beta': 5, 'undecided': 1}; lab-alpha 0% [0%–39%]; lab-beta 83% [44%–97%]; lab-gamma 0% [0%–39%] | {'lab-gamma': 5, 'lab-beta': 1}; lab-alpha 0% [0%–39%]; lab-beta 17% [3%–56%]; lab-gamma 83% [44%–97%] |
| p3 | {'lab-gamma': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 100% [61%–100%] | {'lab-gamma': 5, 'lab-beta': 1}; lab-alpha 0% [0%–39%]; lab-beta 17% [3%–56%]; lab-gamma 83% [44%–97%] | {'lab-gamma': 6}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 100% [61%–100%] |
| p4 | {'lab-alpha': 1, 'undecided': 5}; lab-alpha 17% [3%–56%]; lab-beta 0% [0%–39%]; lab-gamma 0% [0%–39%] | {'undecided': 5, 'lab-beta': 1}; lab-alpha 0% [0%–39%]; lab-beta 17% [3%–56%]; lab-gamma 0% [0%–39%] | {'undecided': 5, 'lab-gamma': 1}; lab-alpha 0% [0%–39%]; lab-beta 0% [0%–39%]; lab-gamma 17% [3%–56%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

### stasser-1985-hidden

#### G1/G2 — naive
Correct candidate: `a`; shared-only verdict: `b`.

| cell | a | b | c |
| --- | --- | --- | --- |
| pooled | a: {'a': 2} (100% [34%–100%]) | b: {'a': 2} (100% [34%–100%]) | c: {'a': 2} (100% [34%–100%]) |
| jordan | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| casey | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| riley | a: {'c': 1, 'b': 1} (100% [34%–100%]) | b: {'c': 1, 'b': 1} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| morgan | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |

Reason excerpts (pooled):
- Candidate A demonstrates consistent initiative in addressing student needs (accessibility, transportation, mental health, voter registration) and transparent governance, though attendance and campaign
- Candidate A demonstrates the most substantive leadership outcomes (voter registration, mental-health center, library hours, accessibility audit, cross-club coalition) despite some process missteps, wh
Reason excerpts (jordan):
- Candidate B demonstrates consistent follow-through on substantive initiatives (food-bank coordination, tutoring expansion, equipment grants), maintains engagement with campus policy, and has relevant
- Candidate B has demonstrated sustained commitment to concrete student outcomes—expanded tutoring access, secured equipment funding, and organized community service—while maintaining institutional enga

#### G0 twin-null — naive
Null band: [0.18, 0.48].

| cell | a | b | c |
| --- | --- | --- | --- |
| pooled | {'a': 6}; a 100% [61%–100%]; b 0% [0%–39%]; c 0% [0%–39%] | {'b': 4, 'a': 2}; a 33% [10%–70%]; b 67% [30%–90%]; c 0% [0%–39%] | {'c': 3, 'a': 2, 'b': 1}; a 33% [10%–70%]; b 17% [3%–56%]; c 50% [19%–81%] |
| jordan | {'a': 5, 'b': 1}; a 83% [44%–97%]; b 17% [3%–56%]; c 0% [0%–39%] | {'b': 4, 'a': 2}; a 33% [10%–70%]; b 67% [30%–90%]; c 0% [0%–39%] | {'c': 5, 'b': 1}; a 0% [0%–39%]; b 17% [3%–56%]; c 83% [44%–97%] |
| casey | {'a': 5, 'c': 1}; a 83% [44%–97%]; b 0% [0%–39%]; c 17% [3%–56%] | {'a': 2, 'b': 4}; a 33% [10%–70%]; b 67% [30%–90%]; c 0% [0%–39%] | {'a': 2, 'c': 3, 'b': 1}; a 33% [10%–70%]; b 17% [3%–56%]; c 50% [19%–81%] |
| riley | {'a': 6}; a 100% [61%–100%]; b 0% [0%–39%]; c 0% [0%–39%] | {'b': 5, 'a': 1}; a 17% [3%–56%]; b 83% [44%–97%]; c 0% [0%–39%] | {'c': 5, 'b': 1}; a 0% [0%–39%]; b 17% [3%–56%]; c 83% [44%–97%] |
| morgan | {'a': 5, 'c': 1}; a 83% [44%–97%]; b 0% [0%–39%]; c 17% [3%–56%] | {'a': 1, 'c': 1, 'b': 4}; a 17% [3%–56%]; b 67% [30%–90%]; c 17% [3%–56%] | {'b': 1, 'c': 4, 'a': 1}; a 17% [3%–56%]; b 17% [3%–56%]; c 67% [30%–90%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

#### G1/G2 — default
Correct candidate: `a`; shared-only verdict: `b`.

| cell | a | b | c |
| --- | --- | --- | --- |
| pooled | a: {'a': 2} (100% [34%–100%]) | b: {'a': 2} (100% [34%–100%]) | c: {'c': 1, 'a': 1} (50% [9%–91%]) |
| jordan | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| casey | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| riley | a: {'c': 1, 'b': 1} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 2} (100% [34%–100%]) |
| morgan | a: {'b': 2} (100% [34%–100%]) | b: {'b': 2} (100% [34%–100%]) | c: {'b': 1, 'c': 1} (100% [34%–100%]) |

Reason excerpts (pooled):
- Candidate A demonstrates sustained institutional engagement through concrete wins: secured mental-health funding, negotiated library hours, organized voter registration, and built cross-club coalition
- Candidate A demonstrates sustained institutional impact through negotiated library hours, mental-health center funding, voter registration, and cross-club coalition work, despite some governance gaps
Reason excerpts (jordan):
- Candidate B shows consistent follow-through on substantive initiatives—food-bank coordination, tutoring expansion, policy communication—with only one incomplete task, while A missed senate meetings an
- Candidate B shows consistent follow-through on policy goals—expanded tutoring access, won unanimous equipment grant support, coordinated a twelve-crate food-bank collection—while also maintaining inst

#### G0 twin-null — default
Null band: [0.18, 0.48].

| cell | a | b | c |
| --- | --- | --- | --- |
| pooled | {'a': 6}; a 100% [61%–100%]; b 0% [0%–39%]; c 0% [0%–39%] | {'b': 4, 'a': 2}; a 33% [10%–70%]; b 67% [30%–90%]; c 0% [0%–39%] | {'c': 4, 'a': 1, 'b': 1}; a 17% [3%–56%]; b 17% [3%–56%]; c 67% [30%–90%] |
| jordan | {'a': 5, 'b': 1}; a 83% [44%–97%]; b 17% [3%–56%]; c 0% [0%–39%] | {'b': 5, 'a': 1}; a 17% [3%–56%]; b 83% [44%–97%]; c 0% [0%–39%] | {'c': 5, 'a': 1}; a 17% [3%–56%]; b 0% [0%–39%]; c 83% [44%–97%] |
| casey | {'a': 5, 'c': 1}; a 83% [44%–97%]; b 0% [0%–39%]; c 17% [3%–56%] | {'a': 1, 'b': 5}; a 17% [3%–56%]; b 83% [44%–97%]; c 0% [0%–39%] | {'c': 6}; a 0% [0%–39%]; b 0% [0%–39%]; c 100% [61%–100%] |
| riley | {'a': 6}; a 100% [61%–100%]; b 0% [0%–39%]; c 0% [0%–39%] | {'b': 6}; a 0% [0%–39%]; b 100% [61%–100%]; c 0% [0%–39%] | {'c': 6}; a 0% [0%–39%]; b 0% [0%–39%]; c 100% [61%–100%] |
| morgan | {'a': 5, 'b': 1}; a 83% [44%–97%]; b 17% [3%–56%]; c 0% [0%–39%] | {'b': 5, 'c': 1}; a 0% [0%–39%]; b 83% [44%–97%]; c 17% [3%–56%] | {'a': 2, 'c': 3, 'b': 1}; a 33% [10%–70%]; b 17% [3%–56%]; c 50% [19%–81%] |

Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.
order dependence: none

## Notes for non-survivors

- **hiddenbench-baker-2010** — failing gate: G2; naive `pooled` counts: `{'roberts': 5, 'stevens': 1}` with Wilson CI `None`.
  - Counts: `{'roberts': 5, 'stevens': 1}`; Wilson CI: `None`; first-listed split: stevens: {'roberts': 2} (0% [0%–66%]); roberts: {'roberts': 1, 'stevens': 1} (0% [0%–66%]); jones: {'roberts': 2} (0% [0%–66%])
  - Reason excerpts: Roberts combines proven higher education leadership with successful fundraising experience, demonstrated commitment to diversity and faculty development, collaborative leadership style, and community  | Roberts combines substantial fundraising success, proven academic leadership with collaborative decision-making and faculty development, and demonstrated commitment to diversity and community service,

- **hiddenbench-critical-hospital-transfer** — failing gate: G1/G2; naive `p2` counts: `{'hospital-a': 4, 'hospital-c': 2}` with Wilson CI `[0.09676933255921683, 0.7000116786584712]`.
  - Counts: `{'hospital-a': 4, 'hospital-c': 2}`; Wilson CI: `[0.09676933255921683, 0.7000116786584712]`; first-listed split: hospital-a: {'hospital-a': 1, 'hospital-c': 1} (50% [9%–91%]); hospital-b: {'hospital-a': 2} (0% [0%–66%]); hospital-c: {'hospital-c': 1, 'hospital-a': 1} (50% [9%–91%])
  - Reason excerpts: Hospital B is blocked by landslide, and while Hospital A has staffing risks at night, its reputation and accessibility via the northern route (despite rain hazards) make it more viable than Hospital C | Hospital B is completely blocked by landslide for 24+ hours, and Hospital C has a history of equipment failures; Hospital A, despite smaller size and potential mountain pass hazard, remains the most v

- **hiddenbench-evacuation-west-city** — failing gate: G1/G2; naive `pooled` counts: `{'east-town': 4, 'west-city': 2}` with Wilson CI `[0.09676933255921683, 0.7000116786584712]`.
  - Counts: `{'east-town': 4, 'west-city': 2}`; Wilson CI: `[0.09676933255921683, 0.7000116786584712]`; first-listed split: west-city: {'east-town': 2} (0% [0%–66%]); east-town: {'west-city': 1, 'east-town': 1} (50% [9%–91%]); north-hill: {'west-city': 1, 'east-town': 1} (50% [9%–91%])
  - Reason excerpts: West City's bridge is passable but the area faces fire blockage and medical supply shortages, North Hill's driveway is completely blocked by mudslide, while East Town's tunnel is problematic but the m | West City has the bridge still passable, hotels with food and accommodations ready, while East Town's tunnel is blocked by the supply truck and North Hill's driveway is blocked by a mudslide.

- **hiddenbench-graetz-et-al-1998** — failing gate: G2; naive `pooled` counts: `{'cape-industries': 4, 'starlight-incorporated': 2}` with Wilson CI `None`.
  - Counts: `{'cape-industries': 4, 'starlight-incorporated': 2}`; Wilson CI: `None`; first-listed split: franklin-enterprises: {'cape-industries': 2} (0% [0%–66%]); starlight-incorporated: {'cape-industries': 2} (0% [0%–66%]); cape-industries: {'starlight-incorporated': 2} (0% [0%–66%])
  - Reason excerpts: Cape Industries meets the most critical criteria (a, c, d, e, i, j) including key vehicle and computer performance requirements, while Franklin fails on vehicle specs (a, b, c) and Starlight lacks veh | Cape Industries meets the most critical criteria (b, c, d, e, i, j) with only cost (h) and computer weight (f) as confirmed failures, while Franklin fails on vehicle requirements (a, b, c) and Starlig

- **hiddenbench-schulz-hardt-mojzisch-2012** — failing gate: G2; naive `pooled` counts: `{'candidate-b': 3, 'candidate-a': 5}` with Wilson CI `None`.
  - Counts: `{'candidate-b': 3, 'candidate-a': 5}`; Wilson CI: `None`; first-listed split: candidate-a: {'candidate-b': 2} (0% [0%–66%]); candidate-b: {'candidate-a': 1, 'candidate-b': 1} (0% [0%–66%]); candidate-c: {'candidate-a': 2} (0% [0%–66%]); candidate-d: {'candidate-a': 2} (0% [0%–66%])
  - Reason excerpts: Candidate B demonstrates critical pilot competencies including exceptional crisis management, reliability, weather assessment expertise, and technical proficiency—essential for long-distance flight sa | Candidate A's ability to anticipate dangerous situations, see complex connections, and excellent spatial vision are critical for long-distance flight safety, despite personality weaknesses that are le

- **hiddenbench-stasser-stewart-1992** — failing gate: G1/G2; naive `pooled` counts: `{'billy-prentice': 3, 'eddie-sullivan': 2, 'mickey-malone': 1}` with Wilson CI `[0.09676933255921683, 0.7000116786584712]`.
  - Counts: `{'billy-prentice': 3, 'eddie-sullivan': 2, 'mickey-malone': 1}`; Wilson CI: `[0.09676933255921683, 0.7000116786584712]`; first-listed split: eddie-sullivan: {'billy-prentice': 2} (0% [0%–66%]); billy-prentice: {'billy-prentice': 1, 'eddie-sullivan': 1} (50% [9%–91%]); mickey-malone: {'eddie-sullivan': 1, 'mickey-malone': 1} (50% [9%–91%])
  - Reason excerpts: Billy had financial motive (borrowed money, needed funds), opportunity (his car left at 7:00 AM per Eddie), access to the crowbar (admitted touching it with his fingerprints found on handle), and the  | Billy had financial motive (borrowed money, needed funds), physical evidence connects him (partial fingerprints on crowbar, admitted touching it, car seen leaving at 7:00 AM coinciding with death wind

- **hiddenbench-the-lead-investor-decision** — failing gate: G1/G2; naive `p2` counts: `{'skylake-ventures': 4, 'peak-capital': 2}` with Wilson CI `[0.09676933255921683, 0.7000116786584712]`.
  - Counts: `{'skylake-ventures': 4, 'peak-capital': 2}`; Wilson CI: `[0.09676933255921683, 0.7000116786584712]`; first-listed split: peak-capital: {'skylake-ventures': 2} (0% [0%–66%]); skylake-ventures: {'peak-capital': 2} (100% [34%–100%]); northstar-partners: {'skylake-ventures': 2} (0% [0%–66%])
  - Reason excerpts: Skylake Ventures has just secured a co-investor partnership yesterday, removing their typical blocking requirement and enabling them to commit funds reliably, while Peak Capital's 3-day timeline is ti | Peak Capital can reliably close within 3 days, eliminating timing risk, while Skylake needs a co-investor (now available but adds complexity) and Northstar has a track record of late legal pullouts th

- **hiddenbench-toma-butera-2009** — failing gate: G1/G2; naive `p1` counts: `{'mr-x-s-son': 4, 'mr-x': 4}` with Wilson CI `[0.21521252682444186, 0.7847874731755582]`.
  - Counts: `{'mr-x-s-son': 4, 'mr-x': 4}`; Wilson CI: `[0.21521252682444186, 0.7847874731755582]`; first-listed split: mr-x: {'mr-x-s-son': 2} (0% [0%–66%]); mr-x-s-son: {'mr-x': 2} (100% [34%–100%]); mrs-y: {'mr-x': 2} (100% [34%–100%]); mr-z: {'mr-x-s-son': 2} (0% [0%–66%])
  - Reason excerpts: The notes directly state the guilty person was driving a car with 1.5 alcohol level and admits inattention at collision, which matches Mr. X's son who was in the first car with his intoxicated father. | Mr. X had consumed several glasses of spirits before driving at night on a poorly lit road, making impaired driving the most serious and clear causative factor in the accident.

- **hiring-adversarial-v1** — failing gate: G1/G2; naive `grace` counts: `{'sally': 8}` with Wilson CI `[0.0, 0.3244156195108769]`.
  - Counts: `{'sally': 8}`; Wilson CI: `[0.0, 0.3244156195108769]`; first-listed split: john: {'sally': 4} (0% [0%–49%]); sally: {'sally': 4} (0% [0%–49%])
  - Reason excerpts: Sally's methodical debugging skills, architectural thinking (ledger migration), and humble learning orientation outweigh her Go gap; John's team exodus and closing-only compensation focus raise retent | Sally demonstrated exceptional technical depth under pressure (race condition diagnosis in 18 minutes, zero-downtime 2B-row migration) and shows genuine investment in her craft through open-source wor

- **hiring-panel-3** — failing gate: G1/G2; naive `dana` counts: `{'sally': 7, 'john': 1}` with Wilson CI `[0.02241690886329617, 0.4708948057698615]`.
  - Counts: `{'sally': 7, 'john': 1}`; Wilson CI: `[0.02241690886329617, 0.4708948057698615]`; first-listed split: john: {'sally': 3, 'john': 1} (25% [5%–70%]); sally: {'sally': 4} (0% [0%–49%])
  - Reason excerpts: Sally demonstrated domain-specific payments expertise (idempotency keys, double-spend), meticulous work quality, and genuine engagement with the role (on-call questions), whereas John shows team reten | Sally demonstrates genuine payment systems thinking (idempotency keys unprompted), ownership mindset (post-mortem template adoption, open-source maintenance), and realistic learning curve assessment,

- **hiring-panel-7** — failing gate: G1/G2; naive `dana` counts: `{'john': 5, 'sally': 3}` with Wilson CI `[0.30573785458380187, 0.863158240538479]`.
  - Counts: `{'john': 5, 'sally': 3}`; Wilson CI: `[0.30573785458380187, 0.863158240538479]`; first-listed split: john: {'john': 3, 'sally': 1} (75% [30%–95%]); sally: {'sally': 2, 'john': 2} (50% [15%–85%])
  - Reason excerpts: Eight years of direct Go and payments domain experience with demonstrated execution speed outweighs Sally's stronger design thinking, given the role requires immediate productivity on a payments team. | Sally demonstrates deeper technical problem-solving (idempotency unprompted, infrastructure optimization, open-source contributions) and genuine engagement with payments domain challenges, while John'

- **hiring-panel-9** — failing gate: G1/G2; naive `dana` counts: `{'sally': 2, 'john': 6}` with Wilson CI `[0.40926987910258916, 0.9285223111419724]`.
  - Counts: `{'sally': 2, 'john': 6}`; Wilson CI: `[0.40926987910258916, 0.9285223111419724]`; first-listed split: john: {'sally': 2, 'john': 2} (50% [15%–85%]); sally: {'john': 4} (100% [51%–100%])
  - Reason excerpts: Sally demonstrated direct payments domain expertise unprompted with idempotency keys and showed stronger engineering judgment through her open-source work and org-wide impact, whereas John's closing q | Eight years of direct Go experience, current payments domain expertise, and team lead credentials outweigh Sally's stronger problem-solving signals, though her payments knowledge gap and lack of Go ex

- **hiring-panel-flat** — failing gate: G1/G2; naive `pooled` counts: `{'sally': 4, 'john': 4}` with Wilson CI `[0.21521252682444186, 0.7847874731755582]`.
  - Counts: `{'sally': 4, 'john': 4}`; Wilson CI: `[0.21521252682444186, 0.7847874731755582]`; first-listed split: john: {'sally': 2, 'john': 2} (50% [15%–85%]); sally: {'sally': 2, 'john': 2} (50% [15%–85%])
  - Reason excerpts: Sally demonstrates stronger judgment and thoroughness (organized thinking, debugging success, incident involvement, mentoring) despite lacking Go experience, while John shows concerning patterns (rush | Sally demonstrates stronger foundational qualities for a senior role—proactive ownership (migration tool adoption, runbook contributions, incident reviews), proven mentorship impact, and careful delib

- **hiring-panel-flat-v2** — failing gate: G1/G2; naive `marcus` counts: `{'john': 3, 'sally': 5}` with Wilson CI `[0.13684175946152105, 0.6942621454161981]`.
  - Counts: `{'john': 3, 'sally': 5}`; Wilson CI: `[0.13684175946152105, 0.6942621454161981]`; first-listed split: john: {'john': 2, 'sally': 2} (50% [15%–85%]); sally: {'sally': 3, 'john': 1} (25% [5%–70%])
  - Reason excerpts: Eight years of Go experience in payments domain with proven team leadership outweighs Sally's stronger engineering practices, given the role's seniority requirement and payments context, despite conce | Sally demonstrates domain-relevant operational excellence (runbook authorship, sub-10-minute incident response) and genuine technical depth (open-source adoption), whereas John's take-home omissions,

- **hiring-panel-null** — failing gate: G2; naive `pooled` counts: `{'john': 1, 'sally': 7}` with Wilson CI `None`.
  - Counts: `{'john': 1, 'sally': 7}`; Wilson CI: `None`; first-listed split: john: {'john': 1, 'sally': 3} (0% [0%–49%]); sally: {'sally': 4} (0% [0%–49%])
  - Reason excerpts: John demonstrates slightly stronger technical leadership through his incident review facilitation, runbook authorship, and proactive ownership patterns, though both candidates are remarkably similar w | Sally demonstrates stronger leadership maturity through running incident reviews, owning unpopular services, and mentoring—evidenced by a mentee's promotion—while both candidates show similar technica

- **hiring-panel-v1** — failing gate: G1/G2; naive `dana` counts: `{'sally': 7, 'john': 1}` with Wilson CI `[0.02241690886329617, 0.4708948057698615]`.
  - Counts: `{'sally': 7, 'john': 1}`; Wilson CI: `[0.02241690886329617, 0.4708948057698615]`; first-listed split: john: {'sally': 4} (0% [0%–49%]); sally: {'sally': 3, 'john': 1} (25% [5%–70%])
  - Reason excerpts: Sally demonstrates deeper payments domain expertise (2B-row ledger migration, idempotency keys), while John's outage ownership and closing focus on compensation raise concerns about accountability and | Sally demonstrates genuine payments domain expertise through unprompted idempotency discussion and proven large-scale ledger work, while John's post-mortem discrepancy and incomplete take-home documen

- **hiring-weak-profile-v1** — failing gate: G1/G2; naive `lena` counts: `{'sally': 8}` with Wilson CI `[0.0, 0.3244156195108769]`.
  - Counts: `{'sally': 8}`; Wilson CI: `[0.0, 0.3244156195108769]`; first-listed split: john: {'sally': 4} (0% [0%–49%]); sally: {'sally': 4} (0% [0%–49%])
  - Reason excerpts: While John has stronger domain experience and technical depth, the exit interview feedback about team retention and his focus on compensation over role substance concern me for a senior position requi | Sally demonstrates genuine technical depth, thoughtful problem-solving (pausing to reconsider), and collaborative communication style, while John shows concerning people management patterns with three

- **incident-review-v1** — failing gate: G1/G2; naive `lena` counts: `{'deploy': 2, 'pool': 6}` with Wilson CI `[0.07147768885802763, 0.5907301208974108]`.
  - Counts: `{'deploy': 2, 'pool': 6}`; Wilson CI: `[0.07147768885802763, 0.5907301208974108]`; first-listed split: deploy: {'deploy': 1, 'pool': 3} (25% [5%–70%]); pool: {'pool': 3, 'deploy': 1} (25% [5%–70%])
  - Reason excerpts: The deploy changed database connection-settings, correlates perfectly with error timing at 40% rollout, affected multiple services, and passed staging—indicating a configuration interaction issue rath | The ledger connection pool reached its configured maximum with positive pool-wait-queue depth during the incident, and latency rose correlating with saturation—this is a clear resource exhaustion patt

- **stasser-1985-shared** — failing gate: G1/G2; naive `jordan` counts: `{'a': 5, 'b': 1}` with Wilson CI `[0.03005258587173032, 0.563509436563646]`.
  - Counts: `{'a': 5, 'b': 1}`; Wilson CI: `[0.03005258587173032, 0.563509436563646]`; first-listed split: a: {'a': 2} (0% [0%–66%]); b: {'b': 1, 'a': 1} (50% [9%–91%]); c: {'a': 2} (0% [0%–66%])
  - Reason excerpts: Candidate A demonstrates concrete policy wins (library hours, mental-health center, voter registration) and coalition-building despite some process lapses, while B has incomplete work and dismissive b | Candidate B demonstrates the most concrete policy achievements directly relevant to student needs—expanded tutoring access, successful grant coordination, and policy transparency through newsletters—w

- **stasser-1992-judge** — failing gate: G1/G2; naive `detective-2` counts: `{'billy': 3, 'eddie': 3}` with Wilson CI `[0.18761280689940868, 0.8123871931005913]`.
  - Counts: `{'billy': 3, 'eddie': 3}`; Wilson CI: `[0.18761280689940868, 0.8123871931005913]`; first-listed split: eddie: {'billy': 2} (100% [34%–100%]); billy: {'eddie': 2} (0% [0%–66%]); mickey: {'eddie': 1, 'billy': 1} (50% [9%–91%])
  - Reason excerpts: Billy's truck was placed near the riverside warehouse that night, his fingerprint was on the office telephone, and he had documented conflict with the victim over an unpaid invoice—combining means, op | Eddie's glove carries the victim's machine-oil residue placing him in direct physical contact with the victim, and despite his alibi, the victim's watch stopped at 10:40 near the riverside warehouse w

- **stasser-1992-solve** — failing gate: G1/G2; naive `detective-1` counts: `{'billy': 2, 'mickey': 2, 'eddie': 2}` with Wilson CI `[0.29998832134152864, 0.9032306674407831]`.
  - Counts: `{'billy': 2, 'mickey': 2, 'eddie': 2}`; Wilson CI: `[0.29998832134152864, 0.9032306674407831]`; first-listed split: eddie: {'billy': 1, 'mickey': 1} (100% [34%–100%]); billy: {'mickey': 1, 'eddie': 1} (50% [9%–91%]); mickey: {'billy': 1, 'eddie': 1} (50% [9%–91%])
  - Reason excerpts: Billy's fingerprint on the warehouse telephone, his truck near the riverside that night, his known dispute with the victim, and the neighbor's report of a vehicle leaving before rain all place him at  | Mickey's connection to the victim's arranged meeting about the disputed invoice, combined with the diner receipt found in the victim's coat and the torn envelope at the phone, establishes both motive

- **vendor-selection-v1** — failing gate: G1/G2; naive `vera` counts: `{'northwind': 6, 'contoso': 2}` with Wilson CI `[0.40926987910258916, 0.9285223111419724]`.
  - Counts: `{'northwind': 6, 'contoso': 2}`; Wilson CI: `[0.40926987910258916, 0.9285223111419724]`; first-listed split: northwind: {'northwind': 4} (100% [51%–100%]); contoso: {'contoso': 2, 'northwind': 2} (50% [15%–85%])
  - Reason excerpts: Northwind's 18% cost savings, faster onboarding, superior UI usability, and willingness to pilot at no cost align with our deadline to close this quarter, despite concerns about SOC 2 coverage depth a | Despite higher cost and longer onboarding, Contoso's proven eleven-year track record, superior uptime SLA, price lock, and two recent customer migrations from Northwind give us better contract securit

## Known issue: HiddenBench converter mis-tags items

backend/app/scenarios/papers/hiddenbench.py infers each fact's candidate/valence via `_mentions(text, answers)` against the full answer strings (e.g. 'Option B: AI hardware startup'), so facts that refer to a candidate by short alias ('Option B has a stable revenue base…') are tagged to the wrong candidate (here option-c-logistics-software-company) or dropped. Consequences: the static arithmetic table for hiddenbench-* is unreliable (two scenarios that 'fail' statically pass G1/G2 with Haiku), and the frontend's designed-verdict panels for these scenarios are wrong. Not fixed in this PR per user decision; fix = alias-aware matching (full name, colon-prefix, id; longest-first, word-boundary) as implemented for twin_null in scripts/probe_lib.py, then re-derive candidate/valence and re-run the static check.

## Appendix: static arithmetic table

```text
S5 static arithmetic check (no API), all 24 SAMPLE_SCENARIOS, 2026-09-14
correct = truth.pooled_verdict; shared_v = truth.shared_only_verdict; alone = truth.verdict(agent hand)
STATIC PASS := correct decided AND shared_v != correct AND every agent alone -> a decided candidate != correct

scenario                          k items agents correct   pooled_margin shared_v   alone (per agent)                      STATIC
hiring-panel-v1                   2 39    5      sally     4             john       john x5 (margins 7,6,9,9,9)             PASS
hiring-panel-3                    2 39    3      sally     4             john       john x3 (7,7,4)                         PASS
hiring-panel-7                    2 39    7      sally     4             john       john x7 (10,8,9,8,7,10,10)              PASS
hiring-panel-9                    2 39    9      sally     4             john       john x9 (9,8,7,10,10,10,10,11,9)        PASS
incident-review-v1                2 41    5      pool      4             deploy     deploy x5 (8,10,9,7,10)                 PASS
vendor-selection-v1               2 41    5      contoso   4             northwind  northwind x5 (7,8,9,9,11)               PASS
hiring-weak-profile-v1            2 23    5      sally     2             john       john x5 (5,5,6,6,8)                     PASS
hiring-adversarial-v1             2 39    5      sally     4             john       john x5 (14,5,6,7,8)                    PASS
hiring-panel-flat                 2 37    5      sally     3             john       john x5 (6,6,5,5,7)                     PASS
hiring-panel-flat-v2              2 39    5      sally     11            john       john x5 (4,4,4,4,5)                     PASS
hiring-panel-null                 2 64    5      undecided -             undecided  undecided x5 (0 margins)                FAIL (control by design)
stasser-1985-hidden               3 48    4      a         4             b          b x4 (5,5,5,5)                          PASS
stasser-1985-shared               3 48    4      a         4             a          a x4 (0)                                FAIL (shared-profile control by design)
stasser-1992-solve                3 24    3      eddie     1             billy      billy x3 (2,2,3)                        PASS
stasser-1992-judge                3 24    3      eddie     1             billy      billy x3 (2,2,3)                        PASS
hiddenbench-evacuation-west-city  3 8     4      west-city 4             west-city  west-city x4 (0)                        FAIL (alone already correct)
hiddenbench-toma-butera-2009      4 6     3      mr-x-s-son 2            undecided  undecided x3 (all 1-1-1-1)              FAIL (alone tied, not wrong)
hiddenbench-baker-2010            3 10    4      undecided -             undecided  undecided x4 (roberts=jones=2)          FAIL (pooled tie)
hiddenbench-schulz-hardt-mojzisch-2012 4 7 3    undecided -             undecided  undecided x3                            FAIL (pooled tie)
hiddenbench-graetz-et-al-1998     3 7     4      undecided -             undecided  undecided x4                            FAIL (pooled tie)
hiddenbench-stasser-stewart-1992  3 11    3      eddie-sullivan 2        eddie-sullivan eddie x3 (0)                        FAIL (alone already correct)
hiddenbench-critical-hospital-transfer 3 7 4    hospital-a 3            hospital-a hospital-a x4 (0)                       FAIL (alone already correct)
hiddenbench-laboratory-theft-deduction 3 7 4    lab-gamma 2             lab-alpha  undecided,lab-alpha,undecided,undecided FAIL (3/4 alone tied)
hiddenbench-the-lead-investor-decision 3 6 3    skylake-ventures 1      undecided  undecided x3                            FAIL (alone tied)
hiddenbench-company-acquisition-decision 3 8 4  option-c 8              option-c   option-c x4 (0)                         FAIL (alone already correct)

Per-agent hand scores (alone margin = top score - correct's score):
hiring-panel-v1: dana {john 6, sally -1}; marcus {5,-1}; priya {5,-4}; tom {4,-5}; omar {4,-5}
hiring-panel-3: dana {7,0}; marcus {2,-5}; priya {3,-1}
hiring-panel-7: dana {7,-3}; marcus {3,-5}; priya {4,-5}; tom {5,-3}; omar {4,-3}; nadia {6,-4}; eli {7,-3}
hiring-panel-9: dana {6,-3}; marcus {3,-5}; priya {4,-3}; tom {6,-4}; omar {5,-5}; nadia {7,-3}; eli {7,-3}; grace {6,-5}; lena {4,-5}
incident-review-v1: kai {deploy 4, pool -4}; lena {4,-6}; jules {5,-4}; mei {5,-2}; ravi {5,-5}
vendor-selection-v1: vera {northwind 3, contoso -4}; noah {5,-3}; ingrid {5,-4}; sofia {5,-4}; hugo {5,-6}
hiring-weak-profile-v1: lena {john 2, sally -3}; kai {5,0}; ines {3,-3}; felix {5,-1}; theo {5,-3}
hiring-adversarial-v1: victor {john 8, sally -6}; grace {4,-1}; ravi {5,-1}; mei {4,-3}; nadia {3,-5}
hiring-panel-flat: dana {5,-1}; marcus {5,-1}; priya {4,-1}; tom {4,-1}; omar {3,-4}
hiring-panel-flat-v2: dana {4,0}; marcus {4,0}; priya {4,0}; tom {4,0}; omar {4,-1}
stasser-1985-hidden: every agent {a -2, b 3, c 0}
stasser-1985-shared: every agent {a 4, b 0, c 0}
stasser-1992-solve/judge: det-1 {eddie 0, billy 2, mickey 1}; det-2 same; det-3 {0,3,0}
hiddenbench-evacuation-west-city: p1 {wc 2, et 0, nh 1}; p2 {3,1,1}; p3 {3,1,1}; p4 {2,1,0}
hiddenbench-toma-butera-2009: every agent {1,1,1,1}
hiddenbench-baker-2010: every agent {stevens 1, roberts 2, jones 2}
hiddenbench-schulz-hardt-mojzisch-2012: every agent {a 0, b 1, c 1, d 1}
hiddenbench-graetz-et-al-1998: every agent {franklin 0, starlight 1, cape 1}
hiddenbench-stasser-stewart-1992: every agent {eddie 5, billy -1, mickey 3}
hiddenbench-critical-hospital-transfer: every agent {a 3, b -1, c 0}
hiddenbench-laboratory-theft-deduction: p1 {alpha 1, beta 0, gamma 1}; p2 {2,-1,1}; p3 {2,0,2}; p4 {1,0,1}
hiddenbench-the-lead-investor-decision: p1 {peak 0, skylake 1, northstar 1}; p2 {1,1,0}; p3 {1,1,0}
hiddenbench-company-acquisition-decision: every agent {a 0, b 0, c 5}
```
