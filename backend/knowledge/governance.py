"""Scientific claim revisions and review. This API is deliberately absent from agent write-tool grants."""
import json
import hashlib
import math
import re
from typing import Literal
from pydantic import Field
from backend.agent.mission_contracts import Contract
from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S, research_context as RC, corpus
from backend.knowledge.sources import doi


class EvidenceInput(Contract):
    source_id:str = Field(max_length=180)
    quote:str = Field(default="",max_length=2000)
    expected_doi:str = Field(default="",max_length=300)
    expected_title:str = Field(default="",max_length=1000)
    expected_authors:list[str] = Field(default_factory=list,max_length=50)
    version_id:str = ""
    page:int|None = Field(default=None,ge=1)
    metric:Literal["paired_psnr_gain_db"]|None = None
    value:float|None = Field(default=None,allow_inf_nan=False)


class ClaimInput(Contract):
    text:str = Field(min_length=1,max_length=16000)
    evidence:list[EvidenceInput] = Field(default_factory=list,max_length=20)
    kind:Literal["source_claim","experiment_observation","tentative_interpretation"] = "source_claim"


def _get(c,cid,tid):
    r=c.execute("SELECT * FROM scientific_claims WHERE id=? AND topic_id=?",(cid,tid)).fetchone()
    if not r:raise ValueError("Claim not found in this Topic/project")
    return {**dict(r),"payload":json.loads(r["payload"]),"evidence":[{**dict(e),"payload":json.loads(e["payload"])} for e in c.execute("SELECT * FROM claim_evidence WHERE claim_id=?",(cid,))],
            "checks":[{"id":v["id"],"at":v["at"],**json.loads(v["payload"])} for v in c.execute("SELECT * FROM claim_checks WHERE claim_id=? ORDER BY rowid DESC LIMIT 20",(cid,))]}


def get(tid,cid):
    with S.db() as c:return _get(c,cid,tid)


def listing(tid):
    with S.db() as c:
        S.topic(c,tid)
        return [_get(c,r[0],tid) for r in c.execute("SELECT id FROM scientific_claims WHERE topic_id=? ORDER BY rowid DESC",(tid,))]


def create(tid,body:ClaimInput,parent_id=""):
    snapshots=[]
    for e in body.evidence:
        snapshot=e.model_dump()
        if e.source_id.startswith("claim:"):raise ValueError("A claim is not a replacement for source or measurement evidence")
        if e.source_id.startswith("experiment:"):
            from backend.execution.protocols import run
            measured=run(tid,e.source_id.split(":",1)[1])
            snapshot["provenance"]={"trust":"measurement_pending_review","observed":S.now(),"protocol_digest":measured["payload"].get("protocol_digest"),"artifacts":[t["payload"].get("artifact",{}) for t in measured["trials"]]}
        elif e.source_id.startswith("doi:"):
            if not doi(e.source_id[4:]):raise ValueError("Malformed DOI")
        else:
            RC.validate_sources(tid,[e.source_id])
            if e.source_id.startswith("evidence:"):
                with S.db() as c:
                    row=c.execute("SELECT ch.*,v.paper_id,vd.sha256 AS document_sha256,d.parser,d.payload AS document_provenance FROM chunks ch JOIN versions v ON v.id=ch.version_id JOIN version_documents vd ON vd.version_id=ch.version_id JOIN documents d ON d.sha256=vd.sha256 WHERE ch.id=?",(e.source_id.split(":",1)[1],)).fetchone()
                    snapshot["provenance"]={"trust":"untrusted_source","observed":S.now(),"paper_id":row["paper_id"],"version_id":row["version_id"],"page":row["page"],"section":row["section"],"chunk_sha256":row["sha256"],"document_sha256":row["document_sha256"],"extraction_method":row["parser"],"document":json.loads(row["document_provenance"])}
        snapshots.append(snapshot)
    with S.db() as c:
        S.topic(c,tid)
        if parent_id:_get(c,parent_id,tid)
        cid=S.uid();payload={"text":body.text,"kind":body.kind,"created":S.now(),"scientific_review":"pending"}
        c.execute("INSERT INTO scientific_claims VALUES(?,?,?,?,?)",(cid,tid,parent_id or None,"sourced" if body.evidence else "proposed",S.dumps(payload)))
        for snapshot in snapshots:
            c.execute("INSERT INTO claim_evidence VALUES(?,?,?,?)",(S.uid(),cid,S.dumps(snapshot),L.digest(snapshot)))
        L.append(c,tid,cid,"claim.proposed",{"parent_id":parent_id,"body":body.model_dump(),"auto_memory_promotion":False})
        return _get(c,cid,tid)


