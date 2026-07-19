# Demo profiles

Real *Klebsiella pneumoniae* isolates from the quarantined holdout. None were used
in training, and none appear in the caseload the application ships with — uploading
one runs the model on data it has genuinely never seen.

Determinants are in raw AMRFinderPlus notation, so the upload path performs the same
normalisation a real laboratory submission would.

| file | source isolate | determinants | mutations |
|---|---|---|---|
| `treatable-isolate.json` | GCA_031013725.2 | 6 | 0 |
| `carbapenemase-mutations.json` | GCA_003069525.1 | 28 | 3 |
| `mutations-no-carbapenemase.json` | GCA_001874695.1 | 24 | 3 |
| `unfamiliar-machinery.json` | GCA_049383465.1 | 7 | 3 |
| `rich-profile.json` | GCA_001709275.1 | 28 | 3 |
