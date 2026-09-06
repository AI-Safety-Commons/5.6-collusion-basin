import json
from pathlib import Path
import tempfile
import unittest

from wiki_synth.viewer import list_runs, load_run, run_directory


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / 'example'
        self.run.mkdir()
        plan = {'config': {'model': 'llama-8b'}, 'jobs': [
            {'id': 'sample-000001', 'request': {'prompt': '<script>untrusted</script>'}},
            {'id': 'sample-000002', 'request': {'prompt': 'example'}}]}
        (self.run / 'run.json').write_text(json.dumps({'identity': {'plan': plan, 'provider': 'acs'}}))
        (self.run / 'sample-000001.json').write_text(json.dumps({'body': 'saved post'}))

    def test_partial_run_and_source_text(self):
        value = load_run(self.root, 'example')
        self.assertEqual((value['completed'], value['planned']), (1, 2))
        self.assertEqual(value['samples'][0]['record']['body'], 'saved post')
        self.assertEqual(value['samples'][0]['request']['prompt'], '<script>untrusted</script>')

    def test_unrelated_files_and_malformed_run(self):
        (self.root / '.env').write_text('SECRET=not served')
        (self.root / 'broken').mkdir()
        (self.root / 'broken' / 'run.json').write_text('{')
        result = list_runs(self.root)
        self.assertEqual(len(result['runs']), 1)
        self.assertEqual(len(result['errors']), 1)

    def test_traversal_and_symlinks_rejected(self):
        for name in ['../example', '..', '/tmp', 'example/../example']:
            with self.assertRaises(ValueError):
                run_directory(self.root, name)
        (self.root / 'alias').symlink_to(self.run, target_is_directory=True)
        with self.assertRaises(ValueError):
            load_run(self.root, 'alias')
        (self.run / 'sample-000001.json').unlink()
        (self.run / 'sample-000001.json').symlink_to(self.run / 'run.json')
        self.assertEqual(load_run(self.root, 'example')['completed'], 0)