def _paper_checks(tid,e):
    checks=[];kind,key=e["source_id"].split(":",1);paper=None;text="";page=None;vid=""
    def add(name,status,detail=""):checks.append({"check":name,"status":status,"detail":detail,"source_id":e["source_id"]})
    if kind=="paper":paper=corpus.paper(tid,key);text=paper["abstract"]
    elif kind=="evidence":
        with S.db() as c:
            row=c.execute("SELECT ch.*,v.paper_id FROM chunks ch JOIN versions v ON v.id=ch.version_id JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE ch.id=? AND pt.topic_id=?",(key,tid)).fetchone()
            if not row:raise ValueError("Page evidence unavailable")
            paper=corpus._paper(c,tid,row["paper_id"]);text=row["text"];page=row["page"];vid=row["version_id"]
        provenance=e.get("provenance",{})
        document=next(v["document"] for v in paper["versions"] if v["id"]==vid)
        actual_sha=hashlib.sha256(corpus.object_path(document["sha256"]).read_bytes()).hexdigest()
        add("persistent_source_hash","passed" if provenance.get("chunk_sha256")==row["sha256"]==hashlib.sha256(text.encode()).hexdigest() and provenance.get("document_sha256")==document["sha256"]==actual_sha else "failed",S.dumps(provenance))
    elif kind=="artifact":
        from backend.research_engines.workspaces import artifact_text
        text=artifact_text(tid,key)["text"]
        add("artifact_observation_only","warning","File observation does not verify scientific intent or experiment provenance")
    elif kind=="doi":
        with S.db() as c:receipt=c.execute("SELECT payload FROM citation_receipts WHERE topic_id=? AND doi=? ORDER BY rowid DESC LIMIT 1",(tid,doi(key))).fetchone()
        if receipt:
            record=json.loads(receipt[0]);ok=record.get("doi")==doi(key)
            if e["expected_title"]:ok &= re.sub(r"\W","",e["expected_title"]).casefold()==re.sub(r"\W","",record.get("title","")).casefold()
            if e["expected_authors"]:ok &= [a.casefold() for a in e["expected_authors"]]==[a.casefold() for a in record.get("authors",[])]
            add("citation_identity","passed" if ok else "failed",S.dumps(record))
            add("source_content","unverifiable","DOI metadata is not page-level evidence")
        else:add("citation_identity","unverifiable","No authoritative DOI lookup has been requested")
        return checks,False
    if paper:
        bad={"retracted","expression_of_concern","rights_uncertain"}&set(paper["flags"])
        add("source_risk_flags","failed" if bad else "passed",", ".join(sorted(bad)))
        if e["expected_doi"]:add("doi_match","passed" if doi(e["expected_doi"])==paper["doi"] and doi(e["expected_doi"]) else "failed")
        if e["expected_title"]:add("title_match","passed" if re.sub(r"\W","",e["expected_title"]).casefold()==re.sub(r"\W","",paper["title"]).casefold() else "failed")
        if e["expected_authors"]:add("authors_match","passed" if [a.casefold() for a in e["expected_authors"]]==[a.casefold() for a in paper["authors"]] else "failed")
        if e["version_id"]:add("version_match","passed" if e["version_id"]==vid or (kind=="paper" and e["version_id"] in [v["id"] for v in paper["versions"]]) else "failed")
        if e["page"] is not None:add("page_match","passed" if e["page"]==page else "failed")
        if not vid:add("abstract_only","unverifiable","No page-level full-text evidence selected")
        if paper["doi"]:
            with S.db() as c:receipt=c.execute("SELECT payload FROM citation_receipts WHERE topic_id=? AND doi=? ORDER BY rowid DESC LIMIT 1",(tid,paper["doi"])).fetchone()
            if not receipt:add("citation_registration","unverifiable","DOI metadata has not been independently resolved; explicit network lookup required")
            else:
                registered=json.loads(receipt[0]);matches=registered.get("doi")==paper["doi"] and re.sub(r"\W","",registered.get("title","")).casefold()==re.sub(r"\W","",paper["title"]).casefold()
                add("citation_registration","passed" if matches else "failed","Crossref metadata receipt; not proof of scientific correctness")
                normalize=lambda names:[re.sub(r"\W","",name).casefold() for name in names]
                add("registered_authors","passed" if normalize(registered.get("authors",[]))==normalize(paper["authors"]) else "failed","Author ordering and identity must match the registered metadata")
        else:add("citation_identity","warning","Local source ID only; no DOI registration is asserted")
    grounded=False
    if e["quote"]:
        start=text.find(e["quote"]);grounded=start>=0 and (kind=="evidence" or kind=="artifact")
        add("quote_span","passed" if start>=0 else "failed",S.dumps({"start":start,"end":start+len(e["quote"]) if start>=0 else None,"page":page,"version_id":vid}))
    else:add("quote_span","unverifiable","No exact quote/span supplied")
    return checks,grounded


