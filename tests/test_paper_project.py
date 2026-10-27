"""REAL_LOCAL SQLite migration and ownership contracts; no model/science claims."""
import _env
import hashlib
import json
import sqlite3
import unittest

from backend.core import config
from backend.knowledge import research_store as store
from backend.research_engines import workspaces


class PaperProject(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('paper-project')

    def test_new_paper_lives_under_data_and_rejects_a_second_topic(self):
        self.assertTrue(config.data_dir().is_relative_to(config.GLOBAL_DIR/'projects'))
        first=store.save_topic(store.TopicInput(title='One paper'))
        with self.assertRaisesRegex(ValueError,'exactly one paper'):
            store.save_topic(store.TopicInput(title='Another paper'))
        store.save_topic(store.TopicInput(title='Updated same paper'),first['id'])
        self.assertEqual(len(store.topics()),1)
        self.assertEqual(store.get_topic(first['id'])['title'],'Updated same paper')

    def test_empty_inventory_is_read_only_and_does_not_create_a_database(self):
        path=config.data_dir()/'workspace/research/research.sqlite3'
        self.assertFalse(path.exists())
        first=store.paper_project_layout()
        self.assertEqual(first['status'],'EMPTY_PAPER_PROJECT')
        self.assertFalse(first['mutations_executed'])
        self.assertEqual(store.paper_project_layout()['plan_sha256'],first['plan_sha256'])
        self.assertFalse(path.exists())

    def test_adoption_is_idempotent_and_preserves_experiments_and_ids(self):
        topic=store.save_topic(store.TopicInput(title='Durable paper'))
        workspace=workspaces.link(topic['id'],workspaces.WorkspaceInput(engine='phdlab'))
        experiment=config.data_dir()/'code/main/experiments/trial-a/result.json'
        experiment.parent.mkdir(parents=True,exist_ok=True);experiment.write_text('{"metric":0.42}')
        original=experiment.read_bytes()
        preview=store.paper_project_layout()
        self.assertEqual(preview['assigned_topic_id'],topic['id'])
        first=store.adopt_paper_project(preview['plan_sha256'])
        second=store.adopt_paper_project(first['plan_sha256'])
        self.assertEqual((first['status'],second['status']),('ADOPTED','ADOPTED'))
        self.assertFalse(second['mutations_executed'])
        self.assertEqual(experiment.read_bytes(),original)
        self.assertEqual(workspaces.get(workspace['id'])['topic_id'],topic['id'])
        self.assertEqual((second['files_moved'],second['files_deleted']),(0,0))

    def test_changed_inventory_is_refused_without_adopting_stale_plan(self):
        topic=store.save_topic(store.TopicInput(title='Original title'))
        preview=store.paper_project_layout()
        store.save_topic(store.TopicInput(title='Changed title'),topic['id'])
        with self.assertRaisesRegex(ValueError,'changed'):
            store.adopt_paper_project(preview['plan_sha256'])
        self.assertEqual(store.get_topic(topic['id'])['title'],'Changed title')

    def test_legacy_multiple_topics_are_preserved_and_never_guessed(self):
        first=store.save_topic(store.TopicInput(title='Historical paper A'))
        # Explicit legacy fixture, not a backdoor in the current create-topic API.
        second=store.uid()
        with store.db() as connection:
            connection.execute('INSERT INTO topics VALUES(?,?,?,?)',
                (second,store.dumps({**first,'title':'Historical paper B'}),store.now(),store.now()))
        path=store.store_dir()/'research.sqlite3';before=path.read_bytes()
        preview=store.paper_project_layout()
        self.assertEqual(preview['status'],'BLOCKED_OWNERSHIP_MAPPING')
        self.assertEqual(preview['topic_count'],2)
        self.assertTrue(preview['ambiguities'])
        self.assertEqual(path.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'exactly one'):
            store.adopt_paper_project(preview['plan_sha256'])
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual({t['id'] for t in store.topics()},{first['id'],second})

    def test_legacy_missing_tables_report_unknown_counts_without_schema_mutation(self):
        folder=config.data_dir()/'workspace/research';folder.mkdir(parents=True,exist_ok=True)
        path=folder/'research.sqlite3'
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE topics(id TEXT PRIMARY KEY,payload TEXT,created TEXT,updated TEXT)')
            connection.execute('INSERT INTO topics VALUES(?,?,?,?)',('legacy',json.dumps({'title':'Old paper'}),'old','old'))
        before=path.read_bytes();preview=store.paper_project_layout()
        self.assertEqual(preview['topics'][0]['records']['figures'],None)
        self.assertIn('figures',preview['unavailable_legacy_tables'])
        self.assertEqual(path.read_bytes(),before)

    def test_schema_migration_backs_up_history_and_accepts_native_workspace(self):
        folder=config.data_dir()/'workspace/research';folder.mkdir(parents=True,exist_ok=True)
        path=folder/'research.sqlite3'
        legacy_schema=store.SCHEMA.replace(",'phdlab'",'')
        self.assertNotEqual(legacy_schema,store.SCHEMA)
        with sqlite3.connect(path) as connection:
            connection.executescript(legacy_schema)
            connection.execute('PRAGMA user_version=8')
            connection.execute('INSERT INTO meta VALUES(?,?)',('project_id','preserved-project-id'))
            connection.execute('INSERT INTO topics VALUES(?,?,?,?)',('paper',json.dumps({'title':'Legacy paper'}),'old','old'))
            connection.execute('INSERT INTO workspaces VALUES(?,?,?,?,?)',('old-workspace','paper','openscience','historical-path','{}'))
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        with store.db() as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],9)
            self.assertEqual(connection.execute('SELECT engine FROM workspaces WHERE id=?',('old-workspace',)).fetchone()[0],'openscience')
            self.assertEqual(connection.execute('SELECT value FROM meta WHERE key=?',('project_id',)).fetchone()[0],'preserved-project-id')
            self.assertFalse(connection.execute('PRAGMA foreign_key_check').fetchall())
        backup=folder/'research.v8.sqlite3.bak'
        self.assertTrue(backup.is_file())
        # SQLite backup is logical: compare preserved schema/data, not incidental file bytes.
        with sqlite3.connect(backup) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],8)
            self.assertNotIn("'phdlab'",connection.execute("SELECT sql FROM sqlite_master WHERE name='workspaces'").fetchone()[0])
        adopted=workspaces.link('paper',workspaces.WorkspaceInput(engine='phdlab'))
        self.assertEqual(adopted['engine'],'phdlab')
        self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        backup_bytes=backup.read_bytes()
        with store.db():pass
        self.assertEqual(backup.read_bytes(),backup_bytes)


if __name__=='__main__':unittest.main()
