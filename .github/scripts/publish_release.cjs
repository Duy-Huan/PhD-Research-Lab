'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {qualify}=require('./release_provenance.cjs');
async function publish({github,context},directory,sha) {
  await qualify({github,context},sha);
  const {owner,repo}=context.repo,root=path.resolve(directory);
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
  // v6.6.2: every release ships source, web and both installers (.exe, .deb) built from the qualified commit.
  if(manifest.source_sha!==sha || !/^\d+\.\d+\.\d+$/.test(manifest.version) || !Array.isArray(manifest.assets) || manifest.assets.length!==4) throw Error('Invalid release manifest');
  if(manifest.assets.some(a=>!a || !/^[a-f0-9]{64}$/.test(a.sha256 || '') || !Number.isSafeInteger(a.size) || a.size<=0 || a.size>200000000)) throw Error('Invalid required archive checksum/size');
  const v=manifest.version;
  const expected=[`phdlab-${v}-source.zip`,`phdlab-${v}-web.zip`,`phdlab-${v}-windows-x64-setup.exe`,`phdlab_${v}_amd64.deb`];
  if(new Set(manifest.assets.map(a=>a.name)).size!==expected.length || !expected.every(name=>manifest.assets.some(a=>a.name===name))) throw Error('Unexpected release assets');
  const records=[...manifest.assets,{name:'manifest.json'}];
  for(const r of records){
    const file=path.join(root,r.name),stat=fs.lstatSync(file);
    if(!stat.isFile() || stat.isSymbolicLink() || stat.size>200000000)throw Error('Unsafe release asset');
    r.bytes=fs.readFileSync(file);r.digest=crypto.createHash('sha256').update(r.bytes).digest('hex');
    if(r.sha256 && (r.digest!==r.sha256 || stat.size!==r.size))throw Error('Modified release asset');
  }
  const tag=`v${manifest.version}`;
  try{
    const ref=(await github.rest.git.getRef({owner,repo,ref:'tags/'+tag})).data;
    let object=ref.object;
    if(object.type==='tag')object=(await github.rest.git.getTag({owner,repo,tag_sha:object.sha})).data.object;
    if(object.type!=='commit' || object.sha!==sha)throw Error('Existing version tag points to a different commit');
  }catch(e){if(e.status!==404)throw e;}
  let release;
  try{release=(await github.rest.repos.getReleaseByTag({owner,repo,tag})).data;}
  catch(e){
    if(e.status!==404)throw e;
    release=(await github.rest.repos.createRelease({owner,repo,tag_name:tag,target_commitish:sha,name:`PhD Research Lab ${tag}`,draft:true,
      body:`Software release for qualified commit ${sha}. Source, web, Windows installer and Linux package checksums are in manifest.json. This is not a scientific or zero-bug certification.`})).data;
  }
  const assets=await github.paginate(github.rest.repos.listReleaseAssets,{owner,repo,release_id:release.id,per_page:100});
  for(const r of records){
    const existing=assets.find(a=>a.name===r.name);
    if(existing){if(existing.digest!=='sha256:'+r.digest)throw Error('Existing release asset digest differs');continue;}
    if(!release.draft)throw Error('Published release is incomplete; do not silently rewrite it');
    await github.rest.repos.uploadReleaseAsset({owner,repo,release_id:release.id,name:r.name,data:r.bytes,headers:{'content-type':'application/octet-stream','content-length':r.bytes.length}});
  }
  if(release.draft)release=(await github.rest.repos.updateRelease({owner,repo,release_id:release.id,draft:false})).data;
  return {decision:'PUBLISHED',tag,sha,url:release.html_url};
}
module.exports={publish};
