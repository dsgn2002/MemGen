# Independent source inspection — Sai Kung sample

This is an AI agent's visual review, not human ground truth or an identity check.
The reviewer received the complete 32-frame adaptive candidate sheet and original
JPGs, with the two requests, before seeing live Qwen conclusions.

Source SHA-256: `efc60dc3aad3e4522fa5afce8e98d9974d9e456264a52cc256775a27c945c687`.
Duration: 247.408617 seconds; original resolution: 1280×720.

## Boat request

- `frame-0029` shows three people on a moving covered boat, but the rear person
  appears to operate it. Three visible people does not establish three companions.
- `frame-0007` shows boarding/boat context and two visible people;
  `frame-0006` shows two people at a pier. Neither supports three together aboard.
- `frame-0000` has three people on a street. Their count and outfits cannot
  support the boat relationship.
- `frame-0022` has four people outdoors and `frame-0025` has a group at a meal.
  These may provide appearance context but do not establish who shared a boat.
- No coarse candidate unambiguously establishes three companions aboard.
  Identity and personal relationships remain unverified.
- Sunset remains a creative request, not an observed source fact.

## Hiking request

- `frame-0010`: strong combined view of people walking, boardwalk, exposed
  rock and adjacent water.
- `frame-0011`: close hiker/trail detail; coastline partly obscured.
- `frame-0012` / `frame-0013`: complementary rocky coast/bay and visible person.
- `frame-0009`: wide dam/water/rock setting; people too small for outfit detail.
- `frame-0015` / `frame-0016`: useful hiking context, without clear coast.

## Exclusions

Definite farm content: `frame-0017`, `frame-0018`, `frame-0019`, `frame-0030`.
`frame-0024` has uncertain managed rural plots. Covered, open-sided piers and
boats are not automatically indoor scenes. Market tanks (`frame-0005`) have
uncertain enclosure; the food close-up (`frame-0023`) lacks setting evidence.

The primary agent separately inspected an existing historical demo reference
showing the requested three-person boat group in a short shot. That reference
and its timestamp were not supplied to the selector. Coarse sampling can miss
brief events; the live refinement and final selections must be evaluated on
their actual results.

## Original-resolution correction

The independent reviewer initially counted two walkers in frame-0010 and the
refined frame-0035. Original-resolution crops show a third, heavily occluded
walker. The count was corrected; uncertain identity and partly hidden outfits
remain valid limitations. Contact-sheet thumbnails alone are insufficient for
final count/appearance judgments.

## v6 independent source audit

A separate coding agent reviewed the completed v6 boat exports. Both adaptive
and uniform briefs contain **zero positive requirement-support claims**; the two
requested companion/outfit requirements remain unresolved. Strict review of raw
Qwen self-checks flagged 3 unsupported positive judgments for adaptive and 5 for
uniform. These counts are AI review judgments, not human ground truth.

The uniform export also contains one incorrect descriptive count: frame-0030 at
235.8113 s says four people, while source inspection finds five visible people.
This error is in the proposed observation text, not a supported requirement. It
is retained and explicitly reported; the release does not claim perfect visual
counting. The worker-role guard only helps when the model names the role; v6
omitted the driver role, so the intent-ambiguity guard prevented those claims.

## v7 hiking findings and corrected v8 exports

The fresh adaptive run proposes boardwalk hiking (84.3438 s), a cliffside view
(95.5897 s), and a mangrove path (190.6 s). These differ from the boat selections.
Its model-assessed coverage is 3/3, but both place requirements include the
qualifier “in Sai Kung,” which the original frames do not establish. The
192.0-second reference visibly has a “Welcome to Lai Chi Wo” sign. The request's
location wording is not source evidence; the model's positive geographic claims
must not be accepted without independent verification. Generic hiking/coast
content and the exact named place are separate questions.

The adaptive selection also has one near-duplicate reference pair by the
configured dHash threshold. The uniform result has two moments (96.644 s and
228.0798 s), two references, and no near-duplicate pair. Raw v7 source checks
contain 14 unsupported adaptive location-qualified links and 3 uniform links.

The corrected v8 exporter leaves all place requirements uncertain, including
generic settings, and retains the original model judgments and brief. No new
inference was used for this deterministic export correction. Both final briefs
have zero unsupported positive requirement claims in the independent AI audit.
The supported requirement is the visible hiker; original-resolution inspection
also confirms the adaptive three-walker counts, including the obscured person.

One separate uniform descriptive overclaim remains: the 96.644-second frame is
described as “Coastal cliff overlooking water.” The image shows a cliff and water
with a MacLehose Trail overlay; it does not establish that the water is coastal
and appears consistent with reservoir context. This description is retained as
a review issue, not promoted to verified place support. The 228.0798-second
reference supports the visible hiker and backpack description.

See [the independent record](INDEPENDENT_CHECK.md) for exact validation checks,
source hashes, artifact paths, and inference correction counts. These judgments
remain AI source review, not human ground truth.
