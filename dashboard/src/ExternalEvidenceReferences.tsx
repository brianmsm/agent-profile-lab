/** External-only source links without redistributing third-party benchmark scores.
 * The linked publisher remains authoritative for each original numerical value. */
import {useMemo,useState} from 'react'
import links from '../../data/public-evidence/source-links.json'
const PAGE=18
export default function ExternalEvidenceReferences(){
  const [query,setQuery]=useState('')
  const [page,setPage]=useState(0)
  const models=links.providerModelLinks
  const filtered=useMemo(()=>{
    const needle=query.trim().toLocaleLowerCase('en')
    return models.filter(row=>(row.model+' '+row.slug).toLocaleLowerCase('en').includes(needle))
  },[query,models])
  const pages=Math.max(1,Math.ceil(filtered.length/PAGE))
  const safePage=Math.min(page,pages-1)
  return <section className="panel external-references" aria-label="External benchmark links without redistributed measurements">
    <div className="section-heading">
      <div><span className="eyebrow">EXTERNAL EVIDENCE — LINK ONLY</span><h2>Artificial Analysis model pages</h2></div>
      <span className="record-count">{models.length} original-page links</span>
    </div>
    <p className="section-description">
      The original baseline profile assignments and reviewed recommendations remain unchanged.
      Artificial Analysis scores and their mirrors are <strong>not redistributed</strong>.
      These direct publisher links are for source verification, not an independent local benchmark table.
      Missing numbers must never be interpreted as scores of zero.
    </p>
    <label>Find an evaluated model
      <input type="search" aria-label="Search externally referenced models" value={query}
        placeholder="Model name or original page slug…" onChange={event=>{setQuery(event.target.value);setPage(0)}} />
    </label>
    <p className="footnote" role="status">{filtered.length} linked model pages; page {safePage+1} of {pages}</p>
    {filtered.length?<ul className="external-link-list">
      {filtered.slice(safePage*PAGE,(safePage+1)*PAGE).map(row=><li key={row.slug+'|'+row.model}>
        <strong>{row.model}</strong> · <a href={row.url} target="_blank" rel="noopener noreferrer">Open original Artificial Analysis model page</a>
      </li>)}
    </ul>:<p>No matching publisher pages. Try another model name.</p>}
    {pages>1&&<div className="pagination">
      <button disabled={safePage===0} onClick={()=>setPage(safePage-1)}>Previous</button>
      <span>{safePage+1} / {pages}</span>
      <button disabled={safePage>=pages-1} onClick={()=>setPage(safePage+1)}>Next</button>
    </div>}
  </section>
}
