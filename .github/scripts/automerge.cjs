'use strict';

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
  if (!p || p.state !== 'open' || p.draft || p.base?.ref !== 'dev' || !/^feature\/[a-z0-9][a-z0-9._/-]*$/i.test(p.head?.ref || '')) errors.push('Only open non-draft feature/* -> dev PRs are eligible');
  if (p?.head?.repo?.full_name !== s.repository || p?.base?.repo?.full_name !== s.repository || p?.user?.login !== s.owner) errors.push('Untrusted repository or author');
  if (p?.mergeable !== true || p?.mergeable_state !== 'clean') errors.push('Conflicted, outdated or indeterminate merge state');
  if (!/Contract:\s*FQC-[A-Z0-9-]+/.test(p?.body || '')) errors.push('Missing feature contract reference');
  const protection = s.protection;
  if (!protection?.enforce_admins?.enabled || !protection?.required_status_checks?.strict || protection.allow_force_pushes?.enabled || protection.allow_deletions?.enabled) errors.push('Branch protection is absent or insufficient');
  const checks = protection?.required_status_checks?.checks || [];
  if (!checks.some(c => c.context === 'Development gate' && c.app_id === 15368)) errors.push('Required GitHub Actions Development gate is absent');
  for (const required of checks) {
    const matches = (s.checks || []).filter(c => c.name === required.context && c.head_sha === p?.head?.sha && c.app?.id === required.app_id);
    if (!matches.length || matches.some(c => c.status !== 'completed' || c.conclusion !== 'success')) errors.push('Required check not successful on this head: ' + required.context);
  }
  if ((s.checks || []).some(c => c.app?.id === 15368 && ['failure','cancelled','timed_out','action_required','stale'].includes(c.conclusion))) errors.push('A GitHub Actions check failed');
  if (blockingReviews(s.reviews || [])) errors.push('Blocking review');
  if (!s.allow_auto_merge) errors.push('Repository auto-merge is disabled');
  if (s.comparison !== 'ahead' && s.comparison !== 'identical') errors.push('Feature branch does not include the current dev');
  return errors;
}

async function run({github, context, core}, number, apply = true) {
  const {owner, repo} = context.repo;
  const repository = `${owner}/${repo}`;
  const pr = (await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (pr.base.ref !== 'dev') return {decision:'BLOCKED', reasons:['Auto-merge is limited to dev']};
  let protection;
  try {
    // This endpoint requires Administration:read, which GITHUB_TOKEN cannot request.
    // Optional separate read-only credential never authorizes the merge mutation.
    const headers=process.env.AUTOMERGE_POLICY_READ_TOKEN ? {authorization:'Bearer '+process.env.AUTOMERGE_POLICY_READ_TOKEN} : {};
    protection=(await github.rest.repos.getBranchProtection({owner,repo,branch:'dev',headers})).data;
  } catch(error) {
    if ([403,404].includes(error.status)) return {decision:'BLOCKED',reasons:[
      'Cannot independently read enforced branch protection. A protected Administration:read policy credential is required; no merge attempted.'
    ]};
    throw error;
  }
  const checks = await github.paginate(github.rest.checks.listForRef,{owner,repo,ref:pr.head.sha,filter:'latest',per_page:100});
  const reviews = await github.paginate(github.rest.pulls.listReviews,{owner,repo,pull_number:number,per_page:100});
  const config = (await github.rest.repos.get({owner,repo})).data;
  const compare = (await github.rest.repos.compareCommitsWithBasehead({owner,repo,basehead:`dev...${pr.head.sha}`})).data;
  const reasons = assess({pr,protection,checks,reviews,allow_auto_merge:config.allow_auto_merge,comparison:compare.status,owner,repository});
  if (reasons.length || !apply) return {decision:reasons.length?'BLOCKED':'ELIGIBLE',reasons,head:pr.head.sha};
  const fresh = (await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (fresh.head.sha !== pr.head.sha || fresh.base.ref !== 'dev') return {decision:'BLOCKED',reasons:['PR changed during eligibility check']};
  // Native GitHub merge policy remains authoritative; never use admin overrides.
  await github.graphql(`mutation($id: ID!, $sha: GitObjectID!) {
    mergePullRequest(input:{pullRequestId:$id, expectedHeadOid:$sha, mergeMethod:SQUASH}) {
      pullRequest { number merged mergeCommit { oid } }
    }
  }`,{id:pr.node_id,sha:pr.head.sha});
  const merged=(await github.rest.pulls.get({owner,repo,pull_number:number})).data;
  if (!merged.merged || !merged.merge_commit_sha) return {decision:'UNVERIFIED',reasons:['Native merge was requested but completion is not confirmed']};
  core.info(`Native squash dev merge confirmed for PR ${number}: ${merged.merge_commit_sha}`);
  return {decision:'MERGED',head:pr.head.sha,merge_commit_sha:merged.merge_commit_sha};
}

module.exports = {assess, run};
