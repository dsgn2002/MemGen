"""CPU tests use explicit test doubles; production CLIs have no mock mode."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from memgen_skills.common import asset_path, command, fresh_run, read_json, schema, sha256
from memgen_skills.evidence import (eligible, export_brief, inspect, requirement_report,
                                   run_selection, select, validate_brief, verify_selected, recheck_run, role_guard_ids)
from memgen_skills.intent import ambiguous_requirement_ids, understand, validate_intent
from memgen_skills.model import json_reply
from memgen_skills.video import (candidate_times, discover_shots, extract_frames, probe,
                                uniform_times)


REQUEST = "Highlight three companions together on the boat. Add a golden sunset. Avoid the farm."


class ReplyModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    def generate(self, prompt, images, max_tokens):
        self.calls += 1
        reply = next(self.replies)
        if isinstance(reply, dict) and "checks" in reply:
            reply = copy.deepcopy(reply)
            reply["checks"] = [[i, j, {"supported": "visible", "absent": "not_visible"}.get(status, status), reason]
                               for i, j, status, reason in reply["checks"]]
            reply["views"] = [[i, 3, "Three synthetic figures", "Synthetic boat setting", "group", ["Test outfits"]]
                              for i in range(len(images))]
        return reply if isinstance(reply, str) else json.dumps(reply)

    def metadata(self):
        return {"provider": "explicit_test_double", "calls": self.calls}


def intent_reply():
    return {"requirements": [
        {"kind": "relationship", "description": "Three companions together on a boat", "priority": 3,
         "source_quote": "Highlight three companions together on the boat."},
        {"kind": "creative_change", "description": "Golden sunset lighting", "priority": 1,
         "source_quote": "Add a golden sunset."},
        {"kind": "exclusion", "description": "Farm", "priority": 3, "source_quote": "Avoid the farm."}],
        "ambiguities": [], "moment_count": 3}


def frame(identifier, timestamp, support=(), uncertain=(), fingerprint="1111111111111111", shot=None):
    return {"id": identifier, "timestamp_s": timestamp, "image": f"assets/{identifier}.jpg", "sha256": "0" * 64,
            "shot_range_s": shot or [timestamp - .2, timestamp + .2],
            "quality": {"sharpness": 200, "brightness": .5, "dark_fraction": 0, "bright_fraction": 0, "dhash": fingerprint},
            "observation": {"frame_id": identifier, "summary": "Synthetic test observation", "people": "Three visible people",
                            "people_count": 3, "setting": "Test setting", "view_role": "group",
                            "supported_requirements": list(support), "uncertain_requirements": list(uncertain),
                            "visible_details": ["Test detail"], "uncertainties": []}}


class SkillsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.intent = understand(ReplyModel([intent_reply()]), REQUEST, fresh_run(self.root / "intent"))

    def tearDown(self):
        self.temp.cleanup()

    def test_frame_detail_scalar_preserved_as_one_phrase(self):
        reply = {"frames": [[0, 1, "detail", [], [], "Person", "Room", "Book cover"]]}
        observed = inspect(ReplyModel([reply]), [frame("a", 1)], self.intent, self.root)
        self.assertEqual(observed[0]["observation"]["visible_details"], ["Book cover"])
        self.assertEqual(observed[0]["observation"]["supported_requirements"], [])

    def test_correction_reports_exact_field_and_keeps_strict_ids(self):
        bad = {"frames": [[0, 1, "detail", [999], [], "Person", "Room", "Book cover"]]}
        with self.assertRaisesRegex(ValueError, "after one correction"):
            inspect(ReplyModel([bad, bad]), [frame("a", 1)], self.intent, self.root)
        prompt = (self.root / "analysis/coarse-000/attempt-2.prompt.txt").read_text()
        self.assertIn("$.frames[0][3][0]", prompt)

    def test_intent_quotes_ids_and_creative_separation(self):
        second = understand(ReplyModel([intent_reply()]), REQUEST, fresh_run(self.root / "second"))
        self.assertEqual(self.intent["requirements"], second["requirements"])
        self.assertTrue(self.intent["requirements"][0]["needs_visual_evidence"])
        self.assertFalse(self.intent["requirements"][1]["needs_visual_evidence"])
        self.assertEqual(self.intent["requirements"][2]["kind"], "exclusion")
        bad = copy.deepcopy(self.intent)
        bad["requirements"][0]["source_quote"] = "invented location"
        with self.assertRaises(ValueError):
            validate_intent(bad)

    def test_ambiguous_identity_retained(self):
        reply = intent_reply()
        reply["requirements"][0].update(description="The user and companions on a boat", source_quote="Highlight us on the boat")
        reply["requirements"] = reply["requirements"][:1]
        reply["ambiguities"] = [{"reference": "us", "question": "Which visible people are you referring to?"}]
        result = understand(ReplyModel([reply]), "Highlight us on the boat", fresh_run(self.root / "ambiguous"))
        self.assertEqual(result["ambiguities"][0]["reference"], "us")
        result["requirements"].append({"id": "appearance", "kind": "appearance", "priority": 2,
            "source_quote": "their outfits", "description": "Travelers clothing", "needs_visual_evidence": True})
        self.assertIn("appearance", ambiguous_requirement_ids(result))

    def test_rendering_preference_requires_correction_not_source_support(self):
        request = 'Highlight the visible people. Keep a natural look. Preserve their brown hair.'
        wrong = {'requirements': [
            {'kind':'appearance', 'description':'Natural look for the visible people',
             'priority':2, 'source_quote':'Keep a natural look.'},
            {'kind':'appearance', 'description':'The people\'s brown hair',
             'priority':2, 'source_quote':'Preserve their brown hair.'}],
            'ambiguities':[], 'moment_count':3}
        corrected = copy.deepcopy(wrong)
        corrected['requirements'][0]['kind'] = 'creative_change'
        model = ReplyModel([wrong, corrected])
        intent = understand(model, request, fresh_run(self.root / 'natural-style'))
        self.assertEqual(model.calls, 2)
        self.assertFalse(intent['requirements'][0]['needs_visual_evidence'])
        self.assertTrue(intent['requirements'][1]['needs_visual_evidence'])
        report = requirement_report(intent, [])
        self.assertEqual(report[0]['status'], 'creative_request')

    def test_unfixed_style_classification_fails_with_diagnostics(self):
        wrong = {'requirements':[{'kind':'appearance','description':'Cinematic style',
            'priority':2,'source_quote':'Use a cinematic style.'}], 'ambiguities':[], 'moment_count':3}
        run = fresh_run(self.root / 'bad-style')
        model = ReplyModel([wrong, wrong])
        with self.assertRaisesRegex(ValueError, 'after one correction'):
            understand(model, 'Use a cinematic style.', run)
        self.assertEqual(model.calls, 2)
        self.assertFalse((run / 'intent.json').exists())
        self.assertTrue((run / 'analysis/intent/attempt-2.response.txt').exists())

    def test_required_companions_outrank_optional_scenery(self):
        request = "Keep three companions together on the boat. Coastal scenery is optional."
        reply = {"requirements": [
            {"kind": "relationship", "description": "Three companions together on the boat", "priority": 3,
             "source_quote": "Keep three companions together on the boat."},
            {"kind": "place", "description": "Coastal scenery", "priority": 1,
             "source_quote": "Coastal scenery is optional."}], "ambiguities": [], "moment_count": 3}
        intent = understand(ReplyModel([reply]), request, fresh_run(self.root / "optional"))
        required, optional = [r["id"] for r in intent["requirements"]]
        pool = [frame("scenery", 1., [optional]), frame("group", 3., [required], fingerprint="ffffffffffffffff")]
        self.assertEqual(select(pool, intent, moments=1)[0]["id"], "group")

    def test_exactly_one_correction_then_failure(self):
        model = ReplyModel(["not JSON", "still not JSON"])
        with self.assertRaisesRegex(ValueError, "after one correction"):
            json_reply(model, "Test", schema("intent-reply"), [], self.root / "bad")
        self.assertEqual(model.calls, 2)
        self.assertTrue((self.root / "bad/attempt-2.response.txt").exists())
        good = ReplyModel(["```json\n{}\n```", intent_reply()])
        self.assertEqual(json_reply(good, "Test", schema("intent-reply"), [], self.root / "corrected"), intent_reply())

    def test_shared_sentence_quotes_reject_ellipsis_then_correct(self):
        request = "Highlight coastal trails and rocky coastline. Avoid farm and indoor scenes."
        valid = {"requirements": [
            {"kind": "place", "description": "Coastal trails", "priority": 3,
             "source_quote": "Highlight coastal trails and rocky coastline."},
            {"kind": "exclusion", "description": "Farm scenes", "priority": 3,
             "source_quote": "Avoid farm and indoor scenes."},
            {"kind": "exclusion", "description": "Indoor scenes", "priority": 3,
             "source_quote": "Avoid farm and indoor scenes."}], "ambiguities": [], "moment_count": 3}
        invalid = copy.deepcopy(valid)
        invalid["requirements"][1]["source_quote"] = "Avoid farm ... scenes"
        model = ReplyModel([invalid, valid])
        result = understand(model, request, fresh_run(self.root / "quotes"))
        self.assertEqual(model.calls, 2)
        self.assertEqual(result["requirements"][1]["source_quote"], result["requirements"][2]["source_quote"])

    def test_fresh_run_and_path_containment(self):
        run = fresh_run(self.root / "fresh")
        (run / "keep").write_text("original")
        with self.assertRaises(ValueError):
            fresh_run(run)
        with self.assertRaises(ValueError):
            asset_path(run, "../escape.jpg")
        (run / "link").symlink_to(self.root)
        with self.assertRaises(ValueError):
            asset_path(run, "link/escape.jpg")

    def test_exclusions_duplicates_and_absent_requirements(self):
        subject, creative, exclude = [r["id"] for r in self.intent["requirements"]]
        frames = [frame("boat", 1, [subject]), frame("duplicate", 3, [subject]),
                  frame("farm", 5, [subject, exclude], fingerprint="ffffffffffffffff"),
                  frame("unrelated", 7, [], fingerprint="7777777777777777")]
        selected = select(frames, self.intent)
        self.assertEqual([f["id"] for f in selected], ["boat"])
        statuses = {r["id"]: r["status"] for r in requirement_report(self.intent, selected)}
        self.assertEqual(statuses[subject], "supported")
        self.assertEqual(statuses[creative], "creative_request")
        self.assertEqual(select([frames[-1]], self.intent), [])
        self.assertEqual(requirement_report(self.intent, [frames[-1]])[0]["status"], "not_observed")

    def test_same_video_pool_changes_with_intent(self):
        boat = self.intent["requirements"][0]["id"]
        other = copy.deepcopy(self.intent)
        other["user_request"] = "Highlight hiking"
        other["requirements"] = [{"id": "hike", "kind": "activity", "description": "Hiking", "priority": 3,
                                   "source_quote": "hiking", "needs_visual_evidence": True}]
        frames = [frame("boat", 1, [boat]), frame("hike", 5, ["hike"], fingerprint="ffffffffffffffff")]
        self.assertEqual(select(frames, self.intent)[0]["id"], "boat")
        self.assertEqual(select(frames, other)[0]["id"], "hike")

    def test_appearance_alone_cannot_be_essential_scene_hero(self):
        intent = copy.deepcopy(self.intent)
        intent["requirements"].append({"id": "outfits", "kind": "appearance", "description": "Distinct outfits",
            "source_quote": "three companions", "priority": 2, "needs_visual_evidence": True})
        subject = intent["requirements"][0]["id"]
        pool = [frame("street", 1., ["outfits"]), frame("boat", 5., [], [subject], fingerprint="ffffffffffffffff")]
        self.assertEqual([f["id"] for f in select(pool, intent)], ["boat"])

    def test_uncertain_exclusion_does_not_beat_clear_evidence(self):
        subject, _, exclude = [r["id"] for r in self.intent["requirements"]]
        unclear = frame("unclear", 1, [subject], [exclude])
        clear = frame("clear", 3, [subject], fingerprint="ffffffffffffffff")
        self.assertEqual([f["id"] for f in select([unclear, clear], self.intent)], ["clear"])

    def test_unknown_frame_id_is_rejected(self):
        raw = frame("expected", 1)
        reply = {"frames": [frame("invented", 1)["observation"]]}
        with self.assertRaisesRegex(ValueError, "after one correction"):
                inspect(ReplyModel([reply, reply]), [raw], self.intent, self.root)

    def test_compact_model_wire_preserves_frame_and_requirement_identity(self):
        # Model sees relationship index 0 and exclusion index 1; creative change is omitted.
        raw = [frame("source-a", 1), frame("source-b", 3)]
        reply = {"frames": [[0, 3, "group", [0], [], "Three people seated together", "Open boat", ["green canopy"]],
                            [1, 0, "overview", [1], [], "No people", "Farm field", ["crops"]]]}
        observed = inspect(ReplyModel([reply]), raw, self.intent, self.root)
        self.assertEqual(observed[0]["observation"]["frame_id"], "source-a")
        self.assertEqual(observed[0]["observation"]["supported_requirements"], [self.intent["requirements"][0]["id"]])
        self.assertEqual(observed[1]["observation"]["supported_requirements"], [self.intent["requirements"][2]["id"]])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_media_roundtrip_short_cuts_invalid_and_hashes(self):
        video = make_video(self.root)
        source = probe(video)
        self.assertAlmostEqual(source["duration_seconds"], 6, places=1)
        shots = discover_shots(video, source["duration_seconds"])
        self.assertGreaterEqual(len(shots), 3)
        adaptive = candidate_times(source["duration_seconds"], 8, shots, "adaptive")
        self.assertLessEqual(len(adaptive), 8)
        self.assertTrue(all(0 < t < 6 for t in adaptive))
        self.assertEqual(len(uniform_times(.1, 96)), 1)
        run = fresh_run(self.root / "media")
        frames = extract_frames(video, adaptive, run, shots)
        self.assertTrue(all(sha256(run / f["image"]) == f["sha256"] for f in frames))
        for f in frames:
            f["observation"] = frame(f["id"], f["timestamp_s"], [self.intent["requirements"][0]["id"]])["observation"]
        brief = export_brief(video, source, frames, self.intent, select(frames, self.intent), run,
                             {"test": True}, ReplyModel([]), 0)
        validate_brief(brief, run)
        self.assertFalse(brief["user_confirmed"])
        self.assertFalse(brief["generation_started"])
        self.assertTrue((run / "review.md").exists())
        broken = copy.deepcopy(brief)
        broken["moments"][0]["clip_range_s"][1] = 100
        with self.assertRaises(ValueError):
            validate_brief(broken, run)
        unsupported = copy.deepcopy(brief)
        unsupported["requirements"][0]["status"] = "not_observed"
        with self.assertRaisesRegex(ValueError, "report must agree"):
            validate_brief(unsupported, run)
        (run / brief["moments"][0]["references"][0]["image"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_brief(brief, run)
        invalid = self.root / "invalid.mp4"
        invalid.write_text("not a video")
        with self.assertRaises(RuntimeError):
            probe(invalid)

    def test_failed_extraction_stops(self):
        with patch("memgen_skills.video.command", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "Failed to extract"):
                extract_frames("missing.mp4", [1.], self.root, [0., 2.])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_place_support_requires_independent_confirmation(self):
        video = make_video(self.root)
        source = probe(video)
        intent = copy.deepcopy(self.intent)
        requirement = intent["requirements"][0]
        requirement["kind"] = "place"
        requirement["description"] = "Requested coastal location"
        rid = requirement["id"]
        run = fresh_run(self.root / "place-guard")
        frames = extract_frames(video, [1.], run, [0., 6.])
        frames[0]["observation"] = frame(frames[0]["id"], 1., [rid])["observation"]
        original = copy.deepcopy(frames)
        result = export_brief(video, source, frames, intent, frames, run,
                              {"test": True}, ReplyModel([]), 0)
        self.assertEqual(frames, original)  # Raw model judgments remain unchanged.
        self.assertEqual(result["requirements"][0]["status"], "uncertain")
        self.assertIn(rid, result["unresolved_requirements"])
        self.assertEqual(result["metrics"]["supported_positive_requirements"], 0)
        self.assertTrue(result["moments"][0]["setting"])
        forged = copy.deepcopy(result)
        ref = forged["moments"][0]["references"][0]
        ref["supports"], ref["uncertain"] = [rid], []
        with self.assertRaisesRegex(ValueError, "independent location"):
            validate_brief(forged, run)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_effective_moment_override_recorded_through_pipeline(self):
        class FrameFixture(ReplyModel):
            def generate(self, prompt, images, max_tokens):
                self.calls += 1
                if "\nPAIRS: " in prompt:
                    pairs = json.loads(prompt.split("\nPAIRS: ")[1].split("\nReturn ONLY")[0])
                    return json.dumps({"views": [[i, 3, "Three test figures", "Synthetic boat", "group", ["Test outfits"]] for i in range(len(images))],
                                       "checks": [[i, j, "visible" if j == 0 else "not_visible", "Explicit synthetic fixture"] for i, j in pairs]})
                return json.dumps({"frames": [[i, 3, "group", [0], [], "Three test figures",
                                              "Synthetic outdoor scene", ["test geometry"]]
                                             for i in range(len(images))]})
        video = make_video(self.root)
        run = fresh_run(self.root / "override")
        brief = run_selection(FrameFixture([]), video, self.intent, run,
                              coarse_budget=4, refinement_budget=2, batch_size=3, moments=1)
        self.assertEqual(brief["intent"]["moment_count"], 3)
        self.assertEqual(brief["sampling"]["target_moments"], 1)
        self.assertEqual(brief["sampling"]["selected_moments"], 1)
        self.assertIn("Proposed 1 of 1", (run / "review.md").read_text())
        resumed = fresh_run(self.root / "resumed")
        with patch("memgen_skills.evidence.inspect", side_effect=AssertionError("Must reuse observations")):
            recovered = run_selection(FrameFixture([]), video, self.intent, resumed, 4, 2, 3, moments=1, resume=run)
        validate_brief(recovered, resumed)
        self.assertEqual(recovered["moments"][0]["hero_timestamp_s"], brief["moments"][0]["hero_timestamp_s"])
        self.assertEqual(recovered["sampling"]["resumed_observations"]["reused_frames"], 6)
        checked = fresh_run(self.root / "rechecked")
        again = recheck_run(FrameFixture([]), video, run, checked)
        validate_brief(again, checked)
        self.assertIn("recheck_seconds", again["metrics"])
        self.assertTrue((checked / "prior-analysis/all-observations.json").is_file())
        saved = (run / "analysis/all-observations.json").read_text()
        (run / "analysis/all-observations.json").write_text(json.dumps(json.loads(saved)[:1]))
        with self.assertRaisesRegex(ValueError, "checksum|count"):
            recheck_run(FrameFixture([]), video, run, fresh_run(self.root / "truncated"))
        (run / "analysis/all-observations.json").write_text(saved)
        brief["sampling"]["shortfall_note"] = "Stale old shortfall"
        (run / "evidence-brief.json").write_text(json.dumps(brief))
        refreshed = recheck_run(FrameFixture([]), video, run, fresh_run(self.root / "fresh-note"))
        self.assertIsNone(refreshed["sampling"]["shortfall_note"])
        ambiguous = copy.deepcopy(self.intent)
        ambiguous["ambiguities"] = [{"reference": "three companions", "question": "Which three people?"}]
        guarded = fresh_run(self.root / "guarded")
        result = run_selection(FrameFixture([]), video, ambiguous, guarded, 4, 0, 3, moments=1)
        self.assertEqual(result["requirements"][0]["status"], "uncertain")
        self.assertEqual(result["metrics"]["supported_positive_requirements"], 0)

    def test_claim_check_removes_partial_relationship(self):
        rid = self.intent["requirements"][0]["id"]
        frames = [frame("street", 1., [rid])]
        result = verify_selected(ReplyModel([{ "checks": [[0, 0, "absent", "Street, no boat visible"], [0, 1, "absent", "No farm"]]}]),
                                 frames, self.intent, self.root)
        self.assertEqual(select(result, self.intent), [])
        self.assertEqual(frames[0]["observation"]["supported_requirements"], [rid])

    def test_claim_check_retains_uncertainty_and_catches_exclusion(self):
        rid = self.intent["requirements"][0]["id"]
        frames = [frame("group", 1., uncertain=[rid])]
        replies = [{"checks": [[0, 0, "supported", "Three figures"], [0, 1, "absent", "No farm"]]}]
        result = verify_selected(ReplyModel(replies), frames, self.intent, self.root / "uncertain")
        self.assertEqual(result[0]["observation"]["supported_requirements"], [])
        self.assertEqual(result[0]["observation"]["uncertain_requirements"], [rid])
        frames = [frame("group", 1., [rid])]
        replies = [{"checks": [[0, 0, "supported", "Three figures"], [0, 1, "supported", "Farm visible"]]}]
        result = verify_selected(ReplyModel(replies), frames, self.intent, self.root / "excluded")
        self.assertEqual(select(result, self.intent), [])

    def test_many_uncertain_claims_expand(self):
        intent = copy.deepcopy(self.intent)
        requirement = intent["requirements"][0]
        intent["requirements"] = [{**requirement, "id": "req-" + str(i).zfill(10)} for i in range(6)]
        reply = {"frames": [[0, None, "other", [], list(range(6)), "Unclear", "Unclear", []]]}
        result = inspect(ReplyModel([reply]), [frame("f", 1.)], intent, self.root)
        self.assertEqual(len(result[0]["observation"]["uncertainties"]), 6)

    def test_claim_view_accepts_one_phrase_without_semantic_rewriting(self):
        rid = self.intent["requirements"][0]["id"]
        reply = {"views": [[0, 3, "Two travelers and driver", "Boat", "group", "White shirt, driver visible"]],
                 "checks": [[0, 0, "uncertain", "Driver is not established as companion"], [0, 1, "not_visible", "No farm"]]}
        model = ReplyModel([json.dumps(reply)])
        result = verify_selected(model, [frame("boat", 1., [rid])], self.intent, self.root / "scalar-view")
        self.assertEqual(result[0]["observation"]["visible_details"], ["White shirt, driver visible"])
        self.assertEqual(model.calls, 1)
        self.assertIn(rid, role_guard_ids(result[0]["observation"]["people"], self.intent))
        self.assertEqual(role_guard_ids("Three travelers", self.intent), set())

    def test_json_envelope_is_strict(self):
        contract = {"type": "object", "properties": {"ok": {"const": True}}, "required": ["ok"], "additionalProperties": False}
        result = json_reply(ReplyModel(['```json\n{"ok":true}\n```']), "Test", contract, [], self.root / "fenced")
        self.assertTrue(result["ok"])
        with self.assertRaisesRegex(ValueError, "after one correction"):
            json_reply(ReplyModel(['Prose {"ok":true}'] * 2), "Test", contract, [], self.root / "prose")


def make_video(root):
    for i, color in enumerate(("#923333", "#337799", "#339944")):
        image = Image.new("RGB", (320, 180), color)
        draw = ImageDraw.Draw(image)
        for x in range(3):
            draw.rectangle((20 + x * (30 + i * 20), 30 + i * 20, 38 + x * (30 + i * 20), 150), fill="white")
        image.save(root / f"shot-{i}.png")
        command(["ffmpeg", "-v", "error", "-loop", "1", "-i", root / f"shot-{i}.png", "-t", "2", "-r", "4",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", root / f"shot-{i}.mp4"])
    (root / "concat.txt").write_text("\n".join(f"file 'shot-{i}.mp4'" for i in range(3)))
    video = root / "test.mp4"
    command(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", root / "concat.txt", "-c", "copy", video])
    return video


if __name__ == "__main__":
    unittest.main()
