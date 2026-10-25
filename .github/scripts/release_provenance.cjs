'use strict';

async function qualify({github,context},requested) {
  const {owner,repo}=context.repo;
  if (context.ref!=='refs/heads/main') throw new Error('CD executes only from main');
  const main=(await github.rest.repos.getBranch({owner,repo,branch:'main'})).data;
  const sha=requested || context.sha;
  if (!/^[a-f0-9]{40}$/.test(sha) || sha!==main.commit.sha || main.protected!==true) throw new Error('Requested release is not the current protected main commit');
  const prs=await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit,{owner,repo,commit_sha:sha,per_page:100});
  const pr=prs.find(p=>p.merged_at && p.merge_commit_sha===sha && p.base.ref==='main' && p.head.ref==='qa' && p.head.repo?.full_name===`${owner}/${repo}`);
  if (!pr) throw new Error('No confirmed qa -> main protected promotion for this commit');
  const checks=await github.paginate(github.rest.checks.listForRef,{owner,repo,ref:pr.head.sha,filter:'latest',per_page:100});
  for (const name of ['Development gate','QA gate']) {
    const matches=checks.filter(c=>c.name===name && c.head_sha===pr.head.sha && c.app?.id===15368);
    if (!matches.length || matches.some(c=>c.status!=='completed' || c.conclusion!=='success')) throw new Error('Qualified QA check is absent: '+name);
  }
  const head=(await github.rest.repos.getCommit({owner,repo,ref:pr.head.sha})).data;
  const merged=(await github.rest.repos.getCommit({owner,repo,ref:sha})).data;
  if (head.commit.tree.sha!==merged.commit.tree.sha) throw new Error('Merged tree differs from tested QA source');
  return {sha,qa_head:pr.head.sha,pr:pr.number,mode:'GITHUB_NATIVE_PROVENANCE',scope:'Qualified software source, not scientific correctness'};
}

module.exports = {qualify};
