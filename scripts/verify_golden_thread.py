"""Real local-model → context → sandbox experiment/replay → figure → paper workflow.

All data is synthetic and disposable. A completed technical workflow does not
certify novelty, empirical generalization or independent scientific peer review.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', default='spark-x2.5-4b')
    parser.add_argument('--tectonic', type=Path, help='Optional pinned native compiler; no online document upload')
    args = parser.parse_args()
    out = args.out.resolve()
    check(out.is_relative_to((ROOT / 'output/playwright').resolve()), 'Golden-thread output must be disposable')
    out.mkdir(parents=True, exist_ok=False)
    os.environ['PHDLAB_DATA_DIR'] = str(out / 'data')
    os.environ['JUPYTER_DATA_DIR'] = str(out / 'data/_jupyter')
    from backend.core import config
    config.save_config({'local_model': args.model, 'lmstudio_base_url': 'http://127.0.0.1:1234/v1',
        'agent_modes': {a: 'local' for a in config.AGENTS}, 'agent_models': {a: args.model for a in config.AGENTS},
        'fallback_to_cloud': False, 'memory': {'embed_engine': 'hashing', 'auto_summarize': False},
        'lifecycle': {'unload_on_exit': False, 'local_interactive': 'keep_loaded'},
        'clearml': {'auto_record': False}, 'ui': {'language': 'en'}, 'aiws': {'max_turn_s': 90}})
    from pdfgen import make_pdf

    from backend.agent import orchestrator, pins, sessions
    from backend.execution import sandbox
    from backend.figures.contracts import FigureSpec
    from backend.figures.store import create_or_regenerate
    from backend.knowledge import corpus, library
    from backend.knowledge import research_store as store
    from backend.paper import writer
    from tools.qa_harness import source_hashes

    report = {'model': args.model, 'mode': 'REAL_E2E', 'status': 'ERROR', 'cases': [],
              'source_files_sha256': source_hashes(), 'limitations': [
                  'Synthetic document and dataset, not a new scientific finding',
                  'Model text is advisory; scientific review remains pending',
                  'Direct core orchestration; browser/HTTP/CLI layers are qualified separately']}
    def step(name, fn):
        start = time.monotonic()
        try:
            value = fn()
            report['cases'].append({'id': name, 'status': 'PASSED', 'elapsed_s': time.monotonic()-start, 'result': value})
            return value
        except Exception:
            report['cases'].append({'id': name, 'status': 'FAILED', 'elapsed_s': time.monotonic()-start, 'error': traceback.format_exc()})
            raise
        finally:
            (out / 'report.json').write_text(json.dumps(report, indent=2, default=str), 'utf-8')
    try:
        config.create_project('Golden Thread Synthetic Research')
        topic = store.save_topic(store.TopicInput(title='Synthetic sine denoising QA', keywords=['sine', 'denoising']))
        pdf = make_pdf([[(18, 'Synthetic Signal Fixture'), (12, 'Abstract'),
                         (12, 'A test signal uses 128 samples and noise sigma 0.25.'),
                         (12, 'This is an authored synthetic QA fixture, not a published paper.'),
                         (12, 'Introduction')]], {'Title': 'Synthetic Signal Fixture', 'Author': 'QA Fixture'})
        entry = step('library-pdf-ingestion', lambda: library.ingest_pdf('synthetic-fixture.pdf', pdf))
        ingested = corpus.ingest(topic['id'], [{'title': 'Synthetic Signal Fixture', 'source': 'manual',
            'abstract': '128 synthetic sine samples; Gaussian noise sigma 0.25.', 'url': 'https://example.invalid/synthetic-qa',
            'authors': ['QA Fixture'], 'year': '2026', 'publication_type': 'other', 'flags': ['synthetic_fixture']}])
        check(ingested['paper_ids'], 'Corpus did not persist the authored fixture')
        paper = corpus.all_papers(topic['id'])[0]
        version = paper['versions'][0]['id']
        step('corpus-pdf-provenance', lambda: corpus.store_document(topic['id'], paper['id'], version, pdf, {'source': 'authored synthetic fixture'}))
        step('corpus-index', lambda: corpus.index_document(topic['id'], paper['id'], version))
        chunks = corpus.retrieve(topic['id'], 'sine samples noise sigma', 6)
        check(chunks, 'No scientific source chunks were indexed/retrieved')
        pins.add('method', 'CPU budget', 'Use CPU only; the budget is 2 seconds for this synthetic fixture.')
        session = sessions.create('Golden thread', module='global', settings={'provider': 'app:local', 'model': args.model,
            'context_mode': 'expanded', 'mcp_auto': False, 'reasoning': 'off'})
        sessions.update(session['id'], lambda s: s.update(selected_sources=['ref:' + entry['key']]))
        def chat():
            turn = orchestrator.start(session['id'], 'From the selected synthetic PDF, state the sample count and noise sigma. Also state the pinned CPU time budget. No tools.')
            end = time.monotonic() + 120
            while time.monotonic() < end:
                saved = sessions.get(session['id'])
                actual = next(t for t in saved['turns'] if t['id'] == turn['id'])
                if actual['status'] not in ('queued', 'running'):
                    break
                time.sleep(0.1)
            else:
                orchestrator.cancel(session['id'], turn['id'])
                raise TimeoutError('Golden-thread chat deadline exceeded')
            check(actual['status'] == 'completed', json.dumps(actual))
            check('128' in saved['messages'][-1]['content'] and '0.25' in saved['messages'][-1]['content'], 'Model did not preserve PDF values')
            check('2' in saved['messages'][-1]['content'], 'Model did not preserve the pin budget')
            check('0.25' in actual['context_text'] and 'budget is 2' in actual['context_text'], 'Prompt dropped source or pin')
            (out / 'context-and-session.json').write_text(json.dumps(saved, indent=2), 'utf-8')
            return {'session_id': session['id'], 'manifest': actual['manifest'], 'answer': saved['messages'][-1]['content']}
        step('context-aware-real-model-chat', chat)
        from backend.execution import code_projects
        code_projects.create('golden-synthetic-experiment', git=False, seed=False)
        sandbox.save_settings({'mode': 'local', 'python_mode': 'existing', 'python_base': sys.executable,
                               'gpu': False, 'auto_deps': False, 'timeout_s': 30})
        code = sandbox.code_dir()
        code.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'scripts/toy_experiment.py', code / 'toy_experiment.py')
        def run_experiment(name):
            job = sandbox.start_job('python toy_experiment.py --output ' + name, 'run', name, extra_env={'CUDA_VISIBLE_DEVICES': ''})
            end = time.monotonic() + 45
            while job.ended is None and time.monotonic() < end:
                time.sleep(0.05)
            check(job.ended is not None and job.exit_code == 0, job.tail())
            folder = code / name
            check((folder / 'raw.csv').is_file(), 'Sandbox produced no raw measurements')
            shutil.copytree(folder, out / name)
            return json.loads((folder / 'metrics.json').read_text('utf-8'))
        measured = step('sandbox-experiment', lambda: run_experiment('experiment'))
        replay = step('fresh-subprocess-replay', lambda: run_experiment('replay'))
        def verify():
            with (out / 'experiment/raw.csv').open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            recomputed = {key: math.fsum((float(row[column])-float(row['clean']))**2 for row in rows)/len(rows)
                          for key, column in [('mse_noisy', 'noisy'), ('mse_filtered', 'filtered')]}
            for key, value in recomputed.items():
                check(abs(measured[key] - value) < 1e-12, 'Reported metric differs from raw recomputation')
                check(abs(replay[key] - value) < 1e-12, 'Replay differs from actual raw measurements')
            check(measured['mse_filtered'] < measured['mse_noisy'], 'Smoothing did not improve this synthetic fixture')
            return {'recomputed': recomputed, 'rows': len(rows), 'raw_sha256': hashlib.sha256((out / 'experiment/raw.csv').read_bytes()).hexdigest()}
        step('independent-raw-recomputation', verify)
        figure = step('figure-store-render', lambda: create_or_regenerate(FigureSpec(topic_id=topic['id'],
            title='Synthetic sine denoising measurement', caption='Actual CPU outputs on an explicitly synthetic fixture; scientific review pending.',
            alt_text='Measured noisy and filtered mean squared error for 128 synthetic samples', plot_kind='bar',
            x_label='Condition', y_label='MSE', source={'kind': 'inline_series', 'x_values': ['Noisy', 'Smoothed'],
            'series': {'Measured MSE': [measured['mse_noisy'], measured['mse_filtered']]}, 'is_synthetic_fixture': True}, outputs=['svg', 'png'])))
        def paper_export():
            project = writer.load_project()
            project.update(title='Reproducible Synthetic Denoising: A PhD Lab QA Experiment', authors='QA Fixture', style='IEEE',
                           keywords='synthetic data, denoising, reproducibility, quality assurance')
            key = entry['key']
            project['sections'] = {'abstract': 'This technical report validates a synthetic CPU workflow, not a new empirical scientific result.',
                'methodology': f'We use 128 sine samples with Gaussian noise sigma 0.25 and a three-point moving average. The authored fixture is cited as \\cite{{{key}}}.',
                'experiments': f"The measured noisy MSE is {measured['mse_noisy']:.12f}; filtered MSE is {measured['mse_filtered']:.12f}. Fresh subprocess replay and independent recomputation agree within $10^{{-12}}$.",
                'discussion': 'The dataset is synthetic. No generalization, novelty, provider parity or peer-review approval is claimed.'}
            figure_path = Path(figure['provenance']['exports']['png']['path'])
            shutil.copyfile(figure_path, out / 'figure.png')
            project['sections']['experiments'] += '\n' + r'\begin{figure}[h]\centering\includegraphics[width=0.7\linewidth]{figure.png}\caption{Measured MSE on the synthetic CPU fixture.}\end{figure}'
            project['sections'] = {sid: writer.clean_section(sid, text) for sid, text in project['sections'].items()}
            writer.save_project(project)
            tex, bib, details = writer.assemble(project)
            check('\\begin{document}' in tex and key in bib and '\\cite{' + key + '}' in tex, 'Paper export lost citation lineage')
            (out / 'main.tex').write_text(tex, 'utf-8')
            (out / 'references.bib').write_text(bib, 'utf-8')
            (out / 'paper.md').write_text('# ' + project['title'] + '\n\n' + '\n\n'.join(project['sections'].values()), 'utf-8')
            (out / 'latex.zip').write_bytes(writer.build_zip())
            return {'files': ['main.tex', 'references.bib', 'paper.md', 'latex.zip'], 'citation_key': key, 'report': details,
                    'scientific_review': 'pending', 'pdf_compilation': 'NOT_EXECUTED'}
        step('paper-writer-and-latex-export', paper_export)
        if args.tectonic:
            from backend.paper import latex
            compiler = args.tectonic.resolve()
            check(compiler.is_file(), 'Configured native LaTeX compiler is missing')
            os.environ['PATH'] = str(compiler.parent) + os.pathsep + os.environ.get('PATH', '')
            def compile_paper():
                build = latex.build_dir()
                build.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out / 'figure.png', build / 'figure.png')
                result = latex.compile_pdf(engine='tectonic', layout='template')
                check(result['ok'], json.dumps(result))
                shutil.copyfile(build / 'main.pdf', out / 'paper.pdf')
                shutil.copyfile(build / 'build.log', out / 'latex-build.log')
                from pypdf import PdfReader
                pdf = PdfReader(out / 'paper.pdf')
                check(pdf.pages and 'synthetic' in ''.join(p.extract_text() or '' for p in pdf.pages).lower(), 'Compiled paper has no expected text')
                return {**result, 'pages': len(pdf.pages), 'compiler_version': subprocess.check_output([str(compiler), '--version'], text=True).strip()}
            step('native-paper-pdf-compilation', compile_paper)
        report['status'] = 'PASSED'
        report['scientific_verified'] = False
        report['artifacts_sha256'] = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in out.rglob('*') if p.is_file() and p.name != 'report.json'}
    except Exception:  # noqa: BLE001 - persist the full failing workflow result instead of losing the report
        report['status'] = 'FAILED'
        report['error'] = traceback.format_exc()
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2, default=str), 'utf-8')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
