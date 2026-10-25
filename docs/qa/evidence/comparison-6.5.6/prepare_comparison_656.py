import hashlib,json,shutil,subprocess,sys
from pathlib import Path

control=Path('D:/git-repo/PhD-Research-Lab-worktrees/candidate-shared-verification-656')
baseline=Path('D:/git-repo/PhD-Research-Lab-worktrees/main-shared-verification-656')
out=Path(__file__).resolve().parent/'comparison-656';out.mkdir(exist_ok=True)
def digest(files,root):
 data={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix in ['.py','.ts','.tsx','.js','.cjs','.mjs','.json','.md','.txt','.lock','.yml','.toml'] or p.name=='.coveragerc' else p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file()}
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),data
def production(root):
 paths=list((root/'backend').rglob('*.py'))
 paths += [p for p in (root/'frontend/src').rglob('*') if p.is_file() and not p.name.endswith(('.test.ts','.test.tsx','.pyc')) and '/src/test/' not in p.as_posix() and '__pycache__' not in p.parts]
 paths += [root/p for p in ['cli.py','start.py','frontend/react.html'] if (root/p).is_file()]
 return digest(paths,root)
before={name:production(root) for name,root in [('main',baseline),('candidate',control)]}
original={'main_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=baseline,text=True).strip(),
 'candidate_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=control,text=True).strip(),
 'main_frontend_package':json.loads((baseline/'frontend/package.json').read_text(encoding='utf-8'))}
# This is a fresh detached benchmark checkout. Preserve its old test suite before
# substituting the identical candidate suite; never move/delete agent or skills files.
archive=baseline/'output/playwright/comparison-original-tests';archive.parent.mkdir(parents=True,exist_ok=True)
if archive.exists():raise RuntimeError('Comparison already prepared; preserve it and use a fresh checkout')
source=(baseline/'tests').resolve();target=archive.resolve()
assert source.is_relative_to(baseline.resolve()) and target.is_relative_to(baseline.resolve())
source.rename(target)
shutil.copytree(control/'tests',baseline/'tests',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=control).decode('utf-8').split('\0')
tools={'tools/backend_quality_gate.py','tools/quality_evidence.py','tools/protect_agent_resources.py','tools/playwright_server.py','tools/qa_harness.py','tools/run_tests.py','tools/bump_version.py','tools/full_harness_report.py','tools/compare_api_contract.py'}
exact={'.coveragerc','requirements-ci.lock','AGENTS.md','CLAUDE.md','GEMINI.md','frontend/package.json','frontend/package-lock.json','frontend/vite.config.ts','frontend/playwright.config.ts','frontend/postbuild.js','docs/qa/KNOWN_ISSUES_BASELINE.json','docs/qa/CRITICAL_SOFTWARE_CHECKS.json'}
bundle=[]
for name in tracked:
 if not name:continue
 is_front_test=name.startswith('frontend/src/') and (name.endswith(('.test.ts','.test.tsx')) or name.startswith('frontend/src/test/'))
 is_node_test=name.startswith('.github/scripts/') and name.endswith('.test.cjs')
 selected=(name.startswith(('tests/','devtools/','scripts/','agent/','skills/','frontend/e2e/','docs/qa/contracts/','docs/qa/evidence/')) or name in exact or name in tools or is_front_test or is_node_test or name.startswith('frontend/tsconfig'))
 if selected:bundle.append(name)
# Preserve any older frontend test files omitted from the fixed suite.
front_archive=baseline/'output/playwright/comparison-original-front-tests'
for p in list((baseline/'frontend/src').rglob('*')):
 if p.is_file() and (p.name.endswith(('.test.ts','.test.tsx')) or '/src/test/' in p.as_posix()):
  rel=p.relative_to(baseline).as_posix()
  if rel not in bundle:
   dest=front_archive/rel;dest.parent.mkdir(parents=True,exist_ok=True)
   assert p.resolve().is_relative_to(baseline.resolve()) and dest.resolve().is_relative_to(baseline.resolve());p.rename(dest)
for name in bundle:
 source=control/name;dest=baseline/name
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
after={name:production(root) for name,root in [('main',baseline),('candidate',control)]}
assert before==after,'Production source changed during test/harness instrumentation'
suite_files=[name for name in bundle if name.startswith(('tests/','frontend/e2e/','frontend/src/')) or name.endswith('.test.cjs')]
policy_files=[name for name in bundle if name not in suite_files and not name.startswith('docs/qa/evidence/')]
left_suite=digest([baseline/p for p in suite_files],baseline);right_suite=digest([control/p for p in suite_files],control)
left_policy=digest([baseline/p for p in policy_files],baseline);right_policy=digest([control/p for p in policy_files],control)
assert left_suite==right_suite and left_policy==right_policy
result={'original':original,'main_root':str(baseline),'candidate_root':str(control),
 'suite_sha256':left_suite[0],'policy_sha256':left_policy[0],'suite_files':left_suite[1], 'policy_files':left_policy[1],
 'production_before':before,'production_after_overlay':after,'overlay_paths':bundle,
 'scope':'Original application backend/frontend components/CLI preserved byte-for-byte (declared text LF normalization). Shared current development harness/test/dependency/build instrumentation; main package metadata recorded above. Branch workflow implementations are not replaced, so governance gaps remain observable.'}
(out/'preparation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'suite_files':len(suite_files),'suite_sha256':left_suite[0],'policy_sha256':left_policy[0],'production_unchanged':True}))