def evaluate(tid,cid):
    claim=get(tid,cid)
    if claim["status"] in ("rejected","retracted"):raise ValueError("Reopen or amend a rejected/retracted claim before checking it")
    checks=[];grounded=False
    for source in claim["evidence"]:
        e=source["payload"]
        if L.digest(e)!=source["hash"]:checks.append({"check":"evidence_snapshot","status":"failed"});continue
        try:
            if e["source_id"].startswith("experiment:"):
                from backend.knowledge.verification import verify_run
                from backend.execution.protocols import run
                rid=e["source_id"].split(":",1)[1];report=verify_run(tid,rid)
                checks.extend(report["checks"])
                checks.append({"check":"independent_reproduction","status":"passed" if report["reproduction_run_id"] else "unverifiable","detail":report["reproduction_run_id"] or "No independent run recorded"})
                grounded|=report["status"]=="passed" and bool(report["reproduction_run_id"])
                if e["metric"]:
                    value=run(tid,rid)["payload"].get("comparison",{}).get(e["metric"])
                    checks.append({"check":"asserted_metric","status":"passed" if e["value"] is not None and isinstance(value,(int,float)) and math.isclose(e["value"],value,abs_tol=1e-8,rel_tol=1e-8) else "failed"})
                elif claim["payload"]["kind"]=="experiment_observation":checks.append({"check":"structured_metric_assertion","status":"unverifiable","detail":"Experiment claims require an explicit metric/value, not interpretation alone"})
            else:
                c,g=_paper_checks(tid,e);checks.extend(c);grounded|=g
        except (ValueError,OSError,KeyError,TypeError) as exc:checks.append({"check":"evidence_available","status":"unverifiable","detail":str(exc)[:500]})
    number_pattern=r"(?<!\w)[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    numbers=re.findall(number_pattern,claim["payload"]["text"])
    supported=re.findall(number_pattern," ".join(e["payload"].get("quote","") for e in claim["evidence"]))
    asserted=[e["payload"]["value"] for e in claim["evidence"] if e["payload"].get("metric") and e["payload"].get("value") is not None]
    if any(not any(math.isclose(float(n),v,rel_tol=1e-8,abs_tol=1e-8) for v in [*asserted,*map(float,supported)]) for n in numbers):
        checks.append({"check":"unstructured_numeric_claim","status":"unverifiable","detail":"Numerical prose is not grounded in quoted values or an exact structured metric assertion"})
    failed=any(c["status"]=="failed" for c in checks)
    uncertain=any(c["status"]=="unverifiable" for c in checks) or not grounded
    status="contested" if failed else "sourced" if uncertain else "independently_checked"
    result={"verifier":"deterministic-source-and-measurement-v1","reviewer_independence":"separate deterministic verifier; no self-certifying model judgment","checks":checks,"grounded":grounded,
            "outcome":"failed" if failed else "unverifiable" if uncertain else "passed","limitations":["Checks cover source linkage and numerical provenance; semantic entailment is not certified","Not automated peer review or a novelty guarantee","Methodological soundness still needs human scientific review"]}
    digest=L.digest(result)
    if claim["status"]=="human_approved" and status=="independently_checked" and claim["payload"].get("approval_check_digest")==digest:status="human_approved"
    with S.db() as c:
        current=_get(c,cid,tid)
        if current["status"] in ("retracted","rejected"):raise ValueError("Claim was concurrently withdrawn")
        check_id=S.uid();c.execute("INSERT INTO claim_checks VALUES(?,?,?,?)",(check_id,cid,S.now(),S.dumps({**result,"digest":digest})))
        c.execute("UPDATE scientific_claims SET status=? WHERE id=?",(status,cid))
        L.append(c,tid,cid,"claim.checked",{"check_id":check_id,"digest":digest,"status":status,"outcome":result["outcome"]})
    return get(tid,cid)


