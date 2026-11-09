const RESULTS = [
  { set: "FUSeg2021 test set", images: "191", dice: "0.92", note: "Images like those the model was trained on" },
  { set: "LowerLimb V3", images: "148", dice: "0.26", note: "External set with different masks. Precision 0.90, recall 0.15" },
];

// Both results always appear together at one size and weight.
export function EvidenceTable() {
  return (
    <div className="panel overflow-hidden">
      <table className="stack-table w-full border-collapse text-sm">
        <caption className="sr-only">Pooled Dice on the internal test set and on an external set</caption>
        <thead>
          <tr className="border-b border-rule text-left text-13 text-ink-2">
            <th scope="col" className="px-4 py-2 font-normal">Dataset</th>
            <th scope="col" className="px-4 py-2 font-normal">Images</th>
            <th scope="col" className="px-4 py-2 font-normal">Pooled Dice</th>
          </tr>
        </thead>
        <tbody>
          {RESULTS.map((row) => (
            <tr key={row.set} className="border-b border-rule last:border-b-0">
              <td data-wide className="px-4 py-3">
                <span className="block font-semibold">{row.set}</span>
                <span className="block text-13 text-ink-2">{row.note}</span>
              </td>
              <td data-label="Images" className="value px-4 py-3">{row.images}</td>
              <td data-label="Pooled Dice" className="px-4 py-3">
                <span className="value text-2xl font-medium">{row.dice}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
