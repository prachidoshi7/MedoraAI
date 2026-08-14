import { useEffect, useId, useState } from 'react';
import type { Medicine } from '../types';

interface MedicineSearchSelectProps {
  medicines: Medicine[];
  value: number | null;
  onChange: (medicine: Medicine | null) => void;
  placeholder?: string;
  ariaLabel?: string;
}

/** Native type-ahead medicine picker backed by the canonical catalog. */
export default function MedicineSearchSelect({
  medicines,
  value,
  onChange,
  placeholder = 'Type to search medicines…',
  ariaLabel = 'Medicine name',
}: MedicineSearchSelectProps) {
  const listId = useId();
  const selected = medicines.find((medicine) => medicine.id === value) ?? null;
  const [query, setQuery] = useState(selected?.name ?? '');
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setQuery(selected?.name ?? '');
  }, [editing, selected?.id, selected?.name]);

  const matchQuery = (next: string) => medicines.find(
    (medicine) => medicine.name.localeCompare(next.trim(), undefined, { sensitivity: 'accent' }) === 0,
  ) ?? null;

  return (
    <>
      <input
        aria-label={ariaLabel}
        autoComplete="off"
        list={listId}
        placeholder={placeholder}
        value={query}
        onFocus={() => setEditing(true)}
        onChange={(event) => {
          const next = event.target.value;
          setQuery(next);
          onChange(matchQuery(next));
        }}
        onBlur={() => {
          const exact = matchQuery(query);
          setEditing(false);
          if (exact) {
            setQuery(exact.name);
            onChange(exact);
          } else {
            onChange(null);
          }
        }}
      />
      <datalist id={listId}>
        {medicines.map((medicine) => (
          <option key={medicine.id} value={medicine.name}>{medicine.category}</option>
        ))}
      </datalist>
    </>
  );
}
