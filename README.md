# Mobvoi Hotwords Label-Noise Audit

Human-verified label annotations for the **Mobvoi Hotwords** corpus
([OpenSLR SLR87](https://www.openslr.org/87/)), released as supplementary
material for an ICASSP 2027 submission:

> A. Sloin, *"Context-Enriched Heads for Wake-Word Detection"*,
> submitted to ICASSP 2027.

The code accompanying the paper is at
<https://github.com/sloina/wake-word-spotting-context-enriched-heads>.

The audit covers the positive utterances of both wake words --
**kw0 = "Hi Xiaowen"** and **kw1 = "Nihao Wenwen"** -- in the test
partition (complete) and the dev partition (complete), plus the
training-set misses of one of the paper's
decision-head models on kw1.

**No audio is redistributed here.** The original audio is available from
OpenSLR SLR87 under its own license. This repository contains only
utterance-ID lists, label annotations, and the scripts used to produce
them.

Note on paper vs.\ census figures: the paper reports the flagged-stage
audit (167 mislabeled, 13 ultra-hard, 449 very-hard test positives),
which defines the cleaning levels of its Table 2 and is a lower bound.
The full census released here subsequently found additional problematic
utterances beyond the automatically flagged set.

## Files

| File | Description |
|---|---|
| `whisper_flagging.py` | ASR pre-filter. Transcribes every positive test utterance with the faster-whisper implementation of Whisper (base model), prompted with the two wake words, and flags an utterance unless its normalized transcript is short and contains a variant of the expected wake word. A stricter near-match pass flags additional borderline cases. |
| `audit_listen.py` | Interactive single-key listening tool used for the listening rounds. |
| `test_round1_listen_to_autoflagged.csv` | Human verdicts, first listening pass over the Whisper-flagged test utterances. |
| `test_round2_notes_for_no_ok_files.csv` | Second pass, re-examining every utterance not marked ok in the first. |
| `dev_round2_notes_for_no_ok_files.csv` | The corresponding dev-set listening (dev uses four labels, without `hard`). |
| `train_misses_kw1_final.csv` | Final verdicts for the 118 kw1 training-set misses of the V2.5 logistic head, merged from a two-pass listening audit. |
| `full_test_audit_with_round2.csv` | **Complete census of all 21,282 test positives.** Columns: `utt_id, kw, verdict, source, round_2`. `source` is `imported_earlier_rounds` for verdicts carried over from the earlier listening rounds over the automatically flagged utterances (the flagged-stage rounds above), and `ear_round1` for the census listening that covered the rest. `round_2` holds a verification pass over every non-ok census verdict. **The final label of an utterance is `round_2` when present, else `verdict`.** |
| `full_dev_audit_with_round2.csv` | **Complete census of all 7,357 dev positives**, same schema and semantics as the test census file above. In the dev census, `very_hard` and `hard` tags are not exhaustive (see the coverage note below). |

## Labels

| Label | Meaning |
|---|---|
| `bad` | Mislabeled: no, partial, or wrong keyword (including "Hey" instead of "Hi"). |
| `ultra_hard` | Barely detectable by ear even after repeated, attentive listening. |
| `very_hard` | Audible but immersed in substantial noise or severely degraded. |
| `hard` | Detectable despite heavy noise. |
| `ok` | A clean, unambiguous positive. |

These match the definitions in Section 4.3 of the paper.

Coverage note: in the census stage (and in the dev audit), the listening
exhaustively targeted `bad` and `ultra_hard` -- the two categories that
matter for cleaning -- while `very_hard` and `hard` were tagged when
encountered but are not exhaustive there. Within the earlier
flagged-stage rounds, all five labels were assigned throughout.

## Audit protocol (summary)

1. **ASR pre-filtering** (`whisper_flagging.py`) flagged 1,879 of the
   Hi Xiaowen positives (17.7%) and 3,564 of the Nihao Wenwen positives
   (33.5%); a stricter near-match criterion flagged 55 more.
2. **Human listening over the flagged utterances**: two passes
   (`test_round1_*.csv`, `test_round2_*.csv`), plus a dedicated pass that
   settled the hardest material with the `ultra_hard` label. This stage
   marked 167 positives as mislabeled, 13 ultra-hard, and 449 very-hard,
   and defines the cleaning levels of Table 2 in the paper.
3. **Train-miss audit (kw1).** The 118 training-set misses of the V2.5
   logistic head were audited with the same two-pass protocol
   (`train_misses_kw1_final.csv` holds the merged final verdicts).
4. **Full census.** Every remaining test positive was then listened to,
   completing coverage of all 21,282 positives
   (`full_test_audit_with_round2.csv`). This stage focused on catching
   residual `bad` and `ultra_hard` recordings (see the coverage note
   above).
5. **Verification pass.** Every non-ok census verdict was re-examined
   (`round_2` column). Borderline "Hey"/"Hi" productions were ruled as
   the intended keyword unless clearly a different word.
6. **Dev set**: the same automatic flagging and the listening passes over
   the flagged utterances were applied to the dev partition
   (`dev_round2_notes_for_no_ok_files.csv`), followed by a full listening
   census of the dev positives matching steps 4-5
   (`full_dev_audit_with_round2.csv`).

## Citation

If you use these annotations, please cite:

```
A. Sloin, "Context-Enriched Heads for Wake-Word Detection,"
submitted to ICASSP 2027.
```

Author: Alba Sloin, Independent Researcher --
[ORCID 0009-0009-5953-1459](https://orcid.org/0009-0009-5953-1459).
A full citation will be added after the review process.

## License

- **Code** (`*.py`): MIT License (see `LICENSE`).
- **Annotations** (`*.csv`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The **audio and original metadata** of Mobvoi Hotwords are *not*
  included and remain subject to the OpenSLR SLR87 license terms.
