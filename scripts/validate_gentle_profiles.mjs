import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseProfileExportTextWithDrops } from '../tests/vendor/gentle-shell-4.0.0/agent-profiles.ts';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const baseDir=path.join(root,'profiles/gentle-shell');
const criticalDir=path.join(root,'profiles/gentle-shell-variants/critical-review');
const contract=JSON.parse(fs.readFileSync(path.join(root,'data/domain-objective-contracts.json'),'utf8'));
const domains=Object.keys(contract.domains ?? {});
const objectives=Object.keys(contract.objectives ?? {});
const harnessContract=JSON.parse(fs.readFileSync(path.join(root,'contracts/harnesses.json'),'utf8')).harnesses['gentle-shell'];
const GENTLE_ROLES=Object.keys(harnessContract.roles);
const JUDGES=new Set(['jd-judge-a','jd-judge-b']);

function parseCsv(text) {
  const records=[];
  let record=[], field='', quoted=false;
  for (let i=0;i<text.length;i++) {
    const ch=text[i];
    if (quoted) {
      if (ch==='"' && text[i+1]==='"') { field+='"'; i++; }
      else if (ch==='"') quoted=false;
      else field+=ch;
    } else if (ch==='"') quoted=true;
    else if (ch===',') { record.push(field); field=''; }
    else if (ch==='\n') {
      record.push(field.replace(/\r$/,''));
      if (record.some(value=>value!=='')) records.push(record);
      record=[]; field='';
    } else field+=ch;
  }
  if (field!=='' || record.length) { record.push(field.replace(/\r$/,'')); records.push(record); }
  const headers=records.shift()?.map(value=>value.replace(/^\uFEFF/,''));
  return records.map(values=>Object.fromEntries(headers.map((key,index)=>[key,values[index] ?? ''])));
}

const portfolioRows=parseCsv(fs.readFileSync(path.join(root,'data/portfolios.csv'),'utf8'));
const expectedProfiles=new Map();
const agentUseExclusions=[];
for (const portfolio of portfolioRows) {
  for (const domain of domains) {
    for (const objective of objectives) {
      // Agent-use excludes Command-only portfolios without an OpenAI primary route:
      // Command GUI vision entitlement remains unverified (A07).
      if (domain==='agent-use' && portfolio.openai==='none' && portfolio.gateway==='cc') {
        agentUseExclusions.push({portfolio:portfolio.id,reason:'No OpenAI primary pool; Command GUI vision remains unverified (A07).'});
        continue;
      }
      const name=`${portfolio.id}-${domain}-${objective}`;
      const roles=GENTLE_ROLES.filter(role=>!(domain==='agent-use' && objective!=='best' && JUDGES.has(role)));
      expectedProfiles.set(name,{domain,objective,roles});
    }
  }
}

function validateSet(dir,critical) {
  const suffix=critical?'-critical-review':'';
  const files=fs.readdirSync(dir).filter(file=>file.endsWith('.export.json')).sort();
  const expectedNames=new Set([...expectedProfiles.keys()].map(name=>name+suffix));
  const actualNames=new Set(files.map(file=>file.slice(0,-'.export.json'.length)));
  const failures=[];
  for (const name of expectedNames) {
    if (!actualNames.has(name)) failures.push({file:name+'.export.json',reason:'missing expected profile'});
  }
  for (const name of actualNames) {
    if (!expectedNames.has(name)) failures.push({file:name+'.export.json',reason:'unexpected profile'});
  }
  let pass=0;
  for (const file of files) {
    const diskName=file.slice(0,-'.export.json'.length);
    const baseName=critical?diskName.slice(0,-suffix.length):diskName;
    const expected=expectedProfiles.get(baseName);
    const text=fs.readFileSync(path.join(dir,file),'utf8');
    const result=parseProfileExportTextWithDrops(text);
    const roles=result?Object.keys(result.config ?? {}).sort():[];
    const expectedRoles=expected?.roles.slice().sort() ?? [];
    const exactRoles=roles.length===expectedRoles.length && roles.every((role,index)=>role===expectedRoles[index]);
    const dropped=result?.droppedAgents ?? [];
    const contentName=result?.name;
    const nameMatches=contentName===diskName;
    if (!result || dropped.length!==0 || !exactRoles || !nameMatches) {
      failures.push({
        file,
        reason:!result?'parser rejected export':!nameMatches?'content/filename mismatch':dropped.length?'parser dropped agents': 'role set mismatch',
        dropped,
        roles,
        expected_roles:expectedRoles,
      });
    } else if (expected) pass++;
  }
  return {files:files.length,expected_files:expectedNames.size,pass,fail:failures.length,failures};
}

const base=validateSet(baseDir,false);
const criticalReview=validateSet(criticalDir,true);
const failures=[
  ...base.failures.map(failure=>({set:'base',...failure})),
  ...criticalReview.failures.map(failure=>({set:'critical_review',...failure})),
];
const receipt={
  gentle_shell_version:harnessContract.harnessVersion,
  built_at:new Date().toISOString(),
  files:base.files+criticalReview.files,
  pass:base.pass+criticalReview.pass,
  fail:failures.length,
  expected_files:base.expected_files+criticalReview.expected_files,
  agent_use_exclusions:agentUseExclusions,
  sets:{base:{files:base.files,expected_files:base.expected_files,pass:base.pass,fail:base.fail},
        critical_review:{files:criticalReview.files,expected_files:criticalReview.expected_files,pass:criticalReview.pass,fail:criticalReview.fail}},
  failures,
};
fs.writeFileSync(path.join(root,'validation/gentle-native-parser-validation.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({...receipt,failures:failures.slice(0,10)},null,2));
process.exit(failures.length?1:0);
