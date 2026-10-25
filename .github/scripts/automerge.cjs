'use strict';
const requiredJobs = require('../required-ci-jobs.json').qa;

function qualifiedErrors(s) {
  const errors=[];
  const run=s.run;
  const sha=s.expected_head_sha || s.pr?.head?.sha;
  if (!run || run.head_sha!==sha || run.status!=='completed' || run.conclusion!=='success'
      || run.event!=='pull_request' || run.path!=='.github/workflows/quality.yml'
      || run.head_repository?.full_name!==s.repository) errors.push('No genuine successful matching-head PR Quality Gates run');
  for (const name of requiredJobs) {
    const matches=(s.jobs || []).filter(j=>j.name===name && j.run_id===run?.id);
    if (!matches.length || matches.some(j=>j.status!=='completed' || j.conclusion!=='success')) errors.push('Mandatory QA job not executed successfully: '+name);
  }
  return errors;
}

function blockingReviews(reviews) {
  const states = new Map();
  for (const review of reviews) {
    if (['APPROVED','CHANGES_REQUESTED','DISMISSED'].includes(review.state)) states.set(review.user?.login || 'unknown',review.state);
  }
  return [...states.values()].includes('CHANGES_REQUESTED');
}

function assess(s) {
  const errors = [];
  const p = s.pr;
  const allowed=p && ((p.base?.ref==='qa' && p.head?.ref==='dev') ||
    (p.base?.ref==='main' && p.head?.ref==='qa' && s.allow_main_promotion===true));
  if (!allowed || p.state !== 'open' || p.draft) errors.push('Only trusted forward promotion with explicit main authorization is eligible');
  errors.push(...qualifiedErrors(s));
  if (p?.head?.repo?.full_name !== s.repository || p?.base?.repo?.full_name !== s.repository || p?.user?.login !== s.owner) errors.push('Untrusted repository or author');
  if (p?.mergeable !== true || p?.mergeable_state !== 'clean') errors.push('Conflicted, outdated or indeterminate merge state');
  if (!/Contract:\s*FQC-[A-Z0-9-]+/.test(p?.body || '')) errors.push('Missing feature contract reference');
  const protection = s.protection;
  if (!protection?.enforce_admins?.enabled || !protection?.required_status_checks?.strict || protection.allow_force_pushes?.enabled || protection.allow_deletions?.enabled) errors.push('Branch protection is absent or insufficient');
  const checks = protection?.required_status_checks?.checks || [];
  if (!checks.some(c => c.context === 'QA gate' && c.app_id === 15368)) errors.push('Required GitHub Actions QA gate is absent');
  for (const required of checks) {
    const matches = (s.checks || []).filter(c => c.name === required.context && c.head_sha === p?.head?.sha && c.app?.id === required.app_id);
    if (!matches.length || matches.some(c => c.status !== 'completed' || c.conclusion !== 'success')) errors.push('Required check not successful on this head: ' + required.context);
  }
  if ((s.checks || []).some(c => c.app?.id === 15368 && ['failure','cancelled','timed_out','action_required','stale'].includes(c.conclusion))) errors.push('A GitHub Actions check failed');
  if (blockingReviews(s.reviews || [])) errors.push('Blocking review');
  if (!s.allow_auto_merge) errors.push('Repository auto-merge is disabled');
  if (s.comparison !== 'ahead' && s.comparison !== 'identical') errors.push('Source does not include current target');
  return errors;
}

async function run({github, context, core}, number, apply = true, policy = {allowMain:false}) {
  const {owner, repo} = context.repo;
  const repository = `${owner}/${repo}`;
  const pr = (await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (!((pr.base.ref==='qa' && pr.head.ref==='dev') || (pr.base.ref==='main' && pr.head.ref==='qa' && policy.allowMain===true))) return {decision:'BLOCKED', reasons:['Automatic main promotion needs explicit trusted owner policy']};
  let protection;
  try {
    // This endpoint requires Administration:read, which GITHUB_TOKEN cannot request.
    // Optional separate read-only credential never authorizes the merge mutation.
    const headers=process.env.AUTOMERGE_POLICY_READ_TOKEN ? {authorization:'Bearer '+process.env.AUTOMERGE_POLICY_READ_TOKEN} : {};
    protection=(await github.rest.repos.getBranchProtection({owner,repo,branch:pr.base.ref,headers})).data;
  } catch(error) {
    if ([403,404].includes(error.status)) return {decision:'BLOCKED',reasons:[
      'Cannot independently read enforced branch protection. A protected Administration:read policy credential is required; no merge attempted.'
    ]};
    throw error;
  }
  const qualifying=context.payload?.workflow_run;
  if (!qualifying || qualifying.head_sha!==pr.head.sha || !qualifying.check_suite_id) return {decision:'BLOCKED',reasons:['Matching Quality Gates run provenance is missing']};
  const jobs=(await github.rest.actions.listJobsForWorkflowRun({owner,repo,run_id:qualifying.id,filter:'latest',per_page:100})).data.jobs;
  // The same commit can have both dev-push and PR checks. Bind checks to the
  // qualifying PR run, never conflate its PASS with an older/other skipped suite.
  const checks = (await github.paginate(github.rest.checks.listForRef,{owner,repo,ref:pr.head.sha,filter:'latest',per_page:100}))
    .filter(c=>c.check_suite?.id===qualifying.check_suite_id);
  const reviews = await github.paginate(github.rest.pulls.listReviews,{owner,repo,pull_number:number,per_page:100});
  const config = (await github.rest.repos.get({owner,repo})).data;
  const compare = (await github.rest.repos.compareCommitsWithBasehead({owner,repo,basehead:`${pr.base.ref}...${pr.head.sha}`})).data;
  const reasons = assess({pr,protection,checks,reviews,run:qualifying,jobs,allow_main_promotion:policy.allowMain,
    allow_auto_merge:config.allow_auto_merge,comparison:compare.status,owner,repository});
  if (reasons.length || !apply) return {decision:reasons.length?'BLOCKED':'ELIGIBLE',reasons,head:pr.head.sha};
  const fresh = (await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (fresh.head.sha !== pr.head.sha || fresh.base.ref !== pr.base.ref || fresh.head.ref !== pr.head.ref) return {decision:'BLOCKED',reasons:['PR changed during eligibility check']};
  // Native GitHub merge policy remains authoritative; never use admin overrides.
  if (!fresh.auto_merge) await github.graphql(`mutation($id: ID!) {
    enablePullRequestAutoMerge(input:{pullRequestId:$id, mergeMethod:MERGE}) {
      pullRequest { number }
    }
  }`,{id:pr.node_id});
  const merged=(await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (!merged.merged || !merged.merge_commit_sha) return {decision:merged.auto_merge?'AUTO_MERGE_ENABLED':'UNVERIFIED',
    reasons:['Native auto-merge requested; actual merge completion must be observed separately'],head:pr.head.sha};
  core.info(`Native ${pr.base.ref} promotion merge confirmed for PR ${number}: ${merged.merge_commit_sha}`);
  return {decision:'MERGED',head:pr.head.sha,merge_commit_sha:merged.merge_commit_sha};
}

module.exports = {assess, qualifiedErrors, run};
