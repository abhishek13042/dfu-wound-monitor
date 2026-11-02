import { PadMark } from "@/components/ReadingStrip";
import { PADS, type PadState } from "@/lib/pads";

const accepted: PadState[] = PADS.map(() => "pass");
const refused: PadState[] = PADS.map((pad) => (pad.key === "sharpness" || pad.key === "glare" ? "fail" : "pass"));

const stateWord = { pass: "Passed", fail: "Failed", none: "Not read" };

function Readings({ label, outcome, states }: { label: string; outcome: string; states: PadState[] }) {
  return (
    <>
      <th scope="row" className="border-t border-rule px-4 py-3 text-left align-middle font-normal">
        <span className="block text-sm font-semibold">{label}</span>
        <span className="block text-13 text-ink-2">{outcome}</span>
      </th>
      {states.map((state, index) => (
        <td key={PADS[index].key} className="border-t border-l border-rule p-1.5">
          <span
            data-state={state}
            data-step=""
            style={{ "--step": index } as React.CSSProperties}
            className="pad mx-auto size-12 lg:size-14"
          >
            <PadMark state={state} className="size-6" />
            <span className="sr-only">{stateWord[state]}</span>
          </span>
        </td>
      ))}
    </>
  );
}

export function KeyChart() {
  return (
    <figure className="panel text-ink">
      <div className="hidden md:block">
        <table className="w-full table-fixed border-collapse">
          <caption className="sr-only">The nine checks, with one refused and one accepted reading</caption>
          <colgroup>
            <col className="w-[17%]" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="px-4 py-3 text-left align-top text-13 font-normal text-ink-2">
                <span className="sr-only">Reading</span>
                <span aria-hidden="true">Quality gate p03-s02-v1</span>
              </th>
              {PADS.map((pad) => (
                <th key={pad.key} scope="col" className="border-l border-rule px-2 py-3 text-left align-top font-normal">
                  <span className="block truncate text-sm font-semibold [font-stretch:78%]" title={pad.name}>
                    {pad.short === "Under" || pad.short === "Over" ? pad.short + "exp." : pad.name}
                  </span>
                  <span className="value block text-xs text-ink-2">{pad.limit}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <Readings label="Photo A" outcome="Refused. No measurement." states={refused} />
            </tr>
            <tr>
              <Readings label="Photo B" outcome="Accepted, then measured." states={accepted} />
            </tr>
          </tbody>
        </table>
      </div>

      <div className="md:hidden">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">The nine checks, with one refused and one accepted reading</caption>
          <thead>
            <tr className="text-left text-13">
              <th scope="col" className="px-3 py-2 font-normal text-ink-2">
                Check
              </th>
              <th scope="col" className="w-20 px-2 py-2 font-semibold">
                Photo A
              </th>
              <th scope="col" className="w-20 px-2 py-2 font-semibold">
                Photo B
              </th>
            </tr>
          </thead>
          <tbody>
            {PADS.map((pad, index) => (
              <tr key={pad.key} className="border-t border-rule">
                <th scope="row" className="px-3 py-1 text-left font-normal">
                  <span className="block font-semibold [font-stretch:85%]">{pad.name}</span>
                  <span className="value block text-xs text-ink-2">{pad.limit}</span>
                </th>
                {[refused[index], accepted[index]].map((state, column) => (
                  <td key={column} className="p-1">
                    <span data-state={state} className="pad h-9 w-full">
                      <PadMark state={state} className="size-4" />
                      <span className="sr-only">{stateWord[state]}</span>
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-rule text-13">
              <th scope="row" className="px-3 py-2 text-left font-normal text-ink-2">
                Outcome
              </th>
              <td className="px-2 py-2 font-semibold text-reject">Refused</td>
              <td className="px-2 py-2 font-semibold text-pass">Measured</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <figcaption className="border-t border-rule px-4 py-2 text-13 text-ink-2">
        Photo A and Photo B are constructed examples. Photo A failed sharpness and glare, so it was never segmented.
      </figcaption>
    </figure>
  );
}
