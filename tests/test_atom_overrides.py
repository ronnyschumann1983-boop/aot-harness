"""
tests/test_atom_overrides.py
Tests Atom dataclass extension (provider/model fields) — Phase 1.3.
"""
import unittest

from aot_harness.core.aot_reasoner import Atom, AtomGraph, AtomStatus


class TestAtomProviderFields(unittest.TestCase):

    def test_atom_defaults_no_override(self):
        atom = Atom(id="a1", question="What?")
        self.assertIsNone(atom.provider)
        self.assertIsNone(atom.model)

    def test_atom_with_provider_override(self):
        atom = Atom(id="a1", question="What?", provider="google", model="gemini/gemini-2.0-flash")
        self.assertEqual(atom.provider, "google")
        self.assertEqual(atom.model, "gemini/gemini-2.0-flash")

    def test_to_dict_serializes_overrides(self):
        graph = AtomGraph(goal="Test goal")
        graph.add(Atom(id="a1", question="Q1"))
        graph.add(Atom(id="a2", question="Q2", provider="mistral", model="mistral/mistral-small-latest"))
        d = graph.to_dict()
        self.assertIsNone(d["atoms"]["a1"]["provider"])
        self.assertEqual(d["atoms"]["a2"]["provider"], "mistral")
        self.assertEqual(d["atoms"]["a2"]["model"], "mistral/mistral-small-latest")

    def test_backward_compat_atom_creation(self):
        """Existing call sites without provider/model still work."""
        atom = Atom(id="a1", question="Q", depends_on=["a0"], status=AtomStatus.PENDING)
        self.assertEqual(atom.id, "a1")
        self.assertIsNone(atom.provider)


if __name__ == "__main__":
    unittest.main()
