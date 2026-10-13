import {createContext,useContext} from 'react'
import type {Snapshot} from './data'
export const SnapshotResource=createContext<(() => Promise<Snapshot>)|null>(null)
export function useCompleteSnapshot(fallback:Snapshot) {
  const load=useContext(SnapshotResource)
  return load || (()=>Promise.resolve(fallback))
}
