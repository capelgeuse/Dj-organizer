import type { LibrarySummary } from '../bridge/contracts'

type SortMenuProps = {
  sort: LibrarySummary['sort']
  onChange: (field: LibrarySummary['sort']['field'], direction: LibrarySummary['sort']['direction']) => void
}

export function SortMenu({ sort, onChange }: SortMenuProps) {
  return (
    <label className="sort-menu">
      <span className="eyebrow">SORT</span>
      <select value={sort.field} onChange={(event) => onChange(event.target.value as LibrarySummary['sort']['field'], sort.direction)}>
        <option value="name">Name</option>
        <option value="title">Title</option>
        <option value="artist">Artist</option>
        <option value="bpm">BPM</option>
        <option value="genre">Genre</option>
        <option value="duration">Duration</option>
      </select>
      <button type="button" onClick={() => onChange(sort.field, sort.direction === 'asc' ? 'desc' : 'asc')} aria-label={`Sort ${sort.direction === 'asc' ? 'descending' : 'ascending'}`}>
        {sort.direction === 'asc' ? '↑' : '↓'}
      </button>
    </label>
  )
}
