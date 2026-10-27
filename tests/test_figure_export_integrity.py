"""Real figure exports must change with measured data and contain the plotted chart."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import _env

from backend.figures.contracts import FigureSpec
from backend.figures.renderers import render_all


class FigureExportIntegrity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('figure-export-integrity')

    def test_legacy_placeholder_versions_are_preserved_but_cannot_be_trusted_or_attached(self):
        from backend.figures import store
        from backend.knowledge import research_store as research
        topic = research.save_topic(research.TopicInput(title='Legacy artifact fixture'))
        figure = store.create_or_regenerate(FigureSpec(topic_id=topic['id'], title='Measured data',
            source={'series': {'MSE': [0.2, 0.1]}}, outputs=['png', 'svg', 'pdf']))
        with research.db() as connection:
            row = connection.execute('SELECT payload FROM figure_versions WHERE figure_id=?', (figure['id'],)).fetchone()
            old = json.loads(row['payload'])
            old['provenance']['renderer_used'] = 'matplotlib'
            old['provenance']['scientific_review'] = 'approved'
            connection.execute('INSERT INTO figure_versions VALUES(?,?,?,?,?,?,?,?,?)',
                (research.uid(), figure['id'], topic['id'], 2, figure['versions'][0]['spec_sha256'],
                 figure['versions'][0]['script_sha256'], figure['versions'][0]['data_sha256'], research.dumps(old), research.now()))
            connection.execute('UPDATE figures SET current_version=2,status=? WHERE id=?', ('approved', figure['id']))
        view = store.get_figure(topic['id'], figure['id'])
        self.assertEqual(view['status'], 'needs_review')
        self.assertEqual(view['provenance']['scientific_review'], 'pending')
        for action in (lambda: store.validate_figure_version(topic['id'], figure['id']),
                       lambda: store.approve_figure(topic['id'], figure['id'], 2, 'Attempt to approve'),
                       lambda: store.export_file_path(topic['id'], figure['id'], 'png'),
                       lambda: store.attach_to_paper(topic['id'], figure['id'])):
            with self.assertRaisesRegex(ValueError, 'placeholder'):
                action()
        # Retained bytes remain on disk, but a v2 row pointing into v1 must
        # never bypass immutable-version confinement, even for SVG download.
        self.assertTrue(Path(old['provenance']['exports']['svg']['path']).is_file())
        with self.assertRaisesRegex(ValueError, 'immutable version directory'):
            store.export_file_path(topic['id'], figure['id'], 'svg')
    def test_png_depends_on_data_instead_of_a_placeholder_grid(self):
        with tempfile.TemporaryDirectory() as folder:
            exports = []
            for index, values in enumerate(([1.0, 3.0], [3.0, 1.0])):
                spec = FigureSpec(topic_id='fixture', title='Measured comparison', x_label='Condition', y_label='MSE',
                    plot_kind='bar', outputs=['png', 'pdf'], source={'series': {'Measured MSE': values}, 'x_values': ['A', 'B']})
                rendered = render_all(spec, Path(folder) / str(index))
                exports.append(rendered)
            self.assertNotEqual(exports[0]['exports']['png']['sha256'], exports[1]['exports']['png']['sha256'])
            self.assertEqual(hashlib.sha256((Path(folder) / '0/preview.png').read_bytes()).hexdigest(), exports[0]['exports']['png']['sha256'])
            from pypdf import PdfReader
            text = ''.join(p.extract_text() or '' for p in PdfReader(exports[0]['exports']['pdf']['path']).pages)
            self.assertIn('Condition', text)
            self.assertIn('Measured MSE', text)

    def test_no_data_cannot_become_an_invented_scientific_curve(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, 'series'):
            render_all(FigureSpec(topic_id='fixture', title='No measurements', outputs=['png']), Path(folder))