def decide(tid,cid,action,note):
    if not note.strip() or action not in ("approve","reject","contest","retract","reopen"):raise ValueError("Explicit supported human decision and note required")
    if action=="approve":
        c=evaluate(tid,cid)
        if c["status"]!="independently_checked":raise ValueError("Human approval requires current independent checks without critical/unverifiable gaps")
    with S.db() as connection:
        c=_get(connection,cid,tid);payload=c["payload"]
        if action=="approve":
            if c["status"]!="independently_checked":raise ValueError("Claim changed before approval")
            payload["approval_check_digest"]=c["checks"][0]["digest"]
            payload["scientific_review"]="human_approved"
        else:payload["scientific_review"]="pending" if action=="reopen" else action
        status={"approve":"human_approved","reject":"rejected","contest":"contested","retract":"retracted","reopen":"sourced"}[action]
        connection.execute("UPDATE scientific_claims SET status=?,payload=? WHERE id=?",(status,S.dumps(payload),cid))
        L.append(connection,tid,cid,"claim."+action,{"by":"researcher","note":note[:8000],"previous_status":c["status"],"new_status":status,"approval_check_digest":payload.get("approval_check_digest"),"evidence_ids":[e["id"] for e in c["evidence"]]})
    return get(tid,cid)


def export_markdown(tid):
    rows=listing(tid)
    lines=["## Scientific verification status", "Status labels are local workflow decisions, not a guarantee of correctness. Auto-publication is disabled."]
    for row in rows:
        if row["status"]=="human_approved":
            row=evaluate(tid,row["id"])
        lines.extend([f"\n### Claim {row['id']} · {row['status']}",row["payload"]["text"]])
        for e in row["evidence"]:lines.append("- Evidence "+e["id"]+" · "+S.dumps(e["payload"])+" · snapshot SHA256 "+e["hash"])
        for c in row["checks"][:1]:lines.append("- Latest checks: "+S.dumps(c))
    return "\n\n".join(lines)


def appendix(topic_id=""):
    from backend.core.config import data_dir
    if not (data_dir()/"workspace/research/research.sqlite3").is_file():return ""
    topics=[S.get_topic(topic_id)] if topic_id else S.topics()
    return "\n\n".join(export_markdown(t["id"]) for t in topics if listing(t["id"]))


def prior_art(tid,query):
    evidence=corpus.retrieve(tid,query,10)
    return {"evidence":evidence,"coverage":"Current local Topic index only; abstracts may be unverified; not exhaustive prior-art search", "novelty_guarantee":False,
            "contested_claims":[c["id"] for c in listing(tid) if c["status"]=="contested" and any(w in c["payload"]["text"].casefold() for w in re.findall(r"\w+",query.casefold())[:20])]}


async def resolve_citation(tid,identifier):
    from urllib.parse import quote
    from backend.knowledge.websearch import _client
    identifier=doi(identifier)
    S.get_topic(tid)
    if not identifier:raise ValueError("Malformed DOI")
    async with _client() as client:
        response=await client.get("https://api.crossref.org/works/"+quote(identifier,safe=""))
        response.raise_for_status()
    if len(response.content)>1024*1024:raise ValueError("Citation metadata exceeds evidence budget")
    raw=response.json().get("message",{})
    record={"doi":doi(raw.get("DOI")),"title":next(iter(raw.get("title") or []),""),"authors":[" ".join(filter(None,[a.get("given"),a.get("family")])) for a in raw.get("author") or []],
            "source_url":"https://api.crossref.org/works/"+quote(identifier,safe=""),"response_sha256":L.digest(raw),"resolution":"Crossref metadata only"}
    with S.db() as c:
        eid=S.uid();c.execute("INSERT INTO citation_receipts VALUES(?,?,?,?,?)",(eid,tid,identifier,S.dumps(record),S.now()))
        L.append(c,tid,eid,"citation.resolved",record)
    return record
